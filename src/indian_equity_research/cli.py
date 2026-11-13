"""CLI for financial ingestion, NSE EOD data, portfolio, event and wealth scans."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Sequence

from indian_equity_research.analytics.bank_snapshot import calculate_snapshot_bank_metrics
from indian_equity_research.analytics.allocation import build_allocation_plan, load_capital_snapshot, write_allocation_csv
from indian_equity_research.analytics.event_study import analyse_events
from indian_equity_research.analytics.market_scan import build_market_scan, write_market_scan
from indian_equity_research.analytics.wealth_scan import (
    build_company_decision, build_decisions, build_opportunity_list, build_sector_decisions, write_decision_register,
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

    sector = sub.add_parser("sector-scan", help="Compare all researched companies classified in one sector")
    sector.add_argument("--sector", required=True)
    sector.add_argument("--research-inputs", type=Path, default=Path("data/templates/research_inputs.csv"))

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


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
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
        print(json.dumps(build_company_decision(args.symbol, args.research_inputs), indent=2))
        return 0

    if args.command == "sector-scan":
        rows = build_sector_decisions(args.sector, args.research_inputs)
        print(json.dumps({"sector": args.sector, "companies_researched": len(rows), "decisions": rows}, indent=2))
        return 0

    if args.command == "market-scan":
        result = build_market_scan(args.db)
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
