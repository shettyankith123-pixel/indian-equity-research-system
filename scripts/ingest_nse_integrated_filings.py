from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
import time
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from nse_xbrl import NSEClient, parse_xbrl
from indian_equity_research.ingestion.xbrl_contexts import parse_iso_or_nse, choose_duration_context, create_run_directory

from indian_equity_research.models.financials import (
    FinancialObservation,
    FinancialPeriod,
    SourceReference,
)
from indian_equity_research.storage.repository import FinancialRepository

SOURCE_NAME = "NSE Integrated Filing - Financials"
SOURCE_TYPE = "exchange_filing"
CRORE = Decimal("10000000")

# Stable, taxonomy-tolerant metric mappings. Values are selected by explicit
# context ID and the raw local XBRL tag is recorded in the coverage report.
METRIC_MAP: dict[str, tuple[tuple[str, ...], str]] = {
    "revenue_from_operations": (("RevenueFromOperations", "RevenueFromOperationsNetOfExciseDuty"), "INR crore"),
    "total_income": (("Income", "TotalIncome"), "INR crore"),
    "other_income": (("OtherIncome",), "INR crore"),
    "total_expenses": (("Expenses", "TotalExpenses"), "INR crore"),
    "employee_benefit_expense": (("EmployeeBenefitExpense",), "INR crore"),
    "finance_costs": (("FinanceCosts",), "INR crore"),
    "depreciation_amortisation": (("DepreciationDepletionAndAmortisationExpense",), "INR crore"),
    "profit_before_tax": (("ProfitBeforeTax", "ProfitLossFromOrdinaryActivitiesBeforeTax", "ProfitBeforeExceptionalItemsAndTax", "ProfitBeforeExtraordinaryItemsAndTax"), "INR crore"),
    "profit_after_tax_total": (("ProfitLossForThePeriod", "ProfitLossForPeriod", "ProfitLossFromOrdinaryActivitiesAfterTax"), "INR crore"),
    "profit_after_tax_attributable_to_owners": (("ProfitOrLossAttributableToOwnersOfParent", "ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates"), "INR crore"),
    "basic_eps": (("BasicEarningsLossPerShareFromContinuingOperations", "BasicEarningsLossPerShare"), "INR/share"),
    "diluted_eps": (("DilutedEarningsLossPerShareFromContinuingOperations", "DilutedEarningsLossPerShare"), "INR/share"),
    "total_assets": (("Assets", "TotalAssets"), "INR crore"),
    "total_equity": (("Equity", "EquityAttributableToOwnersOfParent"), "INR crore"),
    "total_liabilities": (("Liabilities",), "INR crore"),
    "cash_and_cash_equivalents": (("CashAndCashEquivalents",), "INR crore"),
    "borrowings": (("Borrowings",), "INR crore"),
    "interest_earned": (("InterestEarned", "InterestAndDiscountOnAdvances"), "INR crore"),
    "interest_expended": (("InterestExpended",), "INR crore"),
    "bank_operating_profit_before_provisions": (("OperatingProfitBeforeProvisionAndContingencies",), "INR crore"),
    "bank_provisions_and_contingencies": (("ProvisionsAndContingencies", "ProvisionAndContingencies"), "INR crore"),
    "net_cash_from_operating_activities": (("NetCashFlowsFromUsedInOperatingActivities", "NetCashFlowsFromOperatingActivities", "CashFlowsFromUsedInOperatingActivities"), "INR crore"),
    "capital_expenditure": (("PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities", "PurchaseOfPropertyPlantAndEquipment"), "INR crore"),
}

FLOW_METRICS = {
    "revenue_from_operations", "total_income", "other_income", "total_expenses",
    "employee_benefit_expense", "finance_costs", "depreciation_amortisation",
    "profit_before_tax", "profit_after_tax_total",
    "profit_after_tax_attributable_to_owners", "interest_earned",
    "interest_expended", "bank_operating_profit_before_provisions",
    "bank_provisions_and_contingencies", "net_cash_from_operating_activities",
    "capital_expenditure",
}


def row_basis(row: dict[str, Any]) -> str:
    raw = str(row.get("consolidated") or row.get("basis") or "").strip().casefold()
    if "standalone" in raw:
        return "standalone"
    if "consolidated" in raw:
        return "consolidated"
    return ""

def filing_date(row: dict[str, Any]) -> date | None:
    return parse_iso_or_nse(row.get("qe_Date") or row.get("periodEnd") or row.get("period_ended"))

def date_rank(row: dict[str, Any]) -> str:
    return str(row.get("revised_Date") or row.get("creation_Date") or row.get("broadcast_Date") or "")

def latest_for_basis(rows: list[dict[str, Any]], basis: str) -> dict[str, Any] | None:
    matches = [r for r in rows if row_basis(r) == basis]
    if not matches:
        return None
    # Preserve the most recently revised/created filing when NSE exposes revisions.
    matches.sort(key=lambda r: (str(r.get("revised_Date") or ""), str(r.get("creation_Date") or ""), str(r.get("broadcast_Date") or "")), reverse=True)
    return matches[0]

def decimal_fact(facts: dict[str, Any], names: tuple[str, ...], context: str) -> tuple[Decimal | None, str | None]:
    for tag in names:
        value = facts.get(tag, {}).get(context)
        if value in (None, ""):
            continue
        try:
            number = Decimal(str(value))
            if number.is_finite():
                return number, tag
        except (InvalidOperation, ValueError):
            continue
    return None, None

def extract_observations(
    symbol: str,
    row: dict[str, Any],
    xml_text: str,
    expected_end: date,
    period_kind: str,
    retrieved_at: datetime,
) -> tuple[list[FinancialObservation], dict[str, Any]]:
    parsed = parse_xbrl(xml_text)
    facts = parsed.get("facts") or {}
    contexts = parsed.get("contexts") or {}
    preferred_tags = tuple(
        tag for aliases, _unit in METRIC_MAP.values() for tag in aliases
    )
    context_id, start_date, end_date = choose_duration_context(
        contexts, expected_end, period_kind, facts, preferred_tags
    )
    if period_kind == "quarter" and (end_date - start_date).days > 140:
        raise ValueError(f"quarter context unexpectedly spans {(end_date-start_date).days} days")
    if period_kind == "year" and (end_date - start_date).days < 300:
        raise ValueError(f"annual context unexpectedly spans {(end_date-start_date).days} days")

    basis = row_basis(row)
    if not basis:
        raise ValueError("filing has no recognised standalone/consolidated basis")
    annualisation = Decimal("4") if period_kind == "quarter" else (Decimal("2") if period_kind == "half_year" else Decimal("1"))
    period = FinancialPeriod(
        start_date=start_date,
        end_date=end_date,
        kind=period_kind,
        basis=basis,
        annualisation_factor=annualisation,
    )
    publication_date = (
        parse_iso_or_nse(row.get("broadcast_Date"))
        or parse_iso_or_nse(row.get("creation_Date"))
        or parse_iso_or_nse(row.get("revised_Date"))
    )
    if publication_date is None:
        raise ValueError("NSE filing has no parseable broadcast/creation/revision date")
    xbrl_url = str(row.get("xbrl") or row.get("xbrlFile") or "")
    seq_id = str(row.get("seq_Id") or row.get("seqId") or "")
    revision = str(row.get("type_Sub") or "unknown")
    sha = hashlib.sha256(xml_text.encode("utf-8")).hexdigest()
    source = SourceReference(
        source_name=SOURCE_NAME,
        source_type=SOURCE_TYPE,
        publication_date=publication_date,
        retrieved_at=retrieved_at,
        url=xbrl_url,
        reference_id=f"{seq_id}:{revision}:{basis}:{sha[:16]}",
    )
    observations: list[FinancialObservation] = []
    used_tags: dict[str, str] = {}

    for metric, (aliases, unit) in METRIC_MAP.items():
        raw, tag = decimal_fact(facts, aliases, context_id)
        if raw is None or tag is None:
            continue
        if unit == "INR crore":
            value = raw / CRORE
            currency = "INR"
        else:
            value = raw
            currency = "INR"
        observations.append(FinancialObservation(
            symbol=symbol,
            metric=metric,
            value=value,
            unit=unit,
            currency=currency,
            period=period,
            source=source,
            observation_kind="reported",
        ))
        used_tags[metric] = tag

    # Derived bank net interest income is kept separate and explicitly tagged calculated.
    earned = next((o.value for o in observations if o.metric == "interest_earned"), None)
    expended = next((o.value for o in observations if o.metric == "interest_expended"), None)
    if earned is not None and expended is not None:
        observations.append(FinancialObservation(
            symbol=symbol,
            metric="net_interest_income",
            value=earned - expended,
            unit="INR crore",
            currency="INR",
            period=period,
            source=source,
            observation_kind="calculated",
        ))

    if len(observations) < 2:
        raise ValueError(f"only {len(observations)} standard facts parsed; insufficient for trusted import")

    summary = {
        "symbol": symbol,
        "basis": basis,
        "period_kind": period_kind,
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "publication_date": publication_date.isoformat(),
        "sequence_id": seq_id,
        "revision": revision,
        "xbrl_url": xbrl_url,
        "xbrl_sha256": sha,
        "observation_count": len(observations),
        "metrics": sorted(o.metric for o in observations),
        "source_tags": used_tags,
        "context_id": context_id,
    }
    return observations, summary

def select_filing(rows: list[dict[str, Any]], target_end: date, basis: str) -> dict[str, Any] | None:
    by_date = [r for r in rows if filing_date(r) == target_end and row_basis(r) == basis]
    return latest_for_basis(by_date, basis)

def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest official NSE Integrated Filing XBRL for the 64-stock universe.")
    parser.add_argument("--universe", type=Path, default=Path("data/universe/indian_watchlist_companies.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/financials"), help="Base folder; every run gets a unique subfolder.")
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"), help="Unique output folder name; reusing an existing ID is rejected.")
    parser.add_argument("--symbols", default="", help="Optional comma-separated symbol subset for validation.")
    parser.add_argument("--quarter-end", default="2026-09-30")
    parser.add_argument("--annual-end", default=date.today().isoformat())
    parser.add_argument("--quarter-count", type=int, default=4, help="Number of most recent quarter periods per basis.")
    parser.add_argument("--annual-count", type=int, default=3, help="Number of most recent March year-end periods per basis.")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--delay-seconds", type=float, default=0.35)
    parser.add_argument("--fail-on-missing", action="store_true")
    args = parser.parse_args()

    with args.universe.open(newline="", encoding="utf-8-sig") as handle:
        companies = list(csv.DictReader(handle))
    if args.symbols.strip():
        selected = {s.strip().upper() for s in args.symbols.split(",") if s.strip()}
        companies = [r for r in companies if r["symbol"].upper() in selected]
    if not companies:
        raise SystemExit("No universe companies selected.")

    quarter_end = date.fromisoformat(args.quarter_end)
    annual_end = date.fromisoformat(args.annual_end)
    output_dir = create_run_directory(args.output_dir, args.run_id)
    db_path = output_dir / "financials.sqlite"
    repo = FinancialRepository(db_path)

    client = NSEClient()
    client._seed_session()
    retrieved_at = datetime.now(timezone.utc)
    all_observations: list[FinancialObservation] = []
    filing_summaries: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    failures: list[str] = []

    for index, company in enumerate(companies, start=1):
        symbol = company["symbol"].strip().upper()
        issuer = company["issuer_name"].strip()
        print(f"[{index}/{len(companies)}] {symbol} — {issuer}", flush=True)
        row_coverage: dict[str, Any] = {
            "symbol": symbol,
            "issuer_name": issuer,
            "sector": company.get("sector", ""),
            "listing_ok": False,
            "quarter_filings": 0,
            "half_year_filings": 0,
            "annual_filings": 0,
            "observations": 0,
            "status": "",
            "errors": [],
        }
        try:
            listing = client.get_integrated_filings(symbol, issuer, page=1, size=args.page_size)
            if not isinstance(listing, dict):
                raise RuntimeError("NSE filing search returned no JSON")
            rows = listing.get("data") or []
            if not isinstance(rows, list):
                raise RuntimeError("NSE filing response has an unexpected data structure")
            row_coverage["listing_ok"] = True
            row_coverage["listing_rows"] = len(rows)

            xbrl_cache: dict[str, str] = {}
            for basis in sorted({row_basis(r) for r in rows if row_basis(r)}):
                available_dates = sorted(
                    {filing_date(r) for r in rows if row_basis(r) == basis and filing_date(r) is not None},
                    reverse=True,
                )
                quarter_dates = [
                    d for d in available_dates
                    if d <= quarter_end and (
                        (d.month == 3 and d.day == 31) or
                        (d.month == 6 and d.day == 30) or
                        (d.month == 9 and d.day == 30) or
                        (d.month == 12 and d.day == 31)
                    )
                ][:max(1, args.quarter_count)]
                fiscal_year_end = company.get("fiscal_year_end", "03-31").strip()
                annual_dates = [
                    d for d in available_dates
                    if d <= annual_end and f"{d.month:02d}-{d.day:02d}" == fiscal_year_end
                ][:max(1, args.annual_count)]

                for label, period_dates, period_kind in (
                    ("quarter", quarter_dates, "quarter"),
                    ("annual", annual_dates, "year"),
                ):
                    for target in period_dates:
                        filing = select_filing(rows, target, basis)
                        if filing is None:
                            continue
                        xbrl_url = str(filing.get("xbrl") or filing.get("xbrlFile") or "")
                        if not xbrl_url:
                            row_coverage["errors"].append(f"{label}/{basis}/{target}: no XBRL URL")
                            continue
                        stored_label = label
                        try:
                            if xbrl_url not in xbrl_cache:
                                xml_text = None
                                last_error = None
                                for attempt in range(1, 4):
                                    try:
                                        xml_text = client.get_integrated_xbrl(xbrl_url)
                                        if xml_text and "<" in xml_text[:100]:
                                            break
                                        last_error = ValueError("XBRL attachment download returned no XML")
                                    except Exception as download_error:
                                        last_error = download_error
                                    if attempt < 3:
                                        time.sleep(attempt * 2)
                                if not xml_text or "<" not in xml_text[:100]:
                                    raise ValueError(f"XBRL download failed after 3 attempts: {last_error}")
                                xbrl_cache[xbrl_url] = xml_text
                            try:
                                observations, summary = extract_observations(
                                    symbol, filing, xbrl_cache[xbrl_url], target, period_kind, retrieved_at
                                )
                            except ValueError as primary_error:
                                if label != "quarter" or "no quarter duration context" not in str(primary_error):
                                    raise
                                # Some issuers report a half-year duration for the same
                                # period end; store it as half-year, never as a quarter.
                                observations, summary = extract_observations(
                                    symbol, filing, xbrl_cache[xbrl_url], target, "half_year", retrieved_at
                                )
                                stored_label = "half_year"
                            all_observations.extend(observations)
                            filing_summaries.append(summary)
                            row_coverage["observations"] += len(observations)
                            row_coverage[f"{stored_label}_filings"] += 1
                            print(
                                f"  {label} {basis}: {summary['period_start']}..{summary['period_end']} "
                                f"{len(observations)} observations",
                                flush=True,
                            )
                        except Exception as exc:
                            message = f"{stored_label}/{basis}/{target}: {type(exc).__name__}: {exc}"
                            row_coverage["errors"].append(message)
                            failures.append(f"{symbol} {message}")
                        time.sleep(max(0.0, args.delay_seconds))

            if (row_coverage["quarter_filings"] or row_coverage["half_year_filings"]) and row_coverage["annual_filings"]:
                row_coverage["status"] = "quarter_or_half_year_and_annual_loaded"
            elif row_coverage["quarter_filings"] or row_coverage["half_year_filings"] or row_coverage["annual_filings"]:
                row_coverage["status"] = "partial_period_coverage"
            elif row_coverage["errors"]:
                row_coverage["status"] = "filing_parse_error"
            else:
                row_coverage["status"] = "filings_not_found_for_target_periods"
        except Exception as exc:
            row_coverage["status"] = "listing_error"
            row_coverage["errors"].append(f"{type(exc).__name__}: {exc}")
            failures.append(f"{symbol} listing: {type(exc).__name__}: {exc}")
        coverage.append(row_coverage)
        time.sleep(max(0.0, args.delay_seconds))

    if all_observations:
        inserted = repo.insert_many(all_observations)
    else:
        inserted = 0

    # Export the exact long-form schema already supported by the existing CSV importer.
    csv_path = output_dir / "financial_observations.csv"
    fields = [
        "symbol", "metric", "value", "unit", "currency", "period_start", "period_end",
        "period_kind", "basis", "annualisation_factor", "source_name", "source_type",
        "publication_date", "retrieved_at", "source_url", "reference_id", "observation_kind",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in all_observations:
            writer.writerow({
                "symbol": item.symbol,
                "metric": item.metric,
                "value": str(item.value),
                "unit": item.unit,
                "currency": item.currency,
                "period_start": item.period.start_date.isoformat(),
                "period_end": item.period.end_date.isoformat(),
                "period_kind": item.period.kind,
                "basis": item.period.basis,
                "annualisation_factor": str(item.period.annualisation_factor),
                "source_name": item.source.source_name,
                "source_type": item.source.source_type,
                "publication_date": item.source.publication_date.isoformat(),
                "retrieved_at": item.source.retrieved_at.isoformat(),
                "source_url": item.source.url or "",
                "reference_id": item.source.reference_id or "",
                "observation_kind": item.observation_kind,
            })

    coverage_path = output_dir / "filing_coverage.csv"
    coverage_fields = ["symbol", "issuer_name", "sector", "listing_ok", "listing_rows", "quarter_filings", "half_year_filings", "annual_filings", "observations", "status", "errors"]
    with coverage_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=coverage_fields)
        writer.writeheader()
        for row in coverage:
            row_copy = dict(row)
            row_copy["errors"] = " | ".join(row_copy.get("errors", []))
            writer.writerow({key: row_copy.get(key, "") for key in coverage_fields})

    (output_dir / "filing_manifest.json").write_text(json.dumps(filing_summaries, indent=2, default=str), encoding="utf-8")
    counts: dict[str, int] = {}
    for row in coverage:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    summary = {
        "retrieved_at": retrieved_at.isoformat(),
        "universe_count": len(companies),
        "company_count_with_any_filing": sum(1 for r in coverage if r["quarter_filings"] or r["half_year_filings"] or r["annual_filings"]),
        "quarter_company_count": sum(1 for r in coverage if r["quarter_filings"]),
        "half_year_company_count": sum(1 for r in coverage if r["half_year_filings"]),
        "annual_company_count": sum(1 for r in coverage if r["annual_filings"]),
        "observation_count": inserted,
        "sqlite_database": str(db_path),
        "csv_observations": str(csv_path),
        "coverage_csv": str(coverage_path),
        "status_counts": counts,
        "failures": failures,
    }
    (output_dir / "ingest_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if args.fail_on_missing and (summary["quarter_company_count"] + summary["half_year_company_count"] < len(companies) or summary["annual_company_count"] < len(companies)):
        return 2
    if inserted == 0:
        return 3
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
