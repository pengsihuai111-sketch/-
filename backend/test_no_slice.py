"""测试不切片的识别"""
import asyncio
import sys
import os

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.deepseek import _call_multimodal_llm, VISION_SYSTEM_PROMPT, _parse_response, _fill_defaults

async def test():
    test_file = "../uploads/clean/p1_05324c4f4baf.jpg"

    if not os.path.exists(test_file):
        print(f"测试图片不存在: {test_file}")
        return

    print(f"使用测试图片: {test_file}")

    with open(test_file, 'rb') as f:
        image_bytes = f.read()

    print(f"图片大小: {len(image_bytes)} bytes")
    print("开始识别（不切片，max_tokens=8192）...\n")

    try:
        # 直接调用 API，不切片
        content_text = await _call_multimodal_llm(
            image_bytes=image_bytes,
            text_prompt="请识别这张图片中的所有数学题目，按规范输出 JSON。",
            system_prompt=VISION_SYSTEM_PROMPT,
            max_tokens=8192,
            timeout=180.0,
        )

        print(f"✓ API 调用成功")
        print(f"响应长度: {len(content_text)} 字符")
        print(f"响应前 500 字符:\n{content_text[:500]}\n")
        print(f"响应后 500 字符:\n...{content_text[-500:]}\n")

        # 尝试解析
        questions = _parse_response(content_text)
        questions = _fill_defaults(questions)

        print(f"✓ 解析成功! 共识别出 {len(questions)} 道题\n")

        for i, q in enumerate(questions, 1):
            print(f"=== 题目 {i} ===")
            print(f"题目: {q.get('question_text', '')[:150]}")
            print(f"题型: {q.get('question_type', '')}")
            print(f"难度: {q.get('difficulty', '')}")
            print(f"知识点: {q.get('knowledge_point', '')}")
            print()

    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
