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

This repository is the **initial engineering foundation**. It includes the research rules, watchlist, starter valuation code, tests and configuration templates. Live NSE/INDmoney ingestion, company-filing ingestion, persistent database, model endpoints and scheduled production runs are **not yet implemented**. They must be integrated and tested before the system is described as automated or production-ready.

## Repository structure

```
config/
  settings.example.yaml
  watchlists/indian_watchlist.yaml
docs/
  architecture.md
  data_quality.md
  research_methodology.md
src/indian_equity_research/
  __init__.py
  valuation/bank_valuation.py
tests/
  test_bank_valuation.py
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

The valuation module is intentionally small and dependency-light. It implements a simplified justified price-to-book formula for banks; it is a scenario tool, not a full discounted cash-flow model or a recommendation engine.

## Core research commands (planned interface)

- `COMPANY SCAN --symbol ICICIBANK`
- `SECTOR SCAN --sector BANKING`
- `STOCK DISCOVERY`
- `PORTFOLIO REVIEW`
- `RESEARCH REVIEW`
- `FULL UNIVERSE SCAN`

These are target workflows, not currently executable CLI commands.

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

Copy `.env.example` to `.env` and fill only the secrets required by integrations you have separately authorised. Never commit `.env`. The example YAML files contain non-secret settings only.

## Disclaimer

For research and educational purposes only. Nothing in this repository is an offer, solicitation or personalised investment advice. Verify inputs and consult an appropriately registered investment professional before making investment decisions.
