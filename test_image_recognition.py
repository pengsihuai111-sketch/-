import sys
import asyncio
import base64
sys.path.insert(0, 'backend')

from app.utils.deepseek import _call_multimodal_llm

async def test():
    # Create a simple test image (1x1 white pixel)
    import io
    from PIL import Image

    img = Image.new('RGB', (100, 100), color='white')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    image_bytes = img_bytes.getvalue()

    try:
        result = await _call_multimodal_llm(
            image_bytes=image_bytes,
            text_prompt="这是一个测试图片",
            system_prompt="你是测试助手",
            max_tokens=50,
            json_output=True  # This might be the problem
        )
        print("图片识别成功:", result[:200])
    except Exception as e:
        print("图片识别失败:", str(e))
        import traceback
        traceback.print_exc()

asyncio.run(test())
