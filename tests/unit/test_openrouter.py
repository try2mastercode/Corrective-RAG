import httpx
import pytest

from app.llm.openrouter import OpenRouterClient, OpenRouterClientError


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json_data


def test_missing_api_key_raises_immediately():
    with pytest.raises(OpenRouterClientError, match="OPENROUTER_API_KEY"):
        OpenRouterClient(api_key="", model="some-model")


def test_generate_returns_message_content(monkeypatch):
    def fake_post(url, headers, json, timeout):
        assert headers["Authorization"] == "Bearer test-key"
        assert json["model"] == "some-model"
        return FakeResponse({"choices": [{"message": {"content": "The answer."}}]})

    monkeypatch.setattr(httpx, "post", fake_post)

    client = OpenRouterClient(api_key="test-key", model="some-model")
    result = client.generate("a prompt", system="a system prompt")

    assert result == "The answer."


def test_generate_raises_on_unexpected_response_shape(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: FakeResponse({"unexpected": "shape"}))

    client = OpenRouterClient(api_key="test-key", model="some-model")
    with pytest.raises(OpenRouterClientError, match="Unexpected OpenRouter response"):
        client.generate("a prompt")


def test_generate_wraps_http_errors(monkeypatch):
    def fake_post(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", fake_post)

    client = OpenRouterClient(api_key="test-key", model="some-model")
    with pytest.raises(OpenRouterClientError, match="OpenRouter request failed"):
        client.generate("a prompt")


def test_generate_retries_on_429_and_succeeds(monkeypatch):
    """This pipeline makes many LLM calls per question; a 429 from a shared free-tier model
    pool is an expected, retryable condition, not a fatal error."""
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            return FakeResponse({}, status_code=429)
        return FakeResponse({"choices": [{"message": {"content": "recovered"}}]})

    monkeypatch.setattr(httpx, "post", fake_post)

    client = OpenRouterClient(api_key="test-key", model="some-model", max_rate_limit_retries=3)
    result = client.generate("a prompt")

    assert result == "recovered"
    assert calls["count"] == 3


def test_generate_raises_after_exhausting_rate_limit_retries(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: FakeResponse({}, status_code=429))

    client = OpenRouterClient(api_key="test-key", model="some-model", max_rate_limit_retries=2)
    with pytest.raises(OpenRouterClientError, match="OpenRouter request failed"):
        client.generate("a prompt")


def test_generate_does_not_retry_non_429_errors(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        return FakeResponse({}, status_code=500)

    monkeypatch.setattr(httpx, "post", fake_post)

    client = OpenRouterClient(api_key="test-key", model="some-model", max_rate_limit_retries=3)
    with pytest.raises(OpenRouterClientError):
        client.generate("a prompt")

    assert calls["count"] == 1


def test_generate_retries_on_error_embedded_in_200_response(monkeypatch):
    """Regression test: OpenRouter sometimes returns HTTP 200 with the actual failure embedded
    in the JSON body (e.g. {"error": {"code": 429}}) instead of a 429 status code -- observed
    live during manual testing. raise_for_status() can't see this; the body must be checked."""
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 2:
            return FakeResponse({"error": {"message": "Provider returned error", "code": 429}})
        return FakeResponse({"choices": [{"message": {"content": "recovered"}}]})

    monkeypatch.setattr(httpx, "post", fake_post)

    client = OpenRouterClient(api_key="test-key", model="some-model", max_rate_limit_retries=3)
    result = client.generate("a prompt")

    assert result == "recovered"
    assert calls["count"] == 2


def test_generate_raises_on_non_rate_limit_error_embedded_in_200_response(monkeypatch):
    monkeypatch.setattr(
        httpx, "post", lambda *a, **kw: FakeResponse({"error": {"message": "model not found", "code": 400}})
    )

    client = OpenRouterClient(api_key="test-key", model="some-model")
    with pytest.raises(OpenRouterClientError, match="model not found"):
        client.generate("a prompt")
