"""Find the latest available official NSE CM UDiFF EOD file and store it."""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from indian_equity_research.ingestion.nse_bhavcopy import (
    download_udiff_bhavcopy,
    parse_udiff_zip,
    write_eod_csv,
)
from indian_equity_research.storage.market_repository import MarketRepository


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=date.fromisoformat, default=None)
    parser.add_argument("--lookback-days", type=int, default=5)
    parser.add_argument("--db", type=Path, default=Path("data/research.db"))
    args = parser.parse_args()

    anchor = args.date or datetime.now(ZoneInfo('Asia/Kolkata')).date()
    errors: list[dict[str, str]] = []
    for offset in range(0, max(1, args.lookback_days) + 1):
        trading_date = anchor - timedelta(days=offset)
        try:
            payload, url = download_udiff_bhavcopy(trading_date)
            rows = parse_udiff_zip(payload, expected_date=trading_date)
            if not rows:
                raise RuntimeError("NSE archive parsed but contained no equity rows")
            repo = MarketRepository(args.db)
            count = repo.upsert_prices(rows)
            output = Path("data/market") / f"nse_eod_{trading_date.isoformat()}.csv"
            write_eod_csv(rows, output)
            print(json.dumps({
                "status": "ok",
                "trading_date": trading_date.isoformat(),
                "records": count,
                "source_url": url,
                "csv": str(output),
                "database_price_rows": repo.price_count(),
                "previous_attempts": errors,
            }, indent=2))
            return 0
        except Exception as exc:
            errors.append({
                "date": trading_date.isoformat(),
                "error": f"{type(exc).__name__}: {exc}",
            })

    print(json.dumps({
        "status": "no_recent_archive",
        "anchor_date": anchor.isoformat(),
        "lookback_days": args.lookback_days,
        "attempts": errors,
    }, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
