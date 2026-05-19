"""直接测试错题识别接口"""
import requests
from io import BytesIO
from PIL import Image

# 创建一个测试图片
img = Image.new('RGB', (200, 100), color='white')
from PIL import ImageDraw, ImageFont
draw = ImageDraw.Draw(img)
draw.text((10, 10), "1. 1+1=?", fill='black')
img_bytes = BytesIO()
img.save(img_bytes, format='PNG')
img_bytes.seek(0)

# 先登录获取 token
print("1. 登录...")
login_url = "http://localhost:8000/api/auth/login"
login_data = {"username": "testuser", "password": "123456"}
login_response = requests.post(login_url, json=login_data)

if login_response.status_code != 200:
    print(f"登录失败: {login_response.status_code}")
    print(f"响应: {login_response.text}")
    exit(1)

token = login_response.json().get('access_token')
print(f"登录成功，token: {token[:20]}...")

# 测试错题识别接口
print("\n2. 测试错题识别接口...")
url = "http://localhost:8000/api/wrong-questions/recognize"
files = {'file': ('test.png', img_bytes, 'image/png')}
headers = {'Authorization': f'Bearer {token}'}

print(f"请求 URL: {url}")
print(f"文件: test.png")

try:
    response = requests.post(url, files=files, headers=headers, timeout=60)
    print(f"\n状态码: {response.status_code}")

    if response.status_code == 200:
        print(f"成功！")
        result = response.json()
        print(f"识别结果: {result.keys()}")
    else:
        print(f"失败！")
        print(f"响应内容: {response.text}")
        print(f"响应内容(repr): {repr(response.text)}")

except requests.exceptions.Timeout:
    print("请求超时")
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
