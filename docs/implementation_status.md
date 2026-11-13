# Implementation status and integration boundaries

## Implemented in this repository

- Strategy profile and explicit recommendation rules for the moderate-to-high-risk, 7–10-year investor mandate.
- Individual decision engine with BUY, ACCUMULATE, HOLD, WAIT, ASSESS, REDUCE, EXIT and AVOID.
- Mandatory data-completeness, freshness, valuation-confidence and quality gates; missing inputs produce ASSESS.
- Full decision register for all symbols in the configured 64-stock watchlist, plus additional research-input symbols.
- NSE UDiFF common equity bhavcopy ZIP downloader, parser, OHLC validation, normalized CSV output and SQLite storage.
- Portfolio transaction CSV import and average-cost position / realised P&L calculation.
- News catalyst event-study output for subsequent trading sessions.
- IPO intake template, sector valuation-method reference, outside-watchlist opportunity scan and scheduled NSE data workflow.
- Optional first-tranche allocation planner with a 5% cash reserve, 10% single-stock cap and 30% sector cap, requiring an explicit current capital snapshot.

## Not yet a live integration

- INDmoney direct account connection: no supported standalone API credential or authorised GitHub secret was configured. Use a user-exported transaction/watchlist CSV; do not put INDmoney credentials in the repository.
- Company financial filings/PDF/XBRL: the source-aware financial CSV model exists, but automated cross-company disclosure downloads and normalisation have not been implemented.
- Market breadth, corporate action adjustment, BSE data and benchmark-relative event studies are not yet included.
- GitHub Actions artifacts are run outputs, not a hosted persistent database. Local SQLite is persistent on the user's machine; hosted persistence requires a separately authorised database service.
- Research recommendations require reviewed inputs. This code does not fabricate target prices, fair values or BUY signals for stocks whose research fields are missing.
- External LLM/model integration and fully automated news ingestion are not configured; no model API secrets are assumed.

## Commands

See README.md for exact usage. The test suite validates the decision rules, parser, transaction calculations, event study and prior financial ingestion APIs.
