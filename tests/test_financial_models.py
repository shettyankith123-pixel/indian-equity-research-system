from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from indian_equity_research.models.financials import (
    FinancialObservation, FinancialPeriod, FinancialStatementSnapshot, SourceReference,
)


def sample_period() -> FinancialPeriod:
    return FinancialPeriod(date(2026, 7, 1), date(2026, 9, 30), "quarter", "standalone", Decimal("4"))


def sample_source() -> SourceReference:
    return SourceReference("Company Q2 results", "company_filing", date(2026, 10, 18),
        datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc), "https://example.com/results")


def test_snapshot_retrieves_metric_and_keeps_missing_as_none() -> None:
    observation = FinancialObservation("icicibank", "net_profit", Decimal("14843"),
        "crore", "INR", sample_period(), sample_source())
    snapshot = FinancialStatementSnapshot("ICICIBANK", sample_period(), (observation,))
    assert snapshot.get("net_profit") == observation
    assert snapshot.get("gross_npa") is None


def test_snapshot_rejects_duplicate_metrics() -> None:
    observation = FinancialObservation("ICICIBANK", "net_profit", Decimal("100"),
        "crore", "INR", sample_period(), sample_source())
    with pytest.raises(ValueError, match="duplicate metric"):
        FinancialStatementSnapshot("ICICIBANK", sample_period(), (observation, observation))


def test_source_timestamp_must_be_timezone_aware() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        SourceReference("Company filing", "company_filing", date(2026, 10, 18), datetime(2026, 11, 13, 10, 0))


def test_period_dates_must_be_valid() -> None:
    with pytest.raises(ValueError, match="start_date"):
        FinancialPeriod(date(2026, 10, 1), date(2026, 9, 30), "quarter", "standalone", Decimal("4"))
