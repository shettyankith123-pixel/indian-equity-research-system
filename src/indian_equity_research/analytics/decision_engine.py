"""Transparent, conservative-when-data-is-missing long-term decision rules.

This module does not invent recommendations. It only emits BUY/ACCUMULATE when
required company-quality, valuation, confidence and data-quality inputs exist.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from indian_equity_research.models.recommendations import ResearchInput, InvestmentDecision

D = Decimal


def _fmt(value: Optional[Decimal]) -> Optional[str]:
    return str(value.quantize(D("0.01"))) if value is not None else None


def _missing_inputs(item: ResearchInput) -> list[str]:
    required = {
        "current_price": item.current_price,
        "fair_value_base": item.fair_value_base,
        "fair_value_low": item.fair_value_low,
        "fair_value_high": item.fair_value_high,
        "quality_score": item.quality_score,
        "growth_score": item.growth_score,
        "balance_sheet_score": item.balance_sheet_score,
        "governance_score": item.governance_score,
        "data_completeness": item.data_completeness,
        "data_as_of": item.data_as_of,
        "valuation_confidence": item.valuation_confidence,
        "source_name": item.source_name.strip() if item.source_name else None,
        "source_url": item.source_url.strip() if item.source_url else None,
    }
    return [name for name, value in required.items() if value is None]


def decide(
    item: ResearchInput,
    *,
    today: Optional[date] = None,
    max_data_age_days: int = 120,
    minimum_completeness: Decimal = D("0.85"),
) -> InvestmentDecision:
    """Return one explicit action for a stock using the user's moderate-high profile.

    Price bands are based on the supplied base fair value, not guessed market data.
    A BUY needs >=15% margin of safety; ACCUMULATE needs >=8%.
    """
    today = today or date.today()
    missing = _missing_inputs(item)
    price = item.current_price
    fair = item.fair_value_base
    low = item.fair_value_low
    high = item.fair_value_high
    completeness = item.data_completeness

    if item.thesis_broken:
        rec = "EXIT" if item.held else "AVOID"
        rationale = "The investment thesis is marked as broken; review the original evidence and exit criteria."
        action = "Review position size and tax/cost implications; do not average down."
        status = "thesis_broken"
        confidence = "Medium" if not missing else "Low"
        upside = mos = None
        entry = buy_entry = accumulate_entry = None
    elif missing:
        rec = "ASSESS"
        rationale = "Insufficient verified inputs: " + ", ".join(missing) + ". No BUY call is permitted until these are supplied."
        action = "Complete the missing financial, valuation and source fields."
        status = "incomplete"
        confidence = "Low"
        upside = mos = entry = buy_entry = accumulate_entry = None
    elif completeness < minimum_completeness:
        rec = "ASSESS"
        rationale = f"Data completeness is {completeness:.0%}, below the required {minimum_completeness:.0%}."
        action = "Validate missing periods and primary-source references before investing."
        status = "incomplete"
        confidence = "Low"
        upside = mos = entry = buy_entry = accumulate_entry = None
    elif item.data_as_of and (today - item.data_as_of).days > max_data_age_days:
        rec = "ASSESS"
        rationale = f"Research inputs are {(today - item.data_as_of).days} days old; the decision requires refreshed data."
        action = "Refresh the latest price and financial statements."
        status = "stale"
        confidence = "Low"
        upside = mos = entry = buy_entry = accumulate_entry = None
    elif price is None or fair is None or price <= 0 or fair <= 0:
        rec = "ASSESS"
        rationale = "Current price and positive base fair value are required for a valuation decision."
        action = "Resolve the invalid price or fair-value input."
        status = "invalid_valuation"
        confidence = "Low"
        upside = mos = entry = buy_entry = accumulate_entry = None
    else:
        upside_dec = (fair / price) - D("1")
        mos_dec = D("1") - (price / fair)
        upside = _fmt(upside_dec * D("100"))
        mos = _fmt(mos_dec * D("100"))
        buy_entry = _fmt(fair * D("0.85"))
        accumulate_entry = _fmt(fair * D("0.92"))
        entry = buy_entry if mos_dec >= D("0.15") else accumulate_entry

        scores = [item.quality_score, item.growth_score, item.balance_sheet_score, item.governance_score]
        score = sum(scores, D("0")) / D(len(scores))  # type: ignore[arg-type]
        high_quality = (
            item.quality_score >= D("65")
            and item.growth_score >= D("55")
            and item.balance_sheet_score >= D("55")
            and item.governance_score >= D("65")
            and score >= D("65")
        )
        confidence_ok = item.valuation_confidence >= D("0.65")

        if item.major_risk_flag:
            rec = "HOLD" if item.held else "WAIT"
            rationale = "A material risk flag is open. The valuation may look attractive, but the risk needs resolution before adding capital."
            action = "Track the named risk and reassess when primary evidence changes."
            confidence = "Medium" if confidence_ok else "Low"
            status = "risk_flag"
        elif not high_quality:
            rec = "REDUCE" if item.held and score < D("45") else ("HOLD" if item.held else "AVOID")
            rationale = f"The company-quality score is {score:.1f}/100; it does not meet the minimum quality and governance gates."
            action = "Do not add capital; review business quality and thesis risks."
            confidence = "Medium" if confidence_ok else "Low"
            status = "quality_gate_failed"
        elif not confidence_ok:
            rec = "ASSESS"
            rationale = "Valuation confidence is below 70%; the fair-value estimate is not strong enough for an action call."
            action = "Improve valuation evidence and cross-check assumptions."
            confidence = "Low"
            status = "low_valuation_confidence"
        elif mos_dec >= D("0.15"):
            rec = "BUY"
            rationale = f"Quality gates pass and the share price is {mos_dec:.1%} below base fair value, meeting the 15% entry margin."
            action = "Consider starting a position in planned tranches; size it within portfolio and sector limits."
            confidence = "High" if score >= D("80") and item.valuation_confidence >= D("0.85") else "Medium"
            status = "actionable_entry"
        elif mos_dec >= D("0.08"):
            rec = "ACCUMULATE"
            rationale = f"Quality gates pass and the price is {mos_dec:.1%} below base fair value, meeting the 8% accumulation margin."
            action = "Build gradually; reserve later tranches for refreshed results or a better price."
            confidence = "High" if score >= D("80") and item.valuation_confidence >= D("0.85") else "Medium"
            status = "actionable_accumulation"
        elif item.held and mos_dec < D("-0.30"):
            rec = "REDUCE"
            rationale = "The share price is more than 30% above base fair value; review concentration and expected return."
            action = "Consider trimming to target allocation; do not sell solely on valuation without reviewing tax and thesis."
            confidence = "Medium"
            status = "valuation_stretched"
        elif item.held:
            rec = "HOLD"
            rationale = f"The price is not at the 10% accumulation threshold (margin of safety {mos_dec:.1%}); existing position can be held while monitoring fundamentals."
            action = "Hold; add only if the margin-of-safety threshold is met or fair value improves on evidence."
            confidence = "Medium"
            status = "hold_watch"
        else:
            rec = "WAIT"
            rationale = f"Business quality passes, but margin of safety is {mos_dec:.1%}, below the 8% fresh-entry threshold."
            action = "Wait for the price to approach the entry zone or for earnings to increase fair value."
            confidence = "Medium"
            status = "valuation_wait"

    return InvestmentDecision(
        symbol=item.symbol.upper(), sector=item.sector, recommendation=rec,
        rationale=rationale, current_price=_fmt(price), fair_value_base=_fmt(fair),
        fair_value_low=_fmt(low), fair_value_high=_fmt(high),
        upside_to_base_pct=upside, margin_of_safety_pct=mos, ideal_entry_max=entry,
        buy_entry_max=buy_entry, accumulate_entry_max=accumulate_entry,
        suggested_action=action, confidence=confidence, held=item.held,
        data_status=status, data_as_of=item.data_as_of.isoformat() if item.data_as_of else None,
        source_name=item.source_name, source_url=item.source_url, notes=item.notes,
    )
