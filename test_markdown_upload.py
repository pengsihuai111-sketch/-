#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试 Markdown 文件上传到后端 API"""

import requests

# 测试文件
test_file = "test_questions.md"

# API 端点
url = "http://localhost:8000/api/wrong-questions/recognize-pdf"

# 读取测试文件
with open(test_file, "rb") as f:
    files = {"file": (test_file, f, "text/markdown")}
    data = {
        "use_markdown": "true",
        "match_question_bank": "true",
        "remove_correction_marks": "true"
    }

    # 需要认证 token，这里先测试不带 token 的情况
    print(f"正在上传 {test_file} 到 {url}")
    print(f"文件类型: text/markdown")
    print(f"参数: {data}")

    try:
        response = requests.post(url, files=files, data=data)
        print(f"\n状态码: {response.status_code}")
        print(f"响应: {response.text}")
    except Exception as e:
        print(f"错误: {e}")
