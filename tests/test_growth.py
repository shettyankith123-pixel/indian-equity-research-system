from decimal import Decimal

import pytest

from indian_equity_research.analytics.growth import cagr, simple_growth


def test_five_year_cagr() -> None:
    assert cagr(100, 200, 5) == pytest.approx(Decimal("0.148698354997035"))


def test_simple_growth() -> None:
    assert simple_growth(100, 125) == Decimal("0.25")


@pytest.mark.parametrize("start,end,years", [
    (0, 100, 5), (100, 0, 5), (-10, 100, 5), (100, -10, 5), (100, 200, 0),
])
def test_cagr_rejects_undefined_inputs(start: int, end: int, years: int) -> None:
    with pytest.raises(ValueError):
        cagr(start, end, years)


def test_simple_growth_rejects_zero_start() -> None:
    with pytest.raises(ValueError):
        simple_growth(0, 10)
