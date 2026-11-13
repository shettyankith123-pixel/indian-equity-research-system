# Financial data model and bank analytics

## Observation model

A financial observation is keyed by symbol, metric, numeric value, unit and currency; reporting-period start/end dates; period kind; standalone or consolidated basis; source publisher; source type; publication date; timezone-aware retrieval timestamp; URL/reference ID; and observation kind (reported, calculated or estimate).

A statement snapshot requires all observations to share the same symbol, period and reporting basis. Duplicate metrics are rejected. Missing fields remain missing; they are not represented as zero.

## Bank ratios

The bank analytics module returns one result object per supported ratio. Each result contains its value, formula, status and missing input names. Ratios are fractions: 0.0418 represents 4.18%.

- NIM = annualised net interest income / average interest-earning assets
- ROA = annualised net profit / average total assets
- ROE = annualised net profit / average equity
- CASA ratio = CASA deposits / total deposits
- GNPA ratio = gross NPA / gross advances
- NNPA ratio = net NPA / net advances
- Provision coverage = provisions against NPAs / gross NPA
- CET1 ratio = CET1 capital / risk-weighted assets
- Total capital adequacy = total regulatory capital / risk-weighted assets
- Cost-to-income = operating expenses / net total income
- Credit-deposit ratio = gross advances / total deposits

### Comparability caveats

- Flow metrics (NII and profit) require annualisation when a quarter or half-year is supplied. The factor is explicit; quarterly defaults to 4 only in the starter input model.
- Average balance-sheet values should be used for ROA, ROE and NIM. Closing balances can distort the result.
- Cost-to-income definitions vary between banks; supply the comparable net-total-income denominator disclosed by the bank.
- GNPA and NNPA should use the matching gross/net advance denominator disclosed by the bank.
- Provision-coverage definitions vary. Confirm whether the numerator includes specific NPA provisions or additional buffers before peer comparison.
- Capital ratios require the applicable regulatory capital numerator and risk-weighted asset denominator on the same reporting basis.
- Do not compare standalone and consolidated ratios without an explicit reconciliation.

## Growth calculations

CAGR is supported only for strictly positive start/end values. A negative-to-positive earnings transition does not have a meaningful standard CAGR and must be explained separately. Simple period growth is provided for non-zero starting values.

## Current limitations

No source connector, financial statement parser, database writer or scheduler is included yet. This module is a calculation and data-contract foundation; it is not populated with current company values.
