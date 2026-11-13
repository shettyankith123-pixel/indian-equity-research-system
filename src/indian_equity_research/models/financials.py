"""Financial statement records with source and reporting-period provenance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
import re

ReportingBasis = Literal["standalone", "consolidated"]
PeriodKind = Literal["quarter", "half_year", "year", "trailing_twelve_months"]
ObservationKind = Literal["reported", "calculated", "estimate"]
SourceType = Literal["company_filing", "exchange_filing", "regulator", "provider", "other"]


def as_decimal(value: Decimal | int | float | str, field_name: str) -> Decimal:
    """Convert numeric input to Decimal without importing binary float noise."""
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be a valid number.") from exc
    if not result.is_finite():
        raise ValueError(f"{field_name} must be finite.")
    return result


@dataclass(frozen=True, slots=True)
class FinancialPeriod:
    """Reporting period and explicit annualisation factor for flow metrics."""

    start_date: date
    end_date: date
    kind: PeriodKind
    basis: ReportingBasis
    annualisation_factor: Decimal

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise ValueError("start_date cannot be after end_date.")
        factor = as_decimal(self.annualisation_factor, "annualisation_factor")
        if factor <= 0:
            raise ValueError("annualisation_factor must be positive.")
        object.__setattr__(self, "annualisation_factor", factor)


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Publisher and retrieval provenance for a financial observation."""

    source_name: str
    source_type: SourceType
    publication_date: date
    retrieved_at: datetime
    url: str | None = None
    reference_id: str | None = None

    def __post_init__(self) -> None:
        if not self.source_name.strip():
            raise ValueError("source_name is required.")
        if self.retrieved_at.tzinfo is None or self.retrieved_at.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware.")
        if self.url is not None and not self.url.startswith(("https://", "http://")):
            raise ValueError("url must be an HTTP(S) URL when provided.")


@dataclass(frozen=True, slots=True)
class FinancialObservation:
    """One metric value for a particular entity, period, basis and source."""

    symbol: str
    metric: str
    value: Decimal
    unit: str
    currency: str
    period: FinancialPeriod
    source: SourceReference
    observation_kind: ObservationKind = "reported"

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()
        if not re.fullmatch(r"[A-Z0-9&._-]{1,32}", symbol):
            raise ValueError("symbol contains unsupported characters.")
        if not self.metric.strip() or not self.unit.strip() or not self.currency.strip():
            raise ValueError("metric, unit and currency are required.")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "value", as_decimal(self.value, "value"))


@dataclass(frozen=True, slots=True)
class FinancialStatementSnapshot:
    """Consistent set of observations for one company, period and reporting basis."""

    symbol: str
    period: FinancialPeriod
    observations: tuple[FinancialObservation, ...]

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()
        if not symbol:
            raise ValueError("symbol is required.")
        seen: set[str] = set()
        for observation in self.observations:
            if observation.symbol != symbol:
                raise ValueError("all observations must belong to the snapshot symbol.")
            if observation.period != self.period:
                raise ValueError("all observations must share the snapshot period and basis.")
            if observation.metric in seen:
                raise ValueError(f"duplicate metric in snapshot: {observation.metric}")
            seen.add(observation.metric)
        object.__setattr__(self, "symbol", symbol)

    def get(self, metric: str) -> FinancialObservation | None:
        """Return a metric or None; missing data is never converted to zero."""
        return next((item for item in self.observations if item.metric == metric), None)
