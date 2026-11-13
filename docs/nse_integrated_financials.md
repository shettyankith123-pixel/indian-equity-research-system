# NSE Integrated Filing financial-data pipeline

The scheduled ingestion uses NSE's Integrated Filing - Financials XBRL attachments, not third-party analyst estimates.

## Universe and periods

The file data/universe/indian_watchlist_companies.csv contains the 64 imported INDmoney watchlist companies with the display name used to query NSE. The ingestion requests up to four most recent quarter-end periods and three latest March year-end periods for each available reporting basis (standalone and consolidated).

Quarter, half-year and annual flow values are selected by the actual XBRL context start/end dates (roughly 70–120, 150–220 and 300–380 days respectively), not by an issuer-specific context ID. This handles non-standard context names and transition periods. Each observation records the period dates, reporting basis, filing publication date, NSE XBRL URL, sequence/revision identifier, retrieval timestamp and source hash.

## Units and financial metric policy

NSE monetary facts are stored in absolute INR in the XBRL. Monetary observations are normalized to INR crore by dividing by 10,000,000. EPS remains INR/share. Net interest income is separately marked as a calculated observation using reported interest earned less reported interest expended.

Missing tags remain missing. The importer never substitutes zero, analyst target prices, or inferred period values. Sector-specific tags that are not mapped by the current standardized metric dictionary remain available in the public XBRL attachment but are not silently coerced into another metric.

## How to run

GitHub Actions → NSE Quarterly and Annual Financial Ingestion → Run workflow. Leave symbols blank for the full 64-stock universe, or supply a comma-separated test subset. The workflow runs weekly on Saturdays at 09:00 India time after the initial full deployment.

Each run publishes a 90-day artifact containing:
- financials.sqlite: queryable FinancialRepository database
- financial_observations.csv: same long-form schema accepted by the repository CSV loader
- filing_coverage.csv: company-by-company period and parse coverage
- filing_manifest.json: selected filing URLs, sequence IDs, XBRL hash, contexts and metrics
- ingest_summary.json: total companies, filings, observations and errors

A successful workflow means at least some source-attributed filing observations were ingested. It does not imply 64/64 coverage. Review filing_coverage.csv and the manifest before using the database to form investment recommendations.
