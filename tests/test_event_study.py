import csv
from pathlib import Path

from indian_equity_research.analytics.event_study import analyse_events
from indian_equity_research.storage.market_repository import MarketRepository
from indian_equity_research.ingestion.nse_bhavcopy import EodPrice
from datetime import date
from decimal import Decimal as D


def test_event_study_calculates_subsequent_session_returns(tmp_path):
    db = tmp_path / "market.db"
    repo = MarketRepository(db)
    prices = [EodPrice(date(2026, 11, d), "ABC", "EQ", D("100"), D("110"), D("95"), D(str(close)), None, 100, None, None, "fixture.csv") for d, close in [(2,100),(3,105),(4,102),(5,110),(6,115),(9,120)]]
    repo.upsert_prices(prices)
    events = tmp_path / "events.csv"
    with events.open("w", newline="") as h:
        w=csv.DictWriter(h, fieldnames=["event_id","event_date","symbol","headline","event_type","source_name","source_url","expected_direction","notes"])
        w.writeheader(); w.writerow({"event_id":"E1","event_date":"2026-11-02","symbol":"ABC","headline":"Results","source_name":"Company","source_url":"https://example.com"})
    out = tmp_path / "result.csv"
    assert analyse_events(events, db, out) == 1
    with out.open() as h:
        row = next(csv.DictReader(h))
    assert row["return_t1_pct"] == "5.0"
    assert row["return_t3_pct"] == "10.0"
