"""简单测试错题识别"""
import asyncio
import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.deepseek import recognize_questions

async def test():
    # 使用找到的测试图片
    test_file = "../uploads/clean/p1_05324c4f4baf.jpg"

    if not os.path.exists(test_file):
        print(f"测试图片不存在: {test_file}")
        return

    print(f"使用测试图片: {test_file}")

    with open(test_file, 'rb') as f:
        image_bytes = f.read()

    print(f"图片大小: {len(image_bytes)} bytes")
    print("开始识别...\n")

    try:
        questions = await recognize_questions(image_bytes, "test.jpg")

        print(f"✓ 识别成功! 共识别出 {len(questions)} 道题\n")

        for i, q in enumerate(questions, 1):
            print(f"=== 题目 {i} ===")
            print(f"题目: {q.get('question_text', '')[:200]}")
            print(f"题型: {q.get('question_type', '')}")
            print(f"难度: {q.get('difficulty', '')}")
            print(f"知识点: {q.get('knowledge_point', '')}")
            print(f"答案: {q.get('answer', '')[:100]}")
            print()

    except Exception as e:
        print(f"❌ 识别失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
