from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GenerationResult:
    text: str
    latency_ms: int
    tokens_in: int | None = None
    tokens_out: int | None = None


class Provider(Protocol):
    async def generate(
        self, system: str, prompt: str, temperature: float, max_tokens: int
    ) -> GenerationResult: ...


def strip_think_tags(text: str) -> str:
    while "<think>" in text and "</think>" in text:
        start = text.index("<think>")
        end = text.index("</think>", start) + len("</think>")
        text = text[:start] + text[end:]
    return text.strip()
