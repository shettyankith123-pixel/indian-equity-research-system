from decimal import Decimal as D

from scripts.build_research_reports import valuation_screen


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
