"""测试错题识别功能"""
import asyncio
import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.deepseek import recognize_questions, _call_multimodal_llm
from app.config import VISION_API_KEY, VISION_API_URL, VISION_MODEL

async def test_api_connection():
    """测试 API 连接"""
    print("=" * 60)
    print("测试 API 配置")
    print("=" * 60)
    print(f"VISION_API_URL: {VISION_API_URL}")
    print(f"VISION_MODEL: {VISION_MODEL}")
    print(f"VISION_API_KEY: {VISION_API_KEY[:20]}..." if VISION_API_KEY else "未配置")
    print()

    if not VISION_API_KEY:
        print("❌ 错误: VISION_API_KEY 未配置")
        return False

    # 测试简单的 API 调用
    print("测试 API 连接...")
    try:
        # 创建一个简单的测试图片（1x1 白色像素）
        import base64
        from PIL import Image
        import io

        img = Image.new('RGB', (100, 100), color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        test_image_bytes = buf.getvalue()

        result = await _call_multimodal_llm(
            image_bytes=test_image_bytes,
            text_prompt="这是什么颜色？",
            system_prompt="简短回答",
            max_tokens=100,
            timeout=30.0,
        )

        print(f"✓ API 连接成功")
        print(f"响应: {result[:100]}...")
        return True

    except Exception as e:
        print(f"❌ API 连接失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_recognition():
    """测试图片识别"""
    print("\n" + "=" * 60)
    print("测试图片识别功能")
    print("=" * 60)

    # 检查是否有测试图片
    test_image_paths = ["../题目图片", "../../题目图片", "../uploads/images"]
    test_image_path = None

    for path in test_image_paths:
        if os.path.exists(path):
            test_image_path = path
            break

    if not test_image_path:
        print(f"❌ 测试图片目录不存在，尝试过: {test_image_paths}")
        print("跳过图片识别测试")
        return True  # 不算失败，因为 API 连接正常

    # 查找第一张图片
    image_files = [f for f in os.listdir(test_image_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not image_files:
        print(f"❌ 在 {test_image_path} 中未找到图片文件")
        return False

    test_file = os.path.join(test_image_path, image_files[0])
    print(f"使用测试图片: {test_file}")

    try:
        with open(test_file, 'rb') as f:
            image_bytes = f.read()

        print(f"图片大小: {len(image_bytes)} bytes")
        print("开始识别...")

        questions = await recognize_questions(image_bytes, image_files[0])

        print(f"\n✓ 识别成功! 共识别出 {len(questions)} 道题")

        for i, q in enumerate(questions, 1):
            print(f"\n--- 题目 {i} ---")
            print(f"题目文本: {q.get('question_text', '')[:100]}...")
            print(f"题型: {q.get('question_type', '')}")
            print(f"难度: {q.get('difficulty', '')}")
            print(f"知识点: {q.get('knowledge_point', '')}")
            print(f"答案: {q.get('answer', '')[:50]}...")

        return True

    except Exception as e:
        print(f"❌ 识别失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("开始诊断错题识别功能...\n")

    # 测试 API 连接
    api_ok = await test_api_connection()

    if not api_ok:
        print("\n⚠️  API 连接失败，请检查:")
        print("1. .env 文件中的 VISION_API_KEY 是否正确")
        print("2. VISION_API_URL 是否可访问")
        print("3. 网络连接是否正常")
        return

    # 测试识别功能
    await test_recognition()

    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
