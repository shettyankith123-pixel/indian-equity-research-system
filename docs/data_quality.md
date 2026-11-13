# Data quality and source controls

## Required metadata

Each observation should retain:
- symbol / instrument identifier
- metric name and value
- unit and currency
- financial period start/end (where applicable)
- standalone or consolidated basis
- source name and source URL/reference
- publication timestamp
- retrieval timestamp
- price timestamp and market session (where applicable)
- status: reported, calculated, estimate, delayed, stale, missing or disputed

## Price validation

- Distinguish live, delayed, end-of-day and historical prices.
- Do not describe a quote as live solely because a provider labels it live.
- Compare quote timestamps to exchange hours and the official close.
- Do not substitute one day's close for another.
- Historical price series may be unadjusted. Check splits, bonuses and other corporate actions before calculating returns.
- If providers conflict, show the conflict and prefer the primary exchange source for exchange-reported prices.

## Financial statement validation

- Preserve the exact period and basis.
- Check units (rupees, lakh, crore), signs and scale.
- Reconcile subtotals when possible.
- Compare reported values to the previous quarter/year and note restatements or presentation changes.
- Never bridge missing periods with interpolated numbers without labelling them as estimates.

## AI extraction controls

- Store extracted text spans and page references.
- Require human/primary-source verification for high-impact numbers.
- Detect conflicting figures across standalone/consolidated statements and quarter/year-to-date periods.
- Never use sentiment classification as evidence of business quality or a buy signal.

## Failure behaviour

When a source is unavailable, malformed, stale or ambiguous, mark the field missing/disputed and explain the effect on the analysis. Do not silently fall back to fabricated values.
