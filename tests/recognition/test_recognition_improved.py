"""测试改进后的识别功能"""
import asyncio
import sys
import os
import time
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.deepseek import recognize_questions, get_image_info
from app.utils.recognition_config import RecognitionStrategy
from app.config import VISION_API_KEY, VISION_API_URL, VISION_MODEL


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_question_summary(q: dict, index: int):
    """Print a summary of a recognized question."""
    print(f"\n【题目 {index}】")
    print(f"  题号: {q.get('question_no', 'N/A')}")
    print(f"  题型: {q.get('question_type', 'N/A')}")
    print(f"  难度: {q.get('difficulty', 'N/A')}")
    print(f"  知识点: {q.get('knowledge_point', 'N/A')}")
    print(f"  完整性: {'✓ 完整' if q.get('is_complete', True) else '✗ 不完整'}")
    print(f"  置信度: {q.get('confidence', 0.0):.2f}")

    # Question text
    text = q.get('question_text', '')
    if len(text) > 100:
        print(f"  题目: {text[:100]}...")
    else:
        print(f"  题目: {text}")

    # Answer
    answer = q.get('answer', '')
    if len(answer) > 50:
        print(f"  答案: {answer[:50]}...")
    else:
        print(f"  答案: {answer}")

    # Quality issues
    if q.get('quality_issues'):
        print(f"  ⚠ 质量问题: {', '.join(q['quality_issues'])}")


async def test_api_config():
    """测试 API 配置"""
    print_section("API 配置检查")

    print(f"VISION_API_URL: {VISION_API_URL}")
    print(f"VISION_MODEL: {VISION_MODEL}")
    print(f"VISION_API_KEY: {'已配置 ✓' if VISION_API_KEY else '未配置 ✗'}")

    if not VISION_API_KEY:
        print("\n❌ 错误: VISION_API_KEY 未配置")
        return False

    print("\n✓ API 配置正常")
    return True


async def test_image_recognition(image_path: str, strategy: RecognitionStrategy = RecognitionStrategy.AUTO):
    """测试单张图片识别"""
    print_section(f"测试图片识别 - {Path(image_path).name}")

    if not os.path.exists(image_path):
        print(f"❌ 图片不存在: {image_path}")
        return None

    # Read image
    with open(image_path, 'rb') as f:
        image_bytes = f.read()

    # Get image info
    info = get_image_info(image_bytes)
    print(f"\n图片信息:")
    print(f"  尺寸: {info['width']} x {info['height']} 像素")
    print(f"  大小: {len(image_bytes) / 1024:.1f} KB")
    if info.get('warning'):
        print(f"  ⚠ 警告: {info['warning']}")

    # Recognize
    print(f"\n开始识别 (策略: {strategy})...")
    start_time = time.time()

    try:
        questions = await recognize_questions(
            image_bytes,
            Path(image_path).name,
            strategy=strategy
        )
        elapsed = time.time() - start_time

        print(f"\n✓ 识别成功! 耗时: {elapsed:.2f}秒")
        print(f"  识别到 {len(questions)} 道题")

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
            print_question_summary(q, i)

        return questions

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ 识别失败! 耗时: {elapsed:.2f}秒")
        print(f"  错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def compare_strategies(image_path: str):
    """比较不同识别策略的效果"""
    print_section(f"策略对比 - {Path(image_path).name}")

    if not os.path.exists(image_path):
        print(f"❌ 图片不存在: {image_path}")
        return

    strategies = [
        RecognitionStrategy.SINGLE_STAGE,
        RecognitionStrategy.TWO_STAGE,
    ]

    results = {}

    for strategy in strategies:
        print(f"\n{'─' * 70}")
        print(f"测试策略: {strategy}")
        print(f"{'─' * 70}")

        questions = await test_image_recognition(image_path, strategy)
        if questions:
            results[strategy] = {
                'count': len(questions),
                'incomplete': sum(1 for q in questions if not q.get('is_complete', True)),
                'low_confidence': sum(1 for q in questions if q.get('confidence', 1.0) < 0.7),
                'with_issues': sum(1 for q in questions if q.get('quality_issues')),
            }

    # Print comparison
    if len(results) > 1:
        print_section("策略对比结果")
        print(f"\n{'策略':<20} {'题目数':<10} {'不完整':<10} {'低置信':<10} {'有问题':<10}")
        print("─" * 70)
        for strategy, stats in results.items():
            print(f"{strategy:<20} {stats['count']:<10} {stats['incomplete']:<10} "
                  f"{stats['low_confidence']:<10} {stats['with_issues']:<10}")


async def main():
    """主测试流程"""
    print("\n" + "=" * 70)
    print("  PDF识别优化测试")
    print("=" * 70)

    # Check API config
    if not await test_api_config():
        return

    # Find test images
    test_dirs = [
        "../题目图片",
        "../../题目图片",
        "../uploads/images",
        "uploads/images",
    ]

    test_images = []
    for test_dir in test_dirs:
        if os.path.exists(test_dir):
            for ext in ['.png', '.jpg', '.jpeg']:
                test_images.extend(Path(test_dir).glob(f"*{ext}"))
            if test_images:
                break

    if not test_images:
        print(f"\n❌ 未找到测试图片")
        print(f"尝试过的目录: {test_dirs}")
        return

    print(f"\n找到 {len(test_images)} 张测试图片")

    # Test first image with auto strategy
    if test_images:
        await test_image_recognition(str(test_images[0]), RecognitionStrategy.AUTO)

    # Compare strategies if user wants
    if len(test_images) > 0:
        print("\n" + "─" * 70)
        response = input("\n是否进行策略对比测试? (y/n): ").strip().lower()
        if response == 'y':
            await compare_strategies(str(test_images[0]))

    print_section("测试完成")


if __name__ == "__main__":
    asyncio.run(main())
