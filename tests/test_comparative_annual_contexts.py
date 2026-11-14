from datetime import date
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys


# The production importer depends on the optional nse-xbrl package. These tests
# replace only its transport/parser symbols because the extraction function is
# monkeypatched to deterministic XBRL observation fixtures below.
try:
    import nse_xbrl  # noqa: F401
except ImportError:
    stub = ModuleType("nse_xbrl")
    stub.NSEClient = object
    stub.parse_xbrl = lambda *_args, **_kwargs: {}
    sys.modules["nse_xbrl"] = stub

_script_path = Path(__file__).resolve().parents[1] / "scripts" / "ingest_nse_integrated_filings.py"
_spec = spec_from_file_location("ingest_nse_integrated_filings_for_test", _script_path)
assert _spec is not None and _spec.loader is not None
_module = module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)


def _observation(kind, end):
    return SimpleNamespace(
        period=SimpleNamespace(kind=kind, end_date=end)
    )


def test_previous_annual_comparative_extracts_only_annual_duration_facts(monkeypatch):
    target = date(2025, 3, 31)
    comparative = date(2024, 3, 31)
    seen = {}

    def fake_extract(symbol, filing, xml_text, expected_end, period_kind, retrieved_at):
        seen.update(
            symbol=symbol,
            expected_end=expected_end,
            period_kind=period_kind,
        )
        return (
            [
                _observation("year", comparative),
                _observation("instant", comparative),
                _observation("instant", date(2023, 3, 31)),
            ],
            {"period_start": "2023-04-01", "period_end": comparative.isoformat()},
        )

    monkeypatch.setattr(_module, "extract_observations", fake_extract)
    observations, summary, warning = _module.extract_previous_annual_comparative_observations(
        "HCLTECH", {"seq_Id": "filing-1"}, "<xbrl/>", target,
        None, {target},
    )

    assert seen == {
        "symbol": "HCLTECH",
        "expected_end": comparative,
        "period_kind": "year",
    }
    assert len(observations) == 1
    assert observations[0].period.kind == "year"
    assert observations[0].period.end_date == comparative
    assert summary["context_role"] == "comparative"
    assert summary["current_filing_period_end"] == target.isoformat()
    assert warning == ""


def test_previous_annual_comparative_is_skipped_when_own_filing_was_imported(monkeypatch):
    target = date(2025, 3, 31)
    comparative = date(2024, 3, 31)

    def should_not_run(*_args, **_kwargs):
        raise AssertionError("Comparative parser should not run for an already imported year")

    monkeypatch.setattr(_module, "extract_observations", should_not_run)
    observations, summary, warning = _module.extract_previous_annual_comparative_observations(
        "HCLTECH", {}, "<xbrl/>", target, None, {target, comparative}
    )
    assert observations == []
    assert summary is None
    assert warning == ""


def test_previous_annual_comparative_returns_clear_warning_when_context_is_missing(monkeypatch):
    target = date(2025, 3, 31)

    def no_comparative(*_args, **_kwargs):
        raise ValueError("no year duration context")

    monkeypatch.setattr(_module, "extract_observations", no_comparative)
    observations, summary, warning = _module.extract_previous_annual_comparative_observations(
        "HCLTECH", {}, "<xbrl/>", target, None, {target}
    )
    assert observations == []
    assert summary is None
    assert "no year duration context" in warning


def test_previous_fiscal_year_end_handles_leap_day():
    assert _module.previous_fiscal_year_end(date(2024, 2, 29)) == date(2023, 2, 28)
    assert _module.previous_fiscal_year_end(date(2025, 3, 31)) == date(2024, 3, 31)
