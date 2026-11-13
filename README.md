# Indian Equity Research System

A private, evidence-led research platform for Indian equities, built for a **moderate-to-high risk appetite and a 7–10 year wealth-creation horizon**. Its purpose is to identify attractive long-term opportunities, not to default to WAIT or produce BUY signals without evidence.

## Investor mandate

- Long-term investing by default; swing-trading analysis only when explicitly requested.
- Quality businesses, durable earnings growth and reasonable valuations.
- Staged entries and explicit entry/valuation triggers.
- BUY and ACCUMULATE are permitted when research and valuation gates pass.
- No fabricated prices, financial figures, fair values, cash balances or broker data.

## Current capabilities

- Financial observation model with source, period, basis and publication provenance.
- CSV financial-statement ingestion and SQLite persistence.
- Bank financial ratio calculations and growth analytics.
- NSE UDiFF official EOD bhavcopy ZIP downloader/parser, SQLite market-price store and EOD equity breadth/leader-laggard market scan.
- Investment decision engine with BUY, ACCUMULATE, HOLD, WAIT, ASSESS, REDUCE, EXIT and AVOID.
- Full decision register for all 64 configured watchlist symbols plus any additional candidate entered in the research-input file; company and sector scan commands use the same transparent decision engine.
- Portfolio transaction import with average-cost holdings and realised P&L.
- Optional staged allocation planner with stock/sector caps and a cash reserve, driven only by an explicit capital snapshot.
- Outside-watchlist opportunity scan from imported and reviewed company-research inputs.
- News catalyst event-study returns over subsequent trading sessions.
- IPO evidence intake template and sector valuation-framework reference.

## Quick start

Python 3.11+ is recommended.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -e .[dev]
pytest
```

## Commands

### Download official NSE EOD equity data

```bash
ies fetch-nse-eod --date 2026-11-12 --db data/research.db
```

The command downloads the current CM-UDiFF Common Bhavcopy Final ZIP, validates the archive/date/OHLCV rows, writes a normalized CSV under `data/market/`, and stores rows in SQLite. Summarise the latest stored session with `ies market-scan`. See [NSE data pipeline](docs/nse_data_pipeline.md).

### Company and sector scans

```bash
ies company-scan ICICIBANK
ies sector-scan --sector banking
```

These commands analyse imported, reviewed research inputs. They do not fetch or invent company financials on their own.

### Generate the Wealth Scan decision register

Populate `data/templates/research_inputs.csv` with reviewed data, source references and scores (score fields are 0–100; completeness and valuation confidence are 0–1), then run:

```bash
ies wealth-scan
# Optional, when a current portfolio/cash snapshot is available:
ies wealth-scan --capital-snapshot data/templates/capital_snapshot.csv
# Discover actionable BUY/ACCUMULATE candidates outside the 64-stock universe:
ies opportunity-scan
```

Outputs are written to `reports/wealth-scan/decision_register.csv` and `wealth_scan.md`. The configured 64-stock universe always receives an explicit decision. A stock without sufficient data is marked **ASSESS**, not assigned a guessed BUY or WAIT.

### Import portfolio transactions

```bash
ies import-portfolio data/templates/your_transactions.csv --db data/research.db
ies portfolio-status --db data/research.db
```

See [portfolio and event tracking](docs/portfolio_and_event_tracking.md).

### Track news outcomes

Enter sourced events in `data/templates/news_events.csv`, then run:

```bash
ies event-study
```

This reports T+1/T+3/T+5 stock returns. It is descriptive and does not claim causation.

### Existing financial-data commands

```bash
ies import-financials data/templates/your_observations.csv --db data/research.db
ies db-status --db data/research.db
ies bank-ratios --symbol ICICIBANK --period-start 2026-07-01 --period-end 2026-09-30 --basis standalone --source-name "ICICI Q2 results" --db data/research.db
```

## Decision framework

BUY requires at least 85% data completeness, data no older than 120 days, valuation confidence of at least 65%, minimum quality/growth/balance-sheet/governance scores, sourced base/bear/bull valuation inputs and at least 15% margin of safety to base fair value. ACCUMULATE requires at least 8% margin of safety with the same quality gates. A broken thesis or material risk overrides an attractive valuation. Details: [decision framework](docs/decision_framework.md).

## Scheduled workflow

GitHub Actions runs the NSE EOD fetch on weekdays at 18:15 India time and retains the normalized data artifact for 90 days. Run it manually from Actions to request a historical trading date. Artifacts are not a hosted persistent database.

## What is not connected yet

- INDmoney private account sync is not configured. Import a user-exported CSV; do not put broker credentials in Git.
- Automated cross-company financial filing PDF/XBRL extraction is not yet implemented.
- Automated news ingestion, AI model endpoints, corporate-action-adjusted historical prices, BSE feeds, benchmark-relative event studies and hosted persistent storage remain outstanding.
- No recommendation is produced from empty template data. Research fields and fair values must be verified and sourced.

See [implementation status](docs/implementation_status.md) for integration boundaries.

## Research integrity

This is research software, not a brokerage execution system or a personalised investment advisory service. It does not place orders. Verify every input and review risk, concentration, liquidity, taxes and suitability before investing.
