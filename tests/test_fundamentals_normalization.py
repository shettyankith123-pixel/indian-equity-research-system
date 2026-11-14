from datetime import date, datetime, timezone
from decimal import Decimal as D
from indian_equity_research.models.financials import FinancialObservation,FinancialPeriod,SourceReference
from indian_equity_research.analytics.fundamentals import normalize_financial_observations,build_company_fundamentals


def add(rows,metric,value,start,end,kind):
 period=FinancialPeriod(date.fromisoformat(start),date.fromisoformat(end),kind,"consolidated",D("1"))
 source=SourceReference("NSE","exchange_filing",date.fromisoformat(end),datetime(2026,11,14,tzinfo=timezone.utc),"https://example.com/xbrl","ref")
 rows.append(FinancialObservation("TEST",metric,D(str(value)),"INR crore","INR",period,source))


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
 assert p.metrics["free_cash_flow_to_equity_proxy"]==D("70")
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
