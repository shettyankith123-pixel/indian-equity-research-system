# Indian Equity Research System — Project Tracker

Last checkpoint: 2026-11-15 (Asia/Dubai)
Repository: https://github.com/shettyankith123-pixel/indian-equity-research-system
Branch: main
Current reviewed commit: 7bfa4aaed024ec5d612db963b2457a3210cda9a5

## Operating agreement
- Work in milestones and deliver investor-facing outputs, not endless code churn.
- Every user update must show the overall completion percentage, concrete change since the prior checkpoint, pending work and next milestone.
- Percentage measures the usable end-to-end product, not code volume, tests passed or commits.
- Save meaningful checkpoints here. A new chat should read this file first and continue from the saved run IDs and artifacts without asking the user to repeat context.
- Avoid repeated work: use one current ingestion run, retain/download artifacts once, deduplicate source filings, cache by stable source/reference/content hash, use focused tests while editing and run the full suite at integration checkpoints.
- No fabricated financial facts, management/governance conclusions, quality scores, fair values or investment calls. Material claims need source, source date and research date.
- Keep BUY/ACCUMULATE gates strict. Missing evidence remains visible as ASSESS/OBSERVE/WAIT as appropriate.
- User mandate: moderate-to-high risk tolerance, 7–10-year horizon, long-term wealth creation; actively seek opportunities and stage entries without manufacturing BUY calls.
- Work here is synchronous. Do not promise background execution or later delivery.

## Overall completion
<current_score>34%</current_score>

The score stays at 34% until actual 64-company financial coverage and FCFE results are produced. Code implementation, green CI and workflow setup alone do not increase the investor-facing completion percentage.

### Fixed weights (100 total)
| Workstream | Weight | Evidence needed for full credit |
|---|---:|---|
| Platform, 64-stock universe, market-price and portfolio foundation | 15% | Reproducible repo, 64-stock universe, timestamped market data, clear portfolio-import boundaries |
| Annual/quarterly financial history and FCFE quality | 20% | Pagination, reconciled source-attributed periods, coverage matrix for all 64, three consecutive verified FCFE years where applicable, sector exceptions |
| Company quality, management, governance and thesis research | 20% | Sector-aware evidence-backed assessments with sources/dates, risks, counter-evidence and invalidation conditions |
| Sector valuation and decision engine | 15% | Appropriate sector models, bear/base/bull scenarios, fair-value and entry ranges, confidence and tested decision gates |
| Investor-facing Wealth Scan and portfolio action plan | 10% | Full 64-stock register, holding-vs-new-buyer distinctions, triggers and allocation only with current holdings/cash |
| Opportunity discovery, news/IPO/sector intelligence | 10% | Evidence-based outside-watchlist opportunities, IPO coverage and tested news/company mapping |
| Research memory, impact validation and reliability | 10% | Saved original calls; T+1/T+3/T+5/T+10/T+20 outcome checks; benchmark comparison and reliable refresh/freshness |

### Baseline breakdown — still the current score
| Workstream | Earned | Current evidence |
|---|---:|---|
| Platform and data foundation | 15/15 | Repo, 64-stock universe, quote snapshots, market ingestion, CLI/SQLite foundation and CI |
| Financial history and FCFE | 4/20 | Importer, true-FCFE formula and pagination implementation exist; full-universe annual/FCFE coverage not yet proven |
| Company quality and governance | 1/20 | Decision gates exist; repeatable management/governance/thesis evidence layer is not populated |
| Valuation and decision engine | 7/15 | Sector valuation and deterministic decision rules exist; no completed fair values in the inspected Wealth Scan |
| Wealth Scan and portfolio action | 3/10 | 64-row report/register exists, but inspected report has 64 ASSESS |
| Opportunity/news/IPO intelligence | 2/10 | Templates/framework and event/news structures exist; complete automated workflow is not built |
| Research memory/performance | 2/10 | Event-study and EOD foundation exist; longitudinal call scorecard not complete |
| **Total** | **34/100** | **Functioning research foundation, not yet an investment-ready decision product** |

## What was verified before this development session
- Latest baseline code commit inspected: `a8777a5804a6e07d83ce48fea18024ec7334d482`.
- The checked-in Wealth Scan report and decision register contained 64 stocks, 64 prices, zero base fair values and 64 ASSESS decisions. This is a data-readiness report, not an investment decision report.
- A prior full NSE ingestion (run 43645167461) produced 12,807 normalized financial observations; 63 companies returned filings, 62 had annual filings, one had a transition-period filing and one had no NSE filing records. It recorded exceptions including LT, Siemens, CGPOWER and MCX.
- In that old import, most issuers had only two consolidated annual periods. It is not evidence that the page-1-limited importer provided three-year annual coverage.
- The repository documentation says no direct authorized INDmoney API credential is configured in GitHub Actions, no hosted persistent database is configured, and no external LLM/news model is connected. Use supported exports and connected tools; do not assume those integrations exist.

## M1 — Historical financial coverage: implementation status

### Completed and committed
1. **NSE filing pagination** — the importer now fetches every available page using the NSE `totalCount` and page-size metadata; validates the NSE zero-based response page against one-based request parameters; de-duplicates repeated filing rows; keeps the latest revision; fails rather than silently truncating when the expected final page is missing; uses a safe maximum page count.
   - Code commit: `c753bf8493d0d60cf60349a6e952435befa04254`
   - Main files: `src/indian_equity_research/ingestion/nse_filing_client.py`, `tests/test_nse_filing_client.py`
   - A first implementation failed live because NSE response `page` is zero-based. The convention is now explicitly handled and covered by regression tests.
2. **True-FCFE annual audit** — added a reusable audit tool that mirrors the fundamentals normalizer: true FCFE = CFO - abs(capex) + (current closing debt - prior-year closing debt). Current debt must be from the same XBRL filing reference as annual cash flows; prior debt must come from the same basis/source 330–400 days before year-end. Missing inputs are not imputed as zero. Banks are routed to bank-specific valuation rather than a generic FCFE DCF.
   - Commit: `ac086ae056f637209515bdec26e554ce416b4ae6`
   - Files: `scripts/build_financial_coverage_report.py`, `tests/test_financial_coverage_report.py`
   - Outputs: `company_financial_coverage.csv`, `annual_fcfe_audit.csv`, `financial_coverage_summary.json`, `financial_coverage.md`
3. **Test import correction** — the audit tests load the standalone script explicitly by path; they no longer assume `scripts` is an installed Python package.
   - Commit: `4096a99f802feaba4364a25b31f964ba5e4c591a`
4. **Automatic coverage report in future imports** — the NSE financial ingestion workflow now runs the FCFE audit after raw financial normalization and includes the reports in the same uploaded artifact.
   - Commit: `7bfa4aaed024ec5d612db963b2457a3210cda9a5`
   - Workflow: `.github/workflows/nse-financials-ingest.yml`

### Verified CI
- Pagination/test fix passed: https://github.com/shettyankith123-pixel/indian-equity-research-system/actions/runs/43652159517
- FCFE audit test import correction passed: https://github.com/shettyankith123-pixel/indian-equity-research-system/actions/runs/43652641200
- Automated workflow integration commit passed unit tests: https://github.com/shettyankith123-pixel/indian-equity-research-system/actions/runs/43652859072

These prove unit tests and workflow syntax/configuration checks pass. They do not prove actual 64-stock annual/FCFE coverage.

### The one current full-universe import — do not duplicate
- Run ID: `43652209994`
- URL: https://github.com/shettyankith123-pixel/indian-equity-research-system/actions/runs/43652209994
- Branch: main; code SHA: `c753bf8493d0d60cf60349a6e952435befa04254`
- Parameters: all 64 symbols; 4 quarterly periods and 3 annual periods per reporting basis.
- Last verified status: `in_progress`, job `ingest-financials`; the financial-fetch/normalization step was still running.
- This run started before the FCFE audit workflow step was committed. Its artifact will contain the normalized CSV and filing coverage but not the new FCFE report; run the audit script once manually against its artifact after it completes.
- Do not dispatch another full import unless this run fails or the artifact is corrupt/missing. Do not re-run the whole import merely to attach the audit step.
- After the artifact is downloaded, analyze the real files and save the reports/checkpoint. Future scheduled/manual imports will include the audit automatically.

## M1 acceptance criteria still outstanding
1. Confirm the current run finishes successfully and upload artifact exists.
2. Produce a coverage matrix for all configured 64 symbols: annual dates, consolidated/standalone, transition periods, filing refs, conflicts and exact errors.
3. Calculate strict true-FCFE for each annual period and verify three consecutive years wherever applicable. Record missing CFO/capex/current debt/prior debt facts separately.
4. Route banks/financial institutions to sector-appropriate valuation, with explicit reasons.
5. Commit the human-readable report, machine-readable CSV/JSON and updated tracker.
6. Only then increase the financial-history workstream score and overall percentage.

## Next action
Poll run `43652209994`. When it succeeds, download its artifact once, execute `scripts/build_financial_coverage_report.py` once against the artifact CSVs, inspect the results for schema/calculation errors, commit the coverage report and checkpoint, and update the total percentage only after the M1 acceptance criteria are met.

## Remaining milestones
- **M2 — Company-quality research:** evidence-backed sector-aware business, competitive, management/capital allocation, governance/compliance and qualitative thesis assessments. Every assessment stores source URL, publication date, research date, confidence, counter-evidence and review/invalidation trigger. Missing evidence stays unassessed; an LLM may summarize sources but may not invent facts or self-certify high scores.
- **M3 — Valuation and decision engine:** sector-specific valuation, scenarios, sensitivity, fair value and entries; every stock receives a defensible decision or a specific missing-evidence status.
- **M4 — Investor-facing Wealth Scan:** full 64-stock decisions, actual holdings distinctions, best current opportunities, wait triggers, risk and concentration review, capital plan only with current cash/holding data, outside-watchlist ideas and comparison to prior scan.
- **M5 — Broader intelligence and learning:** global/Indian news, sector developments, IPOs, outside-watchlist discovery and research-outcome tracking against relevant market/sector benchmarks.


## 2026-11-15 — First investor-facing holdings research checkpoint
- Added reports/wealth-scan/holdings-research-batch-2026-11-15.md.
- Retrieved live INDmoney Indian equity holdings directly; seven holdings confirmed: TCS (5), POWERGRID (10), SBIN (2), ICICIBANK (1), NMDC (15), VBL (1), MOTHERSON (2).
- Holdings value ₹20,165; invested ₹19,975.38; unrealised P&L +₹189.62; TCS weight 59.7%.
- Researched all seven holdings using latest available 13-Nov-2026 NSE close, Q2 FY27 / Q3 CY26 company results, current market valuation snapshots and INDmoney analyst/news feed.
- Preliminary action labels: TCS HOLD (no add due concentration); POWERGRID ACCUMULATE GRADUALLY; SBI ACCUMULATE GRADUALLY; ICICI Bank HOLD (add only on pullback); NMDC HOLD/WAIT; VBL WAIT; MOTHERSON HOLD.
- Important limitation: no intrinsic fair value or formal governance certification assigned; annual true-FCFE coverage and full management/governance work remain incomplete. Analyst targets are not treated as fair value.
- Overall completion remains 34%. This is a tangible first-pass research deliverable, but it does not satisfy full 64-stock financial/quality/valuation acceptance criteria.
- Next milestone: complete the remaining 57 stocks by sector, then formal governance/management checks and sector-specific bear/base/bull valuation before promoting provisional calls.


## 2026-11-15 checkpoint — first actual holdings research tranche
- Retrieved current Indian-stock holdings from connected INDmoney: 7 holdings, ₹20,165 market value, ₹19,975.38 invested, +₹189.62 unrealised P&L, -₹237.21 one-day change.
- TCS is 59.70% of the Indian-stock book; Power Grid 12.77%, SBI 10.71%, ICICI Bank 7.85%, NMDC 5.19%, Varun Beverages 2.15%, Motherson 1.63%.
- Completed provisional position/company reviews for all 7 holdings using latest Q2 FY27 / Q3 CY2026 results, company releases, account market snapshot and recent news. Saved all 7 analyses to INDmoney; all confirmed saved=true and data_verified=true.
- Durable report: `reports/wealth-scan/holding-review-2026-11-15.md`.
- Portfolio actions: TCS HOLD / no additions due to concentration; SBI ACCUMULATE in tranches; Power Grid selective ACCUMULATE with sizing discipline; ICICI HOLD / wait; NMDC, VBL and Motherson HOLD / WAIT.
- This is holdings-only, not the full 64-stock Wealth Scan. No independent fair values or cash allocation were invented. Governance diligence and intrinsic valuation remain open.
- Completion score updated conservatively from 34% to **36%**: company-quality/thesis work 1/20 → 2/20 (partial; 7 holdings only, governance checks incomplete); investor-facing Wealth Scan/action plan 3/10 → 4/10 (actual holdings and concentration now incorporated). Other workstreams unchanged.
- Next milestone: research the full 64-stock universe by sector; complete board/auditor/related-party/pledge checks and sector-specific valuation before permitting final BUY/ACCUMULATE calls.


## 2026-11-15 — Core Long-Term watchlist research checkpoint
- Added reports/wealth-scan/core-watchlist-batch-1-2026-11-15.md.
- Completed preliminary, evidence-linked screens for HCLTECH, POLYCAB, ULTRACEMCO, PIDILITIND, M&M, MARUTI, APOLLOHOSP and SUNPHARMA.
- Combined first-pass coverage now stands at 15/64 names: seven confirmed account holdings plus eight watchlist-only Core Long-Term names.
- Provisional labels in this batch: HCLTECH ACCUMULATE ON DIPS; POLYCAB ACCUMULATE ON CORRECTIONS; ULTRACEMCO HOLD/WAIT; PIDILITE WAIT; M&M ACCUMULATE GRADUALLY; MARUTI WAIT; APOLLOHOSP HOLD/WAIT; SUNPHARMA HOLD/WAIT.
- No intrinsic fair values or formal governance verdicts were assigned. Primary-source verification of selected legal/regulatory items remains open.
- Overall project completion remains 34%; first-pass screening does not satisfy the full 64-stock annual-FCFE, governance and valuation acceptance criteria.
- Next milestone: complete INFY, BAJFINANCE, LT, NTPC and RELIANCE before moving to the next sector group.


## 2026-11-15 — Core Long-Term watchlist research checkpoint 2
- Added reports/wealth-scan/core-watchlist-batch-2-2026-11-15.md.
- Completed preliminary screens for INFY, BAJFINANCE, LT, NTPC and RELIANCE.
- First-pass coverage now stands at 20/64 configured names: seven actual holdings plus 13 additional watchlist-only names.
- Provisional labels: INFY WAIT; BAJFINANCE HOLD/WAIT; LT HOLD/ACCUMULATE ONLY ON CORRECTIONS; NTPC ACCUMULATE GRADUALLY; RELIANCE ACCUMULATE GRADUALLY.
- News/legal items requiring primary verification are explicitly flagged, not treated as confirmed risk scores.
- Overall completion remains 34%; full financial-history/FCFE, governance and intrinsic valuation gates are not yet met.
- Next: continue sector groups after this Core Long-Term batch; then formal governance and valuation passes.


## 2026-11-15 — Core Long-Term group first-pass complete
- Added reports/wealth-scan/core-watchlist-batch-3-2026-11-15.md.
- Completed preliminary screens for MARICO, HINDUNILVR and ITC.
- All 20 configured Core Long-Term names now have a preliminary screen: four are actual holdings (TCS, SBIN, ICICIBANK, POWERGRID); 16 are watchlist-only.
- Provisional labels in this batch: MARICO WAIT; HINDUNILVR ACCUMULATE GRADUALLY ON CORRECTIONS; ITC ACCUMULATE GRADUALLY.
- First-pass total across the 64-stock universe now stands at 23/64 (seven actual holdings plus 16 additional watchlist-only names). Note overlap: the Core Long-Term group has 20 names and four are already included in the seven account holdings.
- Overall project completion remains 34%; full annual-FCFE, governance and intrinsic valuation gates are still unmet.
- Next milestone: begin the Growth/Compounders group.


## 2026-11-15 — Growth & Compounders research checkpoint 1
- Added reports/wealth-scan/growth-compounders-batch-1-2026-11-15.md.
- Completed preliminary screens for ASTRAL, SUPREMEIND, KEI, HDFCAMC, CAMS, MANKIND, TVSMOTOR and RADICO.
- MOTHERSON and VBL were already screened as current holdings; thus 10/19 Growth & Compounders names now have first-pass coverage. Remaining: OFSS, COFORGE, PERSISTENT, SIEMENS, ABB, CUMMINSIND, CGPOWER, HAL and BEL.
- Provisional labels: ASTRAL WAIT; SUPREMEIND ACCUMULATE ON CORRECTIONS; KEI ACCUMULATE GRADUALLY ON WEAKNESS; HDFCAMC HOLD/WAIT; CAMS ACCUMULATE ON CORRECTIONS; MANKIND WAIT; TVSMOTOR HOLD/WAIT; RADICO WAIT.
- Total first-pass universe coverage now 31/64 (23 prior plus eight in this batch). Overall project completion remains 34% because full FCFE, governance and intrinsic valuation acceptance gates are still unmet.


## 2026-11-15 — Growth & Compounders group first-pass complete
- Added reports/wealth-scan/growth-compounders-batch-2-2026-11-15.md.
- Completed preliminary screens for OFSS, COFORGE, PERSISTENT, SIEMENS, ABB, CUMMINSIND, CGPOWER, HAL and BEL.
- All 19 configured Growth & Compounders names now have first-pass coverage, including MOTHERSON and VBL screened earlier as actual holdings.
- Provisional labels: OFSS ACCUMULATE ON CORRECTIONS; COFORGE HOLD/WAIT; PERSISTENT WAIT; SIEMENS HOLD/WAIT; ABB WAIT; CUMMINSIND WAIT; CGPOWER WAIT; HAL HOLD/WAIT; BEL ACCUMULATE ONLY ON CORRECTIONS.
- Total first-pass universe coverage now stands at 40/64: all 20 Core Long-Term names, all 19 Growth & Compounders names, plus NMDC from the Cyclical group.
- Overall project completion remains 34%; full annual-FCFE, governance and intrinsic valuation acceptance gates are still unmet.
- Next milestone: begin the 16-name Cyclical group.


## 2026-11-15 — Cyclical research checkpoint 1
- Added reports/wealth-scan/cyclical-batch-1-2026-11-15.md.
- Completed preliminary screens for DALBHARAT, SRF, NAVINFLUOR, FLUOROCHEM, DEEPAKNTR, PIIND, HINDALCO and JSWSTEEL.
- NMDC was already screened as a current holding; therefore 9/16 Cyclical names now have first-pass coverage. Remaining: TATASTEEL, COALINDIA, HINDZINC, BHEL, TATAPOWER, GAIL and ONGC.
- Provisional labels: DALBHARAT WAIT; SRF ACCUMULATE GRADUALLY ON WEAKNESS; NAVINFLUOR WAIT; FLUOROCHEM WAIT; DEEPAKNTR HOLD/ACCUMULATE AFTER CASH-FLOW CONFIRMATION; PIIND WAIT; HINDALCO ACCUMULATE GRADUALLY; JSWSTEEL HOLD/WAIT.
- Total first-pass universe coverage now stands at 48/64. Overall project completion remains 34% because full annual-FCFE, governance and intrinsic valuation acceptance gates remain open.
