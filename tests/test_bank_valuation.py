import pytest

from indian_equity_research.valuation.bank_valuation import (
    BankValuationScenario,
    implied_roe,
)


def test_base_case_justified_price_to_book() -> None:
    scenario = BankValuationScenario(
        name="base",
        sustainable_roe=0.175,
        long_term_growth=0.07,
        cost_of_equity=0.11,
    )
    assert scenario.justified_price_to_book == pytest.approx(2.625)
    assert scenario.intrinsic_value_per_share(502.30) == pytest.approx(1318.5375)


def test_implied_roe_from_market_multiple() -> None:
    assert implied_roe(3.17, 0.11, 0.07) == pytest.approx(0.1962)


def test_growth_must_be_below_cost_of_equity() -> None:
    with pytest.raises(ValueError):
        BankValuationScenario("invalid", 0.16, 0.11, 0.11)


def test_positive_book_value_required() -> None:
    scenario = BankValuationScenario("base", 0.17, 0.06, 0.11)
    with pytest.raises(ValueError):
        scenario.intrinsic_value_per_share(0)
