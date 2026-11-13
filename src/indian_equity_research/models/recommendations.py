"""Typed inputs and outputs for long-term investment decisions."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class ResearchInput:
    symbol: str
    sector: str
    current_price: Optional[Decimal]
    fair_value_base: Optional[Decimal]
    fair_value_low: Optional[Decimal]
    fair_value_high: Optional[Decimal]
    quality_score: Optional[Decimal]
    growth_score: Optional[Decimal]
    balance_sheet_score: Optional[Decimal]
    governance_score: Optional[Decimal]
    data_completeness: Optional[Decimal]
    data_as_of: Optional[date]
    valuation_confidence: Optional[Decimal]
    thesis_broken: bool = False
    major_risk_flag: bool = False
    held: bool = False
    notes: str = ""
    source_name: str = ""
    source_url: str = ""


@dataclass(frozen=True)
class InvestmentDecision:
    symbol: str
    sector: str
    recommendation: str
    rationale: str
    current_price: Optional[str]
    fair_value_base: Optional[str]
    fair_value_low: Optional[str]
    fair_value_high: Optional[str]
    upside_to_base_pct: Optional[str]
    margin_of_safety_pct: Optional[str]
    ideal_entry_max: Optional[str]
    buy_entry_max: Optional[str]
    accumulate_entry_max: Optional[str]
    suggested_action: str
    confidence: str
    held: bool
    data_status: str
    data_as_of: Optional[str]
    source_name: str
    source_url: str
    notes: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
