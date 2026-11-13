"""Date-aware XBRL duration-context selection shared by ingestion and tests."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any


def parse_iso_or_nse(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None

def row_basis(row: dict[str, Any]) -> str:
    raw = str(row.get("consolidated") or row.get("basis") or "").strip().casefold()
    if "standalone" in raw:
        return "standalone"
    if "consolidated" in raw:
        return "consolidated"
    return ""

def filing_date(row: dict[str, Any]) -> date | None:
    return parse_iso_or_nse(row.get("qe_Date") or row.get("periodEnd") or row.get("period_ended"))

def date_rank(row: dict[str, Any]) -> str:
    return str(row.get("revised_Date") or row.get("creation_Date") or row.get("broadcast_Date") or "")

def latest_for_basis(rows: list[dict[str, Any]], basis: str) -> dict[str, Any] | None:
    matches = [r for r in rows if row_basis(r) == basis]
    if not matches:
        return None
    # Preserve the most recently revised/created filing when NSE exposes revisions.
    matches.sort(key=lambda r: (str(r.get("revised_Date") or ""), str(r.get("creation_Date") or ""), str(r.get("broadcast_Date") or "")), reverse=True)
    return matches[0]

def decimal_fact(facts: dict[str, Any], names: tuple[str, ...], context: str) -> tuple[Decimal | None, str | None]:
    for tag in names:
        value = facts.get(tag, {}).get(context)
        if value in (None, ""):
            continue
        try:
            number = Decimal(str(value))
            if number.is_finite():
                return number, tag
        except (InvalidOperation, ValueError):
            continue
    return None, None


def choose_duration_context(
    contexts: dict[str, Any],
    expected_end: date,
    period_kind: str,
    facts: dict[str, Any] | None = None,
    preferred_tags: tuple[str, ...] = (),
) -> tuple[str, date, date]:
    """Select a duration context by dates and by the presence of reported facts.

    NSE issuers use different context IDs for the main financial statement and
    attached schedules. Among contexts with the required duration, prefer the
    one containing the most relevant financial facts.
    """
    ranges = {
        "quarter": (70, 120, 91),
        "half_year": (150, 220, 182),
        "year": (300, 380, 365),
    }
    if period_kind not in ranges:
        raise ValueError(f"unsupported period_kind: {period_kind}")
    min_days, max_days, target_days = ranges[period_kind]
    candidates: list[tuple[int, int, str, date, date]] = []
    for context_id, context in contexts.items():
        start = parse_iso_or_nse(context.get("start") or context.get("start_date"))
        end = parse_iso_or_nse(context.get("end") or context.get("end_date"))
        if start is None or end is None or end != expected_end:
            continue
        span = (end - start).days + 1
        if min_days <= span <= max_days:
            fact_count = 0
            if facts and preferred_tags:
                fact_count = sum(
                    1 for tag in preferred_tags
                    if facts.get(tag, {}).get(context_id) not in (None, "")
                )
            candidates.append((fact_count, -abs(span - target_days), context_id, start, end))
    if not candidates:
        durations = []
        for context_id, context in contexts.items():
            start = parse_iso_or_nse(context.get("start") or context.get("start_date"))
            end = parse_iso_or_nse(context.get("end") or context.get("end_date"))
            if start and end and end == expected_end:
                durations.append((context_id, start.isoformat(), end.isoformat(), (end-start).days+1))
        raise ValueError(
            f"no {period_kind} duration context ending {expected_end}; "
            f"available_end_contexts={durations[:30]}"
        )
    candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))
    fact_count, _, context_id, start, end = candidates[0]
    if facts and preferred_tags and fact_count == 0:
        fact_tags = sorted(facts)[:80]
        context_ids = sorted({
            context_id for tag_facts in facts.values() for context_id in tag_facts
        })[:80]
        raise ValueError(
            f"no mapped financial facts in any {period_kind} context ending {expected_end}; "
            f"candidate_contexts={[c[2] for c in candidates[:20]]}; "
            f"available_fact_tags={fact_tags}; fact_context_ids={context_ids}"
        )
    return context_id, start, end


def create_run_directory(base_dir: Path, run_id: str) -> Path:
    """Create an isolated output directory; never overwrite a prior import run."""
    if not run_id or not all(char.isalnum() or char in "._-" for char in run_id):
        raise ValueError("run_id may contain only letters, numbers, dots, underscores and hyphens")
    run_dir = base_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir
