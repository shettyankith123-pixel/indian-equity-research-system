from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urljoin
from nse_xbrl import FilingResult, NSEClient

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
    row = next((r for r in rows if "30-SEP-2026" in str(r.get("qe_Date", "")).upper()), rows[0])
    xbrl_url = row.get("xbrl") or row.get("xbrlFile") or row.get("attachmentFile")
    if not xbrl_url:
        raise RuntimeError(f"Filing metadata has no XBRL link. Row keys: {sorted(row)}")
    if str(xbrl_url).startswith("/"):
        xbrl_url = urljoin("https://nsearchives.nseindia.com/", str(xbrl_url))
    xml_text = client.get_integrated_xbrl(str(xbrl_url))
    if not xml_text or "<" not in xml_text[:100]:
        raise RuntimeError("Could not download official NSE XBRL attachment.")
    result = FilingResult.from_xbrl(
        xml_text, symbol=SYMBOL, company_name=row.get("companyName", ISSUER),
        seq_id=str(row.get("seq_Id", "")),
        is_audited=str(row.get("audited", "")).upper() == "AUDITED",
        is_consolidated=str(row.get("consolidated", "")).upper() == "CONSOLIDATED",
        xbrl_url=str(xbrl_url),
    )
    if result.period_end is None or result.q_pat is None:
        raise RuntimeError("XBRL was downloaded but period/PAT could not be parsed; do not import partial facts.")
    output = {
        "symbol": SYMBOL, "company_name": result.company_name, "seq_id": result.seq_id,
        "period_start": result.period_start.isoformat() if result.period_start else None,
        "period_end": result.period_end.isoformat(), "is_audited": result.is_audited,
        "is_consolidated": result.is_consolidated,
        "revenue_inr_crore": result.q_revenue / 1e7 if result.q_revenue is not None else None,
        "pat_inr_crore": result.q_pat / 1e7, "basic_eps_inr": result.q_basic_eps,
        "xbrl_url": result.xbrl_url,
        "data_source": "NSE Integrated Filing - Financials (official filing; public undocumented endpoint)"
    }
    Path("financials-smoke.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
