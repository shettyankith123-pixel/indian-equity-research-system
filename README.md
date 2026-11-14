# Indian Equity Research System

A private, evidence-led research platform for Indian equities, built for a **moderate-to-high risk appetite and a 7–10 year wealth-creation horizon**. Its purpose is to identify attractive long-term opportunities, not to default to WAIT or produce BUY signals without evidence.

## Investor mandate

- Long-term investing by default; swing-trading analysis only when explicitly requested.
- Quality businesses, durable earnings growth and reasonable valuations.
- Staged entries and explicit entry/valuation triggers.
- BUY and ACCUMULATE are permitted when research and valuation gates pass.
- No fabricated prices, financial figures, fair values, cash balances or broker data.

## Current capabilities

- Financial observation model with source, period, basis and publication provenance, including separate instant-date balance-sheet facts.
- Source-aware financial normalization for margins, YoY growth, cash conversion, FCF proxies, leverage, liquidity, ROE/ROA and bank asset-quality inputs.
- Sector-aware scenario valuation: bank justified P/B; non-bank cash-flow DCF with P/E and EV/EBITDA cross-checks when enough peer evidence exists.
- Automated report builder for financial histories, valuation ranges, assumptions, confidence and research-input registers across the 64-stock universe.
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
pip install -e ".[dev,financials]"
pytest
```

## ChatGPT command interface

You can use the following phrases in the connected ChatGPT conversation. The assistant dispatches the matching Research Command workflow and reads its report artifact:

- MARKET BRIEF
- WEALTH SCAN
- COMPANY SCAN ICICI BANK
- SECTOR SCAN BANKING
- PORTFOLIO REVIEW
- FIND OPPORTUNITIES

The local MARKET BRIEF workflow fetches official NSE EOD breadth. ChatGPT adds live headlines, global context and catalyst interpretation separately. A successful command run does not bypass data-quality gates: missing valuation inputs remain ASSESS.

See [command interface](docs/command_interface.md) for exact behaviour and current boundaries.

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

The GitHub Research Command workflow retrieves the latest successful full-universe financial artifact, validates 64 unique issuer rows and the MCX BSE source fallback, builds current research registers, and then runs the selected command. Financial statements do not bypass the separate governance/qualitative review gate.

### Generate the Wealth Scan decision register

The connected GitHub Research Command workflow retrieves the latest validated 64-stock financial database, builds the financial history and sector valuation registers, and generates research inputs before running WEALTH SCAN. Dispatch the wealth-scan action in GitHub Actions or use the connected ChatGPT conversation command. Manual local mode remains available when you have reviewed inputs:

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

## Current integration boundaries

- INDmoney holdings can be read in the connected ChatGPT session, but private account sync is not configured inside GitHub Actions. Historical trade reconstruction still requires a user-exported transaction CSV; never put broker credentials in Git.
- NSE Integrated Filing XBRL ingestion supports separate duration and instant contexts. The last verified full-universe baseline (before the instant-context fix) covered 63 of 64 issuers and requires a fresh full run after the latest parser corrections.
- Sector-specific fair values are provisional outputs with disclosed assumptions. Manual governance, management-quality and qualitative thesis review remains required before BUY/ACCUMULATE can be emitted; missing review fields deliberately keep recommendations at ASSESS.
- Automated news ingestion, AI model endpoints, corporate-action-adjusted historical prices, BSE feeds, benchmark-relative event studies and hosted persistent storage remain outstanding.
- The full Wealth Scan schedule is intentionally not enabled until the full data and valuation gates pass. On-demand command execution is available through the Research Command GitHub Actions workflow; no separate hosted ChatGPT API endpoint exists.

See [controlled execution plan](docs/project_execution_plan.md) for the single source of truth on progress, acceptance criteria, blockers and run history.

## Research integrity

This is research software, not a brokerage execution system or a personalised investment advisory service. It does not place orders. Verify every input and review risk, concentration, liquidity, taxes and suitability before investing.
