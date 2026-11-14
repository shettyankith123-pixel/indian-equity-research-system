from pathlib import Path

from indian_equity_research.ingestion.csv_loader import parse_financial_csv


HEADER = (
    "symbol,metric,value,unit,currency,period_start,period_end,period_kind,basis,"
    "annualisation_factor,source_name,source_type,publication_date,retrieved_at,"
    "observation_kind,source_url,reference_id\n"
)


def test_parses_valid_observation(tmp_path: Path) -> None:
    path = tmp_path / "input.csv"
    path.write_text(
        HEADER
        + "ICICIBANK,net_profit,14843,crore,INR,2026-07-01,2026-09-30,quarter,"
        "standalone,4,ICICI Q2 results,company_filing,2026-10-18,"
        "2026-11-13T15:00:00+05:30,reported,https://example.com/q2,Q2FY27\n",
        encoding="utf-8",
    )
    result = parse_financial_csv(path)
    assert not result.errors
    assert len(result.observations) == 1
    assert result.observations[0].symbol == "ICICIBANK"
    assert str(result.observations[0].value) == "14843"


def test_invalid_timestamp_fails_validation(tmp_path: Path) -> None:
    path = tmp_path / "input.csv"
    path.write_text(
        HEADER
        + "ICICIBANK,net_profit,14843,crore,INR,2026-07-01,2026-09-30,quarter,"
        "standalone,4,ICICI Q2 results,company_filing,2026-10-18,"
        "2026-11-13T15:00:00,reported,,,\n",
        encoding="utf-8",
    )
    result = parse_financial_csv(path)
    assert not result.observations
    assert "timezone" in result.errors[0]


def test_missing_header_columns_fails(tmp_path: Path) -> None:
    path = tmp_path / "input.csv"
    path.write_text("symbol,metric,value\n", encoding="utf-8")
    result = parse_financial_csv(path)
    assert not result.observations
    assert "Missing required columns" in result.errors[0]


def test_instant_period_kind_is_supported():
    from indian_equity_research.ingestion.csv_loader import PERIOD_KINDS
    assert "instant" in PERIOD_KINDS
