import asyncio
import random
import time

import httpx

from app.providers.base import GenerationResult, strip_think_tags


class OpenAICompatibleProvider:
    def __init__(self, base_url: str, api_key: str | None, model: str, client=None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.client = client

    async def generate(self, system, prompt, temperature, max_tokens):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        for attempt in range(3):
            started = time.perf_counter()
            try:
                if self.client:
                    response = await self.client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=60,
                    )
                else:
                    async with httpx.AsyncClient(timeout=60) as client:
                        response = await client.post(
                            f"{self.base_url}/chat/completions",
                            headers=headers,
                            json=payload,
                        )
                if response.status_code == 200:
                    data = response.json()
                    usage = data.get("usage", {})
                    return GenerationResult(
                        text=strip_think_tags(data["choices"][0]["message"]["content"]),
                        latency_ms=round((time.perf_counter() - started) * 1000),
                        tokens_in=usage.get("prompt_tokens"),
                        tokens_out=usage.get("completion_tokens"),
                    )
                if response.status_code not in {429, 500, 502, 503, 504}:
                    response.raise_for_status()
                if attempt == 2:
                    raise RuntimeError(f"Provider returned HTTP {response.status_code}")
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt == 2:
                    raise RuntimeError(f"Provider request failed: {exc}") from exc
            await asyncio.sleep((2**attempt) * 0.25 + random.random() * 0.1)
        raise RuntimeError("Provider request failed after retries")
