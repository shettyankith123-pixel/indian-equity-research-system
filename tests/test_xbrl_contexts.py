from datetime import date

import pytest

from indian_equity_research.ingestion.xbrl_contexts import choose_duration_context, parse_iso_or_nse


def test_parse_nse_date_and_iso_date():
    assert parse_iso_or_nse("30-SEP-2026") == date(2026, 9, 30)
    assert parse_iso_or_nse("2026-09-30") == date(2026, 9, 30)


def test_quarter_context_selected_by_period_dates_not_id():
    contexts = {
        "OneD": {"start": "2026-07-01", "end": "2026-09-30"},
        "OneI": {"end": "2026-09-30"},
        "FourD": {"start": "2026-04-01", "end": "2026-09-30"},
    }
    context_id, start, end = choose_duration_context(contexts, date(2026, 9, 30), "quarter")
    assert context_id == "OneD"
    assert start == date(2026, 7, 1)
    assert end == date(2026, 9, 30)


def test_annual_context_can_use_nonstandard_context_name():
    contexts = {
        "OneD": {"start": "2025-04-01", "end": "2026-03-31"},
        "StatementDynamic1D1": {"start": "2026-01-01", "end": "2026-03-31"},
        "OneI": {"end": "2026-03-31"},
    }
    context_id, start, end = choose_duration_context(contexts, date(2026, 3, 31), "year")
    assert context_id == "OneD"
    assert start == date(2025, 4, 1)
    assert end == date(2026, 3, 31)


def test_half_year_cannot_be_mislabelled_as_quarter_or_annual():
    contexts = {"OneD": {"start": "2026-04-01", "end": "2026-09-30"}}
    with pytest.raises(ValueError, match="no quarter duration context"):
        choose_duration_context(contexts, date(2026, 9, 30), "quarter")
    with pytest.raises(ValueError, match="no year duration context"):
        choose_duration_context(contexts, date(2026, 9, 30), "year")


def test_transition_period_is_not_called_annual():
    contexts = {"OneD": {"start": "2024-10-01", "end": "2025-03-31"}}
    with pytest.raises(ValueError, match="no year duration context"):
        choose_duration_context(contexts, date(2025, 3, 31), "year")


def test_half_year_is_selected_and_retained_as_half_year():
    contexts = {
        "OneD": {"start": "2026-04-01", "end": "2026-09-30"},
        "OneI": {"end": "2026-09-30"},
    }
    context_id, start, end = choose_duration_context(contexts, date(2026, 9, 30), "half_year")
    assert context_id == "OneD"
    assert start == date(2026, 4, 1)
    assert end == date(2026, 9, 30)


def test_duration_context_prefers_context_with_relevant_facts():
    contexts = {
        "OneD": {"start": "2026-07-01", "end": "2026-09-30"},
        "OneReportable1D": {"start": "2026-07-01", "end": "2026-09-30"},
    }
    facts = {"RevenueFromOperations": {"OneReportable1D": "1234"}}
    context_id, _, _ = choose_duration_context(
        contexts, date(2026, 9, 30), "quarter", facts, ("RevenueFromOperations",)
    )
    assert context_id == "OneReportable1D"


def test_eighteen_month_transition_period_is_selected_only_as_transition():
    contexts = {
        "EighteenMonthContext": {"start": "2024-10-01", "end": "2026-03-31"},
        "QuarterContext": {"start": "2026-01-01", "end": "2026-03-31"},
    }
    with pytest.raises(ValueError, match="no year duration context"):
        choose_duration_context(contexts, date(2026, 3, 31), "year")
    context_id, start, end = choose_duration_context(
        contexts, date(2026, 3, 31), "transition_period"
    )
    assert context_id == "EighteenMonthContext"
    assert start == date(2024, 10, 1)
    assert end == date(2026, 3, 31)



def test_special_transition_period_is_resolved_from_issuer_metadata():
    from indian_equity_research.ingestion.xbrl_contexts import period_kind_for_target

    assert period_kind_for_target(
        date(2026, 3, 31),
        "year",
        "2024-10-01",
        "2026-03-31",
    ) == "transition_period"
    assert period_kind_for_target(
        date(2027, 3, 31),
        "year",
        "2024-10-01",
        "2026-03-31",
    ) == "year"
    assert period_kind_for_target(
        date(2026, 3, 31),
        "quarter",
        "2024-10-01",
        "2026-03-31",
    ) == "quarter"


def test_instant_context_selects_exact_date_populated_facts():
    from indian_equity_research.ingestion.xbrl_contexts import choose_instant_context
    contexts = {
        "empty": {"type": "instant", "instant": date(2026, 9, 30)},
        "balance": {"type": "instant", "instant": date(2026, 9, 30)},
        "prior": {"type": "instant", "instant": date(2026, 3, 31)},
        "duration": {"type": "duration", "start": date(2026, 7, 1), "end": date(2026, 9, 30)},
    }
    facts = {"Assets": {"balance": "1000"}, "Equity": {"balance": "600"}}
    context_id, instant = choose_instant_context(contexts, date(2026, 9, 30), facts, ("Assets", "Equity"))
    assert context_id == "balance"
    assert instant == date(2026, 9, 30)


def test_instant_context_requires_exact_date():
    from indian_equity_research.ingestion.xbrl_contexts import choose_instant_context
    with pytest.raises(ValueError, match="no instant context"):
        choose_instant_context(
            {"prior": {"type": "instant", "instant": date(2026, 3, 31)}},
            date(2026, 9, 30),
        )
