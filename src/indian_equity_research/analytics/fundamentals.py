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


def _equity_from_instant(values: dict[str, Decimal]) -> tuple[Decimal | None, str | None]:
    """Return reported equity or an explicitly derivable accounting residual."""
    reported = values.get("total_equity")
    if reported is not None:
        return reported, "reported_equity"
    capital = values.get("bank_share_capital")
    reserves = values.get("bank_reserves_and_surplus")
    if capital is not None and reserves is not None:
        return capital + reserves, "bank_capital_plus_reserves"
    assets = values.get("total_assets")
    liabilities = values.get("total_liabilities")
    if assets is not None and liabilities is not None and assets >= liabilities:
        return assets - liabilities, "assets_minus_liabilities"
    return None, None


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

    # Average-balance ratios may use prior-year snapshots imported from separate
    # filings. Multiple filings can carry the same instant date but different
    # comparatives (for example, FY25 has a full balance sheet while FY26's
    # comparative context includes only cash). Merge facts by date, preferring
    # the richer snapshot for overlapping facts and retaining facts absent from
    # the shorter comparative context.
    instant_candidates: dict[tuple, dict[date, list[tuple[date, dict[str, Decimal]]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for key, group in groups.items():
        symbol, basis, source, reference_id, start, end, kind = key
        if kind == "instant":
            instant_candidates[(symbol, basis, source)][end].append(
                (group["publication_date"], group["metrics"])
            )

    instant_history: dict[tuple, list[tuple[date, date, dict[str, Decimal]]]] = defaultdict(list)
    for history_key, by_date in instant_candidates.items():
        for snapshot_date, candidates in by_date.items():
            # Most complete snapshot is applied last; the latest publication
            # wins only when completeness is equal.
            candidates.sort(key=lambda item: (len(item[1]), item[0]))
            merged_metrics: dict[str, Decimal] = {}
            latest_publication = max(publication for publication, _ in candidates)
            for _publication, values in candidates:
                merged_metrics.update(values)
            instant_history[history_key].append(
                (snapshot_date, latest_publication, merged_metrics)
            )
        instant_history[history_key].sort(key=lambda item: (item[0], item[1]))

    raw: list[dict] = []
    for key, group in groups.items():
        symbol, basis, source, reference_id, start, end, kind = key
        if kind == "instant":
            continue
        flow = group["metrics"]
        instant = instants.get((symbol, basis, source, reference_id, end), {})
        revenue = _pick(flow, "revenue_from_operations", "total_income")
        pbt = flow.get("profit_before_tax")
        pat = _pick(flow, "profit_after_tax_attributable_to_owners", "profit_after_tax_total", "profit_after_tax")
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
        assets = instant.get("total_assets")
        liabilities = instant.get("total_liabilities")
        equity, equity_method = _equity_from_instant(instant)
        current_assets, current_liabilities = instant.get("current_assets"), instant.get("current_liabilities")
        cfo, capex = flow.get("net_cash_from_operating_activities"), flow.get("capital_expenditure")
        levered_fcf_proxy = cfo - abs(capex) if cfo is not None and capex is not None else None

        prior_snapshots = [
            (snap_date, pub_date, values)
            for snap_date, pub_date, values in instant_history.get((symbol, basis, source), [])
            if snap_date < end and 330 <= (end - snap_date).days <= 400
        ]
        prior = max(prior_snapshots, key=lambda x: (x[0], x[1]))[2] if prior_snapshots else {}
        prior_debt = prior.get("borrowings")
        if prior_debt is None:
            prior_current, prior_noncurrent = prior.get("current_borrowings"), prior.get("non_current_borrowings")
            if prior_current is not None and prior_noncurrent is not None:
                prior_debt = prior_current + prior_noncurrent
        net_borrowing = debt - prior_debt if debt is not None and prior_debt is not None else None
        # True FCFE requires net borrowing (closing debt less prior-year debt).
        # CFO minus capex alone is a levered-FCF proxy, not full FCFE.
        fcfe = levered_fcf_proxy + net_borrowing if levered_fcf_proxy is not None and net_borrowing is not None else None
        prior_equity, prior_equity_method = _equity_from_instant(prior)
        prior_assets = prior.get("total_assets")
        avg_equity = (equity + prior_equity) / 2 if equity is not None and prior_equity is not None else None
        avg_assets = (assets + prior_assets) / 2 if assets is not None and prior_assets is not None else None
        prior_deposits = prior.get("bank_deposits")
        prior_advances = prior.get("bank_advances")
        deposit_growth_yoy = (
            instant.get("bank_deposits") / prior_deposits - D("1")
            if instant.get("bank_deposits") is not None and prior_deposits is not None and prior_deposits > 0
            else None
        )
        advance_growth_yoy = (
            instant.get("bank_advances") / prior_advances - D("1")
            if instant.get("bank_advances") is not None and prior_advances is not None and prior_advances > 0
            else None
        )

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
            "levered_free_cash_flow_proxy": levered_fcf_proxy,
            "net_borrowing": net_borrowing,
            "free_cash_flow_to_equity": fcfe,
            "cfo_to_pat": safe_div(cfo, pat),
            "total_assets": assets,
            "total_equity": equity,
            "total_equity_derivation": equity_method,
            "total_liabilities": liabilities,
            "cash_and_cash_equivalents": cash,
            "bank_share_capital": instant.get("bank_share_capital"),
            "bank_reserves_and_surplus": instant.get("bank_reserves_and_surplus"),
            "bank_cash_and_rbi_balances": instant.get("bank_cash_and_rbi_balances"),
            "bank_balances_with_other_banks": instant.get("bank_balances_with_other_banks"),
            "bank_investments": instant.get("bank_investments"),
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
            "bank_advances_to_deposits": safe_div(instant.get("bank_advances"), instant.get("bank_deposits")),
            "bank_deposit_growth_yoy": deposit_growth_yoy,
            "bank_advances_growth_yoy": advance_growth_yoy,
            "gross_npa": instant.get("gross_npa"),
            "net_npa": instant.get("net_npa"),
            "provisions_against_npa": instant.get("provisions_against_npa"),
            "risk_weighted_assets": instant.get("risk_weighted_assets"),
        }
        bank_like = (
            metrics.get("net_interest_income") is not None
            or (metrics.get("bank_deposits") is not None and metrics.get("bank_advances") is not None)
        )
        if bank_like:
            required = (
                "profit_after_tax", "total_assets", "total_equity",
                "net_interest_income", "bank_deposits", "bank_advances",
            )
        else:
            required = (
                "revenue","profit_before_tax","profit_after_tax","total_assets","total_equity",
                "operating_cash_flow","capital_expenditure_outflow","free_cash_flow_to_equity",
                "cash_and_cash_equivalents","total_debt","annualised_ebitda",
            )
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
    bank_like = "bank" in sector.casefold() or m.get("net_interest_income") is not None
    growths=[v for v in (m.get("revenue_growth_yoy"),m.get("pat_growth_yoy")) if v is not None]
    growth=_clip(D("50")+sum(growths,ZERO)/D(len(growths))*D("150")) if growths else None
    if bank_like:
        latest_roe = m.get("return_on_equity")
        annual_roe_periods = [p for p in annual if p.metrics.get("return_on_equity") is not None]
        fallback_roe_period = annual_roe_periods[-1] if annual_roe_periods else None
        roe = latest_roe if latest_roe is not None else (
            fallback_roe_period.metrics.get("return_on_equity") if fallback_roe_period else None
        )
        profitability = _clip(D("50") + roe * D("200")) if roe is not None else None
        if latest_roe is None and fallback_roe_period is not None:
            notes.append(
                "Latest interim ROE unavailable because a matching prior-year balance sheet is missing; "
                f"the profitability proxy uses annual ROE through {fallback_roe_period.period_end.isoformat()}."
            )
        # Only a disclosed equity/assets proxy and the loans/deposits ratio are
        # used here. Regulatory CET1/CRAR and NPA ratios remain explicit gaps.
        balance_parts=[]
        if m.get("equity_to_assets") is not None:
            balance_parts.append(_clip(m["equity_to_assets"] / D("0.15") * D("100")))
        if m.get("bank_advances_to_deposits") is not None:
            ldr=m["bank_advances_to_deposits"]
            balance_parts.append(_clip(D("100") - abs(ldr-D("0.85"))*D("180")))
        balance=sum(balance_parts,ZERO)/D(len(balance_parts)) if balance_parts else None
        if m.get("gross_npa") is None or m.get("net_npa") is None:
            notes.append("Bank asset-quality review is incomplete: gross/net NPA and provision coverage are not mapped.")
        if m.get("risk_weighted_assets") is None:
            notes.append("Regulatory CRAR/CET1 cannot be calculated because risk-weighted assets are not mapped.")
    else:
        margins=[v for v in (m.get("ebitda_margin"),m.get("pat_margin")) if v is not None]
        profitability=_clip(D("50")+sum(margins,ZERO)/D(len(margins))*D("200")) if margins else None
        balance_parts=[]
        if m.get("current_ratio") is not None: balance_parts.append(_clip(m["current_ratio"]/D("2")*D("100")))
        if m.get("debt_to_equity") is not None: balance_parts.append(_clip(D("100")-m["debt_to_equity"]*D("50")))
        if m.get("equity_to_assets") is not None: balance_parts.append(_clip(m["equity_to_assets"]*D("100")))
        balance=sum(balance_parts,ZERO)/D(len(balance_parts)) if balance_parts else None
    if len(annual)<3: notes.append("Fewer than three annual periods: normalised cycle confidence is limited.")
    annual_roe_available = any(p.metrics.get("return_on_equity") is not None for p in annual)
    if m.get("return_on_equity") is None and not annual_roe_available:
        notes.append("ROE unavailable: prior-year balance-sheet equity is missing in both latest and annual periods.")
    if not bank_like and m.get("free_cash_flow_to_equity") is None:
        notes.append("True FCFE unavailable: CFO, capex and current/prior-year debt balances are all required; proxy-only cash flow is not used for DCF.")
    if m.get("total_equity_derivation") not in (None, "reported_equity"):
        notes.append(f"Book equity is a derived accounting residual ({m.get('total_equity_derivation')}); verify before using book-value multiples.")
    notes.append("Automated financial scores are not a governance, management or qualitative thesis assessment.")
    bank_like = "bank" in sector.casefold() or m.get("net_interest_income") is not None
    if bank_like:
        bank_required=("profit_after_tax","total_assets","total_equity","net_interest_income","bank_deposits","bank_advances")
        company_completeness = D(sum(1 for name in bank_required if m.get(name) is not None))/D(len(bank_required))
    else:
        company_completeness = latest.completeness
    return CompanyFundamentals(
        symbol,basis,sector,latest,annual,quarters,growth,balance,profitability,
        company_completeness,latest.publication_date,latest.source_name,latest.source_url,tuple(notes),
    )
