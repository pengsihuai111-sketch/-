"""测试智谱 AI API 的正确格式"""
import asyncio
import httpx
import base64
import sys

sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "08a75935e68a4ceba53e2e80e4d8e9ea.6dq9N5j7sl935NuU"
API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = "glm-4v-flash"

async def test_formats():
    """测试不同的请求格式"""

    # 读取测试图片
    with open("../uploads/clean/p1_05324c4f4baf.jpg", "rb") as f:
        image_bytes = f.read()

    base64_image = base64.b64encode(image_bytes).decode('utf-8')

    # 格式1: 当前格式（带 max_tokens）
    payload1 = {
        "model": MODEL,
        "max_tokens": 8192,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    },
                    {
                        "type": "text",
                        "text": "请识别这张图片中的内容"
                    }
                ]
            }
        ]
    }

    # 格式2: 不带 max_tokens
    payload2 = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    },
                    {
                        "type": "text",
                        "text": "请识别这张图片中的内容"
                    }
                ]
            }
        ]
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        print("测试格式1: 带 max_tokens=8192")
        try:
            resp1 = await client.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload1
            )
            print(f"状态码: {resp1.status_code}")
            print(f"响应: {resp1.text[:500]}")
        except Exception as e:
            print(f"错误: {e}")

        print("\n" + "="*50 + "\n")

        print("测试格式2: 不带 max_tokens")
        try:
            resp2 = await client.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload2
            )
            print(f"状态码: {resp2.status_code}")
            print(f"响应: {resp2.text[:500]}")
        except Exception as e:
            print(f"错误: {e}")

if __name__ == "__main__":
    asyncio.run(test_formats())
