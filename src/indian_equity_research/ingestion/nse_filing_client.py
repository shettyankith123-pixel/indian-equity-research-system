from __future__ import annotations

from typing import Any


def fetch_integrated_filing_listing(
    client: Any, symbol: str, issuer: str, *, page: int = 1, size: int = 100
) -> tuple[dict[str, Any] | None, str]:
    """Fetch filings by issuer+symbol, then retry by symbol alone if NSE returns no rows."""
    primary = client.get_integrated_filings(symbol, issuer, page=page, size=size)
    if isinstance(primary, dict) and isinstance(primary.get("data"), list) and primary["data"]:
        return primary, "symbol_and_issuer"

    fallback = client._get(
        "/integrated-filing-results",
        params={
            "index": "equities",
            "symbol": symbol,
            "period_ended": "all",
            "type": "Integrated Filing- Financials",
            "page": page,
            "size": size,
        },
        referer_path="/companies-listing/corporate-integrated-filing",
    )
    if isinstance(fallback, dict) and isinstance(fallback.get("data"), list) and fallback["data"]:
        return fallback, "symbol_only_fallback"
    return (primary if isinstance(primary, dict) else fallback), "no_rows"
