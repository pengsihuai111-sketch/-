import httpx, json, asyncio

async def test():
    api_key = "sk-z59A2JvGXUTJ4xpjHON0f2oszOPCThWPTzI7J8wSXJ7PgnwY"
    url = "https://api.newcoin.tech/v1/chat/completions"

    # Simple text test first
    payload = {
        "model": "doubao-seed-1-6-251015",
        "max_tokens": 512,
        "messages": [
            {"role": "user", "content": "Say hello in one word"}
        ],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        print(f"POST {url}")
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )

    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text[:500]}")

    # Also try listing models
    async with httpx.AsyncClient(timeout=30) as client:
        models_url = "https://api.newcoin.tech/v1/models"
        print(f"\nGET {models_url}")
        resp2 = await client.get(
            models_url,
            headers={"Authorization": f"Bearer {api_key}"},
        )
    print(f"Status: {resp2.status_code}")
    print(f"Models: {resp2.text[:500]}")

asyncio.run(test())
