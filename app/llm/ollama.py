import json

import httpx

from app.core.models import LLMTurn, ToolCall
from app.llm.base import LLMClient


class OllamaClientError(Exception):
    pass


class OllamaClient(LLMClient):
    def __init__(self, base_url: str, model: str, timeout: float = 120.0):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.0) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = httpx.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": temperature},
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OllamaClientError(f"Ollama request failed: {exc}") from exc

        data = response.json()
        return data["message"]["content"]

    def generate_with_tools(self, messages: list[dict], tools: list[dict], temperature: float = 0.0) -> LLMTurn:
        """Ollama's /api/chat supports a `tools` field for tool-calling-capable models. Support
        varies by model -- reliable on larger models, noticeably flakier on small local ones
        like the project's default llama3.2:3b (see README known limitations)."""
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if tools:
            payload["tools"] = tools

        try:
            response = httpx.post(f"{self._base_url}/api/chat", json=payload, timeout=self._timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OllamaClientError(f"Ollama request failed: {exc}") from exc

        data = response.json()
        message = data.get("message", {})

        parsed_calls = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function", {})
            arguments = fn.get("arguments") or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            parsed_calls.append(ToolCall(id=tc.get("id") or fn.get("name", ""), name=fn.get("name", ""), arguments=arguments))

        return LLMTurn(content=message.get("content"), tool_calls=parsed_calls)
