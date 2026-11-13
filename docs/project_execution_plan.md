# Indian Equity Research System — Controlled Execution Plan

**Plan version:** 1.0  
**Status baseline:** 13 November 2026  
**Repository:** shettyankith123-pixel/indian-equity-research-system  
**Investor mandate:** Moderate-to-high risk; 7–10 year horizon; long-term wealth creation.

This document is the single source of truth for delivery status, dependencies, acceptance checks and run history. Update it after every meaningful milestone. Do not maintain competing status summaries elsewhere.

---

## 1. Delivery objective

Deliver an evidence-led research system that can:

1. Maintain verified daily NSE prices, volume and market breadth.
2. Maintain source-attributed quarterly and annual financial histories for the 64-stock watchlist.
3. Reconcile the user's holdings and transaction ledger.
4. Calculate sector-appropriate fair value, downside, upside, risk and valuation confidence.
5. Produce one decision per watchlist company and holding: BUY, ACCUMULATE, HOLD, WAIT, ASSESS, OBSERVE, REDUCE, EXIT or AVOID.
6. Rank new opportunities outside the current watchlist.
7. Produce a complete Wealth Scan with staged entry ranges and capital allocation only when deployable cash is known.
8. Schedule routine data updates and scans only after their inputs and outputs have passed acceptance checks.

The goal is not to force BUY recommendations. It is to identify genuine opportunities when the evidence supports them, and to use ASSESS where important evidence is missing.

## 2. Verified baseline — do not repeat these tasks without a reason

| Area | Last verified result | Evidence | Current status |
|---|---|---|---|
| Private GitHub repository | Private main branch exists | Repository access verified | Complete |
| Core Python test suite | Passed on commit 60cdb4e | [CI run 43442173107](https://github.com/shettyankith123-pixel/indian-equity-research-system/actions/runs/43442173107) | Green |
| NSE UDiFF daily ingestion | One official 11-Nov-2026 archive parsed; 3,462 equity records stored and artifact published | [NSE EOD run 43428505083](https://github.com/shettyankith123-pixel/indian-equity-research-system/actions/runs/43428505083) | Working; continue daily monitoring |
| 64-stock quote snapshot | 64 symbols captured from NSE connector with price and volume | Import snapshot dated 13-Nov-2026 | Complete as a dated snapshot |
| INDmoney holdings | Seven positions captured; ₹19,975.38 invested, ₹20,165.00 market value, ₹189.62 unrealised P&L | data/imports/indmoney_holdings_snapshot_2026-11-13.csv | Opening snapshot only |
| Financial filing parser | ICICI Q2 FY27 standalone filing fetched and PAT/period parsed | [XBRL smoke run 43430849252](https://github.com/shettyankith123-pixel/indian-equity-research-system/actions/runs/43430849252) | Proven for this issuer/filing |
| First 64-company financial import | Earlier importer run produced 8,911 observations; 63 companies had at least one quarterly filing, 61 at least one annual filing, and 61 had both | [Run 43433699162](https://github.com/shettyankith123-pixel/indian-equity-research-system/actions/runs/43433699162) | Historical baseline only; rerun after parser changes |
| Four-company filing sample | ICICI Bank, SBI, TCS and UltraTech produced 516 observations | [Run 43433502963](https://github.com/shettyankith123-pixel/indian-equity-research-system/actions/runs/43433502963) | Earlier parser version; use as regression reference |
| Latest XBRL context-selection change | Fact-aware selector and regression tests committed; CI passed | Commit 60cdb4e; [CI run 43442173107](https://github.com/shettyankith123-pixel/indian-equity-research-system/actions/runs/43442173107) | Code green; data subset not yet revalidated |
| Full Wealth Scan | Earlier price-only register returned 64 ASSESS because fair values and quality evidence were absent | reports/wealth-scan/ from first pass | Not an investment decision report |
| Historical INDmoney transactions | Not exposed by the holdings connector | No transaction-level export available | Awaiting user's broker export |
| Automated Wealth Scan schedule | Not activated | No completed end-to-end valuation output | Blocked by research readiness |

**Important:** The 8,911-observation database is an output from an earlier workflow run. It is not evidence that the latest parser version has passed a fresh 64-company import. Keep that distinction in every report.

## 3. Workstreams and strict dependency order

### Gate 0 — Repository and execution hygiene

**Status: Complete, maintenance ongoing**

- Preserve the original four watchlists and all 64 symbols.
- Keep main green. Every change must pass CI before a data run.
- Store source files, parser code, tests and workflow definitions in Git.
- Keep secrets and personal broker credentials out of Git.
- Keep each data run's database, CSV, coverage report, manifest and source hashes together as one immutable artifact.

**Acceptance:** tests pass on the current commit; watchlist count remains 64; the commit SHA is recorded.

### Gate 1 — NSE daily market data

**Status: Working; routine validation ongoing**

- Continue the existing weekday NSE UDiFF EOD workflow.
- Validate trading date, ZIP integrity, required CSV headers, symbol, OHLC, volume and duplicate rows.
- Compare imported row count and a sample of liquid/watchlist symbols with the source file.
- Retain each run's raw source/archive reference and normalized output.

**Acceptance:** successful workflow, correct requested trading date, non-zero records, no invalid OHLC/volume rows, and reproducible artifact.

Do not rerun a historical date already validated unless the source was corrected, code changed, or reconciliation found a discrepancy.

### Gate 2 — NSE financial filing ingestion

**Status: In progress; highest priority**

The new XBRL parser selects contexts using both period dates and presence of mapped facts. It has passed CI, but the latest real-filing subset has not yet passed.

**Test ladder — run strictly in this order:**

1. **Edge-case subset:** ICICIBANK, LT, VBL, ABB, SIEMENS, COALINDIA and MCX. Include one standard non-bank industrial/IT issuer if not already represented.
2. **Cross-sector subset:** one or two companies each from banking, IT, consumer, manufacturing/capital goods, metals/commodities and financial services.
3. **Full 64-stock universe:** only after steps 1 and 2 pass.

The edge-case set is deliberately small: it covers detailed filing contexts, non-March fiscal year-ends, half-year/transition periods, missing/renamed issuers and intermittent archive failures.

**Required parser fixes/checks before the full run:**

- Choose a context by matching start/end dates and mapped facts, not by context ID alone.
- Never label a 6-month or transition period as a 3-month quarter.
- Respect company-specific fiscal year-end dates.
- Resolve revised filings deterministically and retain sequence ID, publication date, source URL and XBRL SHA-256.
- Retry transient downloads with bounded backoff; distinguish 404, no filing and rate-limit/network errors.
- Keep reported, calculated and estimated observations distinct. Missing tags stay missing.
- Do not silently interpret zero/missing values as the same thing.
- Verify units and scale using the filing's displayed statements for a sample from each sector.
- Prevent duplicate source observations on repeat runs.
- Never delete the last successfully validated database when a new run starts. Write each run to a unique output directory/artifact and promote it to current only after validation.

**Coverage acceptance for a company:** a filing listing is resolved; available period/basis combinations are recorded; at least one usable recent financial statement is parsed; source reference and period are retained; and parse gaps are listed explicitly.

**Universe acceptance:** 64/64 companies have a recorded status. Do not require every company to publish every basis/period, but do require every absence or unsupported filing to have a reason. The report must show coverage by symbol, period and basis—not only a green workflow badge.

### Gate 3 — Financial normalization and quality controls

**Status: Pending Gate 2 revalidation**

- Persist quarterly and annual observations in the existing financial model/SQLite schema.
- Add unit tests for money scale, EPS, dates, standalone/consolidated separation, revisions and flow-vs-instant facts.
- Build sector-appropriate derived metrics:
  - Banks/NBFCs: NIM, ROA, ROE, GNPA/NNPA, credit cost, capital adequacy, deposit/loan growth and CASA where reported.
  - IT/services: revenue growth, margins, cash conversion, attrition where sourced, order book where reported.
  - Consumer/FMCG: volume/value growth where disclosed, gross/EBITDA margins, return ratios and cash generation.
  - Industrial/manufacturing: order book, execution, working capital, margins, ROCE and leverage.
  - Metals/mining/energy: production, realization, costs, leverage, capex and cycle sensitivity.
  - Financial platforms/market infrastructure: operating metrics, yield/take-rate, client activity, regulatory concentration and cash conversion.
- Mark a metric unavailable when it is not disclosed or not yet mapped.

**Acceptance:** each metric has formula, unit, source and period; calculated metrics reconcile to underlying reported observations; no cross-company or cross-period source mixing.

### Gate 4 — Portfolio reconciliation

**Status: Partially complete**

- Keep the seven-position INDmoney snapshot as the opening balance.
- Import the user's transaction export to reconstruct dates, buys/sells, quantities, prices, charges, taxes and cash movements.
- Reconcile quantities and average cost to the current INDmoney holdings snapshot.
- Keep long-term positions separate from swing trades.
- Never infer missing fills or use a wallet balance as investable cash without confirming its meaning.

**Acceptance:** transaction ledger quantities and average costs reconcile to INDmoney; unresolved differences are flagged; cash available for new investment is explicitly dated.

**User dependency:** a transaction/order/trade history CSV export from INDmoney is required for full historical reconciliation. This is not available through the current holdings connector.

### Gate 5 — Sector valuation and company research

**Status: Framework only; full research pending Gates 2–4**

- Use separate valuation models by sector. Do not apply bank P/B models to industrial or IT companies.
- Estimate bear/base/bull values from reported financials and explicit assumptions.
- Add business quality, earnings durability, balance-sheet strength, governance, capital allocation, management execution, sector risk and data confidence.
- Track source and as-of date for every important assumption.
- Keep broker target prices as sentiment context only; never substitute them for intrinsic fair value.

**Acceptance per stock:** a reviewed financial history, sector-specific ratios, valuation model, bull/base/bear fair value, current price timestamp, risk register, confidence rating and primary-source references. A stock failing this gate remains ASSESS.

### Gate 6 — Recommendation and allocation engine

**Status: Decision rules exist; complete research integration pending Gate 5**

Use the existing decision categories and investor mandate:

- **BUY:** attractive risk/reward, research completeness and valuation confidence gates all pass.
- **ACCUMULATE:** attractive long-term business and acceptable valuation; build in tranches.
- **HOLD:** existing thesis remains valid.
- **WAIT:** business is attractive but price/conditions are not.
- **ASSESS:** key evidence missing or contradictory.
- **OBSERVE:** early-stage candidate not ready.
- **REDUCE / EXIT:** thesis, risk or portfolio exposure requires action.
- **AVOID:** fails investment criteria.

Current code policy requires at least 85% data completeness, 65% valuation confidence, recent source data, quality gates and a margin of safety to the base fair value (15% for BUY; 8% for ACCUMULATE). These are gates to review and calibrate—not a quota for BUY recommendations.

For each actionable idea, show an entry range, staged tranches, downside, thesis invalidation conditions, position-size ceiling and what evidence would change the recommendation.

**Capital allocation is blocked until a dated deployable-cash figure and portfolio exposure snapshot are available.** No amount is to be invented.

### Gate 7 — Full Wealth Scan and opportunity discovery

**Status: Not ready**

The Wealth Scan will include:

- Decisions for all 64 watchlist names, with clear reasons and evidence gaps.
- Separate decisions for current holdings (including HOLD vs fresh-entry WAIT distinction).
- Best current BUY/ACCUMULATE candidates and entry ranges.
- Suggested allocation only where cash and concentration data are known.
- Outside-watchlist opportunities and IPOs only when researched to the same evidence standard.
- Previous recommendation vs subsequent price/fundamental outcome tracking.

**Acceptance:** 64/64 decision rows; every fair value sourced and dated; every BUY/ACCUMULATE passes the configured gates; allocation totals reconcile to known capital; report includes explicit data-gap count.

### Gate 8 — Scheduling and monitoring

**Status: NSE EOD schedule enabled; full Wealth Scan schedule blocked**

- Keep weekday NSE EOD collection active.
- Keep financial data collection separate from recommendation generation.
- Schedule Wealth Scan only after the full financial import and valuation gates pass.
- Run on a fixed weekly cadence after the latest filings and price snapshot are available.
- Avoid duplicate scans for the same input snapshot hash.
- Alert only on meaningful recommendation/valuation/financial changes, new actionable opportunities or failed data quality checks.
- Retain artifacts and a run manifest so every report can be reproduced.

**Acceptance:** two consecutive scheduled cycles complete; both have valid input freshness, coverage and artifacts; no duplicate reports for identical input hashes.

---

## 4. Time-management and anti-rework rules

These rules apply to every future work session:

1. **One source of truth:** update this plan and its run ledger; do not create a new competing status document.
2. **Batch work:** inspect related files together, implement a coherent change set, run local tests once, commit once, then verify CI once.
3. **Test small before large:** edge-case subset → cross-sector subset → 64-company universe. Never launch a full run to debug a known subset failure.
4. **Checkpoint each data run:** record commit SHA, workflow run ID, requested symbols/date range, artifact ID, source hashes, counts and status.
5. **No duplicate runs:** if the current commit and source snapshot already have a successful run, reuse the artifact. Re-run only for changed code, changed source, invalid output or explicit refresh.
6. **No destructive refresh:** never overwrite or delete the last known-good database before a replacement has passed validation.
7. **Separate code success from data success:** CI green does not mean the financial universe is complete; a workflow success does not mean every symbol parsed.
8. **Separate data success from investment readiness:** reported results alone do not imply fair value or BUY.
9. **One consolidated user update per milestone:** no narration of every tool call. Ask the user only for a true external dependency, and batch all required inputs into one request.
10. **Stop at the acceptance gate:** do not start dependent work while its required inputs are invalid or missing.

## 5. Blockers and user inputs

Only request these when the relevant gate is reached:

| Needed input | Why it is needed |
|---|---|
| INDmoney transaction/order history CSV export | Reconstruct historical portfolio trades, charges, taxes and cash movement |
| Dated deployable investment capital | Calculate staged allocations and position sizes |
| Optional company filings not accessible through NSE | Fill issuer-specific gaps when the exchange XBRL feed does not expose a usable filing |

No broker password, OTP, session cookie or personal access token should be requested in chat or committed to Git.

## 6. Run ledger

Append one row for each meaningful run. Do not remove failed runs; they explain why a fix was needed.

| Date (UTC) | Commit / code | Workflow run | Scope | Result | Reuse / next action |
|---|---|---|---|---|---|
| 2026-11-13 | d39ba3d | [43428505083](https://github.com/shettyankith123-pixel/indian-equity-research-system/actions/runs/43428505083) | NSE UDiFF, 2026-11-11 | Passed; 3,462 equity records | Reuse unless source/parser changes |
| 2026-11-13 | 50652e3 | [43433502963](https://github.com/shettyankith123-pixel/indian-equity-research-system/actions/runs/43433502963) | ICICI, SBI, TCS, UltraTech | Passed; 516 observations | Cross-sector reference for earlier parser |
| 2026-11-13 | 50652e3 | [43433699162](https://github.com/shettyankith123-pixel/indian-equity-research-system/actions/runs/43433699162) | Full 64-company financial import | Passed; 8,911 observations; partial period coverage | Historical baseline, not latest-code signoff |
| 2026-11-13 | 0c68c15 | [43441345492](https://github.com/shettyankith123-pixel/indian-equity-research-system/actions/runs/43441345492) | Six edge-case issuers | Failed; exposed filing context/period issues | Do not repeat unchanged |
| 2026-11-13 | 60cdb4e | [43442173107](https://github.com/shettyankith123-pixel/indian-equity-research-system/actions/runs/43442173107) | Core CI after fact-aware XBRL selector | Passed | Next: run the small edge-case subset on this code |

---

## 7. Immediate next actions

1. Inspect and fix the remaining parser issues identified by the six-company run; add a regression test for each discovered taxonomy/period case.
2. Run the seven-company edge-case subset once on the corrected commit.
3. If it passes, run the cross-sector subset once.
4. Only then run the full 64-company import and publish one complete coverage/financial database artifact.
5. Normalize financial metrics and validate units/ratios before starting full fair-value work.
6. Request the transaction CSV and investable cash together when portfolio allocation work is ready.
7. Build and verify the first full Wealth Scan; only then activate its schedule.

**No time estimate is recorded here.** Work advances by completed acceptance gates, not by promising a finish date that depends on unverified data and external exports.


### Gate 9 — Chat command interface

**Status: Complete — CI and a real GitHub Actions command dispatch passed**

The command layer accepts natural phrases and routes them to the existing CLI:
- MARKET BRIEF — latest available NSE EOD breadth in the local runner; ChatGPT performs the live-news narrative separately.
- WEALTH SCAN — 64-stock decision register from reviewed research inputs.
- COMPANY SCAN <company> — resolves names/symbols against the universe manifest.
- SECTOR SCAN <sector> — includes all universe constituents and explicit ASSESS rows for missing research.
- PORTFOLIO REVIEW — uses the dated broker holdings snapshot and marks missing transaction history.
- FIND OPPORTUNITIES — returns only outside-watchlist candidates that pass the existing action gates.

A manual Research Command GitHub Actions workflow uploads each report artifact. CI passed on commit 2525004. A real PORTFOLIO REVIEW dispatch completed successfully (workflow run 43452523021; artifact 14053355189). Local smoke tests passed for all six commands. A command run is not proof that the underlying research is investment-ready; source coverage and valuation gates remain in force.

**Acceptance: PASSED** — command aliases and company/sector resolution pass unit tests; market data and portfolio snapshot commands are smoke-tested; CI is green; GitHub workflow succeeds and publishes a report artifact. The local market report is EOD breadth; live-news narrative is added by ChatGPT separately.



## 8. Command-interface milestone update — 13 November 2026

- Friendly command routes added to the CLI.
- Company name resolution and sector universe coverage added.
- Portfolio review reads the saved 7-position INDmoney snapshot and labels it snapshot-only.
- Latest-available NSE EOD helper added; 11-Nov-2026 smoke returned 3,462 equity records.
- Manual Research Command workflow added for six supported command types.
- Local validation: Python compilation passed; full unit suite passed; CLI smoke passed for WEALTH SCAN, COMPANY SCAN, SECTOR SCAN, PORTFOLIO REVIEW, FIND OPPORTUNITIES and MARKET BRIEF.
- Remaining: commit the command interface, verify GitHub CI and one dispatched GitHub command artifact. Financial valuation and complete investment recommendations remain separate unfinished gates.


| 2026-11-13 | 2525004 | [43452523021](https://github.com/shettyankith123-pixel/indian-equity-research-system/actions/runs/43452523021) | Research Command → portfolio-review | Passed; artifact 14053355189 published | Reuse command dispatcher; future chat commands dispatch same workflow |


## 9. MCX BSE financial-source fallback — 14 November 2026

**Status: Partial coverage integrated; source and automated import validated**

NSE Integrated Filing returns no MCX listing rows, including after the symbol-only retry. MCX's official BSE Q2 FY27 attachment was therefore inspected as a separate exchange source:
- BSE Scrip: 534091; NSE symbol: MCX.
- Publication date: 3 November 2026.
- Source reference: BSE:534091:2026-11-03:Q2FY27:006dffdb.
- The consolidated P&L statement is a scanned page, visually checked and cross-checked with one OCR pass.
- 24 reported observations are preserved in data/imports/mcx_bse_q2_fy27_observations.csv: revenue from operations, total expenses, PAT and basic EPS for Q1 FY27, Q2 FY27, Q2 FY26, H1 FY27, H1 FY26 and audited FY26.
- Each observation retains the official BSE PDF URL, publication date and filing reference.
- The canonical CSV loader now accepts the explicit transition_period model kind.
- The scheduled/manual NSE financial workflow imports the MCX CSV into its own unique run database before artifact upload.

**Validation:** 5 focused tests passed (24-row parser/provenance and SQLite round-trip plus existing CSV loader tests); workflow YAML parses and the new shell step passes bash -n.

**Data boundary:** This fallback imports the consolidated P&L/EPS fields only. It does not yet import MCX standalone data, balance-sheet instant facts or cash-flow figures. MCX NSE XBRL listing coverage remains zero; the BSE source is a clearly labelled separate-source fallback.

**Still open:** Siemens's disclosed 18-month 2024-10-01 to 2026-03-31 transition year has no matching 18-month context in the inspected NSE XBRL attachment; normal annual extraction is deliberately rejected for that target. The cross-sector batch and full 64-company import must wait for these source-specific rules and remaining issuer checks to pass.
