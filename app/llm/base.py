from abc import ABC, abstractmethod

from app.core.models import LLMTurn


class LLMClient(ABC):
    @abstractmethod
    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.0) -> str: ...

    def generate_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float = 0.0,
    ) -> LLMTurn:
        """Agentic variant of generate(): the model receives a tool schema (e.g. web_search)
        and decides for itself whether to call one, rather than a fixed pipeline branch
        (see app/correction/controller.py) deciding for it. Not every provider implements
        this -- the default raises so a provider that hasn't opted in fails loudly instead of
        silently behaving like generate() and dropping the tool schema on the floor."""
        raise NotImplementedError(f"{type(self).__name__} does not support tool calling")
