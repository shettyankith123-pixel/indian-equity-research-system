"""Financial growth calculations with explicit failure behaviour."""

from __future__ import annotations

from decimal import Decimal

from indian_equity_research.models.financials import as_decimal


def cagr(start_value: Decimal | int | float | str,
         end_value: Decimal | int | float | str,
         years: Decimal | int | float | str) -> Decimal:
    """Return CAGR as a decimal. Zero/negative endpoints require separate analysis."""
    start = as_decimal(start_value, "start_value")
    end = as_decimal(end_value, "end_value")
    duration = as_decimal(years, "years")
    if start <= 0 or end <= 0:
        raise ValueError("CAGR requires positive start_value and end_value.")
    if duration <= 0:
        raise ValueError("years must be positive.")
    return (end / start) ** (Decimal("1") / duration) - Decimal("1")


def simple_growth(start_value: Decimal | int | float | str,
                  end_value: Decimal | int | float | str) -> Decimal:
    """Return simple period growth as a decimal; start value cannot be zero."""
    start = as_decimal(start_value, "start_value")
    end = as_decimal(end_value, "end_value")
    if start == 0:
        raise ValueError("simple growth is undefined when start_value is zero.")
    return (end / start) - Decimal("1")
