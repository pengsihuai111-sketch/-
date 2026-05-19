"""Direct vision API debug test."""
import asyncio, httpx, json, base64, sys, io
from PIL import Image

async def test():
    api_key = "sk-z59A2JvGXUTJ4xpjHON0f2oszOPCThWPTzI7J8wSXJ7PgnwY"
    url = "https://api.newcoin.tech/v1/chat/completions"
    model = "doubao-seed-1-6-vision-250815"

    # Load and compress image
    with open("d:\\project\\题库管理\\题目图片\\测试图片.png", "rb") as f:
        img_bytes = f.read()
    img = Image.open(io.BytesIO(img_bytes))
    print(f"Original image: {img.size}, {len(img_bytes)} bytes")

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    if max(img.size) > 900:
        ratio = 900 / max(img.size)
        img = img.resize((int(img.width*ratio), int(img.height*ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=50, optimize=True)
    img_bytes = buf.getvalue()
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    print(f"Compressed: {img.size}, {len(img_bytes)} bytes, base64={len(b64)} chars")

    payload = {
        "model": model,
        "max_tokens": 4096,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": "请识别这张图片中的所有数学题目"}
            ]
        }]
    }

    # Try with direct httpx (no proxy bypass)
    async with httpx.AsyncClient(timeout=180) as client:
        print(f"\nPOST {url}")
        try:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            print(f"Status: {resp.status_code}")
            print(f"Response ({len(resp.text)} chars):")
            print(resp.text[:2000])
        except Exception as e:
            print(f"Request failed: {type(e).__name__}: {e}")

asyncio.run(test())
