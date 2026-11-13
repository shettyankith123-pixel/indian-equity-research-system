"""Rule-based, staged allocation sizing with explicit portfolio/sector caps."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

D = Decimal


@dataclass(frozen=True)
class CapitalSnapshot:
    snapshot_date: str
    cash_available: Decimal
    portfolio_market_value: Decimal
    positions: dict[str, tuple[str, Decimal]]  # symbol -> (sector, market value)


@dataclass(frozen=True)
class AllocationLine:
    symbol: str
    recommendation: str
    sector: str
    current_position_value: Decimal
    target_position_cap: Decimal
    first_tranche: Decimal
    rationale: str


def load_capital_snapshot(path: Path) -> CapitalSnapshot:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"snapshot_date", "cash_available", "portfolio_market_value", "symbol", "sector", "market_value"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Capital snapshot CSV missing columns: {', '.join(sorted(missing))}")
        rows = list(reader)
    if not rows:
        raise ValueError("Capital snapshot has no rows")
    first = rows[0]
    snapshot_date = first["snapshot_date"].strip()
    cash = D(first["cash_available"])
    portfolio = D(first["portfolio_market_value"])
    if cash < 0 or portfolio <= 0:
        raise ValueError("cash_available must be non-negative and portfolio_market_value positive")
    positions: dict[str, tuple[str, Decimal]] = {}
    for row in rows:
        if row["snapshot_date"].strip() != snapshot_date or D(row["cash_available"]) != cash or D(row["portfolio_market_value"]) != portfolio:
            raise ValueError("Account-level cash, portfolio value and date must be identical on every row")
        symbol = row["symbol"].strip().upper()
        if not symbol:
            continue
        value = D(row["market_value"])
        if value < 0:
            raise ValueError(f"Negative market value for {symbol}")
        positions[symbol] = (row["sector"].strip() or "Unclassified", value)
    return CapitalSnapshot(snapshot_date, cash, portfolio, positions)


def build_allocation_plan(
    decisions: list[dict[str, object]], snapshot: CapitalSnapshot,
    *, max_stock_weight: Decimal = D("0.10"), max_sector_weight: Decimal = D("0.30"),
    cash_reserve_weight: Decimal = D("0.05"),
) -> tuple[list[AllocationLine], Decimal]:
    """Allocate only first tranches; BUY gets 40%, ACCUMULATE 30% of target headroom."""
    portfolio = snapshot.portfolio_market_value
    reserve = portfolio * cash_reserve_weight
    deployable = max(D("0"), snapshot.cash_available - reserve)
    stock_cap = portfolio * max_stock_weight
    sector_cap = portfolio * max_sector_weight
    position_values = {s: value for s, (_, value) in snapshot.positions.items()}
    sector_values: dict[str, Decimal] = {}
    for _, (sector, value) in snapshot.positions.items():
        sector_values[sector] = sector_values.get(sector, D("0")) + value

    candidates = [d for d in decisions if d.get("recommendation") in {"BUY", "ACCUMULATE"}]
    rank = {"BUY": 0, "ACCUMULATE": 1}
    candidates.sort(key=lambda d: (rank[str(d["recommendation"])], -float(d.get("margin_of_safety_pct") or 0), -float(d.get("confidence") == "High")))
    lines: list[AllocationLine] = []
    for item in candidates:
        symbol, sector = str(item["symbol"]), str(item.get("sector") or "Unclassified")
        current = position_values.get(symbol, D("0"))
        target_headroom = max(D("0"), stock_cap - current)
        sector_headroom = max(D("0"), sector_cap - sector_values.get(sector, D("0")))
        tranche_pct = D("0.40") if item["recommendation"] == "BUY" else D("0.30")
        requested = target_headroom * tranche_pct
        amount = min(requested, sector_headroom, deployable)
        if amount > 0:
            rationale = f"First tranche only; stock cap {max_stock_weight:.0%}, sector cap {max_sector_weight:.0%}, cash reserve {cash_reserve_weight:.0%}."
            lines.append(AllocationLine(symbol, str(item["recommendation"]), sector, current, stock_cap, amount, rationale))
            deployable -= amount
            position_values[symbol] = current + amount
            sector_values[sector] = sector_values.get(sector, D("0")) + amount
        else:
            lines.append(AllocationLine(symbol, str(item["recommendation"]), sector, current, stock_cap, D("0"), "No allocation: cash reserve, stock limit or sector limit blocks a first tranche."))
    return lines, deployable


def write_allocation_csv(lines: list[AllocationLine], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["symbol", "recommendation", "sector", "current_position_value", "target_position_cap", "first_tranche", "rationale"])
        writer.writeheader()
        for line in lines:
            writer.writerow({k: str(v) for k, v in line.__dict__.items()})
