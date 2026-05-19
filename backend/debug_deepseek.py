"""Test deepseek.py vision function directly with same params as _call_multimodal_llm."""
import asyncio, sys, os, io, base64, json, httpx
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.utils.deepseek import _call_multimodal_llm, VISION_SYSTEM_PROMPT

async def test():
    with open("d:\\project\\题库管理\\题目图片\\测试图片.png", "rb") as f:
        img = f.read()

    print(f"Image: {len(img)} bytes")

    # Strip the bottom 60% of the image to simulate one strip
    pil = Image.open(io.BytesIO(img))
    w, h = pil.size
    crop = pil.crop((0, 0, w, h // 2))
    buf = io.BytesIO()
    if crop.mode in ("RGBA", "P"):
        crop = crop.convert("RGB")
    crop.save(buf, format="JPEG", quality=50, optimize=True)
    strip_bytes = buf.getvalue()
    print(f"Strip: {crop.size}, {len(strip_bytes)} bytes")

    try:
        text = await _call_multimodal_llm(
            image_bytes=strip_bytes,
            text_prompt="请识别这张图片中的所有数学题目，按规范输出 JSON。",
            system_prompt=VISION_SYSTEM_PROMPT,
            max_tokens=4096,
            timeout=180.0,
        )
        print(f"Response ({len(text)} chars): {text[:500]}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

asyncio.run(test())
