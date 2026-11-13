from datetime import date
from decimal import Decimal
from pathlib import Path

from indian_equity_research.ingestion.csv_loader import PERIOD_KINDS, parse_financial_csv
from indian_equity_research.storage.repository import FinancialRepository


CSV_PATH = Path(__file__).parents[1] / "data/imports/mcx_bse_q2_fy27_observations.csv"
SOURCE_URL = "https://www.bseindia.com/xml-data/corpfiling/AttachLive/006dffdb-6de0-4661-a8d8-087d4f737434.pdf"


def test_mcx_bse_results_parse_and_preserve_source_provenance():
    assert 'transition_period' in PERIOD_KINDS
    parsed = parse_financial_csv(CSV_PATH)
    assert parsed.errors == ()
    assert len(parsed.observations) == 24
    assert {item.source.url for item in parsed.observations} == {SOURCE_URL}
    assert {item.source.reference_id for item in parsed.observations} == {
        "BSE:534091:2026-11-03:Q2FY27:006dffdb"
    }
    assert {item.period.basis for item in parsed.observations} == {"consolidated"}
    assert {item.period.kind for item in parsed.observations} == {
        "quarter", "half_year", "year"
    }


def test_mcx_q2_and_h1_values_are_loaded_into_sqlite_without_period_mixing(tmp_path):
    parsed = parse_financial_csv(CSV_PATH)
    repository = FinancialRepository(tmp_path / "mcx.sqlite")
    assert repository.insert_many(parsed.observations) == 24
    q2 = repository.get_snapshot(
        "MCX", date(2026, 7, 1), date(2026, 9, 30), "consolidated",
        "BSE India — Multi Commodity Exchange of India Limited"
    )
    h1 = repository.get_snapshot(
        "MCX", date(2026, 4, 1), date(2026, 9, 30), "consolidated",
        "BSE India — Multi Commodity Exchange of India Limited"
    )
    assert q2 is not None and h1 is not None
    assert q2.get("revenue_from_operations").value == Decimal("799.66")
    assert q2.get("profit_after_tax").value == Decimal("454.57")
    assert q2.get("earnings_per_share_basic").value == Decimal("17.83")
    assert h1.get("revenue_from_operations").value == Decimal("1501.66")
    assert h1.get("profit_after_tax").value == Decimal("868.01")
    assert all(item.source.url == SOURCE_URL for item in q2.observations)
