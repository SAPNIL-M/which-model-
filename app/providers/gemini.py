import asyncio
import random
import time

import httpx

from app.providers.base import GenerationResult, strip_think_tags


class GeminiProvider:
    def __init__(self, api_key: str, model: str, client=None):
        self.api_key = api_key
        self.model = model
        self.client = client

    async def generate(self, system, prompt, temperature, max_tokens):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        headers = {"x-goog-api-key": self.api_key}
        for attempt in range(3):
            started = time.perf_counter()
            try:
                if self.client:
                    response = await self.client.post(url, headers=headers, json=payload, timeout=60)
                else:
                    async with httpx.AsyncClient(timeout=60) as client:
                        response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    usage = data.get("usageMetadata", {})
                    return GenerationResult(
                        text=strip_think_tags(text),
                        latency_ms=round((time.perf_counter() - started) * 1000),
                        tokens_in=usage.get("promptTokenCount"),
                        tokens_out=usage.get("candidatesTokenCount"),
                    )
                if response.status_code not in {429, 500, 502, 503, 504}:
                    response.raise_for_status()
                if attempt == 2:
                    raise RuntimeError(f"Gemini returned HTTP {response.status_code}")
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt == 2:
                    raise RuntimeError(f"Gemini request failed: {exc}") from exc
            await asyncio.sleep((2**attempt) * 0.25 + random.random() * 0.1)
        raise RuntimeError("Gemini request failed after retries")
