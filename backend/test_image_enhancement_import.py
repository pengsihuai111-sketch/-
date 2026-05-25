"""测试 image_enhancement 模块导入"""
import sys
import traceback

print("=" * 60)
print("测试 image_enhancement 模块导入")
print("=" * 60)

# 测试1: 直接导入依赖包
print("\n1. 测试依赖包...")
try:
    import cv2
    import numpy as np
    from PIL import Image
    print(f"✓ cv2 版本: {cv2.__version__}")
    print(f"✓ numpy 版本: {np.__version__}")
    print(f"✓ Pillow 版本: {Image.__version__}")
except Exception as e:
    print(f"✗ 依赖包导入失败: {e}")
    traceback.print_exc()

# 测试2: 导入 image_enhancement 模块
print("\n2. 测试 image_enhancement 模块...")
try:
    from app.utils.image_enhancement import analyze_image_quality, enhance_image, should_enhance
    print("✓ image_enhancement 模块导入成功")
    print(f"  - analyze_image_quality: {analyze_image_quality}")
    print(f"  - enhance_image: {enhance_image}")
    print(f"  - should_enhance: {should_enhance}")
except Exception as e:
    print(f"✗ image_enhancement 模块导入失败: {e}")
    traceback.print_exc()

# 测试3: 测试功能
print("\n3. 测试功能...")
try:
    from app.utils.image_enhancement import analyze_image_quality
    from PIL import Image
    import io

    # 创建一个简单的测试图片
    img = Image.new('RGB', (100, 100), color='white')
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    image_bytes = buf.getvalue()

    # 分析图片质量
    result = analyze_image_quality(image_bytes)
    print(f"✓ 图片质量分析成功")
    print(f"  - 模糊: {result['is_blurry']}")
    print(f"  - 过暗: {result['is_too_dark']}")
    print(f"  - 过亮: {result['is_too_bright']}")
    print(f"  - 警告: {result['warnings']}")
except Exception as e:
    print(f"✗ 功能测试失败: {e}")
    traceback.print_exc()

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
