"""CLI for financial ingestion, NSE EOD data, portfolio, event and wealth scans."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path
from typing import Sequence

from indian_equity_research.analytics.bank_snapshot import calculate_snapshot_bank_metrics
from indian_equity_research.analytics.allocation import build_allocation_plan, load_capital_snapshot, write_allocation_csv
from indian_equity_research.analytics.event_study import analyse_events
from indian_equity_research.analytics.market_scan import build_market_scan, write_market_scan
from indian_equity_research.analytics.wealth_scan import (
    build_company_decision, build_decisions, build_opportunity_list, build_sector_decisions,
    resolve_company_symbol, resolve_sector_name, write_decision_register,
)
from indian_equity_research.ingestion.csv_loader import parse_financial_csv
from indian_equity_research.ingestion.nse_bhavcopy import download_udiff_bhavcopy, parse_udiff_zip, write_eod_csv
from indian_equity_research.ingestion.portfolio_csv import calculate_positions, import_transactions
from indian_equity_research.storage.market_repository import MarketRepository
from indian_equity_research.storage.repository import FinancialRepository


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ies", description="Indian Equity Research System")
    sub = parser.add_subparsers(dest="command", required=True)

    importer = sub.add_parser("import-financials", help="Validate and import long-form financial observations CSV")
    importer.add_argument("csv_path", type=Path)
    importer.add_argument("--db", type=Path, default=Path("data/research.db"))

    ratios = sub.add_parser("bank-ratios", help="Calculate ratios from one named bank statement source")
    ratios.add_argument("--symbol", required=True)
    ratios.add_argument("--period-start", required=True, type=date.fromisoformat)
    ratios.add_argument("--period-end", required=True, type=date.fromisoformat)
    ratios.add_argument("--basis", choices=["standalone", "consolidated"], required=True)
    ratios.add_argument("--source-name", required=True)
    ratios.add_argument("--db", type=Path, default=Path("data/research.db"))

    status = sub.add_parser("db-status", help="Show stored financial observation count")
    status.add_argument("--db", type=Path, default=Path("data/research.db"))

    nse = sub.add_parser("fetch-nse-eod", help="Download, validate and store official NSE UDiFF EOD bhavcopy")
    nse.add_argument("--date", dest="trading_date", type=date.fromisoformat, default=date.today())
    nse.add_argument("--db", type=Path, default=Path("data/research.db"))
    nse.add_argument("--output", type=Path, default=None)

    p_import = sub.add_parser("import-portfolio", help="Import broker transaction CSV")
    p_import.add_argument("csv_path", type=Path)
    p_import.add_argument("--db", type=Path, default=Path("data/research.db"))

    p_status = sub.add_parser("portfolio-status", help="Show average-cost positions and realised P&L")
    p_status.add_argument("--db", type=Path, default=Path("data/research.db"))

    decisions = sub.add_parser("wealth-scan", help="Generate a complete decision register from reviewed research inputs")
    decisions.add_argument("--watchlist", type=Path, default=Path("config/watchlists/indian_watchlist.yaml"))
    decisions.add_argument("--research-inputs", type=Path, default=Path("data/templates/research_inputs.csv"))
    decisions.add_argument("--output-dir", type=Path, default=Path("reports/wealth-scan"))
    decisions.add_argument("--db", type=Path, default=Path("data/research.db"))
    decisions.add_argument("--capital-snapshot", type=Path, default=None)
    decisions.add_argument("--allocation-output", type=Path, default=Path("reports/wealth-scan/allocation_plan.csv"))

    company = sub.add_parser("company-scan", help="Show one company's latest imported evidence and decision")
    company.add_argument("symbol")
    company.add_argument("--research-inputs", type=Path, default=Path("data/templates/research_inputs.csv"))
    company.add_argument("--universe", type=Path, default=Path("data/universe/indian_watchlist_companies.csv"))

    sector = sub.add_parser("sector-scan", help="Compare all companies in one sector, including missing-data assessments")
    sector.add_argument("--sector", required=True)
    sector.add_argument("--research-inputs", type=Path, default=Path("data/templates/research_inputs.csv"))
    sector.add_argument("--universe", type=Path, default=Path("data/universe/indian_watchlist_companies.csv"))

    portfolio_review = sub.add_parser("portfolio-review", help="Review the latest saved broker holdings snapshot")
    portfolio_review.add_argument("--snapshot", type=Path, default=Path("data/imports/indmoney_holdings_snapshot_2026-11-13.csv"))
    portfolio_review.add_argument("--db", type=Path, default=Path("data/research.db"))

    market_brief = sub.add_parser("market-brief", help="Summarise NSE EOD breadth; the ChatGPT Market Brief adds live news research")
    market_brief.add_argument("--db", type=Path, default=Path("data/research.db"))
    market_brief.add_argument("--output", type=Path, default=Path("reports/market_scan.json"))

    opportunities = sub.add_parser("opportunity-scan", help="Rank actionable BUY/ACCUMULATE ideas outside the existing 64-stock watchlist")
    opportunities.add_argument("--watchlist", type=Path, default=Path("config/watchlists/indian_watchlist.yaml"))
    opportunities.add_argument("--research-inputs", type=Path, default=Path("data/templates/research_inputs.csv"))
    opportunities.add_argument("--output", type=Path, default=Path("reports/opportunities.csv"))

    market = sub.add_parser("market-scan", help="Summarise latest NSE EOD equity breadth, top gainers and laggards")
    market.add_argument("--db", type=Path, default=Path("data/research.db"))
    market.add_argument("--output", type=Path, default=Path("reports/market_scan.json"))

    events = sub.add_parser("event-study", help="Measure T+1/T+3/T+5 price moves after imported news events")
    events.add_argument("--events", type=Path, default=Path("data/templates/news_events.csv"))
    events.add_argument("--db", type=Path, default=Path("data/research.db"))
    events.add_argument("--output", type=Path, default=Path("reports/event_study.csv"))

    return parser


def _route_friendly_command(argv: Sequence[str]) -> list[str]:
    """Translate short natural-language command phrases into existing CLI subcommands."""
    tokens = list(argv)
    if len(tokens) < 2:
        return tokens
    first, second = tokens[0].upper(), tokens[1].upper()
    rest = tokens[2:]
    if (first, second) == ("WEALTH", "SCAN"):
        return ["wealth-scan", *rest]
    if (first, second) == ("MARKET", "SCAN"):
        return ["market-scan", *rest]
    if (first, second) == ("MARKET", "BRIEF"):
        return ["market-brief", *rest]
    if (first, second) == ("PORTFOLIO", "REVIEW"):
        return ["portfolio-review", *rest]
    if (first, second) in {("FIND", "OPPORTUNITIES"), ("OPPORTUNITY", "SCAN")}:
        return ["opportunity-scan", *rest]
    if (first, second) == ("COMPANY", "SCAN"):
        name_parts: list[str] = []
        options: list[str] = []
        found_option = False
        for token in rest:
            if token.startswith("--"):
                found_option = True
            (options if found_option else name_parts).append(token)
        if not name_parts:
            raise ValueError("Use COMPANY SCAN followed by a company name or NSE symbol, e.g. COMPANY SCAN ICICI BANK.")
        return ["company-scan", " ".join(name_parts), *options]
    if (first, second) == ("SECTOR", "SCAN"):
        sector_parts: list[str] = []
        options: list[str] = []
        found_option = False
        for token in rest:
            if token.startswith("--"):
                found_option = True
            (options if found_option else sector_parts).append(token)
        if not sector_parts:
            raise ValueError("Use SECTOR SCAN followed by a sector, e.g. SECTOR SCAN BANKING.")
        return ["sector-scan", "--sector", " ".join(sector_parts), *options]
    return tokens


def _portfolio_snapshot_report(snapshot_path: Path, db_path: Path) -> dict[str, object]:
    """Summarise dated INDmoney positions; never infer historical transactions."""
    if snapshot_path.exists():
        with snapshot_path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            raise ValueError(f"Holdings snapshot is empty: {snapshot_path}")
        as_of = rows[0].get("as_of_date", "")
        total_invested = sum(float(row.get("invested_value_inr") or 0) for row in rows)
        total_market = sum(float(row.get("market_value_inr") or 0) for row in rows)
        total_pnl = sum(float(row.get("unrealized_pnl_inr") or 0) for row in rows)
        age_days = (date.today() - date.fromisoformat(as_of)).days if as_of else None
        return {
            "status": "snapshot_only",
            "as_of_date": as_of or None,
            "snapshot_age_days": age_days,
            "stale_warning": bool(age_days is not None and age_days > 30),
            "positions": rows,
            "position_count": len(rows),
            "invested_value_inr": round(total_invested, 2),
            "market_value_inr": round(total_market, 2),
            "unrealised_pnl_inr": round(total_pnl, 2),
            "transaction_history_available": False,
            "limitations": [
                "This is a holdings snapshot, not a transaction-by-transaction ledger.",
                "Buy/sell dates, charges, taxes and historical cash movements are not inferred.",
            ],
        }
    positions = calculate_positions(db_path)
    return {
        "status": "transaction_ledger",
        "positions": [
            {
                "symbol": p.symbol,
                "quantity": str(p.quantity),
                "average_cost": str(p.average_cost),
                "realised_pnl": str(p.realised_pnl),
            }
            for p in positions
        ],
        "position_count": len(positions),
        "transaction_history_available": True,
        "limitations": [],
    }


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    try:
        routed_argv = _route_friendly_command(raw_argv)
    except ValueError as exc:
        print(str(exc)); return 2
    args = _parser().parse_args(routed_argv)
    if args.command in {"import-financials", "bank-ratios", "db-status"}:
        repository = FinancialRepository(args.db)
        if args.command == "import-financials":
            parsed = parse_financial_csv(args.csv_path)
            if parsed.errors or not parsed.observations:
                for error in parsed.errors:
                    print(error)
                print("Import cancelled; no rows were written.")
                return 2
            try:
                count = repository.insert_many(parsed.observations)
            except ValueError as exc:
                print(str(exc)); return 2
            print(f"Imported {count} financial observations into {args.db}.")
            return 0
        if args.command == "bank-ratios":
            snapshot = repository.get_snapshot(args.symbol, args.period_start, args.period_end, args.basis, args.source_name)
            if snapshot is None:
                print("No observations matched symbol, period, basis and source."); return 2
            result = calculate_snapshot_bank_metrics(snapshot)
            print(json.dumps({name: {"value": str(item.value) if item.value is not None else None, "status": item.status, "formula": item.formula, "missing_inputs": list(item.missing_inputs)} for name, item in result.items()}, indent=2))
            return 0
        print(f"Stored financial observations: {repository.count_observations()}")
        return 0

    if args.command == "fetch-nse-eod":
        payload, url = download_udiff_bhavcopy(args.trading_date)
        rows = parse_udiff_zip(payload, expected_date=args.trading_date)
        repo = MarketRepository(args.db)
        count = repo.upsert_prices(rows)
        output = args.output or Path("data/market") / f"nse_eod_{args.trading_date.isoformat()}.csv"
        write_eod_csv(rows, output)
        print(json.dumps({"trading_date": args.trading_date.isoformat(), "records": count, "source_url": url, "output": str(output), "database_price_rows": repo.price_count()}, indent=2))
        return 0

    if args.command == "import-portfolio":
        count = import_transactions(args.csv_path, args.db)
        print(f"Imported {count} portfolio transactions into {args.db}.")
        return 0

    if args.command == "portfolio-status":
        positions = calculate_positions(args.db)
        print(json.dumps([{"symbol": p.symbol, "quantity": str(p.quantity), "average_cost": str(p.average_cost), "realised_pnl": str(p.realised_pnl)} for p in positions], indent=2))
        return 0

    if args.command == "wealth-scan":
        rows = build_decisions(args.watchlist, args.research_inputs)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = args.output_dir / "decision_register.csv"
        md_path = args.output_dir / "wealth_scan.md"
        write_decision_register(rows, csv_path, md_path)
        MarketRepository(args.db).save_decisions(date.today(), rows)
        allocation_summary = None
        if args.capital_snapshot is not None:
            snapshot = load_capital_snapshot(args.capital_snapshot)
            plan, cash_left = build_allocation_plan(rows, snapshot)
            write_allocation_csv(plan, args.allocation_output)
            allocation_summary = {"lines": len(plan), "remaining_deployable_cash": str(cash_left), "output": str(args.allocation_output)}
        counts: dict[str, int] = {}
        for row in rows:
            rec = str(row["recommendation"]); counts[rec] = counts.get(rec, 0) + 1
        print(json.dumps({"stocks_covered": len(rows), "recommendation_counts": counts, "csv": str(csv_path), "report": str(md_path), "allocation": allocation_summary}, indent=2))
        return 0

    if args.command == "company-scan":
        symbol = resolve_company_symbol(args.symbol, args.universe)
        print(json.dumps(build_company_decision(symbol, args.research_inputs, universe_path=args.universe), indent=2))
        return 0

    if args.command == "sector-scan":
        sector_name = resolve_sector_name(args.sector, args.universe)
        rows = build_sector_decisions(sector_name, args.research_inputs, universe_path=args.universe)
        print(json.dumps({"sector": args.sector, "companies_researched": len(rows), "decisions": rows}, indent=2))
        return 0

    if args.command == "portfolio-review":
        result = _portfolio_snapshot_report(args.snapshot, args.db)
        print(json.dumps(result, indent=2))
        return 0

    if args.command in {"market-scan", "market-brief"}:
        result = build_market_scan(args.db)
        if args.command == "market-brief":
            result["chat_market_brief_note"] = (
                "This local command reports NSE EOD breadth only. For headline explanations, "
                "global macro context and next-session catalyst analysis, the ChatGPT MARKET BRIEF "
                "command performs a separate live-research step."
            )
        write_market_scan(result, args.output)
        print(json.dumps(result, indent=2))
        return 0 if result.get("status") == "ok" else 2

    if args.command == "opportunity-scan":
        rows = build_opportunity_list(args.watchlist, args.research_inputs)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        fields = list(rows[0].keys()) if rows else ["symbol", "sector", "recommendation", "rationale", "current_price", "fair_value_base", "margin_of_safety_pct", "confidence"]
        import csv
        with args.output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
        print(json.dumps({"actionable_outside_watchlist": len(rows), "output": str(args.output), "decisions": [r["symbol"] + ":" + str(r["recommendation"]) for r in rows]}, indent=2))
        return 0

    if args.command == "event-study":
        count = analyse_events(args.events, args.db, args.output)
        print(f"Analysed {count} events; output written to {args.output}.")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
