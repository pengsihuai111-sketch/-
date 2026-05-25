import sys
import asyncio
import io
sys.path.insert(0, 'backend')

from PIL import Image, ImageDraw, ImageFont

# Create a test image with a simple math question
img = Image.new('RGB', (400, 200), color='white')
draw = ImageDraw.Draw(img)

# Draw a simple math question
draw.text((20, 50), "1. 计算: 25 + 37 = ?", fill='black')
draw.text((20, 100), "2. 填空: 5 × 8 = ___", fill='black')

# Save to bytes
img_bytes = io.BytesIO()
img.save(img_bytes, format='JPEG')
image_bytes = img_bytes.getvalue()

# Save to file for testing
with open('test_math_question.jpg', 'wb') as f:
    f.write(image_bytes)

print("测试图片已创建: test_math_question.jpg")
print(f"图片大小: {len(image_bytes)} bytes")
