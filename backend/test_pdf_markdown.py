"""测试基于Markdown的PDF识别"""
import asyncio
import sys
import os
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.pdf_to_markdown import (
    pdf_to_markdown,
    extract_questions_from_markdown,
    detect_has_images,
)
from app.utils.deepseek import _call_text_llm


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


async def test_pdf_to_markdown(pdf_path: str):
    """测试PDF转Markdown"""
    print_section(f"测试 PDF → Markdown - {Path(pdf_path).name}")

    if not os.path.exists(pdf_path):
        print(f"❌ PDF不存在: {pdf_path}")
        return None

    # Read PDF
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()

    print(f"\nPDF大小: {len(pdf_bytes) / 1024:.1f} KB")

    # Convert to markdown
    try:
        markdown_text = pdf_to_markdown(pdf_bytes)
        print(f"\n✓ 转换成功!")
        print(f"  Markdown长度: {len(markdown_text)} 字符")

        # Show preview
        print(f"\n--- Markdown预览 (前500字符) ---")
        print(markdown_text[:500])
        print("...")

        # Detect images
        page_images = detect_has_images(pdf_bytes)
        has_images = any(page_images.values())
        if has_images:
            pages_with_images = [p + 1 for p, has in page_images.items() if has]
            print(f"\n⚠ PDF包含图片，在第 {pages_with_images} 页")
        else:
            print(f"\n✓ PDF不包含图片，纯文本识别效果最佳")

        return markdown_text

    except Exception as e:
        print(f"\n❌ 转换失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_extract_questions(markdown_text: str):
    """测试从Markdown提取题目"""
    print_section("测试 Markdown → 题目提取")

    if not markdown_text:
        print("❌ 没有Markdown文本")
        return None

    try:
        print("\n开始提取题目...")
        questions = await extract_questions_from_markdown(markdown_text, _call_text_llm)

        print(f"\n✓ 提取成功! 共 {len(questions)} 道题")

        # Quality summary
        incomplete = sum(1 for q in questions if not q.get('is_complete', True))
        low_confidence = sum(1 for q in questions if q.get('confidence', 1.0) < 0.7)
        with_issues = sum(1 for q in questions if q.get('quality_issues'))

        print(f"\n质量统计:")
        print(f"  完整题目: {len(questions) - incomplete}/{len(questions)}")
        print(f"  高置信度: {len(questions) - low_confidence}/{len(questions)}")
        print(f"  有质量问题: {with_issues}/{len(questions)}")

        # Print each question
        for i, q in enumerate(questions, 1):
            print(f"\n{'─' * 70}")
            print(f"【题目 {i}】")
            print(f"  题号: {q.get('question_no', 'N/A')}")
            print(f"  题型: {q.get('question_type', 'N/A')}")
            print(f"  难度: {q.get('difficulty', 'N/A')}")
            print(f"  知识点: {q.get('knowledge_point', 'N/A')}")
            print(f"  完整性: {'✓ 完整' if q.get('is_complete', True) else '✗ 不完整'}")
            print(f"  置信度: {q.get('confidence', 0.0):.2f}")

            # Question text
            text = q.get('question_text', '')
            if len(text) > 150:
                print(f"  题目: {text[:150]}...")
            else:
                print(f"  题目: {text}")

            # Answer
            answer = q.get('answer', '')
            if len(answer) > 80:
                print(f"  答案: {answer[:80]}...")
            else:
                print(f"  答案: {answer}")

            # Quality issues
            if q.get('quality_issues'):
                print(f"  ⚠ 质量问题: {', '.join(q['quality_issues'])}")

        return questions

    except Exception as e:
        print(f"\n❌ 提取失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def compare_methods(pdf_path: str):
    """对比Markdown方式和图片方式"""
    print_section(f"方法对比 - {Path(pdf_path).name}")

    if not os.path.exists(pdf_path):
        print(f"❌ PDF不存在: {pdf_path}")
        return

    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()

    results = {}

    # Method 1: Markdown
    print("\n" + "─" * 70)
    print("方法1: PDF → Markdown → LLM提取")
    print("─" * 70)

    import time
    start = time.time()
    try:
        markdown_text = pdf_to_markdown(pdf_bytes)
        questions = await extract_questions_from_markdown(markdown_text, _call_text_llm)
        elapsed = time.time() - start

        results['markdown'] = {
            'count': len(questions),
            'time': elapsed,
            'incomplete': sum(1 for q in questions if not q.get('is_complete', True)),
            'low_confidence': sum(1 for q in questions if q.get('confidence', 1.0) < 0.7),
        }
        print(f"\n✓ 完成! 耗时: {elapsed:.2f}秒")
    except Exception as e:
        print(f"\n❌ 失败: {e}")

    # Method 2: Image (optional)
    print("\n" + "─" * 70)
    response = input("\n是否测试图片识别方式进行对比? (y/n): ").strip().lower()
    if response == 'y':
        print("方法2: PDF → 图片 → 视觉识别")
        print("─" * 70)

        from app.utils.pdf_processor import pdf_to_images
        from app.utils.deepseek import recognize_questions

        start = time.time()
        try:
            page_images = pdf_to_images(pdf_bytes)
            all_questions = []
            for page_num, img_bytes in enumerate(page_images):
                questions = await recognize_questions(img_bytes, f"page_{page_num + 1}.jpg")
                all_questions.extend(questions)
            elapsed = time.time() - start

            results['image'] = {
                'count': len(all_questions),
                'time': elapsed,
                'incomplete': sum(1 for q in all_questions if not q.get('is_complete', True)),
                'low_confidence': sum(1 for q in all_questions if q.get('confidence', 1.0) < 0.7),
            }
            print(f"\n✓ 完成! 耗时: {elapsed:.2f}秒")
        except Exception as e:
            print(f"\n❌ 失败: {e}")

    # Print comparison
    if len(results) > 1:
        print_section("对比结果")
        print(f"\n{'方法':<15} {'题目数':<10} {'耗时(秒)':<12} {'不完整':<10} {'低置信':<10}")
        print("─" * 70)
        for method, stats in results.items():
            print(f"{method:<15} {stats['count']:<10} {stats['time']:<12.2f} "
                  f"{stats['incomplete']:<10} {stats['low_confidence']:<10}")

        # Analysis
        print("\n分析:")
        if 'markdown' in results and 'image' in results:
            md = results['markdown']
            img = results['image']

            if md['time'] < img['time']:
                speedup = img['time'] / md['time']
                print(f"  ✓ Markdown方式快 {speedup:.1f}x")

            if md['count'] == img['count']:
                print(f"  ✓ 两种方式识别题目数量一致")
            elif md['count'] > img['count']:
                print(f"  ⚠ Markdown方式多识别了 {md['count'] - img['count']} 道题")
            else:
                print(f"  ⚠ 图片方式多识别了 {img['count'] - md['count']} 道题")


async def main():
    """主测试流程"""
    print("\n" + "=" * 70)
    print("  PDF Markdown识别测试")
    print("=" * 70)

    # Find test PDFs
    test_dirs = [
        "../uploads/pdfs",
        "uploads/pdfs",
        "..",
        ".",
    ]

    test_pdfs = []
    for test_dir in test_dirs:
        if os.path.exists(test_dir):
            test_pdfs.extend(Path(test_dir).glob("*.pdf"))
            if test_pdfs:
                break

    if not test_pdfs:
        print(f"\n❌ 未找到测试PDF文件")
        print(f"尝试过的目录: {test_dirs}")
        print("\n请将PDF文件放到以下任一目录:")
        for d in test_dirs[:2]:
            print(f"  - {d}")
        return

    print(f"\n找到 {len(test_pdfs)} 个PDF文件:")
    for i, pdf in enumerate(test_pdfs, 1):
        print(f"  {i}. {pdf.name}")

    # Test first PDF
    if test_pdfs:
        pdf_path = str(test_pdfs[0])

        # Step 1: Convert to markdown
        markdown_text = await test_pdf_to_markdown(pdf_path)

        if markdown_text:
            # Step 2: Extract questions
            questions = await test_extract_questions(markdown_text)

            # Step 3: Compare methods (optional)
            if questions:
                print("\n" + "─" * 70)
                response = input("\n是否进行方法对比测试? (y/n): ").strip().lower()
                if response == 'y':
                    await compare_methods(pdf_path)

    print_section("测试完成")


if __name__ == "__main__":
    asyncio.run(main())
