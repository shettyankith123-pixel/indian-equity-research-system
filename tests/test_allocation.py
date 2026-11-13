import csv
from decimal import Decimal as D

from indian_equity_research.analytics.allocation import build_allocation_plan, load_capital_snapshot


def test_staged_buy_allocations_respect_cash_reserve_and_stock_cap(tmp_path):
    p = tmp_path / "capital.csv"
    with p.open("w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=["snapshot_date","cash_available","portfolio_market_value","symbol","sector","market_value"])
        w.writeheader()
        w.writerow({"snapshot_date":"2026-11-13","cash_available":"30000","portfolio_market_value":"100000","symbol":"AAA","sector":"Banks","market_value":"2000"})
    snapshot = load_capital_snapshot(p)
    decisions = [{"symbol":"BBB","sector":"IT","recommendation":"BUY","margin_of_safety_pct":"25","confidence":"High"}]
    plan, remaining = build_allocation_plan(decisions, snapshot)
    assert plan[0].first_tranche == D("4000")  # 40% of 10,000 single-name cap
    assert remaining == D("21000")  # 30,000 cash less 5,000 reserve less 4,000


def test_sector_cap_blocks_overconcentrated_first_tranche(tmp_path):
    p = tmp_path / "capital.csv"
    with p.open("w", newline="") as h:
        w = csv.DictWriter(h, fieldnames=["snapshot_date","cash_available","portfolio_market_value","symbol","sector","market_value"])
        w.writeheader()
        w.writerow({"snapshot_date":"2026-11-13","cash_available":"50000","portfolio_market_value":"100000","symbol":"AAA","sector":"Banks","market_value":"30000"})
    snapshot = load_capital_snapshot(p)
    plan, _ = build_allocation_plan([{"symbol":"BBB","sector":"Banks","recommendation":"BUY","margin_of_safety_pct":"30","confidence":"High"}], snapshot)
    assert plan[0].first_tranche == 0
