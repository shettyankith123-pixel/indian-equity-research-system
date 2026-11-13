# Portfolio and catalyst tracking

## Portfolio CSV

Use `data/templates/portfolio_transactions.csv`. Import with:

```bash
ies import-portfolio data/templates/your_transactions.csv --db data/research.db
ies portfolio-status --db data/research.db
```

The ledger uses average-cost accounting, includes buy-side fees in cost basis and sell-side fees in realised P&L, rejects duplicate transaction IDs and rejects sell quantities above imported holdings. It does not infer missing brokerage taxes or wallet cash flows.

## News/event history

Use `data/templates/news_events.csv`, ensuring event date, symbol, headline, source and URL are populated. Then run:

```bash
ies event-study --events data/templates/news_events.csv --db data/research.db
```

The event study reports the stock close on the first stored session on/after the event date and T+1, T+3 and T+5 session returns. These are descriptive associations, not proof that the headline caused the move; benchmark-adjusted returns and event-confounder controls are future improvements.

## IPO and discovery

`data/templates/ipo_watchlist.csv` is an evidence intake template only. IPO valuation requires prospectus financials, issue structure, fresh peer data and use-of-proceeds assessment. No issue is auto-rated from the template alone.
