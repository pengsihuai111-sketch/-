"""测试图片上传接口"""
import requests
import os
from io import BytesIO
from PIL import Image

# 创建一个测试图片
img = Image.new('RGB', (100, 100), color='red')
img_bytes = BytesIO()
img.save(img_bytes, format='PNG')
img_bytes.seek(0)

# 测试上传
url = "http://localhost:8000/api/questions/upload-image"
files = {'file': ('test.png', img_bytes, 'image/png')}

# 需要登录token，先尝试不带token看看错误
print("测试1: 不带token上传")
response = requests.post(url, files=files)
print(f"状态码: {response.status_code}")
print(f"响应: {response.text}")
print()

# 如果需要token，先注册并登录
if response.status_code == 401:
    print("需要登录，先尝试注册...")
    register_url = "http://localhost:8000/api/auth/register"
    register_data = {"username": "testuser", "password": "123456", "email": "test@test.com"}
    register_response = requests.post(register_url, json=register_data)
    print(f"注册响应: {register_response.status_code}")

    print("尝试登录...")
    login_url = "http://localhost:8000/api/auth/login"
    login_data = {"username": "testuser", "password": "123456"}
    login_response = requests.post(login_url, json=login_data)

    if login_response.status_code == 200:
        token = login_response.json().get('access_token')
        print(f"登录成功，token: {token[:20]}...")

        # 重新创建图片
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        files = {'file': ('test.png', img_bytes, 'image/png')}

        print("\n测试2: 带token上传")
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.post(url, files=files, headers=headers)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")

        if response.status_code == 200:
            result = response.json()
            print(f"\n上传成功！")
            print(f"URL: {result.get('url')}")
            print(f"文件名: {result.get('filename')}")

            # 检查文件是否真的存在
            from app.config import IMAGE_DIR
            filename = result.get('filename')
            if filename:
                filepath = os.path.join(IMAGE_DIR, filename)
                print(f"\n检查文件: {filepath}")
                print(f"文件存在: {os.path.exists(filepath)}")
                if os.path.exists(filepath):
                    print(f"文件大小: {os.path.getsize(filepath)} bytes")
    else:
        print(f"登录失败: {login_response.status_code}")
        print(f"响应: {login_response.text}")
