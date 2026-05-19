"""测试错题识别API"""
import requests
from PIL import Image
from io import BytesIO

# 创建一个简单的测试图片
img = Image.new('RGB', (800, 600), color='white')
buf = BytesIO()
img.save(buf, format='JPEG')
buf.seek(0)

# 准备请求
url = 'http://localhost:8000/api/wrong-questions/recognize'
files = {'file': ('test.jpg', buf, 'image/jpeg')}

# 需要认证token，先获取一个测试token
# 这里假设有一个测试用户
login_url = 'http://localhost:8000/api/auth/login'
login_data = {
    'username': 'test',
    'password': 'test123'
}

try:
    # 尝试登录获取token
    print("正在登录...")
    login_response = requests.post(login_url, json=login_data)
    if login_response.status_code == 200:
        token = login_response.json().get('access_token')
        headers = {'Authorization': f'Bearer {token}'}

        # 测试识别接口
        print("正在测试识别接口...")
        response = requests.post(url, files=files, headers=headers)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text}")
    else:
        print(f"登录失败: {login_response.status_code}")
        print(f"响应: {login_response.text}")
        print("\n尝试不带token直接测试...")
        response = requests.post(url, files=files)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text}")

except Exception as e:
    print(f"测试失败: {e}")
    import traceback
    traceback.print_exc()
