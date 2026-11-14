from datetime import date
from decimal import Decimal as D
from indian_equity_research.analytics.fundamentals import FundamentalPeriod,CompanyFundamentals
from indian_equity_research.valuation.sector_valuation import value_universe,_dcf


def period(symbol,end,metrics):
 return FundamentalPeriod(symbol,"consolidated","NSE","https://example.com",None,date.fromisoformat(end),date(int(end[:4])-1,4,1),date.fromisoformat(end),"year",metrics,D("1"),tuple())


def company(symbol,sector,annual):
 return CompanyFundamentals(symbol,"consolidated",sector,annual[-1],tuple(annual),tuple(),D("70"),D("70"),D("70"),D("1"),annual[-1].publication_date,"NSE","https://example.com",tuple())


def test_dcf_increases_with_growth_and_falls_with_cost_of_equity():
 low=_dcf(D("100"),D("10"),D(".03"),D(".14"),D(".03"))
 high=_dcf(D("100"),D("10"),D(".09"),D(".11"),D(".05"))
 assert low is not None and high is not None and high>low


def test_bank_fair_value_uses_justified_pb_scenarios():
 annual=[]
 for end,roe,equity in [("2024-03-31",D(".15"),D("1000")),("2025-03-31",D(".16"),D("1100")),("2026-03-31",D(".17"),D("1200"))]:
  annual.append(period("BANK",end,{"return_on_equity":roe,"total_equity":equity}))
 c=company("BANK","Banking",annual)
 v=value_universe({"BANK":c},{"BANK":{"price_inr":D("100"),"market_cap_inr_crore":D("12000")}},{"BANK":"Banking"})["BANK"]
 assert v.method.startswith("Justified P/B")
 assert v.fair_value_low<v.fair_value_base<v.fair_value_high


def test_nonbank_dcf_and_peer_multiples_use_peer_universe():
 companies={};market={};sectors={s:"IT Services" for s in ["A","B","C","D"]}
 for symbol,cap,price,fcf,pat,ebitda,netdebt in [
  ("A",10000,100,300,400,500,100),("B",12000,120,350,450,550,150),
  ("C",14000,140,380,480,600,200),("D",16000,160,420,520,650,250)]:
  annual=[period(symbol,y,{"free_cash_flow_to_equity":D(fcf),"profit_after_tax":D(pat),"annualised_ebitda":D(ebitda),"net_debt":D(netdebt),"total_equity":D("1000")}) for y in ["2024-03-31","2025-03-31","2026-03-31"]]
  companies[symbol]=company(symbol,"IT Services",annual)
  market[symbol]={"price_inr":D(price),"market_cap_inr_crore":D(cap)}
 result=value_universe(companies,market,sectors)["A"]
 assert "FCFE DCF" in result.method
 assert result.fair_value_low<result.fair_value_base<result.fair_value_high
 assert result.cross_checks["peer_pe"] is not None
 assert result.cross_checks["peer_ev_ebitda"] is not None


def test_no_dcf_when_fcfe_history_missing():
 annual=[period("X","2025-03-31",{"profit_after_tax":D("10")}),period("X","2026-03-31",{"profit_after_tax":D("11")})]
 result=value_universe({"X":company("X","Industrials",annual)},{"X":{"price_inr":D("10"),"market_cap_inr_crore":D("100")}},{"X":"Industrials"})["X"]
 assert result.fair_value_base is None


def test_missing_net_debt_blocks_ev_ebitda_multiple():
 companies={};market={};sectors={s:"Industrials" for s in ["A","B","C","D"]}
 for symbol,cap,price in [("A",1000,10),("B",1200,12),("C",1400,14),("D",1600,16)]:
  annual=[period(symbol,y,{"free_cash_flow_to_equity":D("20"),"profit_after_tax":D("30"),"annualised_ebitda":D("40"),"net_debt":None,"total_equity":D("100")}) for y in ["2024-03-31","2025-03-31","2026-03-31"]]
  companies[symbol]=company(symbol,"Industrials",annual);market[symbol]={"price_inr":D(price),"market_cap_inr_crore":D(cap)}
 result=value_universe(companies,market,sectors)
 assert all(v.cross_checks["peer_ev_ebitda"] is None for v in result.values())
 assert result["A"].cross_checks["pe_value"] is not None
 assert result["A"].method == "FCFE DCF with sector peer cross-checks"
 assert result["A"].fair_value_base is not None


def test_bajaj_finance_nbfc_uses_justified_pb_not_industrial_dcf():
    annual=[]
    for end,roe,equity in [
        ("2024-03-31",D(".18"),D("1000")),
        ("2025-03-31",D(".19"),D("1200")),
        ("2026-03-31",D(".20"),D("1400")),
    ]:
        annual.append(period("BAJFINANCE",end,{"return_on_equity":roe,"total_equity":equity}))
    c=company("BAJFINANCE","Financial Services",annual)
    v=value_universe(
        {"BAJFINANCE":c},
        {"BAJFINANCE":{"price_inr":D("100"),"market_cap_inr_crore":D("15000")}},
        {"BAJFINANCE":"Financial Services"},
    )["BAJFINANCE"]
    assert v.method.startswith("Justified P/B")
    assert v.fair_value_low < v.fair_value_base < v.fair_value_high


def test_financial_services_peer_multiples_disabled_without_subsector_map():
    companies={};market={}
    symbols=["HDFCAMC","CAMS","CDSL","BSE"]
    for index,symbol in enumerate(symbols,1):
        annual=[period(symbol,y,{
            "free_cash_flow_to_equity":D(str(50+index)),
            "profit_after_tax":D(str(60+index)),
            "annualised_ebitda":D(str(70+index)),
            "net_debt":D("0"),
            "total_equity":D("100"),
        }) for y in ["2024-03-31","2025-03-31","2026-03-31"]]
        companies[symbol]=company(symbol,"Financial Services",annual)
        market[symbol]={"price_inr":D("100"),"market_cap_inr_crore":D(str(1000*index))}
    sectors={symbol:"Financial Services" for symbol in symbols}
    results=value_universe(companies,market,sectors)
    for result in results.values():
        assert result.cross_checks["peer_pe"] is None
        assert result.cross_checks["peer_ev_ebitda"] is None
        assert "sub-sector peer map" in " ".join(result.warnings)



def test_bank_pb_uses_one_annual_roe_plus_latest_annualised_quarter_roe():
    annual=[period("BANK","2026-03-31",{"return_on_equity":D(".16"),"total_equity":D("1200")})]
    q=FundamentalPeriod(
        symbol="BANK",basis="consolidated",source_name="NSE",source_url="https://example.com",
        source_reference_id="BANK-Q2",publication_date=date(2026,11,1),
        period_start=date(2026,7,1),period_end=date(2026,9,30),period_kind="quarter",
        metrics={"return_on_equity":D(".18"),"total_equity":D("1300")},
        completeness=D("1"),missing_metrics=tuple(),
    )
    c=CompanyFundamentals(
        symbol="BANK",basis="consolidated",sector="Banking",latest_period=q,
        annual_periods=tuple(annual),quarterly_periods=(q,),growth_score=D("70"),
        balance_sheet_score=D("70"),profitability_score=D("80"),data_completeness=D("1"),
        data_as_of=q.publication_date,source_name="NSE",source_url="https://example.com",notes=tuple(),
    )
    v=value_universe(
        {"BANK":c},{"BANK":{"price_inr":D("100"),"market_cap_inr_crore":D("13000")}},
        {"BANK":"Banking"},
    )["BANK"]
    assert v.method.startswith("Justified P/B")
    assert v.fair_value_low < v.fair_value_base < v.fair_value_high
    assert any("one annual ROE plus a latest annualised quarter" in warning for warning in v.warnings)



def test_bank_valuation_is_provisional_with_one_annual_roe_only():
    annual=[period("BANK","2026-03-31",{
        "return_on_equity":D(".155"),
        "total_equity":D("380000"),
    })]
    c=company("BANK","Banking",annual)
    v=value_universe(
        {"BANK":c},
        {"BANK":{"price_inr":D("1600"),"market_cap_inr_crore":D("1100000")}},
        {"BANK":"Banking"},
    )["BANK"]
    assert v.method.startswith("Justified P/B")
    assert v.fair_value_base is not None
    assert any("only one valid annual ROE" in w for w in v.warnings)
    assert v.confidence <= D(".55")


def test_proxy_only_cash_flow_does_not_qualify_for_fcfe_dcf():
 annual=[period("X",end,{"levered_free_cash_flow_proxy":D("100"),"profit_after_tax":D("10")})
          for end in ["2024-03-31","2025-03-31","2026-03-31"]]
 result=value_universe({"X":company("X","Industrials",annual)},
                       {"X":{"price_inr":D("10"),"market_cap_inr_crore":D("100")}},
                       {"X":"Industrials"})["X"]
 assert result.fair_value_base is None
 assert any("proxy-only cash flows are not discounted" in warning for warning in result.warnings)


def test_peer_only_multiple_checks_do_not_become_fair_value():
    companies={};market={};sectors={s:"Industrials" for s in ["A","B","C","D"]}
    for symbol,cap,price in [("A",1000,10),("B",1200,12),("C",1400,14),("D",1600,16)]:
        annual=[period(symbol,y,{"profit_after_tax":D("30"),"annualised_ebitda":D("40"),"net_debt":D("0"),"total_equity":D("100")})
                for y in ["2025-03-31","2026-03-31"]]
        companies[symbol]=company(symbol,"Industrials",annual)
        market[symbol]={"price_inr":D(price),"market_cap_inr_crore":D(cap)}
    results=value_universe(companies,market,sectors)
    result=results["A"]
    assert result.cross_checks["pe_value"] is not None
    assert result.method == "Sector-relative P/E / EV-EBITDA"
    assert result.fair_value_base is None
    assert result.fair_value_low is None and result.fair_value_high is None
    assert result.confidence <= D(".50")
