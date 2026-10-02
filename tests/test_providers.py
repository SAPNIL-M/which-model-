import httpx
import pytest

from app.providers.openai_compat import OpenAICompatibleProvider
from app.providers.base import strip_think_tags


@pytest.mark.asyncio
async def test_provider_success_and_think_tag_stripping():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "<think>private</think>hello"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1},
            },
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        result = await OpenAICompatibleProvider(
            "https://example.test/v1", "key", "model", client
        ).generate("system", "prompt", 0.3, 20)
    assert result.text == "hello"
    assert result.tokens_out == 1


@pytest.mark.asyncio
async def test_provider_retries_429():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(429)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}], "usage": {}}
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await OpenAICompatibleProvider(
            "https://example.test/v1", "key", "model", client
        ).generate("system", "prompt", 0.3, 20)
    assert result.text == "ok"
    assert calls == 3


def test_strip_think_tags():
    assert strip_think_tags("a<think>b</think>c") == "ac"
