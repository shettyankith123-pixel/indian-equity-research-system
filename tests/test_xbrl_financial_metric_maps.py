from pathlib import Path


def test_nse_bank_and_debt_aliases_match_observed_taxonomy_names():
    script = (Path(__file__).parents[1] / "scripts/ingest_nse_integrated_filings.py").read_text(encoding="utf-8")
    assert '"bank_share_capital": (("Capital",)' in script
    assert '"bank_reserves_and_surplus": (("ReservesAndSurplus",)' in script
    assert '"bank_advances": (("Advances", "LoansAndAdvancesToCustomers")' in script
    assert '"bank_deposits": (("Deposits", "DepositsFromCustomers")' in script
    assert '"BorrowingsNoncurrent"' in script
    assert '"CashAndCashEquivalentsCashFlowStatement"' in script


def test_bank_credit_quality_and_cet1_tags_are_mapped_from_duration_contexts():
    script = (Path(__file__).parents[1] / "scripts/ingest_nse_integrated_filings.py").read_text(encoding="utf-8")
    assert '"gross_npa_reported": (("GrossNonPerformingAssets",), "INR crore")' in script
    assert '"net_npa_reported": (("NonPerformingAssets",), "INR crore")' in script
    assert '"gross_npa_ratio": (("PercentageOfGrossNpa",), "ratio")' in script
    assert '"net_npa_ratio": (("PercentageOfNpa",), "ratio")' in script
    assert '"cet1_ratio": (("CET1Ratio",), "ratio")' in script
