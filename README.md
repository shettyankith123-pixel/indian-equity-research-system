# Indian Equity Research System

A private, evidence-led research platform for Indian equities. The system is designed to combine exchange and broker data, company disclosures, reproducible financial calculations, AI-assisted document/news analysis, and human-reviewed investment decisions.

## Objectives

- Research the 64-stock personal watchlist and progressively expand to a broader NSE-listed equity universe.
- Keep long-term investing (default 7–10 years) separate from explicitly requested swing-trading analysis.
- Produce company, sector, portfolio, discovery and research-review reports.
- Track financial trends, asset quality, profitability, capital, valuation, governance, risk and thesis changes.
- Record source, publication date, financial period, retrieval time and data-quality status for every material input.
- Compare prior expectations with subsequent results and market outcomes.

## Current status

The repository contains research rules, the imported watchlist, financial data models, bank-ratio calculations, CSV ingestion, SQLite persistence, a CLI and tests. The data pipeline is usable for validated financial statement CSV imports.

**Not yet implemented:** automated NSE/INDmoney provider connections inside GitHub Actions, official filing downloads and parsing, persistent hosted database, external AI model endpoints, scheduled research runs and automated report generation. Connected chat integrations are available in ChatGPT, but are not automatically callable from this GitHub repository.

## Repository structure

```
config/
  settings.example.yaml
  watchlists/indian_watchlist.yaml
data/
  templates/financial_observations.csv
docs/
  architecture.md
  data_quality.md
  financial_data_model.md
  financial_ingestion.md
  research_methodology.md
src/indian_equity_research/
  analytics/
  ingestion/
  models/
  storage/
  valuation/
  cli.py
tests/
.github/workflows/tests.yml
.env.example
pyproject.toml
```

## Quick start

Python 3.11+ is recommended.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

### Available CLI commands

Validate and atomically import a financial observation CSV:

```bash
ies import-financials data/templates/your_observations.csv --db data/research.db
```

Check how many observations are stored:

```bash
ies db-status --db data/research.db
```

Calculate bank ratios for a single statement and named source:

```bash
ies bank-ratios --symbol ICICIBANK \
  --period-start 2026-07-01 --period-end 2026-09-30 \
  --basis standalone --source-name "ICICI Q2 results" --db data/research.db
```

See [financial ingestion](docs/financial_ingestion.md) for the CSV schema and import rules.

The valuation module implements a simplified justified price-to-book formula for banks; it is a scenario tool, not a full multi-stage valuation or recommendation engine.

## Research workflows (planned)

- `COMPANY SCAN --symbol ICICIBANK`
- `SECTOR SCAN --sector BANKING`
- `STOCK DISCOVERY`
- `PORTFOLIO REVIEW`
- `RESEARCH REVIEW`
- `FULL UNIVERSE SCAN`

These remain target workflows, not currently executable CLI commands.

## Safety and research integrity

1. Never invent missing prices, financial periods, ratios, holdings, analyst targets or source references.
2. Keep reported facts, derived calculations, estimates and analyst assumptions visibly separate.
3. Prefer audited annual reports, exchange filings, regulatory notices and official investor presentations.
4. Record whether each price is live, delayed, end-of-day or historical. Reject stale or inconsistent timestamps for live claims.
5. Retain raw source data and transformation metadata where licensing permits.
6. Do not silently adjust historical prices; check corporate actions.
7. Do not store credentials, broker tokens, personal account identifiers or private financial exports in Git.
8. AI model output is an aid to research, not a source of truth. Validate extracted figures against primary disclosures.
9. Long-term and swing-trading analyses must remain separate.
10. Every final decision must state uncertainty, risks, valuation assumptions and thesis-invalidation conditions.

## Configuration

Copy `.env.example` to `.env` locally and fill only the secrets required by integrations you have separately authorised. Never commit `.env`. The example YAML files contain non-secret settings only.

## Disclaimer

For research and educational purposes only. Nothing in this repository is an offer, solicitation or personalised investment advice. Verify inputs and consult an appropriately registered investment professional before making investment decisions.
