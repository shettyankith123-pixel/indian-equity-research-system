"""Build financial histories, valuation register and conservative Wealth Scan inputs."""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from indian_equity_research.analytics.decision_engine import decide
from indian_equity_research.analytics.fundamentals import normalize_financial_observations, build_company_fundamentals
from indian_equity_research.models.recommendations import ResearchInput
from indian_equity_research.storage.repository import FinancialRepository
from indian_equity_research.valuation.sector_valuation import value_universe


def _decimal(value: str | None) -> Decimal | None:
    return Decimal(value.strip()) if value and value.strip() else None


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8"); return
    fields=[]
    for row in rows:
        for key in row:
            if key not in fields: fields.append(key)
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)



def valuation_screen(
    price: Decimal | None,
    low: Decimal | None,
    base: Decimal | None,
    method: str = "Intrinsic valuation",
    confidence: Decimal = Decimal("1"),
) -> dict[str, str]:
    """Show entry zones only when a defensible intrinsic value is available."""
    if method == "Sector-relative P/E / EV-EBITDA":
        return {"valuation_signal": "RELATIVE_ONLY_CONTEXT", "upside_to_base_pct": "", "margin_of_safety_pct": "", "buy_entry_max": "", "accumulate_entry_max": ""}
    if price is None or base is None or price <= 0 or base <= 0:
        return {"valuation_signal": "NO_RELIABLE_FAIR_VALUE", "upside_to_base_pct": "", "margin_of_safety_pct": "", "buy_entry_max": "", "accumulate_entry_max": ""}
    if confidence < Decimal("0.65"):
        return {"valuation_signal": "LOW_CONFIDENCE_REFERENCE_ONLY", "upside_to_base_pct": "", "margin_of_safety_pct": "", "buy_entry_max": "", "accumulate_entry_max": ""}
    buy_entry = base * Decimal("0.85")
    accumulate_entry = base * Decimal("0.92")
    upside = (base / price - Decimal("1")) * Decimal("100")
    margin = (Decimal("1") - price / base) * Decimal("100")
    if low is not None and price <= low:
        signal = "BELOW_BEAR_CASE"
    elif price <= buy_entry:
        signal = "POTENTIALLY_ATTRACTIVE"
    elif price <= accumulate_entry:
        signal = "WATCH_FOR_ACCUMULATION"
    elif price < base:
        signal = "BELOW_BASE_FAIR_VALUE"
    else:
        signal = "ABOVE_BASE_FAIR_VALUE"
    return {
        "valuation_signal": signal,
        "upside_to_base_pct": str(upside),
        "margin_of_safety_pct": str(margin),
        "buy_entry_max": str(buy_entry),
        "accumulate_entry_max": str(accumulate_entry),
    }


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--db",type=Path,required=True)
    parser.add_argument("--market-snapshot",type=Path,default=Path("data/imports/indmoney_market_snapshot_2026-11-14.csv"))
    parser.add_argument("--universe",type=Path,default=Path("data/universe/indian_watchlist_companies.csv"))
    parser.add_argument("--holdings-snapshot",type=Path,default=Path("data/imports/indmoney_holdings_snapshot_2026-11-13.csv"))
    parser.add_argument("--output-dir",type=Path,default=Path("reports/research-build"))
    args=parser.parse_args()

    with args.universe.open(newline="",encoding="utf-8-sig") as f:
        universe_rows=list(csv.DictReader(f))
    universe={r["symbol"].strip().upper():r for r in universe_rows}
    with args.market_snapshot.open(newline="",encoding="utf-8-sig") as f:
        quote_rows=list(csv.DictReader(f))
    market={}
    quote_dates={}
    for r in quote_rows:
        symbol=r["symbol"].strip().upper()
        market[symbol]={
            "price_inr":_decimal(r.get("price_inr")),
            "market_cap_inr_crore":_decimal(r.get("market_cap_inr_crore")),
            "price_updated_at_ist":r.get("price_updated_at_ist",""),
        }
        stamp=(r.get("price_updated_at_ist") or "")[:10]
        if stamp: quote_dates[symbol]=date.fromisoformat(stamp)
    held=set()
    if args.holdings_snapshot.exists():
        with args.holdings_snapshot.open(newline="",encoding="utf-8-sig") as f:
            held={r["symbol"].strip().upper() for r in csv.DictReader(f) if Decimal(r.get("quantity") or "0")>0}

    repo=FinancialRepository(args.db)
    observations=repo.list_observations()
    normalized=normalize_financial_observations(observations)
    instant_observations=[o for o in observations if o.period.kind=="instant"]
    instant_symbols={o.symbol for o in instant_observations}
    latest_instant_by_symbol={}
    instant_metric_symbols={}
    for observation in instant_observations:
        latest_instant_by_symbol[observation.symbol]=max(
            latest_instant_by_symbol.get(observation.symbol,observation.period.end_date),
            observation.period.end_date,
        )
        instant_metric_symbols.setdefault(observation.metric,set()).add(observation.symbol)
    companies={}; basis_used={}
    for symbol,record in universe.items():
        primary=build_company_fundamentals(normalized,symbol=symbol,sector=record.get("sector","Unclassified"),basis="consolidated")
        if primary.latest_period:
            companies[symbol]=primary;basis_used[symbol]="consolidated"
        else:
            secondary=build_company_fundamentals(normalized,symbol=symbol,sector=record.get("sector","Unclassified"),basis="standalone")
            companies[symbol]=secondary
            if secondary.latest_period: basis_used[symbol]="standalone"
    sectors={s:r.get("sector","Unclassified") for s,r in universe.items()}
    valuations=value_universe(companies,market,sectors)

    period_rows=[]
    for p in normalized:
        if p.symbol not in universe: continue
        row={"symbol":p.symbol,"sector":sectors[p.symbol],"basis":p.basis,
             "period_start":p.period_start.isoformat(),"period_end":p.period_end.isoformat(),
             "period_kind":p.period_kind,"source_name":p.source_name,"source_url":p.source_url or "",
             "publication_date":p.publication_date.isoformat(),"completeness":str(p.completeness),
             "missing_metrics":";".join(p.missing_metrics)}
        row.update({f"metric_{k}":str(v) if v is not None else "" for k,v in p.metrics.items()})
        period_rows.append(row)

    fundamentals_rows=[];valuation_rows=[];research_rows=[];decision_rows=[]
    for symbol,record in universe.items():
        c=companies[symbol];v=valuations[symbol];latest=c.latest_period
        fundamentals_rows.append({
            "symbol":symbol,"sector":sectors[symbol],"basis_used":basis_used.get(symbol,"missing"),
            "latest_publication_date":latest.publication_date.isoformat() if latest else "",
            "latest_period_end":latest.period_end.isoformat() if latest else "",
            "latest_period_kind":latest.period_kind if latest else "",
            "annual_period_count":len(c.annual_periods),
            "quarter_or_half_year_period_count":len(c.quarterly_periods),
            "financial_data_completeness":str(c.data_completeness),
            "profitability_score_financial_proxy":str(c.profitability_score) if c.profitability_score is not None else "",
            "growth_score_financial_proxy":str(c.growth_score) if c.growth_score is not None else "",
            "balance_sheet_score_financial_proxy":str(c.balance_sheet_score) if c.balance_sheet_score is not None else "",
            "limitations":"; ".join(c.notes),
        })
        screen = valuation_screen(v.current_price, v.fair_value_low, v.fair_value_base, v.method, v.confidence)
        valuation_rows.append({
            "symbol":symbol,"sector":sectors[symbol],
            "price_inr":str(v.current_price) if v.current_price is not None else "",
            "market_cap_inr_crore":str(v.market_cap_inr_crore) if v.market_cap_inr_crore is not None else "",
            "fair_value_low":str(v.fair_value_low) if v.fair_value_low is not None else "",
            "fair_value_base":str(v.fair_value_base) if v.fair_value_base is not None else "",
            "fair_value_high":str(v.fair_value_high) if v.fair_value_high is not None else "",
            **screen,
            "method":v.method,"confidence":str(v.confidence),"valuation_status":v.valuation_status,
            "quote_timestamp":market.get(symbol,{}).get("price_updated_at_ist",""),
            "cross_checks":"; ".join(f"{k}={value}" for k,value in v.cross_checks.items() if value is not None),
            "assumptions":json.dumps(v.assumptions,sort_keys=True),
            "warnings":"; ".join(v.warnings),
        })
        source_name=c.source_name or ""
        source_url=c.source_url or ""
        as_of=c.data_as_of
        if symbol in quote_dates:
            as_of=min(as_of,quote_dates[symbol]) if as_of else quote_dates[symbol]
        note=("Valuation: "+v.method+" ("+v.valuation_status+"). "
              +" ".join(c.notes)+" "+" ".join(v.warnings)
              +" Governance and qualitative thesis review not completed; no BUY/ACCUMULATE until cleared.").strip()
        # The automated engine deliberately leaves the overall quality and governance
        # scores blank. Financial-only ratios are not substitutes for business quality.
        item=ResearchInput(
            symbol=symbol,sector=sectors[symbol],current_price=v.current_price,
            fair_value_base=v.fair_value_base,fair_value_low=v.fair_value_low,fair_value_high=v.fair_value_high,
            quality_score=None,growth_score=c.growth_score,balance_sheet_score=c.balance_sheet_score,
            governance_score=None,data_completeness=c.data_completeness if latest else None,
            data_as_of=as_of,valuation_confidence=v.confidence if v.fair_value_base is not None else None,
            held=symbol in held,notes=note,source_name=source_name,source_url=source_url,
        )
        research_rows.append({
            "symbol":symbol,"sector":sectors[symbol],
            "current_price":str(item.current_price) if item.current_price is not None else "",
            "fair_value_base":str(item.fair_value_base) if item.fair_value_base is not None else "",
            "fair_value_low":str(item.fair_value_low) if item.fair_value_low is not None else "",
            "fair_value_high":str(item.fair_value_high) if item.fair_value_high is not None else "",
            "quality_score":"","growth_score":str(item.growth_score) if item.growth_score is not None else "",
            "balance_sheet_score":str(item.balance_sheet_score) if item.balance_sheet_score is not None else "",
            "governance_score":"",
            "data_completeness":str(item.data_completeness) if item.data_completeness is not None else "",
            "data_as_of":item.data_as_of.isoformat() if item.data_as_of else "",
            "valuation_confidence":str(item.valuation_confidence) if item.valuation_confidence is not None else "",
            "thesis_broken":"false","major_risk_flag":"false","held":str(item.held).lower(),
            "notes":note,"source_name":source_name,"source_url":source_url,
        })
        decision_rows.append(decide(item).to_dict())

    args.output_dir.mkdir(parents=True,exist_ok=True)
    _write_csv(args.output_dir/"financial_periods.csv",period_rows)
    _write_csv(args.output_dir/"company_fundamentals.csv",fundamentals_rows)
    _write_csv(args.output_dir/"valuation_register.csv",valuation_rows)
    _write_csv(
        args.output_dir/"valuation_opportunity_screen.csv",
        sorted(
            valuation_rows,
            key=lambda row: (
                row.get("valuation_signal") not in {"BELOW_BEAR_CASE","POTENTIALLY_ATTRACTIVE","WATCH_FOR_ACCUMULATION"},
                -float(row["margin_of_safety_pct"]) if row.get("margin_of_safety_pct") else float("inf"),
            ),
        ),
    )
    _write_csv(args.output_dir/"research_inputs.csv",research_rows)
    _write_csv(args.output_dir/"wealth_scan_preview.csv",decision_rows)
    counts={}
    for row in decision_rows:
        rec=row["recommendation"];counts[rec]=counts.get(rec,0)+1
    valuation_method_counts={}
    for result in valuations.values():
        valuation_method_counts[result.method]=valuation_method_counts.get(result.method,0)+1
    valuation_signal_counts={}
    for row in valuation_rows:
        signal=row["valuation_signal"]
        valuation_signal_counts[signal]=valuation_signal_counts.get(signal,0)+1
    latest_period_end_by_symbol={
        symbol:company.latest_period.period_end
        for symbol,company in companies.items() if company.latest_period is not None
    }
    summary={
        "universe_count":len(universe),
        "market_quote_count":sum(1 for s in universe if market.get(s,{}).get("price_inr") is not None),
        "companies_with_financial_history":sum(1 for c in companies.values() if c.latest_period is not None),
        "companies_with_2plus_annual_periods":sum(1 for c in companies.values() if len(c.annual_periods)>=2),
        "companies_with_3plus_annual_periods":sum(1 for c in companies.values() if len(c.annual_periods)>=3),
        "companies_with_any_instant_balance_sheet":len(instant_symbols),
        "companies_with_instant_balance_sheet_at_latest_period":sum(
            1 for symbol in instant_symbols
            if latest_instant_by_symbol.get(symbol)==latest_period_end_by_symbol.get(symbol)
        ),
        "instant_balance_sheet_observation_count":len(instant_observations),
        "instant_balance_sheet_metric_symbol_counts":{
            metric:len(symbols) for metric,symbols in sorted(instant_metric_symbols.items())
        },
        "companies_with_provisional_fair_value":sum(1 for v in valuations.values() if v.fair_value_base is not None),
        "valuation_method_counts":valuation_method_counts,
        "valuation_signal_counts":valuation_signal_counts,
        "financial_observation_count":len(observations),
        "normalized_period_count":len(normalized),
        "decision_counts":counts,"held_symbols":sorted(held),
        "basis_used":basis_used,
        "integrity_note":"Automated score does not include governance, management-quality or qualitative thesis review. BUY/ACCUMULATE is blocked until those gates are reviewed.",
    }
    (args.output_dir/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
