from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


FLOW_METRICS = {"net_cash_from_operating_activities", "capital_expenditure"}
INSTANT_DEBT_METRICS = {"borrowings", "current_borrowings", "non_current_borrowings"}
BANK_SECTOR_TERMS = ("bank", "nbfc")


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _as_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _debt(metrics: dict[str, Decimal]) -> Decimal | None:
    if metrics.get("borrowings") is not None:
        return metrics["borrowings"]
    current = metrics.get("current_borrowings")
    noncurrent = metrics.get("non_current_borrowings")
    if current is not None and noncurrent is not None:
        return current + noncurrent
    return None


def _is_bank_sector(sector: str) -> bool:
    normalized = sector.casefold()
    return any(term in normalized for term in BANK_SECTOR_TERMS)


def has_three_consecutive_years(dates: list[date]) -> bool:
    ordered = sorted(set(dates))
    if len(ordered) < 3:
        return False
    run = 1
    for previous, current in zip(ordered, ordered[1:]):
        gap = (current - previous).days
        run = run + 1 if 330 <= gap <= 400 else 1
        if run >= 3:
            return True
    return False


def max_consecutive_years(dates: list[date]) -> int:
    ordered = sorted(set(dates))
    if not ordered:
        return 0
    best = run = 1
    for previous, current in zip(ordered, ordered[1:]):
        gap = (current - previous).days
        run = run + 1 if 330 <= gap <= 400 else 1
        best = max(best, run)
    return best


def build_fcfe_audit(
    observations: list[dict[str, Any]],
    filing_coverage: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Audit annual true-FCFE eligibility using the same inputs as fundamentals.py.

    True FCFE = CFO - abs(capex) + (current closing debt - prior-year closing debt).
    Current closing debt must exist in the same filing reference as the annual flow.
    Prior debt is the closest earlier instant snapshot 330–400 days before year end,
    using the same reporting basis and source, matching fundamentals.py.
    """
    flow_groups: dict[tuple, dict[str, Any]] = {}
    instant_by_ref: dict[tuple, dict[str, Decimal]] = {}
    instant_candidates: dict[tuple, dict[date, list[tuple[date, dict[str, Decimal]]]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for row in observations:
        symbol = str(row.get("symbol") or "").strip().upper()
        basis = str(row.get("basis") or "").strip().lower()
        source = str(row.get("source_name") or "").strip()
        reference = str(row.get("reference_id") or "").strip()
        kind = str(row.get("period_kind") or "").strip().lower()
        metric = str(row.get("metric") or "").strip()
        period_end = _as_date(row.get("period_end"))
        period_start = _as_date(row.get("period_start"))
        publication = _as_date(row.get("publication_date"))
        value = _decimal(row.get("value"))
        if not symbol or not basis or not source or not period_end or not metric or value is None:
            continue

        if kind == "instant":
            key = (symbol, basis, source, reference, period_end)
            instant_by_ref.setdefault(key, {}).setdefault(metric, value)
            history_key = (symbol, basis, source)
            instant_candidates[history_key][period_end].append(
                (publication or period_end, {metric: value})
            )
        elif kind == "year" and period_start is not None and metric in FLOW_METRICS:
            key = (symbol, basis, source, reference, period_start, period_end)
            group = flow_groups.setdefault(
                key,
                {
                    "symbol": symbol,
                    "basis": basis,
                    "source_name": source,
                    "reference_id": reference,
                    "period_start": period_start,
                    "period_end": period_end,
                    "publication_date": publication,
                    "source_url": str(row.get("source_url") or ""),
                    "metrics": {},
                },
            )
            if metric not in group["metrics"]:
                group["metrics"][metric] = value
            if publication and (
                group["publication_date"] is None or publication > group["publication_date"]
            ):
                group["publication_date"] = publication
                group["source_url"] = str(row.get("source_url") or group["source_url"])

    # Merge same-date instant statements by preferring more complete snapshots,
    # then newer publication dates, as the fundamentals normalizer does.
    merged_history: dict[tuple, list[tuple[date, dict[str, Decimal]]]] = defaultdict(list)
    for history_key, by_date in instant_candidates.items():
        for snapshot_date, candidates in by_date.items():
            candidates.sort(key=lambda item: (len(item[1]), item[0]))
            merged: dict[str, Decimal] = {}
            for _, metrics in candidates:
                merged.update(metrics)
            merged_history[history_key].append((snapshot_date, merged))
        merged_history[history_key].sort(key=lambda item: item[0])

    annual_rows: list[dict[str, Any]] = []
    for group in flow_groups.values():
        symbol = group["symbol"]
        basis = group["basis"]
        source = group["source_name"]
        reference = group["reference_id"]
        end = group["period_end"]
        flow = group["metrics"]
        current_instant = instant_by_ref.get((symbol, basis, source, reference, end), {})

        prior_candidates = [
            (snapshot_date, metrics)
            for snapshot_date, metrics in merged_history.get((symbol, basis, source), [])
            if snapshot_date < end and 330 <= (end - snapshot_date).days <= 400
        ]
        prior = max(prior_candidates, key=lambda item: item[0])[1] if prior_candidates else {}

        cfo = flow.get("net_cash_from_operating_activities")
        capex = flow.get("capital_expenditure")
        current_debt = _debt(current_instant)
        prior_debt = _debt(prior)
        missing: list[str] = []
        if cfo is None:
            missing.append("operating_cash_flow")
        if capex is None:
            missing.append("capital_expenditure")
        if current_debt is None:
            missing.append("current_closing_debt")
        if prior_debt is None:
            missing.append("prior_year_closing_debt")

        fcfe = None
        if not missing:
            fcfe = cfo - abs(capex) + (current_debt - prior_debt)

        annual_rows.append(
            {
                "symbol": symbol,
                "basis": basis,
                "period_start": group["period_start"].isoformat(),
                "period_end": end.isoformat(),
                "source_name": source,
                "reference_id": reference,
                "publication_date": group["publication_date"].isoformat()
                if group["publication_date"] else "",
                "source_url": group["source_url"],
                "operating_cash_flow": str(cfo) if cfo is not None else "",
                "capex_outflow": str(abs(capex)) if capex is not None else "",
                "current_closing_debt": str(current_debt) if current_debt is not None else "",
                "prior_year_closing_debt": str(prior_debt) if prior_debt is not None else "",
                "net_borrowing": str(current_debt - prior_debt)
                if current_debt is not None and prior_debt is not None else "",
                "true_fcfe": str(fcfe) if fcfe is not None else "",
                "fcfe_status": "VERIFIED" if fcfe is not None else "MISSING_INPUTS",
                "missing_inputs": ";".join(missing),
            }
        )

    coverage_by_symbol = {
        str(row.get("symbol") or "").strip().upper(): row for row in filing_coverage
    }
    symbols = sorted(coverage_by_symbol)
    symbols = sorted(set(symbols) | {row["symbol"] for row in annual_rows})
    company_rows: list[dict[str, Any]] = []

    for symbol in symbols:
        filing = coverage_by_symbol.get(symbol, {})
        sector = str(filing.get("sector") or "")
        relevant = [row for row in annual_rows if row["symbol"] == symbol]
        consolidated = [row for row in relevant if row["basis"] == "consolidated"]
        standalone = [row for row in relevant if row["basis"] == "standalone"]

        def unique_years(rows: list[dict[str, Any]]) -> list[date]:
            return sorted({_as_date(row["period_end"]) for row in rows if _as_date(row["period_end"])})

        consolidated_years = unique_years(consolidated)
        standalone_years = unique_years(standalone)
        eligible_fcfe = unique_years([row for row in consolidated if row["fcfe_status"] == "VERIFIED"])
        latest_date = max(consolidated_years) if consolidated_years else None
        latest_rows = [row for row in consolidated if row["period_end"] == latest_date.isoformat()] if latest_date else []
        latest_verified = any(row["fcfe_status"] == "VERIFIED" for row in latest_rows)
        latest_missing = sorted(
            {
                part
                for row in latest_rows if row["fcfe_status"] != "VERIFIED"
                for part in str(row["missing_inputs"]).split(";") if part
            }
        )

        if _is_bank_sector(sector):
            fcfe_decision = "NOT_APPLICABLE_BANK_VALUATION"
            valuation_route = "P/B, residual-income or dividend-based bank valuation"
        elif has_three_consecutive_years(eligible_fcfe):
            fcfe_decision = "PASS_3_CONSECUTIVE_YEARS"
            valuation_route = "FCFE DCF eligible for model review"
        elif len(consolidated_years) < 3:
            fcfe_decision = "INSUFFICIENT_ANNUAL_HISTORY"
            valuation_route = "No strict 3-year FCFE DCF yet"
        else:
            fcfe_decision = "FCFE_INPUT_GAPS"
            valuation_route = "Do not use proxy cash flow as FCFE"

        company_rows.append(
            {
                "symbol": symbol,
                "sector": sector,
                "filing_status": filing.get("status", ""),
                "listing_query": filing.get("listing_query", ""),
                "listing_rows": filing.get("listing_rows", ""),
                "annual_filings": filing.get("annual_filings", ""),
                "transition_period_filings": filing.get("transition_period_filings", ""),
                "consolidated_annual_period_count": len(consolidated_years),
                "consolidated_annual_periods": ";".join(d.isoformat() for d in consolidated_years),
                "standalone_annual_period_count": len(standalone_years),
                "standalone_annual_periods": ";".join(d.isoformat() for d in standalone_years),
                "consolidated_true_fcfe_year_count": len(eligible_fcfe),
                "consolidated_true_fcfe_years": ";".join(d.isoformat() for d in eligible_fcfe),
                "max_consecutive_true_fcfe_years": max_consecutive_years(eligible_fcfe),
                "three_consecutive_fcfe_status": fcfe_decision,
                "latest_consolidated_annual_period": latest_date.isoformat() if latest_date else "",
                "latest_period_fcfe_verified": latest_verified,
                "latest_period_missing_inputs": ";".join(latest_missing),
                "valuation_route": valuation_route,
                "ingestion_errors": filing.get("errors", ""),
            }
        )

    sector_exceptions = sum(1 for row in company_rows if row["three_consecutive_fcfe_status"] == "NOT_APPLICABLE_BANK_VALUATION")
    three_year_pass = sum(1 for row in company_rows if row["three_consecutive_fcfe_status"] == "PASS_3_CONSECUTIVE_YEARS")
    summary = {
        "company_count": len(company_rows),
        "company_count_with_any_filing": sum(1 for row in company_rows if row["filing_status"] not in ("", "filings_not_found_for_target_periods", "listing_error")),
        "companies_with_3plus_consolidated_annual_periods": sum(1 for row in company_rows if int(row["consolidated_annual_period_count"]) >= 3),
        "companies_with_3_consecutive_verified_fcfe_years": three_year_pass,
        "bank_sector_valuation_exceptions": sector_exceptions,
        "status_counts": {},
    }
    for row in company_rows:
        status = row["three_consecutive_fcfe_status"]
        summary["status_counts"][status] = summary["status_counts"].get(status, 0) + 1

    return company_rows, annual_rows, summary


def write_report(
    company_rows: list[dict[str, Any]],
    annual_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    output_dir: Path,
    run_id: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    company_fields = list(company_rows[0]) if company_rows else []
    annual_fields = list(annual_rows[0]) if annual_rows else []
    for filename, rows, fields in (
        ("company_financial_coverage.csv", company_rows, company_fields),
        ("annual_fcfe_audit.csv", annual_rows, annual_fields),
    ):
        with (output_dir / filename).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    (output_dir / "financial_coverage_summary.json").write_text(
        json.dumps({"run_id": run_id, **summary}, indent=2), encoding="utf-8"
    )
    lines = [
        "# Financial history and FCFE coverage",
        "",
        f"Import run: {run_id}",
        "",
        "## Coverage summary",
        "",
        f"- Companies reviewed: {summary['company_count']}",
        f"- Companies with filings: {summary['company_count_with_any_filing']}",
        f"- Companies with at least three consolidated annual periods: {summary['companies_with_3plus_consolidated_annual_periods']}",
        f"- Companies with three consecutive verified true-FCFE years: {summary['companies_with_3_consecutive_verified_fcfe_years']}",
        f"- Bank-sector companies routed to bank-specific valuation: {summary['bank_sector_valuation_exceptions']}",
        "",
        "## Decision status",
        "",
        "| Status | Companies |",
        "|---|---:|",
    ]
    for status, count in sorted(summary["status_counts"].items()):
        lines.append(f"| {status} | {count} |")
    lines += [
        "",
        "## Company-by-company results",
        "",
        "| Symbol | Sector | Annual years | True FCFE years | Consecutive FCFE | Valuation route |",
        "|---|---|---:|---:|---|---|",
    ]
    for row in company_rows:
        lines.append(
            f"| {row['symbol']} | {row['sector']} | {row['consolidated_annual_period_count']} "
            f"| {row['consolidated_true_fcfe_year_count']} | {row['three_consecutive_fcfe_status']} "
            f"| {row['valuation_route']} |"
        )
    lines += [
        "",
        "## Calculation and control rules",
        "",
        "- True FCFE is calculated as operating cash flow minus absolute capital expenditure plus net borrowing.",
        "- Net borrowing is current closing debt less prior-year closing debt.",
        "- Current debt must be present in the same XBRL filing reference as the annual cash flows.",
        "- Prior debt must come from a same-basis instant snapshot 330–400 days before the annual period end.",
        "- Missing values are not replaced with zero. CFO-minus-capex alone is a proxy, not verified FCFE.",
        "- Banks are routed to sector-specific valuation; this report does not force a corporate FCFE DCF onto them.",
        "- Three-year eligibility requires three consecutive annual periods, each with all required inputs.",
        "",
        "Detailed filing references, annual FCFE inputs and exact missing fields are in the two CSV files.",
        "",
    ]
    (output_dir / "financial_coverage.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit annual financial history and true-FCFE coverage.")
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--filing-coverage", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", default="unspecified")
    args = parser.parse_args()

    with args.observations.open(newline="", encoding="utf-8-sig") as handle:
        observations = list(csv.DictReader(handle))
    with args.filing_coverage.open(newline="", encoding="utf-8-sig") as handle:
        filing_coverage = list(csv.DictReader(handle))

    companies, annual, summary = build_fcfe_audit(observations, filing_coverage)
    write_report(companies, annual, summary, args.output_dir, args.run_id)
    print(json.dumps({"run_id": args.run_id, **summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
