"""Compute an auditable EOD breadth and leaders/laggards snapshot from stored NSE prices."""
from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any


def build_market_scan(db_path: Path, *, top_n: int = 10) -> dict[str, Any]:
    with sqlite3.connect(db_path) as conn:
        latest = conn.execute("SELECT MAX(trading_date) FROM market_prices").fetchone()[0]
        if not latest:
            return {"status": "no_data", "message": "No NSE EOD prices have been imported yet."}
        rows = conn.execute("""
            SELECT symbol, series, close, previous_close, volume, turnover
            FROM market_prices
            WHERE trading_date=? AND series='EQ'
            ORDER BY symbol
        """, (latest,)).fetchall()
    analysed = []
    advances = declines = unchanged = unavailable = 0
    total_turnover = Decimal("0")
    turnover_count = 0
    for symbol, series, close, previous, volume, turnover in rows:
        pct = None
        if previous is not None and float(previous) > 0:
            pct = (float(close) / float(previous) - 1) * 100
            if pct > 0.000001:
                advances += 1
            elif pct < -0.000001:
                declines += 1
            else:
                unchanged += 1
        else:
            unavailable += 1
        if turnover is not None:
            total_turnover += Decimal(str(turnover))
            turnover_count += 1
        analysed.append({"symbol": symbol, "close": float(close), "previous_close": float(previous) if previous is not None else None, "change_pct": round(pct, 3) if pct is not None else None, "volume": int(volume)})
    comparable = [r for r in analysed if r["change_pct"] is not None]
    gainers = sorted(comparable, key=lambda r: r["change_pct"], reverse=True)[:top_n]
    losers = sorted(comparable, key=lambda r: r["change_pct"])[:top_n]
    return {
        "status": "ok", "trading_date": latest, "series_scope": "EQ only",
        "stocks_with_data": len(analysed), "advances": advances, "declines": declines,
        "unchanged": unchanged, "previous_close_unavailable": unavailable,
        "advance_decline_ratio": round(advances / declines, 3) if declines else None,
        "turnover_total": str(total_turnover) if turnover_count else None,
        "turnover_records": turnover_count,
        "top_gainers": gainers, "top_losers": losers,
        "limitations": ["Equity-series breadth only; index and F&O data are not included.", "This is official EOD data, not a live intraday quote.", "Gainers/losers are not adjusted for corporate actions."],
    }


def write_market_scan(result: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
