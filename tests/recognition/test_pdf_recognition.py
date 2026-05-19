"""
测试 PDF 识别功能

测试内容：
1. PDF 文本提取
2. OCR 后备功能
3. 图片提取
4. 答案和解析生成
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.pdf_to_markdown import pdf_to_markdown, extract_images_from_pdf, extract_questions_from_markdown
from app.utils.deepseek import call_text_llm


async def test_pdf_recognition():
    """测试 PDF 识别功能"""

    # 测试文件路径（需要准备测试 PDF）
    test_pdf_path = "test_files/sample_math_exam.pdf"

    if not os.path.exists(test_pdf_path):
        print(f"❌ 测试文件不存在: {test_pdf_path}")
        print("请在 backend/test_files/ 目录下放置测试 PDF 文件")
        return

    print("=" * 60)
    print("开始测试 PDF 识别功能")
    print("=" * 60)

    # 读取 PDF 文件
    with open(test_pdf_path, "rb") as f:
        pdf_bytes = f.read()

    print(f"\n✅ 读取 PDF 文件: {len(pdf_bytes)} bytes")

    # 测试 1: PDF 转 Markdown
    print("\n" + "-" * 60)
    print("测试 1: PDF 转 Markdown（含 OCR 后备）")
    print("-" * 60)

    try:
        markdown_text, used_ocr = pdf_to_markdown(pdf_bytes, max_pages=5, use_ocr_fallback=True)
        print(f"✅ PDF 转换成功")
        print(f"   - 文本长度: {len(markdown_text)} 字符")
        print(f"   - 使用 OCR: {'是' if used_ocr else '否'}")
        print(f"\n前 200 字符预览:")
        print(markdown_text[:200])
    except Exception as e:
        print(f"❌ PDF 转换失败: {e}")
        return

    # 测试 2: 提取图片
    print("\n" + "-" * 60)
    print("测试 2: 提取 PDF 图片")
    print("-" * 60)

    try:
        pdf_images = extract_images_from_pdf(pdf_bytes, max_pages=5)
        total_images = sum(len(imgs) for imgs in pdf_images.values())
        print(f"✅ 图片提取成功")
        print(f"   - 包含图片的页数: {len(pdf_images)}")
        print(f"   - 图片总数: {total_images}")
        for page_num, images in pdf_images.items():
            print(f"   - 第 {page_num + 1} 页: {len(images)} 张图片")
    except Exception as e:
        print(f"❌ 图片提取失败: {e}")
        pdf_images = {}

    # 测试 3: LLM 提取题目
    print("\n" + "-" * 60)
    print("测试 3: LLM 提取题目（含答案和解析）")
    print("-" * 60)

    try:
        questions = await extract_questions_from_markdown(
            markdown_text,
            call_text_llm,
            pdf_images
        )
        print(f"✅ 题目提取成功")
        print(f"   - 题目数量: {len(questions)}")

        # 显示第一道题的详细信息
        if questions:
            q = questions[0]
            print(f"\n第一道题详情:")
            print(f"   - 题号: {q.get('question_no')}")
            print(f"   - 题型: {q.get('question_type')}")
            print(f"   - 知识点: {q.get('knowledge_point')}")
            print(f"   - 难度: {q.get('difficulty')}")
            print(f"   - 题目: {q.get('question_text', '')[:100]}...")
            print(f"   - 答案: {q.get('answer', '无')}")
            print(f"   - 解析: {q.get('solution', '无')[:100]}...")
            print(f"   - 包含图片: {'是' if q.get('has_image') else '否'}")
            if q.get('image_urls'):
                print(f"   - 图片数量: {len(q.get('image_urls'))}")
    except Exception as e:
        print(f"❌ 题目提取失败: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_pdf_recognition())
