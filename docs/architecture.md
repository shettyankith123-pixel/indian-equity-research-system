# System architecture

## Design principles

- Provider-independent: business logic must not depend directly on one broker or data vendor.
- Evidence-first: every material number carries a source, period, timestamp and quality state.
- Reproducible: derived values are calculated by tested code with visible assumptions.
- Human-reviewed: AI can extract and explain; it cannot silently promote unverified claims into facts.
- Modular: market data, filings, news, model inference and storage are separate interfaces.

## Target components

1. **Connectors** — NSE, INDmoney, company investor-relations material, NSE/BSE filings, RBI and SEBI sources.
2. **Normalisation** — standardise symbols, units, currencies, reporting periods, standalone/consolidated basis and timestamps.
3. **Storage** — raw/normalised market observations, financial statements, corporate actions, source metadata, research snapshots and thesis history.
4. **Analytics** — banking ratios, non-financial company ratios, peer comparisons, valuation scenarios and portfolio exposures.
5. **AI assistance** — document extraction, news classification, summarisation, contradiction detection and research drafting.
6. **Orchestration** — company scan, sector scan, discovery, portfolio review and outcome review workflows.
7. **Reporting** — versioned Markdown/HTML/PDF/Word outputs with citations and a concise decision record.

## Provider interfaces (target)

- `MarketDataProvider`: quote, historical bars, index data and corporate actions.
- `FundamentalsProvider`: reported financial statements and company KPIs.
- `FilingsProvider`: official filings, annual reports, investor presentations and earnings-call transcripts.
- `NewsProvider`: timestamped article metadata and article text where permitted.
- `LanguageModelProvider`: extraction/classification/summarisation with model name and prompt version recorded.

The current repository does not yet implement these live connectors.

## Storage evolution

Start with SQLite for local development and tests. Move to PostgreSQL when concurrent jobs, durable hosting or multi-user access are required. Keep raw data and derived analytics logically separate. Do not persist restricted market data or copyrighted documents unless the relevant licence allows it.

## Model strategy

ChatGPT is the research orchestrator in the current workflow. Optional models such as FinBERT or FinGPT may later help classify financial sentiment or extract structured information. Their outputs must include model/version metadata and must be checked against primary disclosures. No model endpoint is configured in this initial commit.

## Deployment stages

1. Offline calculation library and tests.
2. Read-only integrations and data-quality checks.
3. Filing ingestion and reproducible research database.
4. AI-assisted extraction and comparison.
5. Scheduled scans, alerting and monitoring.
6. Broader exchange coverage and operational controls.
