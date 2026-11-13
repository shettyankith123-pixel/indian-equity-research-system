"""Transparent bank valuation helpers.

The justified price-to-book calculation is a simplified stable-growth model:
    justified P/B = (ROE - g) / (cost of equity - g)

Inputs are decimals (e.g. 0.16 for 16%). This model does not replace a
multi-stage residual-income or dividend-discount valuation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BankValuationScenario:
    """Assumptions and outputs for a stable-growth justified P/B scenario."""

    name: str
    sustainable_roe: float
    long_term_growth: float
    cost_of_equity: float

    def __post_init__(self) -> None:
        for field_name in ("sustainable_roe", "long_term_growth", "cost_of_equity"):
            value = getattr(self, field_name)
            if not 0 < value < 1:
                raise ValueError(f"{field_name} must be expressed as a decimal between 0 and 1.")
        if self.long_term_growth >= self.cost_of_equity:
            raise ValueError("long_term_growth must be lower than cost_of_equity.")
        if self.sustainable_roe <= self.long_term_growth:
            raise ValueError("sustainable_roe must exceed long_term_growth.")

    @property
    def justified_price_to_book(self) -> float:
        """Return the scenario's justified price-to-book multiple."""
        return (
            (self.sustainable_roe - self.long_term_growth)
            / (self.cost_of_equity - self.long_term_growth)
        )

    def intrinsic_value_per_share(self, book_value_per_share: float) -> float:
        """Return indicative value per share from book value and justified P/B."""
        if book_value_per_share <= 0:
            raise ValueError("book_value_per_share must be positive.")
        return self.justified_price_to_book * book_value_per_share


def implied_roe(
    market_price_to_book: float,
    cost_of_equity: float,
    long_term_growth: float,
) -> float:
    """Solve the stable-growth justified P/B formula for its implied ROE."""
    if market_price_to_book <= 0:
        raise ValueError("market_price_to_book must be positive.")
    if not 0 < long_term_growth < cost_of_equity < 1:
        raise ValueError(
            "Require 0 < long_term_growth < cost_of_equity < 1, expressed as decimals."
        )
    return (
        market_price_to_book * (cost_of_equity - long_term_growth)
        + long_term_growth
    )
