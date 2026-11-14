"""Transparent sector-aware valuation scenarios. Not a recommendation engine."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from indian_equity_research.analytics.fundamentals import CompanyFundamentals

D=Decimal
ZERO=D("0")


@dataclass(frozen=True,slots=True)
class SectorAssumptions:
    bear_growth:D
    base_growth:D
    bull_growth:D
    bear_cost_of_equity:D
    base_cost_of_equity:D
    bull_cost_of_equity:D
    bear_terminal_growth:D
    base_terminal_growth:D
    bull_terminal_growth:D


@dataclass(frozen=True,slots=True)
class ValuationResult:
    symbol:str
    sector:str
    current_price:D|None
    market_cap_inr_crore:D|None
    fair_value_low:D|None
    fair_value_base:D|None
    fair_value_high:D|None
    method:str
    confidence:D
    valuation_status:str
    assumptions:dict[str,str]
    cross_checks:dict[str,D|None]
    warnings:tuple[str,...]


def assumptions_for_sector(sector:str)->SectorAssumptions:
    s=sector.casefold()
    if "bank" in s:
        return SectorAssumptions(D("0"),D("0"),D("0"),D(".145"),D(".13"),D(".12"),D(".04"),D(".05"),D(".055"))
    if s == "financial services":
        return SectorAssumptions(D(".04"),D(".07"),D(".09"),D(".14"),D(".13"),D(".12"),D(".035"),D(".045"),D(".05"))
    if any(x in s for x in ("mining","metals","chemicals","oil & gas","gas utilities")):
        return SectorAssumptions(D(".02"),D(".06"),D(".09"),D(".15"),D(".135"),D(".12"),D(".025"),D(".035"),D(".04"))
    if any(x in s for x in ("fmcg","consumer","beverage")):
        return SectorAssumptions(D(".03"),D(".07"),D(".10"),D(".125"),D(".115"),D(".105"),D(".035"),D(".045"),D(".05"))
    if any(x in s for x in ("it services","technology")):
        return SectorAssumptions(D(".04"),D(".08"),D(".12"),D(".13"),D(".12"),D(".11"),D(".035"),D(".045"),D(".05"))
    if "power" in s or "utilities" in s:
        return SectorAssumptions(D(".03"),D(".055"),D(".08"),D(".125"),D(".115"),D(".105"),D(".03"),D(".04"),D(".045"))
    if "health" in s or "pharma" in s:
        return SectorAssumptions(D(".03"),D(".07"),D(".10"),D(".13"),D(".12"),D(".11"),D(".035"),D(".045"),D(".05"))
    return SectorAssumptions(D(".03"),D(".07"),D(".10"),D(".13"),D(".12"),D(".11"),D(".03"),D(".04"),D(".05"))


def _median(values:list[D])->D|None:
    return D(str(median(values))) if values else None


def _annual(company:CompanyFundamentals,metric:str)->list[D]:
    return [p.metrics[metric] for p in company.annual_periods if p.metrics.get(metric) is not None]


def _dcf(fcf:D,shares:D,growth:D,coe:D,terminal_growth:D)->D|None:
    if fcf<=0 or shares<=0 or coe<=terminal_growth:
        return None
    projected=ZERO
    value=fcf
    for year in range(1,6):
        value*=D("1")+growth
        projected+=value/((D("1")+coe)**year)
    terminal=value*(D("1")+terminal_growth)/(coe-terminal_growth)
    return (projected+terminal/((D("1")+coe)**5))/shares


def value_universe(
    companies:dict[str,CompanyFundamentals],
    market:dict[str,dict[str,D|str|None]],
    sectors:dict[str,str],
)->dict[str,ValuationResult]:
    raw={}
    for symbol,company in companies.items():
        q=market.get(symbol,{})
        cap=q.get("market_cap_inr_crore");price=q.get("price_inr")
        cap=D(str(cap)) if cap not in (None,"") else None
        price=D(str(price)) if price not in (None,"") else None
        pat=_median(_annual(company,"profit_after_tax")[-3:])
        ebitda=_median(_annual(company,"annualised_ebitda")[-3:])
        netdebt=_median(_annual(company,"net_debt")[-3:])
        equity=_median(_annual(company,"total_equity")[-3:])
        shares=cap/price if cap and price and cap>0 and price>0 else None
        raw[symbol]={"cap":cap,"price":price,"shares":shares,"pat":pat,
                     "ebitda":ebitda,"netdebt":netdebt,"equity":equity}
    results={}
    for symbol,company in companies.items():
        sector=sectors.get(symbol,company.sector)
        own=raw[symbol]
        quote=market.get(symbol,{})
        price=own["price"];cap=own["cap"];shares=own["shares"]
        warnings=[]
        dcf_values=[]
        annual_count=len(company.annual_periods)
        checks={"dcf_base":None,"peer_pe":None,"peer_ev_ebitda":None,
                "pe_value":None,"ev_ebitda_value":None,"justified_pb":None}
        assumptions=assumptions_for_sector(sector)
        low=base=high=None;method="No reliable valuation";model_conf=D(".1")
        if company.latest_period is None:
            warnings.append("No financial statements available.")
        elif "bank" in sector.casefold() or symbol == "BAJFINANCE":
            roes=[v for v in _annual(company,"return_on_equity") if v>0]
            latest=company.latest_period
            # The latest annual ROE plus an annualised current quarter/half-year
            # ROE provides two observations when only two annual balance sheets
            # are currently available. It remains a provisional bank valuation.
            if (
                latest is not None
                and latest.period_kind in {"quarter","half_year"}
                and latest.metrics.get("return_on_equity") is not None
                and latest.metrics["return_on_equity"] > 0
                and all(p.period_end != latest.period_end for p in company.annual_periods)
            ):
                roes.append(latest.metrics["return_on_equity"])
            equity=(latest.metrics.get("total_equity") if latest is not None else None) or own["equity"]
            if len(roes)>=1 and equity is not None and shares is not None and shares>0:
                bps=equity/shares
                roe=min(D(".30"),_median(roes) or ZERO)
                scenarios=[]
                for r,coe,g in [
                    (roe*D(".8"),assumptions.bear_cost_of_equity,assumptions.bear_terminal_growth),
                    (roe,assumptions.base_cost_of_equity,assumptions.base_terminal_growth),
                    (min(D(".30"),roe*D("1.1")),assumptions.bull_cost_of_equity,assumptions.bull_terminal_growth),
                ]:
                    scenarios.append(((r-g)/(coe-g))*bps if r>g and coe>g else None)
                if all(v is not None for v in scenarios):
                    low,base,high=scenarios
                    checks["justified_pb"]=base
                    method="Justified P/B using sustainable ROE"
                    if len(roes) == 1:
                        model_conf=D(".45")
                        warnings.append("Justified P/B uses only one valid annual ROE observation; valuation confidence is reduced pending a longer bank earnings history.")
                    elif len(company.annual_periods)<2:
                        model_conf=D(".60")
                        warnings.append("Bank P/B includes one annual ROE plus a latest annualised quarter/half-year ROE; confidence is reduced.")
                    else:
                        model_conf=D(".70")
                else:
                    warnings.append("Sustainable ROE does not support all P/B scenarios.")
            else:
                warnings.append("Bank valuation requires at least one valid annual ROE observation and current book value per share.")
        else:
            fcfs=[v for v in _annual(company,"free_cash_flow_to_equity_proxy") if v>0]
            if len(fcfs)>=2 and shares is not None and shares>0:
                normalised=_median(fcfs[-3:])
                sc=[]
                for g,coe,tg in [
                    (assumptions.bear_growth,assumptions.bear_cost_of_equity,assumptions.bear_terminal_growth),
                    (assumptions.base_growth,assumptions.base_cost_of_equity,assumptions.base_terminal_growth),
                    (assumptions.bull_growth,assumptions.bull_cost_of_equity,assumptions.bull_terminal_growth),
                ]:
                    sc.append(_dcf(normalised,shares,g,coe,tg))
                if all(v is not None for v in sc):
                    dcf_values=[v for v in sc if v is not None]
                    checks["dcf_base"]=dcf_values[1]
            else:
                warnings.append("DCF requires two or more positive annual CFO-minus-capex observations.")
            if sector.casefold() == "financial services":
                peers=[]
                warnings.append("Financial Services contains materially different business models in this universe; cross-peer P/E and EV/EBITDA comparisons are disabled without a sub-sector peer map.")
            else:
                peers=[s for s in companies if s!=symbol and sectors.get(s,companies[s].sector).casefold()==sector.casefold()]
            pe_values=[];ev_values=[]
            for peer in peers:
                item=raw[peer]
                if item["cap"] and item["pat"] and item["pat"]>0:
                    pe_values.append(item["cap"]/item["pat"])
                if item["cap"] and item["ebitda"] and item["ebitda"]>0 and item["netdebt"] is not None:
                    ev_values.append((item["cap"]+item["netdebt"])/item["ebitda"])
            peer_pe=_median(pe_values) if len(pe_values)>=3 else None
            peer_ev=_median(ev_values) if len(ev_values)>=3 else None
            checks["peer_pe"]=peer_pe;checks["peer_ev_ebitda"]=peer_ev
            peer_values=[]
            if peer_pe and own["pat"] and own["pat"]>0 and shares:
                checks["pe_value"]=own["pat"]*peer_pe/shares
                peer_values.append(checks["pe_value"])
            if peer_ev and own["ebitda"] and own["ebitda"]>0 and own["netdebt"] is not None and shares:
                enterprise=own["ebitda"]*peer_ev-own["netdebt"]
                if enterprise>0:
                    checks["ev_ebitda_value"]=enterprise/shares
                    peer_values.append(checks["ev_ebitda_value"])
            if dcf_values and peer_values:
                peer_base=_median(peer_values)
                low=min(dcf_values[0],peer_base*D(".85"))
                base=(dcf_values[1]+peer_base)/2
                high=max(dcf_values[2],peer_base*D("1.15"))
                method="FCFE DCF with sector peer cross-checks"
                model_conf=D(".9")
            elif dcf_values:
                low,base,high=dcf_values
                method="FCFE DCF"
                model_conf=D(".65")
                warnings.append("Sector peer cross-check unavailable; DCF only.")
            elif peer_values:
                pb=_median(peer_values)
                low,base,high=pb*D(".85"),pb,pb*D("1.15")
                method="Sector-relative P/E / EV-EBITDA"
                model_conf=D(".5")
                warnings.append("Relative-multiple valuation only; intrinsic DCF unavailable.")
            else:
                warnings.append("Insufficient annual FCF, earnings or peer coverage for a fair value.")

        if annual_count<3:
            warnings.append("Fewer than three full annual periods; mid-cycle normalization confidence is limited.")
        if company.profitability_score is None or company.growth_score is None or company.balance_sheet_score is None:
            warnings.append("Some filing-derived quality metrics are unavailable.")
        warnings.append("Governance, management, related-party and qualitative thesis review remain separate manual gates.")
        data_factor=company.data_completeness
        hist_factor=min(D("1"),D(annual_count)/D("3"))
        quote_factor=D("1") if price is not None and cap is not None else ZERO
        confidence=min(D(".95"),D(".25")*hist_factor+D(".35")*data_factor+D(".25")*model_conf+D(".15")*quote_factor)
        status="provisional" if base is not None and annual_count>=2 else "insufficient_data"
        results[symbol]=ValuationResult(
            symbol,sector,price,cap,low,base,high,method,confidence,status,
            {f: str(getattr(assumptions,f)) for f in assumptions.__dataclass_fields__},
            checks,tuple(warnings),
        )
    return results
