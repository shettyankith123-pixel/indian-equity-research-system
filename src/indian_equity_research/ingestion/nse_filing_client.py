from __future__ import annotations

import json
from typing import Any


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed >= 0 else None


def _fallback_page(client: Any, symbol: str, *, page: int, size: int) -> Any:
    return client._get(
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


def _row_identity(row: dict[str, Any]) -> str:
    # NSE normally supplies seq_Id. XBRL URLs are the next-best stable key;
    # canonical JSON is a deterministic fallback for unexpected row shapes.
    for field in ("seq_Id", "seq_id", "seqId", "xbrl", "xbrlFile", "attachmentFile"):
        value = row.get(field)
        if value not in (None, ""):
            return f"{field}:{value}"
    return "row:" + json.dumps(row, sort_keys=True, default=str)


def _revision_rank(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("revised_Date") or ""),
        str(row.get("creation_Date") or ""),
        str(row.get("broadcast_Date") or ""),
    )


def fetch_integrated_filing_listing(
    client: Any,
    symbol: str,
    issuer: str,
    *,
    page: int = 1,
    size: int = 100,
    max_pages: int = 100,
) -> tuple[dict[str, Any] | None, str]:
    """Fetch and combine all available NSE Integrated Filing pages.

    NSE's response exposes totalCount, page and size. When totalCount is
    available, it determines the final page. Older/unexpected responses
    without a usable totalCount fall back to the short-page termination
    rule. A hard page cap prevents an accidental unbounded request loop.

    The returned dictionary retains the first-page metadata, replaces data
    with the combined de-duplicated rows, and adds a private _pagination
    summary for the importer/audit report.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if size < 1:
        raise ValueError("size must be >= 1")
    if max_pages < 1:
        raise ValueError("max_pages must be >= 1")

    primary = client.get_integrated_filings(symbol, issuer, page=page, size=size)
    if isinstance(primary, dict) and isinstance(primary.get("data"), list) and primary["data"]:
        listing = primary
        query_mode = "symbol_and_issuer"
    else:
        fallback = _fallback_page(client, symbol, page=page, size=size)
        if isinstance(fallback, dict) and isinstance(fallback.get("data"), list) and fallback["data"]:
            listing = fallback
            query_mode = "symbol_only_fallback"
        else:
            return (primary if isinstance(primary, dict) else fallback), "no_rows"

    first_rows = listing.get("data")
    if not isinstance(first_rows, list):
        raise RuntimeError(f"NSE filing page {page} has an invalid data field")

    raw_total = listing.get("totalCount", listing.get("total_count"))
    total_count = _positive_int(raw_total)
    last_page = (total_count + size - 1) // size if total_count is not None else None
    if last_page is not None:
        last_page = max(page, last_page)
        pages_to_fetch = last_page - page + 1
        if pages_to_fetch > max_pages:
            raise RuntimeError(
                f"NSE filing pagination requires {pages_to_fetch} pages; "
                f"configured safety cap is {max_pages}"
            )

    combined: dict[str, dict[str, Any]] = {}
    duplicate_count = 0
    raw_row_count = 0
    pages_fetched = 0

    def add_rows(rows: list[Any]) -> None:
        nonlocal duplicate_count, raw_row_count
        raw_row_count += len(rows)
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = _row_identity(row)
            previous = combined.get(key)
            if previous is None:
                combined[key] = row
            else:
                duplicate_count += 1
                if _revision_rank(row) > _revision_rank(previous):
                    combined[key] = row

    current_listing = listing
    current_page = page
    while True:
        current_rows = current_listing.get("data")
        if not isinstance(current_rows, list):
            raise RuntimeError(f"NSE filing page {current_page} has an invalid data field")
        if not current_rows:
            if pages_fetched == 0 or last_page is None:
                break
            raise RuntimeError(
                f"NSE filing pagination stopped at empty page {current_page} "
                f"before the expected final page {last_page}"
            )

        pages_fetched += 1
        add_rows(current_rows)

        if last_page is not None:
            if current_page >= last_page:
                break
        elif len(current_rows) < size:
            break

        next_page = current_page + 1
        if pages_fetched >= max_pages:
            raise RuntimeError(
                f"NSE filing pagination reached the safety cap of {max_pages} pages "
                "without proving that the listing is complete"
            )

        if query_mode == "symbol_and_issuer":
            next_listing = client.get_integrated_filings(
                symbol, issuer, page=next_page, size=size
            )
        else:
            next_listing = _fallback_page(
                client, symbol, page=next_page, size=size
            )

        if not isinstance(next_listing, dict) or not isinstance(next_listing.get("data"), list):
            raise RuntimeError(
                f"NSE filing pagination returned an invalid response for page {next_page}"
            )
        current_listing = next_listing
        current_page = next_page

    listing["data"] = list(combined.values())
    listing["_pagination"] = {
        "start_page": page,
        "pages_fetched": pages_fetched,
        "page_size": size,
        "reported_total_count": total_count,
        "raw_rows": raw_row_count,
        "unique_rows": len(combined),
        "duplicates_removed": duplicate_count,
        "complete": (
            len(combined) >= total_count
            if total_count is not None
            else (pages_fetched > 0)
        ),
    }
    return listing, query_mode
