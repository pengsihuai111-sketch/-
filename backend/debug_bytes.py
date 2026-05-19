"""Check raw response bytes for encoding issues."""
import asyncio, httpx, json, io, base64
from PIL import Image

async def test():
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
                {"type": "text", "text": "请识别这张图片中的所有数学题目，按规范输出 JSON。"}
            ]
        }]
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )

    # Get raw content
    raw = resp.content  # bytes
    print(f"Status: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('content-type')}")
    print(f"Raw bytes: {len(raw)}")

    # Check encoding by looking at specific byte patterns
    text = raw.decode("utf-8")
    print(f"Decoded OK: {len(text)} chars")

    # Check for backslash escapes
    import re
    bad_escapes = re.findall(r'\\(?!["\\/bfnrtu])', text[:2000])
    print(f"Suspicious escapes found: {len(bad_escapes)}")

    # Check the content field specifically
    try:
        data = json.loads(text)
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"JSON valid! Content length: {len(content)}")
        print(f"First 300 chars: {content[:300]}")
        print(f"Last 300 chars: {content[-300:]}")
    except json.JSONDecodeError as e:
        print(f"JSON INVALID: {e}")
        # Show the problematic area
        pos = e.pos
        print(f"Around position {pos}: ...{text[max(0,pos-50):pos+50]}...")

asyncio.run(test())
