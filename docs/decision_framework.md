# Investment profile and decision framework

## Investor mandate

- Risk appetite: moderate to high.
- Horizon: 7–10 years.
- Objective: long-term wealth creation and capital appreciation.
- Style: durable business quality and earnings growth at reasonable valuations.
- Position building: staged entries; swing trading remains separate and only runs when explicitly requested.

## Decision categories

| Decision | Meaning | Typical action |
|---|---|---|
| BUY | High-quality business, verified inputs, adequate confidence and at least 15% margin of safety to base fair value | Start position in planned tranches |
| ACCUMULATE | Same quality gates and at least 8% margin of safety | Build gradually |
| HOLD | Existing thesis remains intact, but no fresh entry margin | Retain and monitor |
| WAIT | Business passes quality screens, but entry price/risk does not | Set a price/research trigger |
| ASSESS | Required data is missing, stale, inconsistent or low confidence | Resolve evidence gaps; no capital call |
| OBSERVE | Early-stage candidate not ready for investment review | Monitor milestones |
| REDUCE | Valuation, concentration or thesis risk requires exposure review | Consider trimming with documented reasoning |
| EXIT | Thesis invalidated | Review exit; do not average down |
| AVOID | Fails quality or thesis requirements for new capital | No new position |

## Explicit BUY gates

A BUY is allowed only when all of the following are true:

1. Research data completeness is at least 85%.
2. Latest research is no more than 120 days old.
3. Valuation confidence is at least 65%.
4. Quality score >=65, growth >=55, balance sheet >=55 and governance >=65 (each on a 0–100 scale).
5. Average of the four scores >=65.
6. Price is at least 15% below base fair value.
7. No unresolved major-risk flag and no broken thesis.

ACCUMULATE uses the same quality gates but requires at least 8% margin of safety. A reasonable premium can be justified by durable growth only when the fair-value model itself reflects that growth; the system must not bypass valuation discipline.

The report exposes two separate price triggers for every sufficiently researched company: **BUY entry maximum = 85% of base fair value** and **ACCUMULATE entry maximum = 92% of base fair value**. `ideal_entry_max` identifies the nearer applicable level for the current recommendation. These are screening thresholds, not guaranteed support prices.

## Important guardrails

- A price decline alone never triggers a BUY or averaging down.
- Fair value must be sector-appropriate; use justified P/B for banks, normalised P/E/FCF for IT and consumer, cycle-normalised methods for cyclicals, and DCF/EV-based methods where appropriate.
- A held stock can be HOLD while a new buyer receives WAIT.
- Missing inputs map to ASSESS, not a fabricated BUY/WAIT.
- Position sizing must check existing holdings, sector concentration, cash available and portfolio limits before calculating rupee allocations.
- The current engine gives a recommendation category and action. It does not place orders or determine an allocation amount until a verified portfolio snapshot and investable cash balance are supplied.

## Allocation planning

A rupee allocation is produced only when an explicit capital snapshot is supplied in `data/templates/capital_snapshot.csv`. The snapshot needs current investable cash, total portfolio market value, and every holding's current market value and sector. The planner preserves a 5% cash reserve, caps a single name at 10% of portfolio value and a sector at 30%, and proposes only a first tranche (40% of remaining single-stock headroom for BUY, 30% for ACCUMULATE). It does not place orders or treat cash/positions from old chat messages as current account data.
