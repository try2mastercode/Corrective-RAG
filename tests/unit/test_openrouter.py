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
