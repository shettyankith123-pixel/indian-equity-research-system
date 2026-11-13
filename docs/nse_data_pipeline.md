# NSE EOD price ingestion

The supported equity end-of-day source is NSE's **CM-UDiFF Common Bhavcopy Final (ZIP)**. NSE's All Reports page marks the legacy CM common bhavcopy CSV as discontinued from 8 July 2024 and points users to the UDiFF ZIP format.

Command:

```bash
ies fetch-nse-eod --date 2026-11-12 --db data/research.db
```

The downloader first requests the official All Reports page, then resolves the date-specific archive from NSE's archive host. The parser validates ZIP contents, required OHLCV fields, date, series, positive prices, volume and OHLC consistency. Equity series are retained; non-equity series are ignored. Raw ZIPs are not committed to Git. A normalized CSV and SQLite rows are created locally.

The scheduled GitHub Action runs on weekdays at 18:15 India time and uploads an artifact. NSE holidays, archive publication delays and access restrictions may cause a run to fail; a failed/no-data run must not be treated as a zero-price market observation.

## Data-quality constraints

- Every record retains the source filename and source URL in the run output.
- A requested date must match the archive row's trading date.
- No price is represented as live; these are official end-of-day snapshots.
- Historical prices are not adjusted silently for corporate actions.
- Corporate-action adjustment and benchmark return calculations remain separate planned extensions.


## Equity market scan

After importing one or more sessions, run `ies market-scan`. It reports latest-session EQ-series advances, declines, unchanged securities, turnover coverage and the strongest/weakest movers. It deliberately does not call the result a full index/market scan because index constituents, index values, derivatives and corporate-action adjustments are not yet ingested.
