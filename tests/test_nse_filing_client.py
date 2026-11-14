from indian_equity_research.ingestion.nse_filing_client import fetch_integrated_filing_listing


class FakeNSEClient:
    def __init__(self, primary, fallback):
        self.primary = primary
        self.fallback = fallback
        self.fallback_call = None
        self.primary_calls = []
        self.fallback_calls = []

    def get_integrated_filings(self, symbol, issuer, page=1, size=100):
        self.primary_calls.append((symbol, issuer, page, size))
        if isinstance(self.primary, dict) and "pages" in self.primary:
            return self.primary["pages"].get(page)
        return self.primary

    def _get(self, endpoint, params=None, referer_path="/"):
        self.fallback_call = (endpoint, params, referer_path)
        self.fallback_calls.append((endpoint, params, referer_path))
        if isinstance(self.fallback, dict) and "pages" in self.fallback:
            return self.fallback["pages"].get(params["page"])
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
    assert listing["_pagination"]["pages_fetched"] == 1


def test_symbol_and_issuer_lookup_is_kept_when_it_returns_rows():
    client = FakeNSEClient({"data": [{"symbol": "ICICIBANK"}]}, {"data": []})
    listing, query_mode = fetch_integrated_filing_listing(
        client, "ICICIBANK", "ICICI Bank Limited"
    )
    assert query_mode == "symbol_and_issuer"
    assert listing["data"][0]["symbol"] == "ICICIBANK"
    assert client.fallback_call is None


def test_all_pages_are_fetched_using_total_count_and_rows_are_deduplicated():
    client = FakeNSEClient(
        {
            "pages": {
                1: {"data": [{"seq_Id": 1}, {"seq_Id": 2}], "totalCount": 4, "page": 1, "size": 2},
                2: {"data": [{"seq_Id": 2}, {"seq_Id": 3}], "totalCount": 4, "page": 2, "size": 2},
            }
        },
        {"data": []},
    )
    listing, mode = fetch_integrated_filing_listing(
        client, "TEST", "Test Limited", size=2
    )
    assert mode == "symbol_and_issuer"
    assert [row["seq_Id"] for row in listing["data"]] == [1, 2, 3]
    assert [call[2] for call in client.primary_calls] == [1, 2]
    assert listing["_pagination"] == {
        "start_page": 1,
        "pages_fetched": 2,
        "page_size": 2,
        "reported_total_count": 4,
        "raw_rows": 4,
        "unique_rows": 3,
        "duplicates_removed": 1,
        "complete": True,
    }


def test_pagination_continues_on_symbol_only_fallback():
    client = FakeNSEClient(
        {"data": []},
        {
            "pages": {
                1: {"data": [{"seq_Id": "a"}, {"seq_Id": "b"}], "totalCount": 3},
                2: {"data": [{"seq_Id": "c"}], "totalCount": 3},
            }
        },
    )
    listing, mode = fetch_integrated_filing_listing(
        client, "TEST", "Test Limited", size=2
    )
    assert mode == "symbol_only_fallback"
    assert [row["seq_Id"] for row in listing["data"]] == ["a", "b", "c"]
    assert [call[1]["page"] for call in client.fallback_calls] == [1, 2]


def test_missing_total_count_uses_short_final_page_to_stop():
    client = FakeNSEClient(
        {
            "pages": {
                1: {"data": [{"seq_Id": 1}, {"seq_Id": 2}]},
                2: {"data": [{"seq_Id": 3}]},
            }
        },
        {"data": []},
    )
    listing, _ = fetch_integrated_filing_listing(
        client, "TEST", "Test Limited", size=2
    )
    assert [row["seq_Id"] for row in listing["data"]] == [1, 2, 3]
    assert listing["_pagination"]["pages_fetched"] == 2


def test_empty_page_before_reported_final_page_fails_instead_of_silently_truncating():
    client = FakeNSEClient(
        {
            "pages": {
                1: {"data": [{"seq_Id": 1}, {"seq_Id": 2}], "totalCount": 4},
                2: {"data": []},
            }
        },
        {"data": []},
    )
    try:
        fetch_integrated_filing_listing(client, "TEST", "Test Limited", size=2)
    except RuntimeError as exc:
        assert "empty page 2" in str(exc)
    else:
        raise AssertionError("Expected incomplete pagination to fail")
