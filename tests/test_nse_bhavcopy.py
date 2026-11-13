import io
import zipfile
from datetime import date

import pytest

from indian_equity_research.ingestion.nse_bhavcopy import parse_udiff_zip


def zip_csv(content: str) -> bytes:
    handle = io.BytesIO()
    with zipfile.ZipFile(handle, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("BhavCopy.csv", content)
    return handle.getvalue()


def test_parse_udiff_equity_row_and_ignore_other_series():
    content = (
        "TradDt,TckrSymb,SctySrs,OpnPric,HghPric,LwPric,ClsPric,PrvsClsgPric,TtlTradgVol,TtlTrfVal,TtlNbOfTxs\n"
        "2026-11-12,ICICIBANK,EQ,100,105,99,103,98,1000,102000,200\n"
        "2026-11-12,ICICIBANK,BL,100,105,99,103,98,1000,102000,200\n"
    )
    rows = parse_udiff_zip(zip_csv(content), expected_date=date(2026, 11, 12))
    assert len(rows) == 1
    assert rows[0].symbol == "ICICIBANK"
    assert rows[0].close == 103
    assert rows[0].volume == 1000


def test_reject_bad_date_or_invalid_ohlc():
    content = "TradDt,TckrSymb,SctySrs,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol\n2026-11-12,ABC,EQ,100,90,95,96,100\n"
    with pytest.raises(ValueError, match="OHLC"):
        parse_udiff_zip(zip_csv(content))
