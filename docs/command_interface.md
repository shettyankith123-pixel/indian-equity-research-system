# Research command interface

The private repository supports a small command vocabulary. The GitHub Actions workflow named Research Command is the execution backend. In this ChatGPT conversation, the same phrases can be used directly; the assistant dispatches the matching workflow and interprets the returned artifact. GitHub is the backend, not the everyday interface.

## Supported phrases

| ChatGPT phrase | Workflow command | Inputs |
|---|---|---|
| MARKET BRIEF | market-brief | Optional trading date; blank discovers the latest available NSE UDiFF date |
| WEALTH SCAN | wealth-scan | None |
| COMPANY SCAN ICICI BANK | company-scan | Company name or NSE symbol |
| SECTOR SCAN BANKING | sector-scan | Sector name; shorthand such as IT, Banks and Auto is resolved |
| PORTFOLIO REVIEW | portfolio-review | Uses the latest committed INDmoney holdings snapshot |
| FIND OPPORTUNITIES | find-opportunities | Uses reviewed outside-watchlist inputs |

## How execution works

- A command is routed to one existing CLI entry point; there is no duplicate implementation of research logic.
- MARKET BRIEF fetches the latest available official NSE EOD file and calculates EOD breadth, gainers and laggards. Live headlines, global developments and news-to-stock explanation are a separate ChatGPT live-research step; this local report is not presented as a news feed.
- WEALTH SCAN creates the 64-stock decision register from reviewed research inputs. Until financial statements are normalized into valuation inputs, missing fields remain ASSESS.
- COMPANY SCAN resolves known issuer names to NSE symbols and uses the 64-company universe to show the correct sector.
- SECTOR SCAN returns all companies in that sector, including ASSESS rows where research inputs are incomplete.
- PORTFOLIO REVIEW uses a dated holdings snapshot when no transaction ledger is available. It explicitly states that trade dates, fees, taxes and historic cash flows are missing.
- FIND OPPORTUNITIES returns only outside-watchlist BUY/ACCUMULATE records that already pass the decision engine. With empty or incomplete research inputs, it returns no actionable candidates rather than inventing recommendations.

Each execution publishes a report artifact for 30 days. The workflow can also be started manually from GitHub Actions → Research Command, but users should normally type the phrase in ChatGPT.

## Current boundaries

The command router is an execution interface, not completion of every research workstream. It does not yet calculate full intrinsic values from the historical financial artifact, perform automatic governance assessments, import INDmoney transaction history, or place trades. A green workflow means the command ran; inspect coverage and data status before acting.
