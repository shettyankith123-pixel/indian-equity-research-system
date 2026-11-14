from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from nse_xbrl import NSEClient, parse_xbrl
from indian_equity_research.ingestion.xbrl_contexts import parse_iso_or_nse, choose_duration_context, create_run_directory, period_kind_for_target, choose_instant_context

from indian_equity_research.models.financials import (
    FinancialObservation,
    FinancialPeriod,
    SourceReference,
)
from indian_equity_research.ingestion.nse_filing_client import fetch_integrated_filing_listing
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
    # Bank asset-quality and capital ratios are reported in NSE quarter-duration
    # contexts (for example OneD/FourD), even though the values are period-end
    # snapshots. They are handled as source-reported period-end metrics below.
    "gross_npa_reported": (("GrossNonPerformingAssets",), "INR crore"),
    "net_npa_reported": (("NonPerformingAssets",), "INR crore"),
    "gross_npa_ratio": (("PercentageOfGrossNpa",), "ratio"),
    "net_npa_ratio": (("PercentageOfNpa",), "ratio"),
    "cet1_ratio": (("CET1Ratio",), "ratio"),
    "additional_tier1_ratio": (("AdditionalTier1Ratio",), "ratio"),
}


INSTANT_METRIC_MAP = {
    "total_assets": (("Assets", "TotalAssets"), "INR crore"),
    "total_equity": (("EquityAttributableToOwnersOfParent", "Equity"), "INR crore"),
    "total_liabilities": (("Liabilities",), "INR crore"),
    "cash_and_cash_equivalents": (("CashAndCashEquivalents", "CashAndCashEquivalentsAndBankBalances", "CashAndCashEquivalentsCashFlowStatement"), "INR crore"),
    "borrowings": (("Borrowings", "BorrowingsCurrentAndNonCurrent"), "INR crore"),
    "current_assets": (("CurrentAssets", "TotalCurrentAssets"), "INR crore"),
    "current_liabilities": (("CurrentLiabilities", "TotalCurrentLiabilities"), "INR crore"),
    "inventories": (("Inventories",), "INR crore"),
    "trade_receivables": (("TradeReceivables",), "INR crore"),
    "trade_payables": (("TradePayables",), "INR crore"),
    "current_borrowings": (("CurrentBorrowings", "BorrowingsCurrent", "ShortTermBorrowings"), "INR crore"),
    "non_current_borrowings": (("BorrowingsNoncurrent", "NoncurrentBorrowings", "BorrowingsNonCurrent", "LongTermBorrowings"), "INR crore"),
    "bank_deposits": (("Deposits", "DepositsFromCustomers"), "INR crore"),
    "bank_advances": (("Advances", "LoansAndAdvancesToCustomers"), "INR crore"),
    "gross_npa": (("GrossNonPerformingAssets", "GrossNPA"), "INR crore"),
    "net_npa": (("NetNonPerformingAssets", "NetNPA"), "INR crore"),
    "provisions_against_npa": (("ProvisionsForNonPerformingAssets", "ProvisionForNPA"), "INR crore"),
    "bank_share_capital": (("Capital",), "INR crore"),
    "bank_reserves_and_surplus": (("ReservesAndSurplus",), "INR crore"),
    "bank_cash_and_rbi_balances": (("CashAndBalancesWithReserveBankOfIndia",), "INR crore"),
    "bank_balances_with_other_banks": (("BalancesWithBanksAndMoneyAtCallAndShortNotice",), "INR crore"),
    "bank_investments": (("Investments",), "INR crore"),
    "risk_weighted_assets": (("RiskWeightedAssets",), "INR crore"),
}
DURATION_METRIC_MAP = {k: v for k, v in METRIC_MAP.items() if k not in INSTANT_METRIC_MAP}

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
        tag for aliases, _unit in DURATION_METRIC_MAP.values() for tag in aliases
    )
    stored_period_kind = period_kind
    try:
        context_id, start_date, end_date = choose_duration_context(
            contexts, expected_end, period_kind, facts, preferred_tags
        )
    except ValueError as primary_error:
        if period_kind == "year":
            try:
                context_id, start_date, end_date = choose_duration_context(
                    contexts, expected_end, "transition_period", facts, preferred_tags
                )
                stored_period_kind = "transition_period"
            except ValueError:
                raise primary_error
        elif period_kind == "transition_period":
            # The filer may supply only the 12-month current-year comparative.
            # Import the reported year as a year and preserve the missing transition
            # interval as an explicit coverage exception; do not annualise it as 18 months.
            try:
                context_id, start_date, end_date = choose_duration_context(
                    contexts, expected_end, "year", facts, preferred_tags
                )
                stored_period_kind = "year"
            except ValueError:
                raise primary_error
        else:
            raise

    span_days = (end_date - start_date).days + 1
    if stored_period_kind == "quarter" and span_days > 140:
        raise ValueError(f"quarter context unexpectedly spans {span_days} days")
    if stored_period_kind == "year" and span_days < 300:
        raise ValueError(f"annual context unexpectedly spans {span_days} days")
    if stored_period_kind == "transition_period" and not 450 <= span_days <= 730:
        raise ValueError(f"transition context unexpectedly spans {span_days} days")

    basis = row_basis(row)
    if not basis:
        raise ValueError("filing has no recognised standalone/consolidated basis")
    if stored_period_kind == "quarter":
        annualisation = Decimal("4")
    elif stored_period_kind == "half_year":
        annualisation = Decimal("2")
    elif stored_period_kind == "transition_period":
        annualisation = Decimal("365") / Decimal(span_days)
    else:
        annualisation = Decimal("1")
    period = FinancialPeriod(
        start_date=start_date,
        end_date=end_date,
        kind=stored_period_kind,
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

    for metric, (aliases, unit) in DURATION_METRIC_MAP.items():
        raw, tag = decimal_fact(facts, aliases, context_id)
        if raw is None or tag is None:
            continue
        if unit == "INR crore":
            value = raw / CRORE
            currency = "INR"
        elif unit == "ratio":
            value = raw
            currency = "N/A"
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

    # Balance-sheet facts are instant-date facts, not duration flows. Import
    # both the reporting-date snapshot and a prior-year comparative when the
    # filing supplies them. This allows average-balance ROE/ROA without mixing
    # a closing balance sheet with a flow period.
    instant_used_tags: dict[str, str] = {}
    instant_context_id = ""
    instant_warning = ""
    instant_preferred_tags = tuple(
        tag for aliases, _unit in INSTANT_METRIC_MAP.values() for tag in aliases
    )
    instant_dates: set[date] = set()
    minimum_comparative_date = end_date - timedelta(days=800)
    for candidate in contexts.values():
        if candidate.get("type") not in (None, "instant"):
            continue
        raw_instant = candidate.get("instant") or candidate.get("instant_date")
        if raw_instant in (None, ""):
            continue
        try:
            candidate_date = parse_iso_or_nse(raw_instant)
        except (TypeError, ValueError):
            continue
        if minimum_comparative_date <= candidate_date <= end_date:
            instant_dates.add(candidate_date)

    instant_contexts_by_date: dict[str, dict[str, Any]] = {}
    instant_warnings: list[str] = []
    for selected_date in sorted(instant_dates):
        try:
            selected_context_id, selected_instant_date = choose_instant_context(
                contexts, selected_date, facts, instant_preferred_tags
            )
        except ValueError as instant_error:
            instant_warnings.append(f"{selected_date}: {instant_error}")
            continue

        instant_period = FinancialPeriod(
            start_date=selected_instant_date,
            end_date=selected_instant_date,
            kind="instant",
            basis=basis,
            annualisation_factor=Decimal("1"),
        )
        date_tags: dict[str, str] = {}
        for metric, (aliases, unit) in INSTANT_METRIC_MAP.items():
            raw, tag = decimal_fact(facts, aliases, selected_context_id)
            if raw is None or tag is None:
                continue
            value = raw / CRORE if unit == "INR crore" else raw
            currency = "INR" if unit == "INR crore" else ("N/A" if unit == "ratio" else "INR")
            observations.append(FinancialObservation(
                symbol=symbol,
                metric=metric,
                value=value,
                unit=unit,
                currency=currency,
                period=instant_period,
                source=source,
                observation_kind="reported",
            ))
            date_tags[metric] = tag
        instant_contexts_by_date[selected_instant_date.isoformat()] = {
            "context_id": selected_context_id,
            "metrics": date_tags,
        }
        if selected_instant_date == end_date:
            instant_context_id = selected_context_id
            instant_used_tags = date_tags

    if not instant_context_id:
        instant_warning = (
            f"No mapped instant balance-sheet context ending {end_date}."
            + (" " + "; ".join(instant_warnings) if instant_warnings else "")
        )
    else:
        instant_warning = "; ".join(instant_warnings)

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
        "period_kind": stored_period_kind,
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "publication_date": publication_date.isoformat(),
        "sequence_id": seq_id,
        "revision": revision,
        "xbrl_url": xbrl_url,
        "xbrl_sha256": sha,
        "observation_count": len(observations),
        "metrics": sorted(o.metric for o in observations),
        "duration_metrics": sorted(used_tags),
        "instant_metrics": sorted(instant_used_tags),
        "instant_contexts_by_date": instant_contexts_by_date,
        "instant_snapshot_dates": sorted(instant_contexts_by_date),
        "source_tags": used_tags,
        "instant_source_tags": instant_used_tags,
        "context_id": context_id,
        "instant_context_id": instant_context_id or None,
        "instant_warning": instant_warning,
        "transition_period_note": (
            "Expected longer transition interval was not present; only the available 12-month annual context was imported."
            if period_kind == "transition_period" and stored_period_kind == "year" else ""
        ),
    }
    return observations, summary


def reconcile_duplicate_observations(
    observations: list[FinancialObservation],
) -> tuple[list[FinancialObservation], int, list[dict[str, Any]]]:
    """Remove exact repeated facts; quarantine value conflicts instead of aborting a whole run.

    The SQLite uniqueness contract intentionally identifies one fact by source, metric,
    basis and exact period dates. If two period labels collide for the same span, the
    span-derived label is preferred (instant/quarter/half-year/year/transition). If
    values or units conflict for the same source key, every conflicting copy is omitted
    and a diagnostic is returned for the coverage report.
    """
    def identity(item: FinancialObservation) -> tuple[str, ...]:
        p = item.period
        return (
            item.symbol, item.metric, p.start_date.isoformat(), p.end_date.isoformat(),
            p.basis, item.source.source_name, item.source.reference_id or "",
            item.observation_kind,
        )

    def expected_period_kind(item: FinancialObservation) -> str:
        span = (item.period.end_date - item.period.start_date).days + 1
        if span == 1:
            return "instant"
        if 70 <= span <= 140:
            return "quarter"
        if 150 <= span <= 220:
            return "half_year"
        if 300 <= span <= 400:
            return "year"
        if 450 <= span <= 730:
            return "transition_period"
        return item.period.kind

    selected: dict[tuple[str, ...], FinancialObservation] = {}
    conflicts: dict[tuple[str, ...], dict[str, Any]] = {}
    duplicate_count = 0

    for item in observations:
        key = identity(item)
        if key in conflicts:
            conflict = conflicts[key]
            conflict["values"].append({
                "value": str(item.value),
                "unit": item.unit,
                "period_kind": item.period.kind,
            })
            continue
        existing = selected.get(key)
        if existing is None:
            selected[key] = item
            continue

        if (
            existing.value == item.value
            and existing.unit == item.unit
            and existing.currency == item.currency
        ):
            duplicate_count += 1
            # Preserve the period-kind label implied by the exact duration.
            expected = expected_period_kind(existing)
            if item.period.kind == expected and existing.period.kind != expected:
                selected[key] = item
            continue

        selected.pop(key, None)
        conflicts[key] = {
            "symbol": item.symbol,
            "metric": item.metric,
            "period_start": item.period.start_date.isoformat(),
            "period_end": item.period.end_date.isoformat(),
            "basis": item.period.basis,
            "source_name": item.source.source_name,
            "reference_id": item.source.reference_id or "",
            "values": [
                {
                    "value": str(existing.value),
                    "unit": existing.unit,
                    "period_kind": existing.period.kind,
                },
                {
                    "value": str(item.value),
                    "unit": item.unit,
                    "period_kind": item.period.kind,
                },
            ],
        }

    return list(selected.values()), duplicate_count, list(conflicts.values())

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
            "transition_period_filings": 0,
            "observations": 0,
            "status": "",
            "errors": [],
        }
        try:
            listing, listing_query = fetch_integrated_filing_listing(
                client, symbol, issuer, page=1, size=args.page_size
            )
            row_coverage["listing_query"] = listing_query
            if not isinstance(listing, dict):
                raise RuntimeError("NSE filing search returned no JSON")
            rows = listing.get("data") or []
            if not isinstance(rows, list):
                raise RuntimeError("NSE filing response has an unexpected data structure")
            row_coverage["listing_ok"] = True
            row_coverage["listing_rows"] = len(rows)
            if not rows:
                row_coverage["errors"].append(
                    "No NSE Integrated Filing records returned after issuer and symbol-only lookup."
                )
                failures.append(f"{symbol}: no NSE Integrated Filing records returned by either lookup.")

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
                        target_period_kind = period_kind_for_target(
                            target,
                            period_kind,
                            company.get("transition_period_start", ""),
                            company.get("transition_period_end", ""),
                        )
                        if target_period_kind == "transition_period":
                            stored_label = "transition_period"
                        else:
                            stored_label = label
                        filing = select_filing(rows, target, basis)
                        if filing is None:
                            continue
                        xbrl_url = str(filing.get("xbrl") or filing.get("xbrlFile") or "")
                        if not xbrl_url:
                            row_coverage["errors"].append(f"{label}/{basis}/{target}: no XBRL URL")
                            continue
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
                                    symbol, filing, xbrl_cache[xbrl_url], target, target_period_kind, retrieved_at
                                )
                            except ValueError as primary_error:
                                if target_period_kind != "quarter" or "no quarter duration context" not in str(primary_error):
                                    raise
                                # Some issuers report a half-year duration for the same
                                # period end; store it as half-year, never as a quarter.
                                observations, summary = extract_observations(
                                    symbol, filing, xbrl_cache[xbrl_url], target, "half_year", retrieved_at
                                )
                                stored_label = "half_year"
                            if summary.get("period_kind") != target_period_kind and target_period_kind == "transition_period":
                                raise ValueError(
                                    "issuer fiscal transition period did not match the XBRL context"
                                )
                            if summary.get("period_kind") == "transition_period":
                                stored_label = "transition_period"
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
            elif (row_coverage["quarter_filings"] or row_coverage["half_year_filings"]) and row_coverage["transition_period_filings"]:
                row_coverage["status"] = "quarter_or_half_year_and_transition_period_loaded"
            elif row_coverage["quarter_filings"] or row_coverage["half_year_filings"] or row_coverage["annual_filings"] or row_coverage["transition_period_filings"]:
                row_coverage["status"] = "partial_period_coverage"
            elif row_coverage.get("listing_query") == "no_rows":
                row_coverage["status"] = "filings_not_found_for_target_periods"
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

    raw_observation_count = len(all_observations)
    reconciled_observations, duplicate_observation_count, observation_conflicts = (
        reconcile_duplicate_observations(all_observations)
    )
    for conflict in observation_conflicts:
        message = (
            f"Conflicting duplicate fact excluded: {conflict['metric']} "
            f"{conflict['period_start']}..{conflict['period_end']} "
            f"{conflict['basis']} source={conflict['reference_id']} "
            f"values={conflict['values']}"
        )
        failures.append(f"{conflict['symbol']}: {message}")
        for row in coverage:
            if row["symbol"] == conflict["symbol"]:
                row["errors"].append(message)
                row["status"] = "data_conflict_partial"
                break

    if reconciled_observations:
        inserted = repo.insert_many(reconciled_observations)
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
    coverage_fields = ["symbol", "issuer_name", "sector", "listing_ok", "listing_rows", "listing_query", "quarter_filings", "half_year_filings", "annual_filings", "transition_period_filings", "observations", "status", "errors"]
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
        "company_count_with_any_filing": sum(1 for r in coverage if r["quarter_filings"] or r["half_year_filings"] or r["annual_filings"] or r["transition_period_filings"]),
        "quarter_company_count": sum(1 for r in coverage if r["quarter_filings"]),
        "half_year_company_count": sum(1 for r in coverage if r["half_year_filings"]),
        "annual_company_count": sum(1 for r in coverage if r["annual_filings"]),
        "transition_period_company_count": sum(1 for r in coverage if r["transition_period_filings"]),
        "observation_count": inserted,
        "raw_observation_count": raw_observation_count,
        "duplicate_observation_count": duplicate_observation_count,
        "conflicting_observation_count": len(observation_conflicts),
        "observation_conflicts": observation_conflicts,
        "sqlite_database": str(db_path),
        "csv_observations": str(csv_path),
        "coverage_csv": str(coverage_path),
        "status_counts": counts,
        "failures": failures,
    }
    (output_dir / "ingest_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if args.fail_on_missing and (
        summary["quarter_company_count"] + summary["half_year_company_count"] < len(companies)
        or summary["annual_company_count"] + summary["transition_period_company_count"] < len(companies)
    ):
        return 2
    if inserted == 0:
        return 3
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
