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
