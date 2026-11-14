from datetime import date, datetime, timezone
from decimal import Decimal
from indian_equity_research.models.financials import (
    FinancialObservation, FinancialPeriod, SourceReference,
)
from importlib.util import spec_from_file_location
from pathlib import Path
import sys

script = Path(__file__).resolve().parents[1] / "scripts" / "ingest_nse_integrated_filings.py"
spec = spec_from_file_location("ies_ingestion_script", script)
module = __import__("importlib.util").util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
reconcile_duplicate_observations = module.reconcile_duplicate_observations


def observation(value, *, kind="quarter", metric="revenue", start="2026-07-01", end="2026-09-30"):
    period = FinancialPeriod(
        date.fromisoformat(start), date.fromisoformat(end), kind, "consolidated", Decimal("4")
    )
    source = SourceReference(
        "NSE", "exchange_filing", date(2026, 11, 14),
        datetime(2026, 11, 14, tzinfo=timezone.utc),
        "https://example.com/filing.xml", "seq-1:unknown:consolidated:abc123",
    )
    return FinancialObservation(
        "TEST", metric, Decimal(str(value)), "INR crore", "INR", period, source
    )


def test_identical_facts_are_deduplicated():
    first = observation("100")
    unique, duplicate_count, conflicts = reconcile_duplicate_observations([first, first])
    assert unique == [first]
    assert duplicate_count == 1
    assert conflicts == []


def test_period_kind_collision_prefers_the_label_implied_by_exact_span():
    quarter = observation("100", kind="half_year")
    duplicate = observation("100", kind="quarter")
    unique, duplicate_count, conflicts = reconcile_duplicate_observations([quarter, duplicate])
    assert len(unique) == 1
    assert unique[0].period.kind == "quarter"
    assert duplicate_count == 1
    assert conflicts == []


def test_conflicting_source_values_are_quarantined_and_reported():
    first = observation("100")
    second = observation("101")
    unique, duplicate_count, conflicts = reconcile_duplicate_observations([first, second])
    assert unique == []
    assert duplicate_count == 0
    assert len(conflicts) == 1
    assert conflicts[0]["symbol"] == "TEST"
    assert conflicts[0]["metric"] == "revenue"
    assert {x["value"] for x in conflicts[0]["values"]} == {"100", "101"}


def test_conflicting_fact_does_not_remove_other_metrics():
    revenue = observation("100")
    duplicate_revenue = observation("102")
    assets = observation("500", metric="total_assets", kind="instant", start="2026-09-30", end="2026-09-30")
    unique, _, conflicts = reconcile_duplicate_observations([revenue, duplicate_revenue, assets])
    assert [x.metric for x in unique] == ["total_assets"]
    assert len(conflicts) == 1
