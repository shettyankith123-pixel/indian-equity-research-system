from datetime import date, timedelta
from decimal import Decimal as D

from indian_equity_research.analytics.decision_engine import decide
from indian_equity_research.models.recommendations import ResearchInput


def item(**overrides):
    values = dict(
        symbol="TEST", sector="industrials", current_price=D("80"), fair_value_base=D("100"),
        fair_value_low=D("75"), fair_value_high=D("120"), quality_score=D("80"),
        growth_score=D("75"), balance_sheet_score=D("75"), governance_score=D("80"),
        data_completeness=D("0.98"), data_as_of=date(2026, 11, 13),
        valuation_confidence=D("0.90"), thesis_broken=False, major_risk_flag=False,
        held=False, notes="", source_name="Annual report", source_url="https://example.com/report",
    )
    values.update(overrides)
    return ResearchInput(**values)


def test_buy_when_quality_data_and_twenty_percent_margin_pass():
    result = decide(item(), today=date(2026, 11, 13))
    assert result.recommendation == "BUY"
    assert result.margin_of_safety_pct == "20.00"
    assert result.ideal_entry_max == "85.00"
    assert result.buy_entry_max == "85.00"
    assert result.accumulate_entry_max == "92.00"


def test_accumulate_at_ten_percent_margin():
    result = decide(item(current_price=D("90")), today=date(2026, 11, 13))
    assert result.recommendation == "ACCUMULATE"
    assert result.ideal_entry_max == "92.00"


def test_missing_data_becomes_assess_not_wait_or_buy():
    result = decide(item(fair_value_base=None), today=date(2026, 11, 13))
    assert result.recommendation == "ASSESS"
    assert "fair_value_base" in result.rationale


def test_stale_data_becomes_assess():
    result = decide(item(data_as_of=date(2026, 1, 1)), today=date(2026, 11, 13))
    assert result.recommendation == "ASSESS"
    assert result.data_status == "stale"


def test_material_risk_overrides_attractive_valuation():
    result = decide(item(major_risk_flag=True), today=date(2026, 11, 13))
    assert result.recommendation == "WAIT"


def test_broken_thesis_for_holding_is_exit():
    result = decide(item(thesis_broken=True, held=True), today=date(2026, 11, 13))
    assert result.recommendation == "EXIT"
