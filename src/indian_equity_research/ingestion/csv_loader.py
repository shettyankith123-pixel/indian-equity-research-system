"""CSV ingestion for the canonical long-form financial observations format."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from indian_equity_research.models.financials import (
    FinancialObservation,
    FinancialPeriod,
    SourceReference,
)

REQUIRED_COLUMNS = {
    "symbol", "metric", "value", "unit", "currency",
    "period_start", "period_end", "period_kind", "basis",
    "annualisation_factor", "source_name", "source_type",
    "publication_date", "retrieved_at", "observation_kind",
}
PERIOD_KINDS = {"quarter", "half_year", "year", "transition_period", "instant", "trailing_twelve_months"}
BASES = {"standalone", "consolidated"}
SOURCE_TYPES = {"company_filing", "exchange_filing", "regulator", "provider", "other"}
OBSERVATION_KINDS = {"reported", "calculated", "estimate"}


@dataclass(frozen=True, slots=True)
class CsvParseResult:
    observations: tuple[FinancialObservation, ...]
    errors: tuple[str, ...]


def _parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field} must use YYYY-MM-DD.") from exc


def _parse_decimal(value: str, field: str) -> Decimal:
    try:
        result = Decimal(value.strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(f"{field} must be numeric.") from exc
    if not result.is_finite():
        raise ValueError(f"{field} must be finite.")
    return result


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("retrieved_at must be an ISO 8601 timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("retrieved_at must include a timezone, e.g. +05:30 or Z.")
    return parsed


def parse_financial_csv(path: str | Path) -> CsvParseResult:
    """Parse rows without writing anything; any row errors are returned to caller."""
    csv_path = Path(path)
    observations: list[FinancialObservation] = []
    errors: list[str] = []

    try:
        handle = csv_path.open("r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        return CsvParseResult((), (f"Cannot open {csv_path}: {exc}",))

    with handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return CsvParseResult((), ("CSV is empty or has no header row.",))
        missing = REQUIRED_COLUMNS.difference(reader.fieldnames)
        if missing:
            return CsvParseResult((), (f"Missing required columns: {', '.join(sorted(missing))}",))

        for row_number, row in enumerate(reader, start=2):
            try:
                period_kind = (row["period_kind"] or "").strip()
                basis = (row["basis"] or "").strip()
                source_type = (row["source_type"] or "").strip()
                observation_kind = (row["observation_kind"] or "").strip()
                if period_kind not in PERIOD_KINDS:
                    raise ValueError(f"period_kind must be one of {sorted(PERIOD_KINDS)}.")
                if basis not in BASES:
                    raise ValueError(f"basis must be one of {sorted(BASES)}.")
                if source_type not in SOURCE_TYPES:
                    raise ValueError(f"source_type must be one of {sorted(SOURCE_TYPES)}.")
                if observation_kind not in OBSERVATION_KINDS:
                    raise ValueError(
                        f"observation_kind must be one of {sorted(OBSERVATION_KINDS)}."
                    )

                period = FinancialPeriod(
                    start_date=_parse_date(row["period_start"], "period_start"),
                    end_date=_parse_date(row["period_end"], "period_end"),
                    kind=period_kind,  # validated above
                    basis=basis,  # validated above
                    annualisation_factor=_parse_decimal(
                        row["annualisation_factor"], "annualisation_factor"
                    ),
                )
                source = SourceReference(
                    source_name=(row["source_name"] or "").strip(),
                    source_type=source_type,  # validated above
                    publication_date=_parse_date(row["publication_date"], "publication_date"),
                    retrieved_at=_parse_datetime(row["retrieved_at"]),
                    url=(row.get("source_url") or "").strip() or None,
                    reference_id=(row.get("reference_id") or "").strip() or None,
                )
                observations.append(
                    FinancialObservation(
                        symbol=row["symbol"],
                        metric=row["metric"],
                        value=_parse_decimal(row["value"], "value"),
                        unit=row["unit"],
                        currency=row["currency"],
                        period=period,
                        source=source,
                        observation_kind=observation_kind,  # validated above
                    )
                )
            except (KeyError, ValueError) as exc:
                errors.append(f"Row {row_number}: {exc}")

    return CsvParseResult(tuple(observations), tuple(errors))
