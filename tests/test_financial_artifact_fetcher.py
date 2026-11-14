import io,json,sqlite3,zipfile
import pytest
from scripts.download_latest_financial_artifact import validate_artifact,safe_member


def make_artifact(count=64,include_mcx=True):
 db=sqlite3.connect(":memory:")
 db.execute("create table financial_observations(symbol text,source_url text)")
 if include_mcx:
  for _ in range(24): db.execute("insert into financial_observations values('MCX','https://www.bseindia.com/example')")
 payload=db.serialize();db.close()
 out=io.BytesIO()
 with zipfile.ZipFile(out,"w") as z:
  prefix="runs/github-12345/"
  z.writestr(prefix+"ingest_summary.json",json.dumps({"universe_count":count}))
  z.writestr(prefix+"filing_coverage.csv","symbol,status\n"+"".join(f"S{i},ok\n" for i in range(count)))
  z.writestr(prefix+"financials.sqlite",payload)
 return out.getvalue()


def test_full_universe_artifact_with_mcx_validates():
 db,summary,coverage,mcx=validate_artifact(make_artifact())
 assert db.endswith("financials.sqlite") and summary["universe_count"]==64
 assert len(coverage)==64 and mcx==24


def test_artifact_without_mcx_is_rejected():
 with pytest.raises(ValueError,match="MCX BSE fallback"):
  validate_artifact(make_artifact(include_mcx=False))


def test_incomplete_universe_is_rejected():
 with pytest.raises(ValueError,match="Incomplete universe"):
  validate_artifact(make_artifact(count=63))


@pytest.mark.parametrize("name",["../escape","/root/file","C:/outside","runs/../../bad"])
def test_path_traversal_is_rejected(name):
 assert not safe_member(name)
