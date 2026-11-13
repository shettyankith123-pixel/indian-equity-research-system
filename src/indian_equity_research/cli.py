"""Command-line entry points for importing and analysing financial statements."""

from __future__ import annotations

import argparse
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Sequence

from indian_equity_research.analytics.bank_snapshot import calculate_snapshot_bank_metrics
from indian_equity_research.ingestion.csv_loader import parse_financial_csv
from indian_equity_research.storage.repository import FinancialRepository


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ies", description="Indian Equity Research System")
    subparsers = parser.add_subparsers(dest="command", required=True)

    importer = subparsers.add_parser("import-financials", help="Validate and import long-form CSV data")
    importer.add_argument("csv_path", type=Path)
    importer.add_argument("--db", type=Path, default=Path("data/research.db"))

    ratios = subparsers.add_parser("bank-ratios", help="Calculate ratios for one stored bank statement")
    ratios.add_argument("--symbol", required=True)
    ratios.add_argument("--period-start", required=True, type=date.fromisoformat)
    ratios.add_argument("--period-end", required=True, type=date.fromisoformat)
    ratios.add_argument("--basis", choices=["standalone", "consolidated"], required=True)
    ratios.add_argument("--source-name", required=True)
    ratios.add_argument("--db", type=Path, default=Path("data/research.db"))

    status = subparsers.add_parser("db-status", help="Show stored observation count")
    status.add_argument("--db", type=Path, default=Path("data/research.db"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repository = FinancialRepository(args.db)

    if args.command == "import-financials":
        parsed = parse_financial_csv(args.csv_path)
        if parsed.errors:
            for error in parsed.errors:
                print(error)
            print("Import cancelled; no rows were written.")
            return 2
        if not parsed.observations:
            print("No observations found; nothing imported.")
            return 2
        try:
            count = repository.insert_many(parsed.observations)
        except ValueError as exc:
            print(str(exc))
            return 2
        print(f"Imported {count} financial observations into {args.db}.")
        return 0

    if args.command == "bank-ratios":
        snapshot = repository.get_snapshot(
            args.symbol, args.period_start, args.period_end, args.basis, args.source_name
        )
        if snapshot is None:
            print("No observations matched that symbol, period, basis and source.")
            return 2
        results = calculate_snapshot_bank_metrics(snapshot)
        output = {
            name: {
                "value": str(result.value) if result.value is not None else None,
                "percentage": (
                    str(result.value * Decimal("100"))
                    if result.value is not None else None
                ),
                "status": result.status,
                "formula": result.formula,
                "missing_inputs": list(result.missing_inputs),
            }
            for name, result in results.items()
        }
        print(json.dumps(output, indent=2))
        return 0

    if args.command == "db-status":
        print(f"Stored financial observations: {repository.count_observations()}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
