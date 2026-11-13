from datetime import date
from decimal import Decimal as D

from indian_equity_research.analytics.market_scan import build_market_scan
from indian_equity_research.ingestion.nse_bhavcopy import EodPrice
from indian_equity_research.storage.market_repository import MarketRepository


def test_market_scan_counts_breadth_and_ranks_movers(tmp_path):
    repo = MarketRepository(tmp_path / "market.db")
    repo.upsert_prices([
        EodPrice(date(2026, 11, 12), "AAA", "EQ", D("101"), D("102"), D("99"), D("101"), D("100"), 100, D("10100"), 10, "x.zip"),
        EodPrice(date(2026, 11, 12), "BBB", "EQ", D("98"), D("99"), D("97"), D("98"), D("100"), 100, D("9800"), 10, "x.zip"),
    ])
    result = build_market_scan(tmp_path / "market.db")
    assert result["advances"] == 1
    assert result["declines"] == 1
    assert result["top_gainers"][0]["symbol"] == "AAA"
