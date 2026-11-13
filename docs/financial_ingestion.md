# Financial statement ingestion workflow

## Canonical CSV format

The system currently accepts a long-form CSV containing one financial metric per row. Use `data/templates/financial_observations.csv` as the header template.

Required fields:
- symbol, metric, value, unit, currency
- period_start, period_end, period_kind, basis, annualisation_factor
- source_name, source_type, publication_date, retrieved_at, observation_kind

Optional provenance fields:
- source_url
- reference_id

Dates use YYYY-MM-DD. `retrieved_at` must be ISO 8601 and timezone-aware. All monetary observations in a statement should use the same currency and scale. Use metric names from the supported bank mapping in `analytics/bank_snapshot.py`.

## Commands

Install the project:

```bash
pip install -e ".[dev]"
```

Validate and import a CSV atomically:

```bash
ies import-financials path/to/financial_observations.csv --db data/research.db
```

Calculate bank ratios from one source and one period:

```bash
ies bank-ratios --symbol ICICIBANK \
  --period-start 2026-07-01 --period-end 2026-09-30 \
  --basis standalone --source-name "ICICI Q2 results" --db data/research.db
```

Check database count:

```bash
ies db-status --db data/research.db
```

## Atomicity and source separation

CSV parsing validates every row before writing. If any row fails, the CLI cancels the import. The SQLite batch insert is transactional: a duplicate causes the whole batch to roll back. A statement query requires a source name, preventing metrics from different publishers from being silently combined.

## Current limitations

This is a validated import and analytics pipeline, not an automated filing scraper. Data must currently be supplied in the canonical CSV format. NSE and INDmoney live integrations, PDF/XBRL extraction, automated source discovery, PostgreSQL hosting and scheduled ingestion remain later work.
