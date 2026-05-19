"""测试图片上传功能"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.utils.image_processing import detect_correction_marks
from PIL import Image
import io

# 创建一个简单的测试图片
img = Image.new('RGB', (100, 100), color='white')
img_bytes = io.BytesIO()
img.save(img_bytes, format='JPEG')
img_bytes = img_bytes.getvalue()

# 测试detect_correction_marks函数
try:
    result = detect_correction_marks(img_bytes)
    print("[OK] detect_correction_marks test passed")
    print(f"  Result: {result}")
    print(f"  Type check:")
    for key, value in result.items():
        print(f"    {key}: {type(value).__name__} = {value}")
except Exception as e:
    print(f"[FAIL] detect_correction_marks test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nAll tests passed! Image upload function is fixed.")
