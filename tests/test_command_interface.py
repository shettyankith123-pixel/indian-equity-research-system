from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pytest

from indian_equity_research.analytics.wealth_scan import (
    build_company_decision,
    build_sector_decisions,
    resolve_company_symbol,
    resolve_sector_name,
)
from indian_equity_research.cli import _portfolio_snapshot_report, _route_friendly_command


ROOT = Path(__file__).parents[1]
UNIVERSE = ROOT / "data/universe/indian_watchlist_companies.csv"
RESEARCH = ROOT / "data/templates/research_inputs.csv"


def test_friendly_command_aliases():
    assert _route_friendly_command(["WEALTH", "SCAN"]) == ["wealth-scan"]
    assert _route_friendly_command(["MARKET", "SCAN"]) == ["market-scan"]
    assert _route_friendly_command(["MARKET", "BRIEF"]) == ["market-brief"]
    assert _route_friendly_command(["PORTFOLIO", "REVIEW"]) == ["portfolio-review"]
    assert _route_friendly_command(["FIND", "OPPORTUNITIES"]) == ["opportunity-scan"]


def test_company_and_sector_commands_accept_human_names():
    assert _route_friendly_command(["COMPANY", "SCAN", "ICICI", "BANK"]) == [
        "company-scan", "ICICI BANK"
    ]
    assert _route_friendly_command(["SECTOR", "SCAN", "IT", "SERVICES"]) == [
        "sector-scan", "--sector", "IT SERVICES"
    ]


def test_company_and_sector_aliases_resolve_to_universe_taxonomy():
    assert resolve_company_symbol("ICICI Bank", UNIVERSE) == "ICICIBANK"
    assert resolve_company_symbol("State Bank of India", UNIVERSE) == "SBIN"
    assert resolve_company_symbol("Varun Beverages", UNIVERSE) == "VBL"
    assert resolve_sector_name("banks", UNIVERSE) == "Banking"
    assert resolve_sector_name("IT", UNIVERSE) == "IT Services"


def test_company_scan_shows_correct_sector_and_assess_for_missing_research():
    result = build_company_decision("ICICI Bank", RESEARCH, today=date(2026, 11, 13), universe_path=UNIVERSE)
    assert result["symbol"] == "ICICIBANK"
    assert result["sector"] == "Banking"
    assert result["recommendation"] == "ASSESS"


def test_sector_scan_covers_universe_even_without_research_inputs():
    results = build_sector_decisions("Banking", RESEARCH, today=date(2026, 11, 13), universe_path=UNIVERSE)
    assert {row["symbol"] for row in results} == {"ICICIBANK", "SBIN"}
    assert {row["recommendation"] for row in results} == {"ASSESS"}


def test_missing_company_or_sector_argument_is_rejected():
    with pytest.raises(ValueError, match="COMPANY SCAN"):
        _route_friendly_command(["COMPANY", "SCAN"])
    with pytest.raises(ValueError, match="SECTOR SCAN"):
        _route_friendly_command(["SECTOR", "SCAN"])


def test_portfolio_review_uses_dated_holdings_snapshot_without_fabricating_trades(tmp_path):
    snapshot = tmp_path / "holdings.csv"
    with snapshot.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "as_of_date", "symbol", "quantity", "invested_value_inr",
            "market_value_inr", "unrealized_pnl_inr"
        ])
        writer.writeheader()
        writer.writerow({
            "as_of_date": "2026-11-13", "symbol": "TCS", "quantity": 1,
            "invested_value_inr": "1000", "market_value_inr": "1100",
            "unrealized_pnl_inr": "100"
        })
        writer.writerow({
            "as_of_date": "2026-11-13", "symbol": "SBIN", "quantity": 2,
            "invested_value_inr": "500", "market_value_inr": "450",
            "unrealized_pnl_inr": "-50"
        })
    result = _portfolio_snapshot_report(snapshot, tmp_path / "empty.db")
    assert result["status"] == "snapshot_only"
    assert result["position_count"] == 2
    assert result["invested_value_inr"] == 1500.0
    assert result["market_value_inr"] == 1550.0
    assert result["unrealised_pnl_inr"] == 50.0
    assert result["transaction_history_available"] is False
