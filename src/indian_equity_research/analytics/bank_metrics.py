"""Bank ratios with explicit formulas, annualisation and missing-input states."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from indian_equity_research.models.financials import as_decimal

MetricStatus = Literal["calculated", "missing_input", "invalid_denominator"]


@dataclass(frozen=True, slots=True)
class BankMetricInputs:
    """Raw bank values; monetary values must share currency, scale and basis.

    Use period averages for ROA, ROE and NIM. Flow metrics are annualised using
    the explicit factor. Unavailable inputs remain None.
    """

    annualisation_factor: Decimal = Decimal("4")
    net_interest_income: Decimal | None = None
    average_interest_earning_assets: Decimal | None = None
    net_profit: Decimal | None = None
    average_total_assets: Decimal | None = None
    average_equity: Decimal | None = None
    casa_deposits: Decimal | None = None
    total_deposits: Decimal | None = None
    gross_npa: Decimal | None = None
    gross_advances: Decimal | None = None
    net_npa: Decimal | None = None
    net_advances: Decimal | None = None
    provisions_against_npa: Decimal | None = None
    cet1_capital: Decimal | None = None
    total_regulatory_capital: Decimal | None = None
    risk_weighted_assets: Decimal | None = None
    operating_expenses: Decimal | None = None
    net_total_income: Decimal | None = None

    def __post_init__(self) -> None:
        factor = as_decimal(self.annualisation_factor, "annualisation_factor")
        if factor <= 0:
            raise ValueError("annualisation_factor must be positive.")
        object.__setattr__(self, "annualisation_factor", factor)
        for field_name in self.__dataclass_fields__:
            if field_name == "annualisation_factor":
                continue
            value = getattr(self, field_name)
            if value is not None:
                converted = as_decimal(value, field_name)
                if converted < 0:
                    raise ValueError(f"{field_name} cannot be negative.")
                object.__setattr__(self, field_name, converted)


@dataclass(frozen=True, slots=True)
class BankMetricResult:
    """A calculated ratio or a visible missing/invalid state."""

    name: str
    value: Decimal | None
    formula: str
    status: MetricStatus
    missing_inputs: tuple[str, ...] = ()


def _ratio(
    name: str,
    numerator: Decimal | None,
    denominator: Decimal | None,
    formula: str,
    *,
    numerator_name: str,
    denominator_name: str,
    multiplier: Decimal = Decimal("1"),
) -> BankMetricResult:
    missing = tuple(
        field for field, value in ((numerator_name, numerator), (denominator_name, denominator))
        if value is None
    )
    if missing:
        return BankMetricResult(name, None, formula, "missing_input", missing)
    assert numerator is not None and denominator is not None
    if denominator <= 0:
        return BankMetricResult(name, None, formula, "invalid_denominator", (denominator_name,))
    return BankMetricResult(name, (numerator * multiplier) / denominator, formula, "calculated")


def calculate_bank_metrics(inputs: BankMetricInputs) -> dict[str, BankMetricResult]:
    """Calculate core bank ratios. Values are fractions: 0.0418 means 4.18%."""
    annualiser = inputs.annualisation_factor
    return {
        "nim": _ratio("nim", inputs.net_interest_income, inputs.average_interest_earning_assets,
            "net_interest_income × annualisation_factor / average_interest_earning_assets",
            numerator_name="net_interest_income", denominator_name="average_interest_earning_assets",
            multiplier=annualiser),
        "roa": _ratio("roa", inputs.net_profit, inputs.average_total_assets,
            "net_profit × annualisation_factor / average_total_assets",
            numerator_name="net_profit", denominator_name="average_total_assets", multiplier=annualiser),
        "roe": _ratio("roe", inputs.net_profit, inputs.average_equity,
            "net_profit × annualisation_factor / average_equity",
            numerator_name="net_profit", denominator_name="average_equity", multiplier=annualiser),
        "casa_ratio": _ratio("casa_ratio", inputs.casa_deposits, inputs.total_deposits,
            "casa_deposits / total_deposits", numerator_name="casa_deposits",
            denominator_name="total_deposits"),
        "gross_npa_ratio": _ratio("gross_npa_ratio", inputs.gross_npa, inputs.gross_advances,
            "gross_npa / gross_advances", numerator_name="gross_npa",
            denominator_name="gross_advances"),
        "net_npa_ratio": _ratio("net_npa_ratio", inputs.net_npa, inputs.net_advances,
            "net_npa / net_advances", numerator_name="net_npa", denominator_name="net_advances"),
        "provision_coverage_ratio": _ratio("provision_coverage_ratio", inputs.provisions_against_npa,
            inputs.gross_npa, "provisions_against_npa / gross_npa",
            numerator_name="provisions_against_npa", denominator_name="gross_npa"),
        "cet1_ratio": _ratio("cet1_ratio", inputs.cet1_capital, inputs.risk_weighted_assets,
            "cet1_capital / risk_weighted_assets", numerator_name="cet1_capital",
            denominator_name="risk_weighted_assets"),
        "capital_adequacy_ratio": _ratio("capital_adequacy_ratio", inputs.total_regulatory_capital,
            inputs.risk_weighted_assets, "total_regulatory_capital / risk_weighted_assets",
            numerator_name="total_regulatory_capital", denominator_name="risk_weighted_assets"),
        "cost_to_income_ratio": _ratio("cost_to_income_ratio", inputs.operating_expenses,
            inputs.net_total_income, "operating_expenses / net_total_income",
            numerator_name="operating_expenses", denominator_name="net_total_income"),
        "credit_deposit_ratio": _ratio("credit_deposit_ratio", inputs.gross_advances,
            inputs.total_deposits, "gross_advances / total_deposits",
            numerator_name="gross_advances", denominator_name="total_deposits"),
    }
