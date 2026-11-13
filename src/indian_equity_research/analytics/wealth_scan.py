"""Build a complete decision register for the configured watchlist and imported opportunities."""
from __future__ import annotations

import csv
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

from indian_equity_research.analytics.decision_engine import decide
from indian_equity_research.models.recommendations import ResearchInput


def _normalise_lookup(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def load_company_universe(path: Path = Path("data/universe/indian_watchlist_companies.csv")) -> dict[str, dict[str, str]]:
    """Load the issuer and sector reference; missing file means no metadata, not an error."""
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return {
            row["symbol"].strip().upper(): {
                key: (value or "").strip()
                for key, value in row.items()
                if key is not None
            }
            for row in csv.DictReader(handle)
            if row.get("symbol", "").strip()
        }


def resolve_company_symbol(
    query: str,
    universe_path: Path = Path("data/universe/indian_watchlist_companies.csv"),
) -> str:
    """Resolve symbols or common issuer-name queries using the local universe manifest."""
    raw = query.strip()
    key = _normalise_lookup(raw)
    universe = load_company_universe(universe_path)
    for symbol, record in universe.items():
        symbol_key = _normalise_lookup(symbol)
        issuer_key = _normalise_lookup(record.get("issuer_name", ""))
        if key and (key == symbol_key or key == issuer_key or issuer_key.startswith(key)):
            return symbol
    aliases = {
        "ICICI": "ICICIBANK",
        "ICICIBANK": "ICICIBANK",
        "STATEBANKOFINDIA": "SBIN",
        "SBI": "SBIN",
        "TATACONSULTANCYSERVICES": "TCS",
        "VARUNBEVERAGES": "VBL",
        "SAMVARDHANAMOTHERSON": "MOTHERSON",
        "MAHINDRAANDMAHINDRA": "M&M",
        "LARSENTOUBRO": "LT",
        "POWERGRIDCORPORATION": "POWERGRID",
    }
    return aliases.get(key, raw.upper().replace(" ", ""))


def resolve_sector_name(
    query: str,
    universe_path: Path = Path("data/universe/indian_watchlist_companies.csv"),
) -> str:
    """Resolve common sector shorthand to the taxonomy used by the universe manifest."""
    raw = query.strip()
    key = _normalise_lookup(raw)
    aliases = {
        "BANK": "Banking",
        "BANKS": "Banking",
        "BANKING": "Banking",
        "IT": "IT Services",
        "TECH": "IT Services",
        "TECHNOLOGY": "IT Services",
        "IT_SERVICES": "IT Services",
        "AUTO": "Automobiles",
        "AUTOMOBILE": "Automobiles",
        "AUTOMOBILES": "Automobiles",
        "FMCG": "FMCG",
        "CONSUMER": "FMCG",
        "METAL": "Metals",
        "METALS": "Metals",
        "CAPITALGOODS": "Capital Goods",
        "POWER": "Power Utilities",
        "POWERUTILITIES": "Power Utilities",
        "CHEMICALS": "Specialty Chemicals",
        "SPECIALTYCHEMICALS": "Specialty Chemicals",
    }
    if key in aliases:
        return aliases[key]
    universe = load_company_universe(universe_path)
    for record in universe.values():
        sector = record.get("sector", "")
        if _normalise_lookup(sector) == key:
            return sector
    return raw


def _empty_research_input(symbol: str, sector: str, *, held: bool = False) -> ResearchInput:
    return ResearchInput(
        symbol=symbol,
        sector=sector or "Unclassified",
        current_price=None,
        fair_value_base=None,
        fair_value_low=None,
        fair_value_high=None,
        quality_score=None,
        growth_score=None,
        balance_sheet_score=None,
        governance_score=None,
        data_completeness=None,
        data_as_of=None,
        valuation_confidence=None,
        held=held,
        notes="No complete reviewed valuation input is available; this is a research-readiness assessment.",
    )


def read_watchlist(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    symbols: list[str] = []
    in_symbols = False
    for raw in text.splitlines():
        line = raw.strip()
        if line == "symbols:":
            in_symbols = True
            continue
        if in_symbols and line.startswith("-"):
            value = line[1:].strip().strip("\"'")
            if value and re.fullmatch(r"[A-Z0-9&._-]+", value.upper()):
                symbols.append(value.upper())
        elif in_symbols and line and not line.startswith("#") and not raw.startswith("      "):
            in_symbols = False
    return list(dict.fromkeys(symbols))


def _d(value: Optional[str]) -> Optional[Decimal]:
    if value is None or value.strip() == "":
        return None
    try:
        return Decimal(value.strip())
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal in research input: {value!r}") from exc


def load_research_inputs(path: Path) -> dict[str, ResearchInput]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"symbol", "sector", "current_price", "fair_value_base", "quality_score", "growth_score", "balance_sheet_score", "governance_score", "data_completeness", "data_as_of", "valuation_confidence"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Research input CSV missing columns: {', '.join(sorted(missing))}")
        result = {}
        for line, row in enumerate(reader, start=2):
            symbol = row["symbol"].strip().upper()
            try:
                date_value = date.fromisoformat(row["data_as_of"].strip()) if row.get("data_as_of", "").strip() else None
                item = ResearchInput(
                    symbol=symbol, sector=row["sector"].strip(), current_price=_d(row.get("current_price")),
                    fair_value_base=_d(row.get("fair_value_base")), fair_value_low=_d(row.get("fair_value_low")),
                    fair_value_high=_d(row.get("fair_value_high")), quality_score=_d(row.get("quality_score")),
                    growth_score=_d(row.get("growth_score")), balance_sheet_score=_d(row.get("balance_sheet_score")),
                    governance_score=_d(row.get("governance_score")), data_completeness=_d(row.get("data_completeness")),
                    data_as_of=date_value, valuation_confidence=_d(row.get("valuation_confidence")),
                    thesis_broken=row.get("thesis_broken", "false").strip().lower() in {"1", "true", "yes"},
                    major_risk_flag=row.get("major_risk_flag", "false").strip().lower() in {"1", "true", "yes"},
                    held=row.get("held", "false").strip().lower() in {"1", "true", "yes"},
                    notes=row.get("notes", ""), source_name=row.get("source_name", ""), source_url=row.get("source_url", ""),
                )
                if not symbol:
                    raise ValueError("blank symbol")
                for score_name in ("quality_score", "growth_score", "balance_sheet_score", "governance_score"):
                    score_value = getattr(item, score_name)
                    if score_value is not None and not (Decimal("0") <= score_value <= Decimal("100")):
                        raise ValueError(f"{score_name} must be on a 0–100 scale")
                for fraction_name in ("data_completeness", "valuation_confidence"):
                    fraction_value = getattr(item, fraction_name)
                    if fraction_value is not None and not (Decimal("0") <= fraction_value <= Decimal("1")):
                        raise ValueError(f"{fraction_name} must be between 0 and 1")
                if item.current_price is not None and item.current_price <= 0:
                    raise ValueError("current_price must be positive")
                if item.fair_value_base is not None and item.fair_value_base <= 0:
                    raise ValueError("fair_value_base must be positive")
                if item.fair_value_low is not None and item.fair_value_base is not None and item.fair_value_low > item.fair_value_base:
                    raise ValueError("fair_value_low cannot exceed fair_value_base")
                if item.fair_value_high is not None and item.fair_value_base is not None and item.fair_value_high < item.fair_value_base:
                    raise ValueError("fair_value_high cannot be below fair_value_base")
                if symbol in result:
                    raise ValueError(f"duplicate symbol {symbol}")
                result[symbol] = item
            except (ValueError, InvalidOperation) as exc:
                raise ValueError(f"Invalid research input row {line}: {exc}") from exc
    return result


def build_decisions(watchlist_path: Path, research_path: Path, *, today: Optional[date] = None) -> list[dict[str, object]]:
    watchlist = read_watchlist(watchlist_path)
    research = load_research_inputs(research_path)
    symbols = list(dict.fromkeys(watchlist + sorted(set(research) - set(watchlist))))
    decisions = []
    for symbol in symbols:
        item = research.get(symbol)
        if item is None:
            item = ResearchInput(
                symbol=symbol, sector="Unclassified", current_price=None, fair_value_base=None,
                fair_value_low=None, fair_value_high=None, quality_score=None, growth_score=None,
                balance_sheet_score=None, governance_score=None, data_completeness=None,
                data_as_of=None, valuation_confidence=None,
            )
        decisions.append(decide(item, today=today).to_dict())
    return decisions


def build_company_decision(
    symbol: str,
    research_path: Path,
    *,
    today: Optional[date] = None,
    universe_path: Path = Path("data/universe/indian_watchlist_companies.csv"),
) -> dict[str, object]:
    canonical = resolve_company_symbol(symbol, universe_path)
    research = load_research_inputs(research_path)
    item = research.get(canonical)
    if item is None:
        metadata = load_company_universe(universe_path).get(canonical, {})
        item = _empty_research_input(canonical, metadata.get("sector", "Unclassified"))
    return decide(item, today=today).to_dict()


def build_sector_decisions(
    sector: str,
    research_path: Path,
    *,
    today: Optional[date] = None,
    universe_path: Path = Path("data/universe/indian_watchlist_companies.csv"),
) -> list[dict[str, object]]:
    research = load_research_inputs(research_path)
    universe = load_company_universe(universe_path)
    canonical_sector = resolve_sector_name(sector, universe_path)
    selected: dict[str, ResearchInput] = {
        symbol: item
        for symbol, item in research.items()
        if item.sector.casefold() == canonical_sector.casefold()
    }
    # Include every company in the reference universe, even when research is missing.
    # That makes sector coverage gaps explicit rather than returning an empty sector.
    for symbol, metadata in universe.items():
        if metadata.get("sector", "").casefold() == canonical_sector.casefold():
            selected.setdefault(symbol, _empty_research_input(symbol, canonical_sector))
    decisions = [decide(item, today=today).to_dict() for item in selected.values()]
    order = {
        "BUY": 0, "ACCUMULATE": 1, "HOLD": 2, "WAIT": 3, "ASSESS": 4,
        "OBSERVE": 5, "REDUCE": 6, "EXIT": 7, "AVOID": 8,
    }
    return sorted(decisions, key=lambda row: (order.get(str(row["recommendation"]), 9), row["symbol"]))


def write_decision_register(decisions: list[dict[str, object]], output_csv: Path, output_md: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(decisions[0].keys()) if decisions else []
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader(); writer.writerows(decisions)
    counts: dict[str, int] = {}
    for row in decisions:
        key = str(row["recommendation"])
        counts[key] = counts.get(key, 0) + 1
    lines = ["# Wealth Scan Decision Register", "", f"Run date: {date.today().isoformat()}", "", f"Coverage: {len(decisions)} stocks (watchlist plus imported outside-watchlist candidates).", "", "## Decision counts", ""]
    lines.extend([f"- **{key}:** {value}" for key, value in sorted(counts.items())])
    lines += ["", "## Individual decisions", "", "| Symbol | Sector | Decision | Price | Base fair value | Margin of safety | Confidence |", "|---|---|---:|---:|---:|---:|---|"]
    for r in decisions:
        lines.append(f"| {r['symbol']} | {r['sector']} | **{r['recommendation']}** | {r['current_price'] or '—'} | {r['fair_value_base'] or '—'} | {r['margin_of_safety_pct'] or '—'} | {r['confidence']} |")
    lines += ["", "## Individual rationale and next action", ""]
    for r in decisions:
        lines.append(f"### {r['symbol']} — {r['recommendation']}")
        lines.append(str(r['rationale']))
        lines.append(f"**Action:** {r['suggested_action']}")
        if r.get("source_name") or r.get("source_url"):
            lines.append(f"**Source:** {r.get('source_name') or 'Not named'} — {r.get('source_url') or 'No URL supplied'}")
        lines.append("")
    lines += ["## Integrity notes", "", "- A missing or stale input is reported as **ASSESS**, never silently converted into WAIT or BUY.", "- BUY requires verified financial/valuation inputs, company-quality gates, valuation confidence of at least 65%, and at least 15% margin of safety to base fair value.", "- ACCUMULATE requires the same quality gates and at least 8% margin of safety.", "- A share-price fall alone is not a reason to add; broken thesis and material risk flags override valuation.", "- Research inputs must include primary-source references and be reviewed before an investment decision.", ""]
    output_md.write_text("\n".join(lines), encoding="utf-8")


def build_opportunity_list(watchlist_path: Path, research_path: Path, *, today: Optional[date] = None) -> list[dict[str, object]]:
    """Return only actionable extra-watchlist BUY/ACCUMULATE candidates."""
    watchlist = set(read_watchlist(watchlist_path))
    research = load_research_inputs(research_path)
    decisions = []
    for symbol in sorted(set(research) - watchlist):
        row = decide(research[symbol], today=today).to_dict()
        if row["recommendation"] in {"BUY", "ACCUMULATE"}:
            decisions.append(row)
    rank = {"BUY": 0, "ACCUMULATE": 1}
    return sorted(decisions, key=lambda row: (rank[str(row["recommendation"])], -(float(row["margin_of_safety_pct"] or 0))))
