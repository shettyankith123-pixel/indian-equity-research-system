"""Source-aware normalization of statement flows and instant balance sheets."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from indian_equity_research.models.financials import FinancialObservation

D = Decimal
ZERO = D("0")


def safe_div(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


@dataclass(frozen=True, slots=True)
class FundamentalPeriod:
    symbol: str
    basis: str
    source_name: str
    source_url: str | None
    source_reference_id: str | None
    publication_date: date
    period_start: date
    period_end: date
    period_kind: str
    metrics: dict[str, Decimal | None]
    completeness: Decimal
    missing_metrics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompanyFundamentals:
    symbol: str
    basis: str
    sector: str
    latest_period: FundamentalPeriod | None
    annual_periods: tuple[FundamentalPeriod, ...]
    quarterly_periods: tuple[FundamentalPeriod, ...]
    growth_score: Decimal | None
    balance_sheet_score: Decimal | None
    profitability_score: Decimal | None
    data_completeness: Decimal
    data_as_of: date | None
    source_name: str
    source_url: str | None
    notes: tuple[str, ...]


def _pick(values: dict[str, Decimal], *keys: str) -> Decimal | None:
    return next((values[k] for k in keys if k in values), None)


def _clip(value: Decimal) -> Decimal:
    return min(D("100"), max(ZERO, value))


def normalize_financial_observations(observations: Iterable[FinancialObservation]) -> list[FundamentalPeriod]:
    groups: dict[tuple, dict] = {}
    for obs in observations:
        p = obs.period
        key = (obs.symbol, p.basis, obs.source.source_name, obs.source.reference_id or "",
               p.start_date, p.end_date, p.kind)
        group = groups.setdefault(key, {
            "metrics": {}, "url": obs.source.url, "reference_id": obs.source.reference_id,
            "publication_date": obs.source.publication_date,
        })
        group["metrics"].setdefault(obs.metric, obs.value)

    instants: dict[tuple, dict[str, Decimal]] = {}
    for key, group in groups.items():
        symbol, basis, source, reference_id, start, end, kind = key
        if kind == "instant":
            instants[(symbol, basis, source, reference_id, end)] = group["metrics"]

    # Average-balance ratios may use the previous year's snapshot from a different filing.
    instant_history: dict[tuple, list[tuple[date, date, dict[str, Decimal]]]] = defaultdict(list)
    for key, group in groups.items():
        symbol, basis, source, reference_id, start, end, kind = key
        if kind == "instant":
            instant_history[(symbol, basis, source)].append((end, group["publication_date"], group["metrics"]))
    for history in instant_history.values():
        history.sort(key=lambda x: (x[0], x[1]))

    raw: list[dict] = []
    for key, group in groups.items():
        symbol, basis, source, reference_id, start, end, kind = key
        if kind == "instant":
            continue
        flow = group["metrics"]
        instant = instants.get((symbol, basis, source, reference_id, end), {})
        revenue = _pick(flow, "revenue_from_operations", "total_income")
        pbt = flow.get("profit_before_tax")
        pat = _pick(flow, "profit_after_tax_attributable_to_owners", "profit_after_tax_total")
        finance_cost = flow.get("finance_costs")
        depreciation = flow.get("depreciation_amortisation")
        ebit = pbt + finance_cost if pbt is not None and finance_cost is not None else None
        ebitda = ebit + depreciation if ebit is not None and depreciation is not None else None
        debt = instant.get("borrowings")
        if debt is None:
            current = instant.get("current_borrowings")
            noncurrent = instant.get("non_current_borrowings")
            if current is not None and noncurrent is not None:
                debt = current + noncurrent
        cash = instant.get("cash_and_cash_equivalents")
        net_debt = debt - cash if debt is not None and cash is not None else None
        equity, assets = instant.get("total_equity"), instant.get("total_assets")
        current_assets, current_liabilities = instant.get("current_assets"), instant.get("current_liabilities")
        cfo, capex = flow.get("net_cash_from_operating_activities"), flow.get("capital_expenditure")
        fcf = cfo - abs(capex) if cfo is not None and capex is not None else None

        prior_snapshots = [
            (snap_date, pub_date, values)
            for snap_date, pub_date, values in instant_history.get((symbol, basis, source), [])
            if snap_date < end and 330 <= (end - snap_date).days <= 400
        ]
        prior = max(prior_snapshots, key=lambda x: (x[0], x[1]))[2] if prior_snapshots else {}
        prior_equity, prior_assets = prior.get("total_equity"), prior.get("total_assets")
        avg_equity = (equity + prior_equity) / 2 if equity is not None and prior_equity is not None else None
        avg_assets = (assets + prior_assets) / 2 if assets is not None and prior_assets is not None else None

        factor = {
            "quarter": D("4"), "half_year": D("2"),
            "year": D("1"), "trailing_twelve_months": D("1"),
        }.get(kind)
        if kind == "transition_period":
            factor = D("365") / D((end - start).days + 1)
        factor = factor or D("1")

        metrics: dict[str, Decimal | None] = {
            "revenue": revenue,
            "total_income": flow.get("total_income"),
            "total_expenses": flow.get("total_expenses"),
            "profit_before_tax": pbt,
            "profit_after_tax": pat,
            "finance_costs": finance_cost,
            "depreciation_amortisation": depreciation,
            "ebit_proxy": ebit,
            "ebitda_proxy": ebitda,
            "ebitda_margin": safe_div(ebitda, revenue),
            "pat_margin": safe_div(pat, revenue),
            "interest_coverage_proxy": safe_div(ebit, finance_cost),
            "operating_cash_flow": cfo,
            "capital_expenditure_outflow": abs(capex) if capex is not None else None,
            "free_cash_flow_to_equity_proxy": fcf,
            "cfo_to_pat": safe_div(cfo, pat),
            "total_assets": assets,
            "total_equity": equity,
            "total_liabilities": instant.get("total_liabilities"),
            "cash_and_cash_equivalents": cash,
            "total_debt": debt,
            "net_debt": net_debt,
            "debt_to_equity": safe_div(debt, equity),
            "net_debt_to_equity": safe_div(net_debt, equity),
            "current_assets": current_assets,
            "current_liabilities": current_liabilities,
            "current_ratio": safe_div(current_assets, current_liabilities),
            "equity_to_assets": safe_div(equity, assets),
            "return_on_equity": (pat * factor / avg_equity) if pat is not None and avg_equity is not None and avg_equity > 0 else None,
            "return_on_assets": (pat * factor / avg_assets) if pat is not None and avg_assets is not None and avg_assets > 0 else None,
            "annualised_ebitda": ebitda * factor if ebitda is not None else None,
            "annualised_pat": pat * factor if pat is not None else None,
            "net_interest_income": flow.get("net_interest_income"),
            "interest_earned": flow.get("interest_earned"),
            "interest_expended": flow.get("interest_expended"),
            "bank_deposits": instant.get("bank_deposits"),
            "bank_advances": instant.get("bank_advances"),
            "gross_npa": instant.get("gross_npa"),
            "net_npa": instant.get("net_npa"),
            "provisions_against_npa": instant.get("provisions_against_npa"),
            "risk_weighted_assets": instant.get("risk_weighted_assets"),
        }
        required = ("revenue","profit_before_tax","profit_after_tax","total_assets","total_equity",
                    "operating_cash_flow","capital_expenditure_outflow","cash_and_cash_equivalents",
                    "total_debt","annualised_ebitda")
        missing = tuple(metric for metric in required if metrics.get(metric) is None)
        completeness = D(len(required)-len(missing))/D(len(required))
        raw.append({
            "symbol":symbol,"basis":basis,"source":source,"reference_id":reference_id,
            "start":start,"end":end,"kind":kind,"metrics":metrics,"url":group["url"],
            "publication_date":group["publication_date"],
            "completeness":completeness,"missing":missing,
        })

    for current in raw:
        if current["kind"] not in {"quarter","half_year","year"}:
            current["metrics"]["revenue_growth_yoy"] = None
            current["metrics"]["pat_growth_yoy"] = None
            continue
        prevs = [
            prev for prev in raw
            if prev["symbol"] == current["symbol"] and prev["basis"] == current["basis"]
            and prev["source"] == current["source"] and prev["kind"] == current["kind"]
            and prev["end"] < current["end"] and 330 <= (current["end"]-prev["end"]).days <= 400
        ]
        previous = max(prevs,key=lambda x:x["end"]) if prevs else None
        for metric, output in (("revenue","revenue_growth_yoy"),("profit_after_tax","pat_growth_yoy")):
            old = previous["metrics"].get(metric) if previous else None
            new = current["metrics"].get(metric)
            current["metrics"][output] = new/old-D("1") if old is not None and new is not None and old > 0 else None

    return [
        FundamentalPeriod(
            symbol=r["symbol"],basis=r["basis"],source_name=r["source"],
            source_url=r["url"],source_reference_id=r["reference_id"],
            publication_date=r["publication_date"],
            period_start=r["start"],period_end=r["end"],period_kind=r["kind"],
            metrics=r["metrics"],completeness=r["completeness"],missing_metrics=r["missing"],
        )
        for r in sorted(raw,key=lambda x:(x["symbol"],x["basis"],x["end"],x["kind"],x["source"]))
    ]


def build_company_fundamentals(
    periods: Iterable[FundamentalPeriod], *, symbol: str, sector: str, basis: str = "consolidated",
) -> CompanyFundamentals:
    selected=[p for p in periods if p.symbol==symbol and p.basis==basis]
    annual=tuple(sorted((p for p in selected if p.period_kind=="year"),key=lambda p:p.period_end))
    quarters=tuple(sorted((p for p in selected if p.period_kind in {"quarter","half_year"}),key=lambda p:p.period_end))
    latest=max(selected,key=lambda p:(p.period_end,p.publication_date)) if selected else None
    notes=[]
    if latest is None:
        notes.append("No financial period available for this issuer/basis.")
        return CompanyFundamentals(symbol,basis,sector,None,annual,quarters,None,None,None,ZERO,None,"",None,tuple(notes))
    m=latest.metrics
    margins=[v for v in (m.get("ebitda_margin"),m.get("pat_margin")) if v is not None]
    profitability=_clip(D("50")+sum(margins,ZERO)/D(len(margins))*D("200")) if margins else None
    growths=[v for v in (m.get("revenue_growth_yoy"),m.get("pat_growth_yoy")) if v is not None]
    growth=_clip(D("50")+sum(growths,ZERO)/D(len(growths))*D("150")) if growths else None
    balance_parts=[]
    if m.get("current_ratio") is not None: balance_parts.append(_clip(m["current_ratio"]/D("2")*D("100")))
    if m.get("debt_to_equity") is not None: balance_parts.append(_clip(D("100")-m["debt_to_equity"]*D("50")))
    if m.get("equity_to_assets") is not None: balance_parts.append(_clip(m["equity_to_assets"]*D("100")))
    balance=sum(balance_parts,ZERO)/D(len(balance_parts)) if balance_parts else None
    if len(annual)<3: notes.append("Fewer than three annual periods: normalised cycle confidence is limited.")
    if m.get("return_on_equity") is None: notes.append("ROE unavailable: prior-year balance-sheet equity is missing.")
    if m.get("free_cash_flow_to_equity_proxy") is None: notes.append("FCF unavailable: operating cash flow or capex is missing.")
    notes.append("Automated financial scores are not a governance, management or qualitative thesis assessment.")
    return CompanyFundamentals(
        symbol,basis,sector,latest,annual,quarters,growth,balance,profitability,
        latest.completeness,latest.publication_date,latest.source_name,latest.source_url,tuple(notes),
    )
