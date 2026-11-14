from datetime import date,datetime,timezone
from decimal import Decimal
from indian_equity_research.models.financials import FinancialObservation,FinancialPeriod,SourceReference
from indian_equity_research.storage.repository import FinancialRepository


def make(symbol,metric,value,start,end,kind,basis,ref):
 period=FinancialPeriod(date.fromisoformat(start),date.fromisoformat(end),kind,basis,Decimal("1"))
 source=SourceReference("NSE","exchange_filing",date.fromisoformat(end),datetime(2026,11,14,tzinfo=timezone.utc),"https://example.com/a.xml",ref)
 return FinancialObservation(symbol,metric,Decimal(str(value)),"INR crore","INR",period,source)


def test_list_observations_preserves_bases_and_instant_kinds(tmp_path):
 repo=FinancialRepository(tmp_path/"test.sqlite")
 repo.insert_many([
  make("ABC","revenue_from_operations","100","2025-04-01","2026-03-31","year","consolidated","filing-c"),
  make("ABC","total_assets","500","2026-03-31","2026-03-31","instant","consolidated","filing-c"),
  make("ABC","revenue_from_operations","90","2025-04-01","2026-03-31","year","standalone","filing-s"),
 ])
 rows=repo.list_observations()
 assert len(rows)==3
 assert {x.period.basis for x in rows}=={"consolidated","standalone"}
 assert {x.period.kind for x in rows}=={"year","instant"}
 assert len(repo.list_observations(basis="consolidated"))==2
 assert len(repo.list_observations(symbol="ABC",period_kind="instant"))==1
