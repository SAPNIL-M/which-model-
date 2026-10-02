import asyncio
import os

from app.config import load_config
from app.providers.gemini import GeminiProvider
from app.providers.openai_compat import OpenAICompatibleProvider


def provider_for(model):
    key = os.environ.get(model.api_key_env)
    if model.kind == "gemini":
        return GeminiProvider(key or "", model.provider_model_id)
    return OpenAICompatibleProvider(model.base_url, key, model.provider_model_id)


async def main():
    config = load_config()
    for model in config.models:
        if not model.live_enabled:
            continue
        try:
            result = await provider_for(model).generate(
                config.generation.get("system_prompt", ""),
                "Reply with the word hello.",
                config.generation.get("temperature", 0.3),
                config.generation.get("max_tokens", 800),
            )
            print(f"{model.id}: {result.text} ({result.latency_ms} ms, {result.tokens_out} output tokens)")
        except Exception as exc:
            print(f"{model.id}: ERROR: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
