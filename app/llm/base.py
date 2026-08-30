from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def generate(self, prompt: str, system: str | None = None, temperature: float = 0.0) -> str: ...
