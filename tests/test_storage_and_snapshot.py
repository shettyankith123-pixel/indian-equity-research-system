from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from indian_equity_research.analytics.bank_snapshot import calculate_snapshot_bank_metrics
from indian_equity_research.models.financials import (
    FinancialObservation, FinancialPeriod, SourceReference,
)
from indian_equity_research.storage.repository import FinancialRepository


def test_repository_round_trip_and_bank_snapshot(tmp_path: Path) -> None:
    db = FinancialRepository(tmp_path / "research.sqlite")
    period = FinancialPeriod(date(2026, 7, 1), date(2026, 9, 30), "quarter",
        "standalone", Decimal("4"))
    source = SourceReference("ICICI Q2 results", "company_filing", date(2026, 10, 18),
        datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc), "https://example.com/q2", "Q2FY27")
    observations = [
        FinancialObservation("ICICIBANK", "net_interest_income", Decimal("100"), "crore", "INR", period, source),
        FinancialObservation("ICICIBANK", "average_interest_earning_assets", Decimal("10000"), "crore", "INR", period, source),
        FinancialObservation("ICICIBANK", "net_profit", Decimal("50"), "crore", "INR", period, source),
        FinancialObservation("ICICIBANK", "average_total_assets", Decimal("10000"), "crore", "INR", period, source),
    ]
    assert db.insert_many(observations) == 4
    assert db.count_observations() == 4

    snapshot = db.get_snapshot("ICICIBANK", period.start_date, period.end_date,
        "standalone", "ICICI Q2 results")
    assert snapshot is not None
    metrics = calculate_snapshot_bank_metrics(snapshot)
    assert metrics["nim"].value == Decimal("0.04")
    assert metrics["roa"].value == Decimal("0.02")
    assert metrics["roe"].status == "missing_input"
    assert "average_equity" in metrics["roe"].missing_inputs


def test_batch_insert_rolls_back_on_duplicate(tmp_path: Path) -> None:
    db = FinancialRepository(tmp_path / "research.sqlite")
    period = FinancialPeriod(date(2026, 7, 1), date(2026, 9, 30), "quarter",
        "standalone", Decimal("4"))
    source = SourceReference("ICICI Q2 results", "company_filing", date(2026, 10, 18),
        datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc))
    item = FinancialObservation("ICICIBANK", "net_profit", Decimal("50"), "crore",
        "INR", period, source)
    db.insert_many([item])
    try:
        db.insert_many([
            FinancialObservation("ICICIBANK", "net_interest_income", Decimal("100"),
                "crore", "INR", period, source),
            item,
        ])
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate insert should fail")
    assert db.count_observations() == 1
