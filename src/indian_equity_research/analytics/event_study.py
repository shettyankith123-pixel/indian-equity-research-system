"""Simple event-study returns against subsequent NSE EOD sessions."""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path


def analyse_events(events_csv: Path, db_path: Path, output_csv: Path) -> int:
    with events_csv.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"event_id", "event_date", "symbol", "headline", "source_name", "source_url"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Events CSV missing columns: {', '.join(sorted(missing))}")
        events = list(reader)
    results = []
    with sqlite3.connect(db_path) as conn:
        for event in events:
            rows = conn.execute(
                "SELECT trading_date, close FROM market_prices WHERE symbol=? AND trading_date>=? ORDER BY trading_date",
                (event["symbol"].upper(), event["event_date"]),
            ).fetchall()
            if not rows:
                base = None
            else:
                base = float(rows[0][1])
            out = dict(event)
            out["event_session_close"] = base if base is not None else ""
            for horizon in (1, 3, 5):
                if base and len(rows) > horizon:
                    out[f"return_t{horizon}_pct"] = round((float(rows[horizon][1]) / base - 1) * 100, 3)
                else:
                    out[f"return_t{horizon}_pct"] = ""
            results.append(out)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = list(results[0].keys()) if results else ["event_id", "event_date", "symbol", "headline", "source_name", "source_url", "event_session_close", "return_t1_pct", "return_t3_pct", "return_t5_pct"]
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(results)
    return len(results)
