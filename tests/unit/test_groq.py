import httpx
import pytest

from app.llm.groq import GroqClient, GroqClientError


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
    with pytest.raises(GroqClientError, match="GROQ_API_KEY"):
        GroqClient(api_key="", model="some-model")


def test_generate_returns_message_content(monkeypatch):
    def fake_post(url, headers, json, timeout):
        assert url == "https://api.groq.com/openai/v1/chat/completions"
        assert headers["Authorization"] == "Bearer test-key"
        assert json["model"] == "some-model"
        return FakeResponse({"choices": [{"message": {"content": "The answer."}}]})

    monkeypatch.setattr(httpx, "post", fake_post)

    client = GroqClient(api_key="test-key", model="some-model")
    result = client.generate("a prompt", system="a system prompt")

    assert result == "The answer."


def test_generate_retries_on_429(monkeypatch):
    # The shared retry/error-handling logic itself has full coverage in test_openrouter.py
    # (same base class) -- this just confirms Groq's client is actually wired to it.
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 2:
            return FakeResponse({}, status_code=429)
        return FakeResponse({"choices": [{"message": {"content": "recovered"}}]})

    monkeypatch.setattr(httpx, "post", fake_post)

    client = GroqClient(api_key="test-key", model="some-model", max_rate_limit_retries=3)
    assert client.generate("a prompt") == "recovered"
    assert calls["count"] == 2
