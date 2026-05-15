"""查看完整的 AI 响应"""
import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8')

from app.utils.deepseek import _call_multimodal_llm, VISION_SYSTEM_PROMPT

async def test():
    with open("../uploads/clean/p1_05324c4f4baf.jpg", "rb") as f:
        image_bytes = f.read()

    print("开始调用 API...")
    content_text = await _call_multimodal_llm(
        image_bytes=image_bytes,
        text_prompt="请识别这张图片中的所有数学题目，按规范输出 JSON。",
        system_prompt=VISION_SYSTEM_PROMPT,
        max_tokens=8192,
        timeout=180.0,
    )

    print(f"\n完整响应长度: {len(content_text)} 字符")
    print("\n完整响应内容:")
    print("="*80)
    print(content_text)
    print("="*80)

    # 保存到文件
    with open("response_full.txt", "w", encoding="utf-8") as f:
        f.write(content_text)
    print("\n已保存到 response_full.txt")

if __name__ == "__main__":
    asyncio.run(test())
