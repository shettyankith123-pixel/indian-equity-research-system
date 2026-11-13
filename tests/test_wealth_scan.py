from datetime import date
from pathlib import Path

from indian_equity_research.analytics.wealth_scan import build_decisions, read_watchlist


def test_full_watchlist_yields_explicit_assess_for_unresearched_names():
    root = Path(__file__).parents[1]
    symbols = read_watchlist(root / "config/watchlists/indian_watchlist.yaml")
    decisions = build_decisions(root / "config/watchlists/indian_watchlist.yaml", root / "data/templates/research_inputs.csv", today=date(2026, 11, 13))
    assert len(symbols) == 64
    assert len(decisions) == 64
    assert {row["recommendation"] for row in decisions} == {"ASSESS"}
