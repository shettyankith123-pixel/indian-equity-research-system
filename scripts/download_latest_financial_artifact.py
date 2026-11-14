"""Fetch and validate the newest successful complete financial-ingestion artifact."""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

API="https://api.github.com"
WORKFLOW="nse-financials-ingest.yml"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None


def api_json(url:str,token:str)->dict[str,Any]:
    request=urllib.request.Request(url,headers={
        "Authorization":f"Bearer {token}","Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28","User-Agent":"ies-research",
    })
    with urllib.request.urlopen(request,timeout=45) as response:
        return json.loads(response.read().decode())


def download_zip(repo:str,artifact_id:int,token:str)->bytes:
    url=f"{API}/repos/{repo}/actions/artifacts/{artifact_id}/zip"
    request=urllib.request.Request(url,headers={
        "Authorization":f"Bearer {token}","Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28","User-Agent":"ies-research",
    })
    try:
        with urllib.request.build_opener(NoRedirect).open(request,timeout=45) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        if exc.code not in {301,302,303,307,308}: raise
        location=exc.headers.get("Location")
        if not location: raise RuntimeError("Artifact download redirect missing Location header.")
    with urllib.request.urlopen(urllib.request.Request(location,headers={"User-Agent":"ies-research"}),timeout=90) as response:
        return response.read()


def safe_member(name:str)->bool:
    path=PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and not re.match(r"^[A-Za-z]:",name)


def validate_artifact(payload:bytes,minimum_universe:int=64)->tuple[str,dict[str,Any],list[dict[str,str]],int]:
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        names=z.namelist()
        for name in names:
            if not safe_member(name): raise ValueError(f"Unsafe path in artifact: {name}")
        summary_name=next((n for n in names if n.endswith("/ingest_summary.json")),None)
        coverage_name=next((n for n in names if n.endswith("/filing_coverage.csv")),None)
        db_name=next((n for n in names if n.endswith("/financials.sqlite")),None)
        if not summary_name or not coverage_name or not db_name:
            raise ValueError("Artifact missing ingestion summary, coverage CSV or SQLite database.")
        summary=json.loads(z.read(summary_name).decode())
        coverage=list(csv.DictReader(io.StringIO(z.read(coverage_name).decode("utf-8-sig"))))
        symbols={r.get("symbol","").strip().upper() for r in coverage if r.get("symbol")}
        if int(summary.get("universe_count") or 0)<minimum_universe or len(symbols)<minimum_universe:
            raise ValueError(f"Incomplete universe: summary={summary.get('universe_count')}, coverage symbols={len(symbols)}")
        with z.open(db_name) as dbfile:
            data=dbfile.read()
        db=sqlite3.connect(":memory:")
        db.deserialize(data)
        mcx=db.execute("""
            SELECT COUNT(*) FROM financial_observations
            WHERE symbol='MCX' AND source_url LIKE '%bseindia.com%'
        """).fetchone()[0]
        if mcx<24:
            raise ValueError(f"MCX BSE fallback not present in same DB (observations={mcx}).")
        return db_name,summary,coverage,int(mcx)


def download_latest_full_universe(repo:str,token:str,output_dir:Path)->dict[str,Any]:
    workflow=urllib.parse.quote(WORKFLOW,safe="")
    runs=api_json(f"{API}/repos/{repo}/actions/workflows/{workflow}/runs?branch=main&status=success&per_page=100",token).get("workflow_runs",[])
    last_error=None
    for run in runs:
        run_id=int(run["id"])
        artifacts=api_json(f"{API}/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100",token).get("artifacts",[])
        artifact=next((a for a in artifacts if a.get("name")==f"nse-financial-database-{run_id}" and not a.get("expired")),None)
        if not artifact: continue
        payload=download_zip(repo,int(artifact["id"]),token)
        try:
            db_name,summary,coverage,mcx_count=validate_artifact(payload)
        except (ValueError,KeyError,zipfile.BadZipFile) as exc:
            last_error=f"run {run_id}: {exc}";continue
        run_dir=output_dir/"runs"/f"github-{run_id}"
        run_dir.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            for member in z.infolist():
                if not safe_member(member.filename): raise ValueError(f"Unsafe member: {member.filename}")
            z.extractall(output_dir)
        db_path=output_dir/"runs"/f"github-{run_id}"/"financials.sqlite"
        coverage_path=output_dir/"runs"/f"github-{run_id}"/"filing_coverage.csv"
        if not db_path.exists() or not coverage_path.exists():
            raise RuntimeError("Expected database/coverage files were not extracted to their manifest paths.")
        coverage_counts={}
        for row in coverage:
            key=row.get("status") or "unknown";coverage_counts[key]=coverage_counts.get(key,0)+1
        result={
            "run_id":run_id,"run_url":run.get("html_url"),"head_sha":run.get("head_sha"),
            "created_at":run.get("created_at"),"artifact_id":artifact.get("id"),
            "database_path":str(db_path),"coverage_csv":str(coverage_path),
            "universe_count":int(summary.get("universe_count") or 0),
            "company_count_with_any_filing":int(summary.get("company_count_with_any_filing") or 0),
            "annual_company_count":int(summary.get("annual_company_count") or 0),
            "quarter_company_count":int(summary.get("quarter_company_count") or 0),
            "half_year_company_count":int(summary.get("half_year_company_count") or 0),
            "transition_period_company_count":int(summary.get("transition_period_company_count") or 0),
            "observation_count":int(summary.get("observation_count") or 0),
            "mcx_bse_observations":mcx_count,"coverage_status_counts":coverage_counts,
            "failures":summary.get("failures",[]),
        }
        (output_dir/"latest_64_run.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
        return result
    msg="No successful complete 64-company financial artifact found."
    if last_error: msg += " Latest rejected candidate: "+last_error
    raise RuntimeError(msg)


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--repo",default=os.environ.get("GITHUB_REPOSITORY",""))
    parser.add_argument("--token",default=os.environ.get("GITHUB_TOKEN",""))
    parser.add_argument("--output-dir",type=Path,default=Path("data/financials"))
    args=parser.parse_args()
    if not args.repo or not args.token: parser.error("GitHub repository and token are required.")
    print(json.dumps(download_latest_full_universe(args.repo,args.token,args.output_dir),indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
