"""SQLite persistence for source-aware financial observations."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from indian_equity_research.models.financials import (
    FinancialObservation,
    FinancialPeriod,
    FinancialStatementSnapshot,
    SourceReference,
)


class FinancialRepository:
    """Small SQLite repository with atomic batch insertion and explicit queries."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialise(self) -> None:
        """Create the observation table and supporting indexes if absent."""
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS financial_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    value TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    period_kind TEXT NOT NULL,
                    basis TEXT NOT NULL,
                    annualisation_factor TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    publication_date TEXT NOT NULL,
                    retrieved_at TEXT NOT NULL,
                    source_url TEXT,
                    reference_id TEXT NOT NULL DEFAULT '',
                    observation_kind TEXT NOT NULL,
                    UNIQUE (
                        symbol, metric, period_start, period_end, basis,
                        source_name, reference_id, observation_kind
                    )
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_financial_observations_lookup
                ON financial_observations (
                    symbol, period_start, period_end, basis, source_name
                )
                """
            )

    def insert_many(self, observations: tuple[FinancialObservation, ...] | list[FinancialObservation]) -> int:
        """Insert a batch atomically. Duplicate source observations fail the whole batch."""
        if not observations:
            return 0
        rows = [
            (
                item.symbol,
                item.metric,
                str(item.value),
                item.unit,
                item.currency,
                item.period.start_date.isoformat(),
                item.period.end_date.isoformat(),
                item.period.kind,
                item.period.basis,
                str(item.period.annualisation_factor),
                item.source.source_name,
                item.source.source_type,
                item.source.publication_date.isoformat(),
                item.source.retrieved_at.isoformat(),
                item.source.url,
                item.source.reference_id or "",
                item.observation_kind,
            )
            for item in observations
        ]
        try:
            with self._connect() as connection:
                connection.executemany(
                    """
                    INSERT INTO financial_observations (
                        symbol, metric, value, unit, currency, period_start, period_end,
                        period_kind, basis, annualisation_factor, source_name, source_type,
                        publication_date, retrieved_at, source_url, reference_id, observation_kind
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                "Batch not imported: at least one observation duplicates an existing "
                "symbol/metric/period/basis/source record."
            ) from exc
        return len(rows)

    def get_snapshot(
        self,
        symbol: str,
        period_start: date,
        period_end: date,
        basis: str,
        source_name: str,
    ) -> FinancialStatementSnapshot | None:
        """Load one period from one named source; avoid silently mixing sources."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM financial_observations
                WHERE symbol = ? AND period_start = ? AND period_end = ?
                  AND basis = ? AND source_name = ?
                ORDER BY metric
                """,
                (
                    symbol.strip().upper(),
                    period_start.isoformat(),
                    period_end.isoformat(),
                    basis,
                    source_name,
                ),
            ).fetchall()

        if not rows:
            return None

        first = rows[0]
        period = FinancialPeriod(
            start_date=date.fromisoformat(first["period_start"]),
            end_date=date.fromisoformat(first["period_end"]),
            kind=first["period_kind"],
            basis=first["basis"],
            annualisation_factor=Decimal(first["annualisation_factor"]),
        )
        observations = tuple(
            FinancialObservation(
                symbol=row["symbol"],
                metric=row["metric"],
                value=Decimal(row["value"]),
                unit=row["unit"],
                currency=row["currency"],
                period=period,
                source=SourceReference(
                    source_name=row["source_name"],
                    source_type=row["source_type"],
                    publication_date=date.fromisoformat(row["publication_date"]),
                    retrieved_at=datetime.fromisoformat(row["retrieved_at"]),
                    url=row["source_url"],
                    reference_id=row["reference_id"] or None,
                ),
                observation_kind=row["observation_kind"],
            )
            for row in rows
        )
        return FinancialStatementSnapshot(symbol, period, observations)

    def count_observations(self) -> int:
        """Return the total number of stored observations."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM financial_observations"
            ).fetchone()
        return int(row["count"])
