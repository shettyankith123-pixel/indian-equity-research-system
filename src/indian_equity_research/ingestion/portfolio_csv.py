"""Import transaction ledgers and calculate average-cost holdings and realised P&L."""
from __future__ import annotations

import csv
import sqlite3
from datetime import date
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

REQUIRED = {"transaction_id", "date", "symbol", "side", "quantity", "price", "fees"}


@dataclass(frozen=True)
class PortfolioPosition:
    symbol: str
    quantity: Decimal
    average_cost: Decimal
    realised_pnl: Decimal


def import_transactions(csv_path: Path, db_path: Path) -> int:
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing = REQUIRED - headers
        if missing:
            raise ValueError(f"Portfolio CSV missing columns: {', '.join(sorted(missing))}")
        rows = []
        for line, row in enumerate(reader, start=2):
            try:
                date.fromisoformat(row["date"].strip())
                if not row["transaction_id"].strip() or not row["symbol"].strip():
                    raise ValueError("transaction_id and symbol are required")
                qty = Decimal(row["quantity"])
                price = Decimal(row["price"])
                fees = Decimal(row["fees"] or "0")
                side = row["side"].strip().upper()
                if qty <= 0 or price <= 0 or fees < 0 or side not in {"BUY", "SELL"}:
                    raise ValueError("quantity/price must be positive; side must be BUY or SELL")
                rows.append((row["transaction_id"].strip(), row["date"].strip(), row["symbol"].strip().upper(), side, str(qty), str(price), str(fees), row.get("broker", ""), row.get("notes", "")))
            except (InvalidOperation, ValueError, KeyError) as exc:
                raise ValueError(f"Invalid portfolio CSV row {line}: {exc}") from exc
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS portfolio_transactions (
            transaction_id TEXT PRIMARY KEY, trade_date TEXT NOT NULL, symbol TEXT NOT NULL,
            side TEXT NOT NULL CHECK(side IN ('BUY','SELL')), quantity TEXT NOT NULL,
            price TEXT NOT NULL, fees TEXT NOT NULL, broker TEXT, notes TEXT
        )""")
        # Validate the entire batch before inserting to avoid partial imports.
        existing = {r[0] for r in conn.execute("SELECT transaction_id FROM portfolio_transactions")}
        seen = set()
        for row in rows:
            if row[0] in existing or row[0] in seen:
                raise ValueError(f"Duplicate transaction_id: {row[0]}")
            seen.add(row[0])
        conn.executemany("INSERT INTO portfolio_transactions VALUES (?,?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def calculate_positions(db_path: Path) -> list[PortfolioPosition]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM portfolio_transactions ORDER BY trade_date, transaction_id").fetchall()
    state: dict[str, dict[str, Decimal]] = {}
    for row in rows:
        symbol = row["symbol"]
        qty, price, fees = Decimal(row["quantity"]), Decimal(row["price"]), Decimal(row["fees"])
        item = state.setdefault(symbol, {"qty": Decimal(0), "cost": Decimal(0), "realised": Decimal(0)})
        if row["side"] == "BUY":
            item["qty"] += qty
            item["cost"] += qty * price + fees
        else:
            if qty > item["qty"]:
                raise ValueError(f"SELL quantity exceeds imported BUY quantity for {symbol}")
            avg = item["cost"] / item["qty"] if item["qty"] else Decimal(0)
            item["realised"] += qty * (price - avg) - fees
            item["qty"] -= qty
            item["cost"] -= avg * qty
    return [
        PortfolioPosition(symbol, v["qty"], v["cost"] / v["qty"] if v["qty"] else Decimal(0), v["realised"])
        for symbol, v in sorted(state.items()) if v["qty"] > 0 or v["realised"] != 0
    ]
