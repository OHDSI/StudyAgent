from typing import Any, Dict, Protocol


class LLMAdapter(Protocol):
    def generate(self, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        """Generate a structured response from a prompt."""


class DummyLLMAdapter:
    def generate(self, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        return {
            "warning": "LLM adapter not configured",
            "prompt_length": len(prompt),
        }
