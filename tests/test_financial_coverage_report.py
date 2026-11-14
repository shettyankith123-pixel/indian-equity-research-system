from datetime import date

from scripts.build_financial_coverage_report import (
    build_fcfe_audit,
    has_three_consecutive_years,
)


def _observation(symbol, metric, value, start, end, kind, reference):
    return {
        "symbol": symbol,
        "metric": metric,
        "value": str(value),
        "period_start": start,
        "period_end": end,
        "period_kind": kind,
        "basis": "consolidated",
        "source_name": "NSE Integrated Filing - Financials",
        "publication_date": end,
        "source_url": "https://example.com/filing",
        "reference_id": reference,
    }


def test_three_consecutive_true_fcfe_years_require_all_four_inputs():
    rows = []
    debt_by_year = {
        "2023-03-31": "100",
        "2024-03-31": "150",
        "2025-03-31": "170",
        "2026-03-31": "180",
    }
    for year_end, debt in debt_by_year.items():
        rows.append(_observation("TEST", "borrowings", debt, year_end, year_end, "instant", f"ref-{year_end}"))
    annual_data = [
        ("2023-04-01", "2024-03-31", "100", "20"),
        ("2024-04-01", "2025-03-31", "120", "30"),
        ("2025-04-01", "2026-03-31", "140", "40"),
    ]
    for start, end, cfo, capex in annual_data:
        ref = f"ref-{end}"
        rows.append(_observation("TEST", "net_cash_from_operating_activities", cfo, start, end, "year", ref))
        rows.append(_observation("TEST", "capital_expenditure", capex, start, end, "year", ref))

    company_rows, annual_rows, summary = build_fcfe_audit(
        rows,
        [{"symbol": "TEST", "sector": "Industrials", "status": "quarter_or_half_year_and_annual_loaded"}],
    )
    assert [row["true_fcfe"] for row in annual_rows] == ["130", "110", "110"]
    assert company_rows[0]["three_consecutive_fcfe_status"] == "PASS_3_CONSECUTIVE_YEARS"
    assert summary["companies_with_3_consecutive_verified_fcfe_years"] == 1


def test_missing_prior_year_debt_is_not_treated_as_zero():
    rows = [
        _observation("TEST", "borrowings", "150", "2024-03-31", "2024-03-31", "instant", "ref-2024"),
        _observation("TEST", "net_cash_from_operating_activities", "100", "2023-04-01", "2024-03-31", "year", "ref-2024"),
        _observation("TEST", "capital_expenditure", "20", "2023-04-01", "2024-03-31", "year", "ref-2024"),
    ]
    _, annual_rows, _ = build_fcfe_audit(
        rows,
        [{"symbol": "TEST", "sector": "Industrials", "status": "partial_period_coverage"}],
    )
    assert annual_rows[0]["true_fcfe"] == ""
    assert annual_rows[0]["missing_inputs"] == "prior_year_closing_debt"


def test_three_consecutive_year_helper_rejects_gaps():
    assert has_three_consecutive_years(
        [date(2024, 3, 31), date(2025, 3, 31), date(2026, 3, 31)]
    )
    assert not has_three_consecutive_years(
        [date(2023, 3, 31), date(2025, 3, 31), date(2026, 3, 31)]
    )


def test_bank_is_routed_to_bank_valuation_without_fcfe_dcf_requirement():
    company_rows, _, _ = build_fcfe_audit(
        [],
        [{"symbol": "ICICIBANK", "sector": "Banking", "status": "partial_period_coverage"}],
    )
    assert company_rows[0]["three_consecutive_fcfe_status"] == "NOT_APPLICABLE_BANK_VALUATION"
    assert "bank valuation" in company_rows[0]["valuation_route"]
