from decimal import Decimal as D
import importlib.util
import sys
from pathlib import Path

_REPORT_SCRIPT = Path(__file__).parents[1] / "scripts" / "build_research_reports.py"
_SPEC = importlib.util.spec_from_file_location("build_research_reports_test", _REPORT_SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
valuation_screen = _MODULE.valuation_screen
preferred_reporting_basis = _MODULE.preferred_reporting_basis


def test_valuation_screen_distinguishes_entry_zones_from_recommendations():
    attractive=valuation_screen(D("70"),D("80"),D("100"))
    watch=valuation_screen(D("90"),D("80"),D("100"))
    above=valuation_screen(D("110"),D("80"),D("100"))
    missing=valuation_screen(D("10"),None,None)
    assert attractive["valuation_signal"]=="BELOW_BEAR_CASE"
    assert attractive["buy_entry_max"]=="85.00"
    assert watch["valuation_signal"]=="BELOW_BASE_FAIR_VALUE" or watch["valuation_signal"]=="WATCH_FOR_ACCUMULATION"
    assert above["valuation_signal"]=="ABOVE_BASE_FAIR_VALUE"
    assert missing["valuation_signal"]=="NO_RELIABLE_FAIR_VALUE"


def test_relative_multiples_do_not_create_fair_value_or_entry_zones():
    relative=valuation_screen(
        D("100"),D("80"),D("120"),method="Sector-relative P/E / EV-EBITDA",confidence=D(".90")
    )
    assert relative["valuation_signal"]=="RELATIVE_ONLY_CONTEXT"
    assert relative["buy_entry_max"]==""
    assert relative["accumulate_entry_max"]==""


def test_low_confidence_intrinsic_reference_does_not_create_entry_zones():
    provisional=valuation_screen(
        D("100"),D("80"),D("120"),method="Justified P/B using sustainable ROE",confidence=D(".55")
    )
    assert provisional["valuation_signal"]=="LOW_CONFIDENCE_REFERENCE_ONLY"
    assert provisional["buy_entry_max"]==""


def test_banking_research_prefers_standalone_and_other_sectors_keep_consolidated():
    assert preferred_reporting_basis("Banking")=="standalone"
    assert preferred_reporting_basis("Financial Services")=="consolidated"
    assert preferred_reporting_basis("IT Services")=="consolidated"
