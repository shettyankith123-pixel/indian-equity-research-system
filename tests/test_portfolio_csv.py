import csv
from decimal import Decimal as D
from pathlib import Path

import pytest

from indian_equity_research.ingestion.portfolio_csv import calculate_positions, import_transactions


def write_csv(path: Path, rows):
    fields = ["transaction_id", "date", "symbol", "side", "quantity", "price", "fees", "broker", "notes"]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def test_average_cost_and_realised_pnl(tmp_path):
    source, db = tmp_path / "trades.csv", tmp_path / "portfolio.db"
    write_csv(source, [
        {"transaction_id":"1","date":"2026-01-01","symbol":"ABC","side":"BUY","quantity":"10","price":"100","fees":"10"},
        {"transaction_id":"2","date":"2026-02-01","symbol":"ABC","side":"BUY","quantity":"10","price":"120","fees":"10"},
        {"transaction_id":"3","date":"2026-03-01","symbol":"ABC","side":"SELL","quantity":"5","price":"130","fees":"5"},
    ])
    assert import_transactions(source, db) == 3
    positions = calculate_positions(db)
    assert positions[0].quantity == D("15")
    assert positions[0].average_cost == D("2220") / D("20")
    assert positions[0].realised_pnl == D("90")


def test_reject_sell_above_quantity(tmp_path):
    source, db = tmp_path / "trades.csv", tmp_path / "portfolio.db"
    write_csv(source, [{"transaction_id":"1","date":"2026-01-01","symbol":"ABC","side":"SELL","quantity":"1","price":"100","fees":"0"}])
    import_transactions(source, db)
    with pytest.raises(ValueError, match="exceeds"):
        calculate_positions(db)
