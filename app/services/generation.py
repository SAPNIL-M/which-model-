from app.providers.base import Provider


async def generate_answer(provider: Provider, system: str, prompt: str, temperature: float, max_tokens: int):
    return await provider.generate(system, prompt, temperature, max_tokens)
