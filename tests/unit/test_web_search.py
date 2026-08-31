from ddgs.exceptions import DDGSException

from app.web.search import compute_web_chunk_id, web_search


class FakeDDGS:
    def __init__(self, results=None, raise_exc=None, **kwargs):
        self._results = results or []
        self._raise_exc = raise_exc

    def text(self, query, max_results=5):
        if self._raise_exc:
            raise self._raise_exc
        return self._results


def test_compute_web_chunk_id_is_deterministic():
    id1 = compute_web_chunk_id("https://example.com/a")
    id2 = compute_web_chunk_id("https://example.com/a")
    id3 = compute_web_chunk_id("https://example.com/b")
    assert id1 == id2
    assert id1 != id3
    assert id1.startswith("web_")


def test_web_search_normalizes_results(monkeypatch):
    fake_results = [
        {"title": "Title A", "href": "https://a.example.com", "body": "snippet a"},
        {"title": "Title B", "href": "https://b.example.com", "body": "snippet b"},
    ]
    monkeypatch.setattr("app.web.search.DDGS", lambda **kw: FakeDDGS(results=fake_results))

    results = web_search("some query", provider="duckduckgo", max_results=5, timeout=5.0)

    assert len(results) == 2
    assert results[0].url == "https://a.example.com"
    assert results[0].title == "Title A"
    assert results[0].snippet == "snippet a"
    assert results[0].retrieved_at


def test_web_search_deduplicates_by_url(monkeypatch):
    fake_results = [
        {"title": "Title A", "href": "https://a.example.com", "body": "first"},
        {"title": "Title A dup", "href": "https://a.example.com", "body": "duplicate"},
    ]
    monkeypatch.setattr("app.web.search.DDGS", lambda **kw: FakeDDGS(results=fake_results))

    results = web_search("some query", provider="duckduckgo")
    assert len(results) == 1


def test_web_search_skips_results_without_url(monkeypatch):
    fake_results = [{"title": "No URL", "href": "", "body": "text"}]
    monkeypatch.setattr("app.web.search.DDGS", lambda **kw: FakeDDGS(results=fake_results))

    results = web_search("some query", provider="duckduckgo")
    assert results == []


def test_web_search_handles_provider_exception_gracefully(monkeypatch):
    monkeypatch.setattr(
        "app.web.search.DDGS", lambda **kw: FakeDDGS(raise_exc=DDGSException("rate limited"))
    )

    results = web_search("some query", provider="duckduckgo")
    assert results == []


def test_web_search_handles_unexpected_exception_gracefully(monkeypatch):
    monkeypatch.setattr("app.web.search.DDGS", lambda **kw: FakeDDGS(raise_exc=RuntimeError("boom")))

    results = web_search("some query", provider="duckduckgo")
    assert results == []


def test_web_search_unknown_provider_returns_empty():
    results = web_search("some query", provider="bing")
    assert results == []
