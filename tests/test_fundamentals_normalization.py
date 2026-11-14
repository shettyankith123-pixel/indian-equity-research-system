from datetime import date, datetime, timezone
from decimal import Decimal as D
from indian_equity_research.models.financials import FinancialObservation,FinancialPeriod,SourceReference
from indian_equity_research.analytics.fundamentals import normalize_financial_observations,build_company_fundamentals


def add(rows,metric,value,start,end,kind,reference="ref"):
 period=FinancialPeriod(date.fromisoformat(start),date.fromisoformat(end),kind,"consolidated",D("1"))
 source=SourceReference("NSE","exchange_filing",date.fromisoformat(end),datetime(2026,11,14,tzinfo=timezone.utc),"https://example.com/xbrl",reference)
 unit="ratio" if metric in {"gross_npa_ratio","net_npa_ratio","cet1_ratio","additional_tier1_ratio"} else "INR crore"
 currency="N/A" if unit == "ratio" else "INR"
 rows.append(FinancialObservation("TEST",metric,D(str(value)),unit,currency,period,source))


def fixture():
 rows=[]
 for metric,value in [("total_assets",500),("total_equity",250),("cash_and_cash_equivalents",30),("borrowings",90),("current_assets",220),("current_liabilities",110)]:
  add(rows,metric,value,"2025-03-31","2025-03-31","instant")
 for metric,value in [("revenue_from_operations",900),("profit_before_tax",130),("profit_after_tax_total",90),("finance_costs",15),("depreciation_amortisation",25),("net_cash_from_operating_activities",95),("capital_expenditure",35)]:
  add(rows,metric,value,"2024-04-01","2025-03-31","year")
 for metric,value in [("total_assets",600),("total_equity",300),("cash_and_cash_equivalents",50),("borrowings",120),("current_assets",260),("current_liabilities",130)]:
  add(rows,metric,value,"2026-03-31","2026-03-31","instant")
 for metric,value in [("revenue_from_operations",1000),("profit_before_tax",150),("profit_after_tax_total",100),("finance_costs",20),("depreciation_amortisation",30),("net_cash_from_operating_activities",110),("capital_expenditure",40)]:
  add(rows,metric,value,"2025-04-01","2026-03-31","year")
 return rows


def test_balance_sheet_facts_are_matched_to_instant_period():
 periods=normalize_financial_observations(fixture())
 p=next(x for x in periods if x.period_end==date(2026,3,31) and x.period_kind=="year")
 assert p.metrics["total_assets"]==D("600")
 assert p.metrics["total_equity"]==D("300")
 assert p.metrics["total_debt"]==D("120")
 assert p.metrics["debt_to_equity"]==D(".4")
 assert p.metrics["levered_free_cash_flow_proxy"]==D("70")
 assert p.metrics["net_borrowing"]==D("30")
 assert p.metrics["free_cash_flow_to_equity"]==D("100")
 assert p.metrics["return_on_equity"]==D("100")/D("275")


def test_yoy_growth_is_computed_from_matching_annual_periods():
 periods=normalize_financial_observations(fixture())
 p=next(x for x in periods if x.period_end==date(2026,3,31) and x.period_kind=="year")
 assert p.metrics["revenue_growth_yoy"]==D("1000")/D("900")-D("1")
 assert p.metrics["pat_growth_yoy"]==D("100")/D("90")-D("1")


def test_unknown_noncurrent_debt_does_not_become_zero():
 rows=[]
 for metric,value in [("revenue_from_operations",100),("profit_before_tax",20),("profit_after_tax_total",15),("net_cash_from_operating_activities",20),("capital_expenditure",5)]:
  add(rows,metric,value,"2025-04-01","2026-03-31","year")
 add(rows,"current_borrowings",0,"2026-03-31","2026-03-31","instant")
 add(rows,"total_equity",50,"2026-03-31","2026-03-31","instant")
 p=normalize_financial_observations(rows)[0]
 assert p.metrics["total_debt"] is None
 assert p.metrics["debt_to_equity"] is None


def test_company_data_notes_expose_history_limit():
 periods=normalize_financial_observations(fixture())
 c=build_company_fundamentals(periods,symbol="TEST",sector="Industrials")
 assert len(c.annual_periods)==2
 assert any("Fewer than three" in n for n in c.notes)



def test_bank_equity_is_derived_from_capital_and_reserves_and_roes_are_computed():
 rows=[]
 # Prior-year instant snapshot.
 for metric,value in [
  ("total_assets",4200),("bank_share_capital",40),("bank_reserves_and_surplus",360),
  ("bank_deposits",2600),("bank_advances",2300),("cash_and_cash_equivalents",180),
 ]:
  add(rows,metric,value,"2025-09-30","2025-09-30","instant")
 for metric,value in [
  ("total_income",100),("profit_before_tax",28),("profit_after_tax_total",20),
  ("net_interest_income",35),
 ]:
  add(rows,metric,value,"2025-07-01","2025-09-30","quarter")
 # Current-year instant snapshot.
 for metric,value in [
  ("total_assets",5200),("bank_share_capital",40),("bank_reserves_and_surplus",460),
  ("bank_deposits",3200),("bank_advances",2900),("cash_and_cash_equivalents",220),
 ]:
  add(rows,metric,value,"2026-09-30","2026-09-30","instant")
 for metric,value in [
  ("total_income",125),("profit_before_tax",38),("profit_after_tax_total",30),
  ("net_interest_income",48),
 ]:
  add(rows,metric,value,"2026-07-01","2026-09-30","quarter")

 periods=normalize_financial_observations(rows)
 current=next(p for p in periods if p.period_end==date(2026,9,30) and p.period_kind=="quarter")
 assert current.metrics["total_equity"]==D("500")
 assert current.metrics["total_equity_derivation"]=="bank_capital_plus_reserves"
 assert current.metrics["return_on_equity"]==D("120")/D("450")
 assert current.metrics["bank_advances_to_deposits"]==D("2900")/D("3200")
 assert current.metrics["bank_deposit_growth_yoy"]==D("3200")/D("2600")-D("1")
 company=build_company_fundamentals(periods,symbol="TEST",sector="Banking")
 assert company.data_completeness==D("1")
 assert company.profitability_score==D("100")
 assert company.balance_sheet_score is not None
 assert any("CRAR/CET1" in note for note in company.notes)
 assert any("NPA" in note for note in company.notes)


def test_mcx_profit_after_tax_source_alias_is_normalized():
 rows=[]
 add(rows,"profit_after_tax","454.57","2026-07-01","2026-09-30","quarter")
 periods=normalize_financial_observations(rows)
 current=next(p for p in periods if p.period_kind=="quarter")
 assert current.metrics["profit_after_tax"]==D("454.57")



def test_same_date_instant_snapshots_merge_facts_across_filings():
 rows=[]
 # The FY25 filing contains the full opening bank balance sheet.
 for metric,value in [
  ("bank_share_capital",40),("bank_reserves_and_surplus",360),
  ("total_assets",4200),("bank_deposits",2600),("bank_advances",2200),
 ]:
  add(rows,metric,value,"2025-03-31","2025-03-31","instant","FY25")
 # The FY26 filing carries the same comparative date, but only has cash.
 add(rows,"cash_and_cash_equivalents",180,"2025-03-31","2025-03-31","instant","FY26")
 # The FY26 filing has its full closing balance sheet.
 for metric,value in [
  ("bank_share_capital",40),("bank_reserves_and_surplus",460),
  ("total_assets",5200),("bank_deposits",3200),("bank_advances",2900),
 ]:
  add(rows,metric,value,"2026-03-31","2026-03-31","instant","FY26")
 add(rows,"profit_after_tax_total",90,"2025-04-01","2026-03-31","year","FY26")
 add(rows,"net_interest_income",150,"2025-04-01","2026-03-31","year","FY26")
 periods=normalize_financial_observations(rows)
 current=next(p for p in periods if p.period_kind=="year" and p.period_end==date(2026,3,31))
 assert current.metrics["total_equity"]==D("500")
 assert current.metrics["return_on_equity"]==D("90")/D("450")
 assert current.metrics["bank_deposit_growth_yoy"]==D("3200")/D("2600")-D("1")


def test_bank_uses_annual_roe_when_latest_interim_cannot_calculate_roe():
 rows=fixture()
 # Latest interim statement has no comparable snapshot from a year earlier.
 for metric,value in [("total_assets",700),("total_equity",350),("borrowings",130)]:
  add(rows,metric,value,"2026-09-30","2026-09-30","instant")
 for metric,value in [("total_income",35),("profit_before_tax",10),("profit_after_tax_total",8),("net_interest_income",12)]:
  add(rows,metric,value,"2026-07-01","2026-09-30","quarter")
 periods=normalize_financial_observations(rows)
 interim=next(p for p in periods if p.period_end==date(2026,9,30) and p.period_kind=="quarter")
 assert interim.metrics["return_on_equity"] is None
 company=build_company_fundamentals(periods,symbol="TEST",sector="Banking")
 assert company.profitability_score is not None
 assert any("profitability proxy uses annual ROE" in note for note in company.notes)
 assert not any("ROE unavailable:" in note for note in company.notes)


def test_bank_risk_metrics_reported_in_duration_context_reach_latest_fundamentals():
 rows=[]
 for metric,value in [
  ("total_assets",5200),("bank_share_capital",40),("bank_reserves_and_surplus",460),
  ("bank_deposits",3200),("bank_advances",2900),("cash_and_cash_equivalents",220),
 ]:
  add(rows,metric,value,"2026-09-30","2026-09-30","instant")
 for metric,value in [
  ("total_income",125),("profit_before_tax",38),("profit_after_tax_total",30),
  ("net_interest_income",48),("gross_npa_reported",23577.02),("net_npa_reported",5706.22),
  ("gross_npa_ratio",0.012),("net_npa_ratio",0.003),("cet1_ratio",0.1601),
  ("additional_tier1_ratio",0.0),
 ]:
  add(rows,metric,value,"2026-07-01","2026-09-30","quarter")
 periods=normalize_financial_observations(rows)
 company=build_company_fundamentals(periods,symbol="TEST",sector="Banking")
 latest=company.latest_period
 assert latest is not None
 assert latest.metrics["gross_npa"]==D("23577.02")
 assert latest.metrics["net_npa"]==D("5706.22")
 assert latest.metrics["gross_npa_ratio"]==D("0.012")
 assert latest.metrics["net_npa_ratio"]==D("0.003")
 assert latest.metrics["cet1_ratio"]==D("0.1601")
 assert company.data_completeness==D("1")
 assert any("GNPA 1.20%, NNPA 0.30%" in note for note in company.notes)
 assert any("CET1 ratio: 16.01%" in note for note in company.notes)
 assert any("Provision coverage/PCR is not mapped" in note for note in company.notes)
