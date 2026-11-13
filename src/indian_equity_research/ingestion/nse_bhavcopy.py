"""Download and parse NSE's current UDiFF equity end-of-day bhavcopy ZIP."""
from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request

REPORTS_URL = "https://www.nseindia.com/all-reports"
ARCHIVE_BASE = "https://nsearchives.nseindia.com/content/cm"


@dataclass(frozen=True)
class EodPrice:
    trading_date: date
    symbol: str
    series: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    previous_close: Optional[Decimal]
    volume: int
    turnover: Optional[Decimal]
    trades: Optional[int]
    source_file: str


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _get(row: dict[str, str], aliases: Iterable[str], required: bool = True) -> Optional[str]:
    by_norm = {_norm(k): v for k, v in row.items() if k is not None}
    for alias in aliases:
        if _norm(alias) in by_norm:
            value = (by_norm[_norm(alias)] or "").strip()
            if value:
                return value
    if required:
        raise ValueError(f"Missing required NSE column; expected one of {list(aliases)}")
    return None


def _decimal(value: Optional[str], field: str, required: bool = True) -> Optional[Decimal]:
    if value is None or value.strip() in {"", "-", "NA", "N/A"}:
        if required:
            raise ValueError(f"Missing numeric value for {field}")
        return None
    try:
        result = Decimal(value.replace(",", "").strip())
    except InvalidOperation as exc:
        raise ValueError(f"Invalid numeric value for {field}: {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"Non-finite numeric value for {field}")
    return result


def parse_udiff_zip(payload: bytes, *, expected_date: Optional[date] = None) -> list[EodPrice]:
    """Parse UDiFF ZIP bytes; only EQ series are retained by default."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise ValueError("NSE response was not a valid ZIP archive") from exc
    csv_names = [n for n in archive.namelist() if n.lower().endswith(".csv")]
    if not csv_names:
        raise ValueError("NSE ZIP contains no CSV file")
    all_rows: list[EodPrice] = []
    for name in csv_names:
        with archive.open(name) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
            reader = csv.DictReader(text)
            for row in reader:
                if not row or not any(row.values()):
                    continue
                sym = (_get(row, ["TckrSymb", "Symbol", "SYMBOL"]) or "").upper()
                series = (_get(row, ["SctySrs", "Series", "SERIES"]) or "").upper()
                if series not in {"EQ", "BE", "BZ", "SM", "ST", "SZ"}:
                    continue
                raw_date = _get(row, ["TradDt", "Trade Date", "Date"])
                parsed_date = date.fromisoformat(str(raw_date)[:10])
                if expected_date and parsed_date != expected_date:
                    continue
                open_p = _decimal(_get(row, ["OpnPric", "Open Price", "OPEN"]), "open")
                high_p = _decimal(_get(row, ["HghPric", "High Price", "HIGH"]), "high")
                low_p = _decimal(_get(row, ["LwPric", "Low Price", "LOW"]), "low")
                close_p = _decimal(_get(row, ["ClsPric", "Close Price", "CLOSE"]), "close")
                prev = _decimal(_get(row, ["PrvsClsgPric", "Previous Close", "PREV_CLOSE"], False), "previous_close", False)
                volume_s = _get(row, ["TtlTradgVol", "Total Traded Volume", "TOTTRDQTY"])
                turnover = _decimal(_get(row, ["TtlTrfVal", "Total Traded Value", "TOTTRDVAL"], False), "turnover", False)
                trades_s = _get(row, ["TtlNbOfTxs", "Total Number of Trades", "TOTALTRADES"], False)
                try:
                    volume = int(Decimal(str(volume_s).replace(",", "")))
                    trades = int(Decimal(trades_s)) if trades_s else None
                except (ValueError, InvalidOperation) as exc:
                    raise ValueError(f"Invalid volume/trade count for {sym}") from exc
                if not sym or min(open_p, high_p, low_p, close_p) <= 0 or volume < 0:  # type: ignore[arg-type]
                    raise ValueError(f"Invalid price/volume row for {sym}")
                if high_p < max(open_p, close_p, low_p) or low_p > min(open_p, close_p, high_p):  # type: ignore[arg-type]
                    raise ValueError(f"OHLC consistency check failed for {sym}")
                all_rows.append(EodPrice(
                    parsed_date, sym, series, open_p, high_p, low_p, close_p,
                    prev, volume, turnover, trades, name,
                ))
    if not all_rows:
        raise ValueError("No eligible equity-series records found in NSE UDiFF file")
    return all_rows


def download_udiff_bhavcopy(
    trading_date: date, *, timeout: int = 90, attempts: int = 3
) -> tuple[bytes, str]:
    """Download NSE's UDiFF archive directly, retrying transient archive/network failures.

    The reports landing page is deliberately not fetched first: it is slow and is not
    required to construct NSE's documented archive URL. NSE archive access may still
    be transiently unavailable, so retries are bounded and every response is validated.
    """
    from time import sleep
    from http.cookiejar import CookieJar
    from urllib.request import HTTPCookieProcessor, build_opener

    ymd = trading_date.strftime("%Y%m%d")
    filename = f"BhavCopy_NSE_CM_0_0_0_{ymd}_F_0000.csv.zip"
    url = f"{ARCHIVE_BASE}/{filename}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        ),
        "Accept": "application/zip,application/octet-stream,*/*",
        "Referer": REPORTS_URL,
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    last_error: Exception | None = None

    for attempt in range(1, max(1, attempts) + 1):
        request = Request(url, headers=headers)
        try:
            with opener.open(request, timeout=timeout) as response:
                payload = response.read()
            if not payload.startswith(b"PK"):
                raise ValueError("NSE archive endpoint did not return a ZIP file")
            # Validate ZIP central directory before returning data to the importer.
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                if not any(name.lower().endswith(".csv") for name in archive.namelist()):
                    raise ValueError("NSE ZIP archive contains no CSV file")
            return payload, url
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = exc
            if attempt < max(1, attempts):
                sleep(min(2 ** (attempt - 1), 8))

    raise RuntimeError(
        f"Could not download NSE UDiFF bhavcopy for {trading_date} "
        f"after {max(1, attempts)} attempt(s): {last_error}"
    ) from last_error


def write_eod_csv(rows: list[EodPrice], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "trading_date", "symbol", "series", "open", "high", "low", "close",
            "previous_close", "volume", "turnover", "trades", "source_file",
        ])
        writer.writeheader()
        for row in rows:
            writer.writerow({k: str(v) if v is not None else "" for k, v in row.__dict__.items()})
