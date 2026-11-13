from indian_equity_research.ingestion.nse_filing_client import fetch_integrated_filing_listing


class FakeNSEClient:
    def __init__(self, primary, fallback):
        self.primary = primary
        self.fallback = fallback
        self.fallback_call = None

    def get_integrated_filings(self, symbol, issuer, page=1, size=100):
        self.primary_call = (symbol, issuer, page, size)
        return self.primary

    def _get(self, endpoint, params=None, referer_path="/"):
        self.fallback_call = (endpoint, params, referer_path)
        return self.fallback


def test_symbol_only_fallback_runs_when_issuer_filtered_listing_is_empty():
    client = FakeNSEClient({"data": []}, {"data": [{"symbol": "MCX"}]})
    listing, query_mode = fetch_integrated_filing_listing(
        client, "MCX", "Multi Commodity Exchange of India Limited", page=1, size=100
    )
    assert query_mode == "symbol_only_fallback"
    assert listing["data"][0]["symbol"] == "MCX"
    endpoint, params, referer = client.fallback_call
    assert endpoint == "/integrated-filing-results"
    assert params["symbol"] == "MCX"
    assert "issuer" not in params
    assert referer == "/companies-listing/corporate-integrated-filing"


def test_symbol_and_issuer_lookup_is_kept_when_it_returns_rows():
    client = FakeNSEClient({"data": [{"symbol": "ICICIBANK"}]}, {"data": []})
    listing, query_mode = fetch_integrated_filing_listing(
        client, "ICICIBANK", "ICICI Bank Limited"
    )
    assert query_mode == "symbol_and_issuer"
    assert listing["data"][0]["symbol"] == "ICICIBANK"
    assert client.fallback_call is None
