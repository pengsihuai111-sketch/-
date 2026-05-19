"""测试错题识别 API 端点"""
import requests
import os
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def test_recognition_api():
    """测试错题识别 API"""

    # 1. 先登录获取 token
    print("=" * 60)
    print("步骤 1: 登录获取 token")
    print("=" * 60)

    login_url = "http://localhost:8000/api/auth/login"
    login_data = {
        "username": "admin",
        "password": "admin123"
    }

    try:
        response = requests.post(login_url, json=login_data)
        if response.status_code == 200:
            token = response.json().get("access_token")
            print(f"✓ 登录成功，获取到 token")
        else:
            print(f"❌ 登录失败: {response.status_code} - {response.text}")
            return
    except Exception as e:
        print(f"❌ 登录请求失败: {e}")
        return

    # 2. 测试错题识别
    print("\n" + "=" * 60)
    print("步骤 2: 上传图片进行识别")
    print("=" * 60)

    # 查找测试图片
    test_image = "../uploads/clean/p1_05324c4f4baf.jpg"

    if not os.path.exists(test_image):
        print(f"❌ 测试图片不存在: {test_image}")
        return

    print(f"使用测试图片: {test_image}")

    recognize_url = "http://localhost:8000/api/wrong-questions/recognize"

    with open(test_image, 'rb') as f:
        files = {'file': ('test.jpg', f, 'image/jpeg')}
        headers = {'Authorization': f'Bearer {token}'}

        print("发送识别请求...")

        try:
            response = requests.post(
                recognize_url,
                files=files,
                headers=headers,
                timeout=180
            )

            print(f"响应状态码: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print("\n✓ 识别成功!")
                print(f"识别出题目数量: {len(result.get('questions', []))}")

                if result.get('recognized'):
                    rec = result['recognized']
                    print(f"\n第一题预览:")
                    print(f"  题目: {rec.get('question_text', '')[:100]}...")
                    print(f"  题型: {rec.get('question_type', '')}")
                    print(f"  难度: {rec.get('difficulty', '')}")
                    print(f"  知识点: {rec.get('knowledge_point', '')}")
                    print(f"  答案: {rec.get('answer', '')[:50]}...")

                print(f"\n匹配到的题库题目数: {result.get('match_count', 0)}")
                print(f"查重状态: {result.get('dedup_status', 'new')}")

                if result.get('matched_question_id'):
                    print(f"匹配的题目ID: {result['matched_question_id']}")

            elif response.status_code == 400:
                print(f"❌ 请求错误: {response.json().get('detail', response.text)}")
            elif response.status_code == 502:
                print(f"❌ AI 服务错误: {response.json().get('detail', response.text)}")
            else:
                print(f"❌ 识别失败: {response.status_code}")
                print(f"响应: {response.text[:500]}")

        except requests.exceptions.Timeout:
            print("❌ 请求超时（180秒）")
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_recognition_api()
