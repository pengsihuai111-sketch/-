"""Test if parallel vision API calls cause timeout."""
import asyncio, sys, os, io
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.utils.deepseek import _call_multimodal_llm, VISION_SYSTEM_PROMPT

async def test():
    with open("d:\\project\\题库管理\\题目图片\\测试图片.png", "rb") as f:
        img = f.read()

    # Create 2 strips like _call_vision_api does
    pil = Image.open(io.BytesIO(img))
    w, h = pil.size
    strip_h = h // 2
    overlap = int(strip_h * 0.1)
    strips = []
    for i in range(2):
        y0 = max(0, i * strip_h - (overlap if i > 0 else 0))
        y1 = min(h, (i + 1) * strip_h + overlap)
        crop = pil.crop((0, y0, w, y1))
        if crop.mode in ("RGBA", "P"):
            crop = crop.convert("RGB")
        buf = io.BytesIO()
        crop.save(buf, format="JPEG", quality=50, optimize=True)
        strips.append(buf.getvalue())
    print(f"Strips: {len(strips[0])} bytes, {len(strips[1])} bytes")

    # Test 1: Sequential calls
    print("\n--- Sequential calls ---")
    for i, s in enumerate(strips):
        t0 = asyncio.get_event_loop().time()
        try:
            text = await _call_multimodal_llm(
                image_bytes=s,
                text_prompt="请识别这张图片中的所有数学题目，按规范输出 JSON。",
                system_prompt=VISION_SYSTEM_PROMPT,
                max_tokens=4096,
                timeout=180.0,
            )
            elapsed = asyncio.get_event_loop().time() - t0
            print(f"Strip {i}: OK, {len(text)} chars, {elapsed:.1f}s")
        except Exception as e:
            elapsed = asyncio.get_event_loop().time() - t0
            print(f"Strip {i}: FAIL ({e}), {elapsed:.1f}s")

    # Test 2: Parallel calls
    print("\n--- Parallel calls ---")
    t0 = asyncio.get_event_loop().time()
    async def call_strip(s, i):
        try:
            text = await _call_multimodal_llm(
                image_bytes=s,
                text_prompt="请识别这张图片中的所有数学题目，按规范输出 JSON。",
                system_prompt=VISION_SYSTEM_PROMPT,
                max_tokens=4096,
                timeout=180.0,
            )
            return f"Strip {i}: OK, {len(text)} chars"
        except Exception as e:
            return f"Strip {i}: FAIL ({e})"

    results = await asyncio.gather(*[call_strip(s, i) for i, s in enumerate(strips)])
    elapsed = asyncio.get_event_loop().time() - t0
    for r in results:
        print(r)
    print(f"Total: {elapsed:.1f}s")

asyncio.run(test())
