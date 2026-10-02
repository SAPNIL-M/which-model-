import asyncio
import os

import httpx
from dotenv import load_dotenv


async def main():
    load_dotenv()
    key = os.environ.get("NVIDIA_API_KEY")
    if not key:
        raise SystemExit("NVIDIA_API_KEY is required")
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(
            "https://integrate.api.nvidia.com/v1/models",
            headers={"Authorization": f"Bearer {key}"},
        )
    response.raise_for_status()
    for model in response.json().get("data", []):
        print(model["id"])


if __name__ == "__main__":
    asyncio.run(main())
