import httpx, json, asyncio

async def test():
    api_key = "sk-z59A2JvGXUTJ4xpjHON0f2oszOPCThWPTzI7J8wSXJ7PgnwY"
    url = "https://api.newcoin.tech/v1/models"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})

    models = resp.json().get("data", [])
    print(f"Available models ({len(models)}):")
    for m in models:
        print(f"  - {m['id']}")

asyncio.run(test())
