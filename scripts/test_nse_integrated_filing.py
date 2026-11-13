from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urljoin
from nse_xbrl import FilingResult, NSEClient, parse_xbrl

SYMBOL = "ICICIBANK"
ISSUER = "ICICI Bank Limited"

def main() -> int:
    client = NSEClient()
    client._seed_session()
    listing = client.get_integrated_filings(SYMBOL, ISSUER, page=1, size=50)
    if not isinstance(listing, dict):
        raise RuntimeError("NSE Integrated Filing API returned no JSON; cookie-backed access may be required.")
    rows = listing.get("data") or []
    if not rows:
        raise RuntimeError(f"NSE Integrated Filing API returned zero filings. Response keys: {sorted(listing)}")
    target_rows = [r for r in rows if "30-SEP-2026" in str(r.get("qe_Date", "")).upper()]
    if not target_rows:
        raise RuntimeError(f"No 30-Sep-2026 filing found in first page; count={len(rows)}")
    row = next((r for r in target_rows if str(r.get("consolidated", "")).casefold() == "standalone"), target_rows[0])
    xbrl_url = row.get("xbrl") or row.get("xbrlFile") or row.get("attachmentFile")
    if not xbrl_url:
        raise RuntimeError(f"Filing metadata has no XBRL link. Row keys: {sorted(row)}")
    if str(xbrl_url).startswith("/"):
        xbrl_url = urljoin("https://nsearchives.nseindia.com/", str(xbrl_url))
    xml_text = client.get_integrated_xbrl(str(xbrl_url))
    if not xml_text or "<" not in xml_text[:100]:
        raise RuntimeError("Could not download official NSE XBRL attachment.")
    result = FilingResult.from_xbrl(
        xml_text, symbol=SYMBOL, company_name=row.get("companyName", row.get("cmName", ISSUER)),
        seq_id=str(row.get("seq_Id", "")),
        is_audited=str(row.get("audited", "")).upper() == "AUDITED",
        is_consolidated=str(row.get("consolidated", "")).upper() == "CONSOLIDATED",
        xbrl_url=str(xbrl_url),
    )
    parsed = parse_xbrl(xml_text)
    contexts = parsed["contexts"]
    facts = parsed["facts"]
    def fact_value(*names: str, context: str = "OneD"):
        for name in names:
            value = facts.get(name, {}).get(context)
            if value not in (None, ""):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass
        return None
    period_end = contexts.get("OneD", {}).get("end")
    period_start = contexts.get("OneD", {}).get("start")
    # The Banking taxonomy uses ProfitLossForThePeriod rather than the
    # near-identical tag expected by the generic parser package.
    q_pat = fact_value("ProfitLossForThePeriod", "ProfitLossFromOrdinaryActivitiesAfterTax")
    q_pbt = fact_value("ProfitLossFromOrdinaryActivitiesBeforeTax", "ProfitBeforeTax")
    q_total_income = fact_value("Income", "TotalIncome")
    q_op_profit_pre_provisions = fact_value("OperatingProfitBeforeProvisionAndContingencies")
    q_interest_earned = fact_value("InterestEarned")
    q_interest_expended = fact_value("InterestExpended")
    q_nii = (
        q_interest_earned - q_interest_expended
        if q_interest_earned is not None and q_interest_expended is not None else None
    )
    if period_end is None or q_pat is None:
        Path("nse-financials-debug.xml").write_text(xml_text, encoding="utf-8")
        interesting = {
            tag: values for tag, values in parsed["facts"].items()
            if any(word in tag.lower() for word in ("profit", "pat", "revenue", "income", "result"))
        }
        print(json.dumps({
            "filing_metadata": row,
            "xbrl_url": str(xbrl_url),
            "xml_prefix": xml_text[:600],
            "context_ids": list(parsed["contexts"].keys())[:80],
            "context_examples": contexts,
            "selected_period_end": period_end,
            "selected_period_start": period_start,
            "parsed_bank_metrics": {
                "q_pat_inr": q_pat,
                "q_pbt_inr": q_pbt,
                "q_total_income_inr": q_total_income,
                "q_operating_profit_before_provisions_inr": q_op_profit_pre_provisions,
                "q_interest_earned_inr": q_interest_earned,
                "q_interest_expended_inr": q_interest_expended,
                "q_nii_inr": q_nii,
            },
            "interesting_facts": interesting,
            "fact_count": len(parsed["facts"]),
        }, indent=2, default=str))
        raise RuntimeError("XBRL downloaded but parser mapping did not produce period/PAT. Debug details printed; no financials imported.")
    output = {
        "symbol": SYMBOL, "company_name": row.get("cmName", result.company_name), "seq_id": result.seq_id,
        "period_start": period_start.isoformat() if period_start else None,
        "period_end": period_end.isoformat(), "basis": row.get("consolidated"),
        "audited": row.get("audited"),
        "q_pat_inr_crore": q_pat / 1e7,
        "q_pbt_inr_crore": q_pbt / 1e7 if q_pbt is not None else None,
        "q_total_income_inr_crore": q_total_income / 1e7 if q_total_income is not None else None,
        "q_operating_profit_before_provisions_inr_crore": q_op_profit_pre_provisions / 1e7 if q_op_profit_pre_provisions is not None else None,
        "q_nii_inr_crore": q_nii / 1e7 if q_nii is not None else None,
        "q_interest_earned_inr_crore": q_interest_earned / 1e7 if q_interest_earned is not None else None,
        "q_interest_expended_inr_crore": q_interest_expended / 1e7 if q_interest_expended is not None else None,
        "xbrl_url": str(xbrl_url),
        "data_source": "NSE Integrated Filing - Financials (official filing; public undocumented endpoint)"
    }
    Path("financials-smoke.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
