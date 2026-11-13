"""Translate a financial statement snapshot into bank-ratio calculations."""

from __future__ import annotations

from decimal import Decimal

from indian_equity_research.analytics.bank_metrics import (
    BankMetricInputs,
    BankMetricResult,
    calculate_bank_metrics,
)
from indian_equity_research.models.financials import FinancialStatementSnapshot

METRIC_FIELDS = {
    "net_interest_income": "net_interest_income",
    "average_interest_earning_assets": "average_interest_earning_assets",
    "net_profit": "net_profit",
    "average_total_assets": "average_total_assets",
    "average_equity": "average_equity",
    "casa_deposits": "casa_deposits",
    "total_deposits": "total_deposits",
    "gross_npa": "gross_npa",
    "gross_advances": "gross_advances",
    "net_npa": "net_npa",
    "net_advances": "net_advances",
    "provisions_against_npa": "provisions_against_npa",
    "cet1_capital": "cet1_capital",
    "total_regulatory_capital": "total_regulatory_capital",
    "risk_weighted_assets": "risk_weighted_assets",
    "operating_expenses": "operating_expenses",
    "net_total_income": "net_total_income",
}


def calculate_snapshot_bank_metrics(
    snapshot: FinancialStatementSnapshot,
) -> dict[str, BankMetricResult]:
    """Calculate bank ratios from canonical observations in a single snapshot."""
    values: dict[str, Decimal | None] = {field: None for field in METRIC_FIELDS.values()}
    for metric, field in METRIC_FIELDS.items():
        observation = snapshot.get(metric)
        if observation is not None:
            values[field] = observation.value

    inputs = BankMetricInputs(
        annualisation_factor=snapshot.period.annualisation_factor,
        **values,
    )
    return calculate_bank_metrics(inputs)
