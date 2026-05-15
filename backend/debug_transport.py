"""Test if custom mounts cause the timeout issue."""
import asyncio, httpx, io, base64, time
from PIL import Image

async def test_with_mounts(label, use_mounts):
    api_key = "sk-z59A2JvGXUTJ4xpjHON0f2oszOPCThWPTzI7J8wSXJ7PgnwY"
    url = "https://api.newcoin.tech/v1/chat/completions"
    model = "doubao-seed-1-6-vision-250815"

    with open("d:\\project\\题库管理\\题目图片\\测试图片.png", "rb") as f:
        img_bytes = f.read()
    img = Image.open(io.BytesIO(img_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    if max(img.size) > 900:
        ratio = 900 / max(img.size)
        img = img.resize((int(img.width*ratio), int(img.height*ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=50, optimize=True)
    img_bytes = buf.getvalue()
    b64 = base64.b64encode(img_bytes).decode("utf-8")

    payload = {
        "model": model,
        "max_tokens": 4096,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": "Say hello"}
            ]
        }]
    }

    if use_mounts:
        transport = httpx.AsyncHTTPTransport(verify=True)
        mounts = {"https://": transport, "http://": httpx.AsyncHTTPTransport()}
        client = httpx.AsyncClient(timeout=30.0, mounts=mounts)
    else:
        client = httpx.AsyncClient(timeout=30.0)

    async with client:
        t0 = time.time()
        try:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            elapsed = time.time() - t0
            print(f"[{label}] Status={resp.status_code}, time={elapsed:.1f}s, body={len(resp.text)} chars")
        except Exception as e:
            elapsed = time.time() - t0
            print(f"[{label}] FAIL after {elapsed:.1f}s: {type(e).__name__}: {e}")

async def main():
    # Test sequential without mounts first
    await test_with_mounts("no-mounts-1", False)
    await test_with_mounts("no-mounts-2", False)

    # Test with mounts
    await test_with_mounts("with-mounts-1", True)
    await test_with_mounts("with-mounts-2", True)

    # Parallel with mounts (the current code)
    print("\n--- Parallel with mounts ---")
    t0 = time.time()
    results = await asyncio.gather(*[
        test_with_mounts(f"mounts-parallel-{i}", True) for i in range(2)
    ])
    print(f"Total: {time.time()-t0:.1f}s")

    # Parallel without mounts
    print("\n--- Parallel without mounts ---")
    t0 = time.time()
    results = await asyncio.gather(*[
        test_with_mounts(f"no-mounts-parallel-{i}", False) for i in range(2)
    ])
    print(f"Total: {time.time()-t0:.1f}s")

asyncio.run(main())
