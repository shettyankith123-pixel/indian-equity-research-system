"""SQLite storage for NSE EOD prices, decision snapshots and research events."""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Iterable

from indian_equity_research.ingestion.nse_bhavcopy import EodPrice


class MarketRepository:
    def __init__(self, db_path: Path | str):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS market_prices (
                trading_date TEXT NOT NULL, symbol TEXT NOT NULL, series TEXT NOT NULL,
                open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL, close REAL NOT NULL,
                previous_close REAL, volume INTEGER NOT NULL, turnover REAL, trades INTEGER,
                source_file TEXT NOT NULL, ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (trading_date, symbol, series)
            );
            CREATE INDEX IF NOT EXISTS idx_market_symbol_date ON market_prices(symbol, trading_date);
            CREATE TABLE IF NOT EXISTS decision_snapshots (
                run_date TEXT NOT NULL, symbol TEXT NOT NULL, recommendation TEXT NOT NULL,
                current_price TEXT, fair_value_base TEXT, upside_to_base_pct TEXT,
                confidence TEXT, data_status TEXT, payload_json TEXT NOT NULL,
                PRIMARY KEY (run_date, symbol)
            );
            CREATE TABLE IF NOT EXISTS research_events (
                event_id TEXT PRIMARY KEY, event_date TEXT NOT NULL, symbol TEXT NOT NULL,
                headline TEXT NOT NULL, event_type TEXT, source_name TEXT, source_url TEXT,
                expected_direction TEXT, notes TEXT
            );
            """)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def upsert_prices(self, rows: Iterable[EodPrice]) -> int:
        items = list(rows)
        if not items:
            return 0
        with self._connect() as conn:
            conn.executemany("""
                INSERT INTO market_prices (
                    trading_date,symbol,series,open,high,low,close,previous_close,
                    volume,turnover,trades,source_file
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(trading_date,symbol,series) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low,
                    close=excluded.close, previous_close=excluded.previous_close,
                    volume=excluded.volume, turnover=excluded.turnover,
                    trades=excluded.trades, source_file=excluded.source_file,
                    ingested_at=CURRENT_TIMESTAMP
            """, [(
                r.trading_date.isoformat(), r.symbol, r.series, float(r.open), float(r.high),
                float(r.low), float(r.close), float(r.previous_close) if r.previous_close is not None else None,
                r.volume, float(r.turnover) if r.turnover is not None else None, r.trades, r.source_file,
            ) for r in items])
        return len(items)

    def price_count(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM market_prices").fetchone()[0])

    def prices_for(self, symbol: str) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM market_prices WHERE symbol=? ORDER BY trading_date",
                (symbol.upper(),),
            ).fetchall()

    def save_decisions(self, run_date: date, decisions: list[dict[str, object]]) -> int:
        import json
        with self._connect() as conn:
            conn.executemany("""
                INSERT INTO decision_snapshots (
                    run_date,symbol,recommendation,current_price,fair_value_base,
                    upside_to_base_pct,confidence,data_status,payload_json
                ) VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(run_date,symbol) DO UPDATE SET
                    recommendation=excluded.recommendation, current_price=excluded.current_price,
                    fair_value_base=excluded.fair_value_base,upside_to_base_pct=excluded.upside_to_base_pct,
                    confidence=excluded.confidence,data_status=excluded.data_status,payload_json=excluded.payload_json
            """, [(
                run_date.isoformat(), str(d["symbol"]), str(d["recommendation"]),
                d.get("current_price"), d.get("fair_value_base"), d.get("upside_to_base_pct"),
                d.get("confidence"), d.get("data_status"), json.dumps(d, ensure_ascii=False),
            ) for d in decisions])
        return len(decisions)

    def latest_decisions(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute("""
                SELECT * FROM decision_snapshots
                WHERE run_date=(SELECT MAX(run_date) FROM decision_snapshots)
                ORDER BY symbol
            """).fetchall()
