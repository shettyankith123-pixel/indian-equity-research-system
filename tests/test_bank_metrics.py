from decimal import Decimal

import pytest

from indian_equity_research.analytics.bank_metrics import BankMetricInputs, calculate_bank_metrics


def test_calculates_core_bank_ratios() -> None:
    inputs = BankMetricInputs(
        annualisation_factor=Decimal("4"), net_interest_income=Decimal("100"),
        average_interest_earning_assets=Decimal("10000"), net_profit=Decimal("50"),
        average_total_assets=Decimal("10000"), average_equity=Decimal("1000"),
        casa_deposits=Decimal("4000"), total_deposits=Decimal("10000"),
        gross_npa=Decimal("120"), gross_advances=Decimal("10000"),
        net_npa=Decimal("30"), net_advances=Decimal("9900"),
        provisions_against_npa=Decimal("90"), cet1_capital=Decimal("1500"),
        total_regulatory_capital=Decimal("1700"), risk_weighted_assets=Decimal("10000"),
        operating_expenses=Decimal("300"), net_total_income=Decimal("1000"),
    )
    metrics = calculate_bank_metrics(inputs)
    assert metrics["nim"].value == pytest.approx(Decimal("0.04"))
    assert metrics["roa"].value == pytest.approx(Decimal("0.02"))
    assert metrics["roe"].value == pytest.approx(Decimal("0.20"))
    assert metrics["casa_ratio"].value == pytest.approx(Decimal("0.40"))
    assert metrics["gross_npa_ratio"].value == pytest.approx(Decimal("0.012"))
    assert metrics["net_npa_ratio"].value == pytest.approx(Decimal("0.003030303030303030303030303030"))
    assert metrics["provision_coverage_ratio"].value == pytest.approx(Decimal("0.75"))
    assert metrics["cet1_ratio"].value == pytest.approx(Decimal("0.15"))
    assert metrics["capital_adequacy_ratio"].value == pytest.approx(Decimal("0.17"))
    assert metrics["cost_to_income_ratio"].value == pytest.approx(Decimal("0.30"))
    assert metrics["credit_deposit_ratio"].value == pytest.approx(Decimal("1.0"))


def test_missing_inputs_are_not_treated_as_zero() -> None:
    nim = calculate_bank_metrics(BankMetricInputs())["nim"]
    assert nim.value is None
    assert nim.status == "missing_input"
    assert set(nim.missing_inputs) == {"net_interest_income", "average_interest_earning_assets"}


def test_zero_denominator_is_marked_invalid() -> None:
    casa = calculate_bank_metrics(BankMetricInputs(casa_deposits=Decimal("100"), total_deposits=Decimal("0")))["casa_ratio"]
    assert casa.value is None
    assert casa.status == "invalid_denominator"


def test_negative_bank_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        BankMetricInputs(net_profit=Decimal("-5"))


def test_annualisation_factor_must_be_positive() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        BankMetricInputs(annualisation_factor=Decimal("0"))
