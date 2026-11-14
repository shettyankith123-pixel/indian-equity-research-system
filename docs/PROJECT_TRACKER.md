# Project execution tracker — Indian Equity Research System

Last checkpoint: 2026-11-15 (Asia/Dubai)
Repository: https://github.com/shettyankith123-pixel/indian-equity-research-system
Default branch: main
Baseline commit reviewed: a8777a5804a6e07d83ce48fea18024ec7334d482

## Operating agreement

- The user wants milestone-led execution, not repeated planning or code-only progress.
- Every progress update must include one overall completion percentage, what changed since the last checkpoint, what remains, and the next milestone.
- The percentage measures investor-facing product capability, not code volume, number of commits, or green CI runs.
- Save each meaningful milestone to this repository. A new chat must resume from this file and the linked artifacts rather than asking the user to repeat context.
- Avoid repeated work: cache downloaded filings, key them by stable source/reference and content hash, deduplicate observations, run focused tests during development, and run the full suite at integration checkpoints.
- Do not invent financial facts, company-quality scores, fair values, management assessments, governance conclusions, or BUY recommendations. Every material claim needs a source and date.
- Preserve the BUY/ACCUMULATE evidence gates. Missing or low-confidence evidence must remain explicit (ASSESS/OBSERVE/WAIT as appropriate).
- Do not describe a workflow as financially complete merely because GitHub Actions passed.
- User mandate: moderate-to-high risk tolerance, 7–10 year horizon, long-term wealth creation; seek attractive opportunities and allow staged entry without manufacturing BUY calls.
- Work in this chat is synchronous only. No background execution or future delivery is available. Continue as far as tools permit in each active session and commit verified checkpoints.

## Completion measure

Overall progress is weighted by the usable end-to-end product, with these fixed weights (100 total):

| Workstream | Weight | Evidence required for full credit |
|---|---:|---|
| Platform, 64-stock universe, market-price and portfolio foundation | 15% | Reproducible repository, CI, 64-stock universe, timestamped market data, clear portfolio-import boundaries |
| Annual/quarterly financial history and FCFE quality | 20% | Pagination handled; source-attributed periods reconciled; coverage report for all 64; three consecutive verified FCFE years wherever applicable; explicit sector-specific exceptions |
| Company-quality, management, governance and thesis research | 20% | Evidence-backed, sector-aware assessments with source/date, risk flags, thesis, counter-thesis and invalidation conditions; no inferred scores presented as facts |
| Sector valuation and decision engine | 15% | Appropriate valuation methods, bear/base/bull scenarios, fair-value ranges, entry levels, confidence and tested BUY/ACCUMULATE/HOLD/WAIT/ASSESS/OBSERVE/REDUCE/EXIT/AVOID rules |
| Investor-facing Wealth Scan and portfolio action plan | 10% | Full 64-stock decision register, existing-holding distinction, actionable reasons/triggers, allocation only with current capital/holdings data |
| Opportunity discovery, news/IPO/sector intelligence | 10% | Outside-watchlist candidates and IPO coverage with evidence and a tested company/news relevance workflow |
| Research memory, impact validation and operational reliability | 10% | Original calls retained; T+1/T+3/T+5/T+10/T+20 outcome evaluation; benchmarks; reproducible scheduled data refresh and clear freshness status |

### Baseline score at this checkpoint: 34% complete

| Workstream | Earned | Reason |
|---|---:|---|
| Platform and data foundation | 15/15 | Repository, 64-stock universe, quote snapshots, market-data ingestion, CLI/SQLite foundation and CI exist |
| Financial history and FCFE | 4/20 | NSE/XBRL importer and true-FCFE calculation logic exist; filing pagination and full-universe verified multi-year coverage are not yet proven |
| Company-quality and governance | 1/20 | Decision inputs/gates exist, but management, governance and qualitative thesis evidence are not populated as a repeatable assessment layer |
| Valuation and decision engine | 7/15 | Sector valuation and deterministic decision rules exist; current generated register has no populated fair values or completed quality evidence |
| Wealth Scan and portfolio action | 3/10 | A 64-row report/register is generated, but the latest inspected report classified all 64 as ASSESS |
| Opportunity/news/IPO intelligence | 2/10 | Some framework, templates and event/news structures exist; full automatic intelligence flow is not complete |
| Research memory and performance | 2/10 | Event-study and scheduled EOD foundation exist; longitudinal research-call scorecard is not complete |
| **Total** | **34/100** | **The system is a functioning research foundation, not yet an investment-ready decision product.** |

This is a conservative, evidence-based engineering estimate, not a claim that 34% of the eventual investment outcome is already achieved. Percentages rise only when acceptance criteria are demonstrated in source data and generated outputs.

## Milestones and acceptance criteria

### M1 — Reliable historical financial coverage (next)
Deliverables:
1. Fix NSE filing pagination without silently stopping at the first page; handle API pagination metadata and a safe termination condition.
2. Deduplicate filing rows/revisions and preserve the latest valid filing for each period/basis.
3. Verify annual periods across the configured 64 symbols; distinguish consolidated/standalone and transition years.
4. Validate three consecutive years of true FCFE where applicable. CFO minus capex alone is not FCFE; net borrowing requires supported current and prior debt balances. For financial institutions where FCFE DCF is not suitable, record the sector-specific alternative instead of forcing DCF.
5. Produce a machine-readable and human-readable coverage matrix: years available, FCFE years verified, missing facts, source links, conflicts, and exception reasons.
Acceptance: tests cover multi-page responses, duplicate/revised filings, empty/short final page, invalid pagination metadata, and annual/FCFE gaps; a 64-company coverage report is generated from the actual run.

### M2 — Company-quality and qualitative research
Deliverables:
1. Use sector-aware scorecards (banks, IT, consumer, industrials, commodities, utilities, healthcare, capital-market infrastructure, etc.).
2. Assess business model, competitive position, management execution/capital allocation, governance/compliance, promoter/shareholding and material risks where relevant.
3. Store every assessment with evidence URL, source publication date, research date, confidence, analyst rationale, counter-evidence and review trigger.
4. Keep missing evidence explicitly unassessed; an LLM may summarize evidence but may not invent facts or self-certify a high score.
Acceptance: each of the 64 has a research status; scored companies have evidence-backed assessments and the decision engine blocks BUY/ACCUMULATE without required evidence.

### M3 — Valuation and decisions
Deliverables: sector-appropriate valuation; bear/base/bull values; assumptions and sensitivity; historical/peer context; margin of safety; entry zones; downside/risk; confidence; conditions that change the decision.
Acceptance: all 64 have either a defensible valuation and decision or a precise ASSESS/OBSERVE reason and next evidence needed. The output must not be 64 generic ASSESS labels.

### M4 — Wealth Scan release
Deliverables: investor-facing summary; 64-stock decision register; current holdings review; buy/accumulate shortlist; WAIT price triggers; risk/concentration review; capital allocation only from a current portfolio/cash snapshot; outside-watchlist opportunities; prior-scan comparison.
Acceptance: output is reproducible, dated, source-linked and useful without reading the code.

### M5 — Broader intelligence and learning
Deliverables: global/Indian news and filings, sector events, IPO screening, outside-watchlist discovery, stock/event mapping, outcome tracking and benchmark comparison.
Acceptance: forecasts and thesis changes are saved before outcomes; subsequent results are measured at defined horizons; accuracy is reported rather than asserted.

## Current verified state at baseline

- Latest reviewed code commit: a8777a5804a6e07d83ce48fea18024ec7334d482.
- Repository is private; authenticated GitHub access has admin/push permission.
- The following workflow runs were completed successfully on that commit:
  - Research Command: https://github.com/shettyankith123-pixel/indian-equity-research-system/actions/runs/43646937732
  - NSE Financial Ingestion: https://github.com/shettyankith123-pixel/indian-equity-research-system/actions/runs/43645167461
  - Tests: https://github.com/shettyankith123-pixel/indian-equity-research-system/actions/runs/43645087190
- These green runs prove execution/tests passed, not that the 64-stock history is complete or investment decisions are validated.
- Latest inspected committed report: reports/wealth-scan/wealth_scan.md and reports/wealth-scan/decision_register.csv; it contains 64/64 ASSESS, 64 prices, and no base fair values. It is a data-readiness report, not a completed investment recommendation set.
- Code review found the importer calls fetch_integrated_filing_listing(... page=1 ...) and only processes that response's data list. The listing helper accepts a page parameter but the importer does not iterate later pages.
- True FCFE logic exists in fundamentals.py as CFO less capex plus net borrowing, and requires current/prior-year debt observations; three-year consecutive coverage still needs to be demonstrated.
- Decision engine already requires financial, quality, governance, valuation-confidence, completeness and source inputs; the generated report lacks those inputs.
- docs/implementation_status.md notes there is no direct authenticated INDmoney API integration in GitHub Actions, no hosted persistent database, and no external LLM/news model integration. Use supported exports/tools and make these boundaries visible.

## Next action

Execute M1 in the existing architecture: inspect the actual NSE response pagination contract and existing tests; implement robust page retrieval plus tests; run focused tests, then full CI; run the 64-stock importer once and evaluate actual annual/FCFE coverage; commit the code, test results, data coverage report and updated progress score. Do not spend time on a dashboard or unrelated features before this deliverable exists.
