"""直接测试恢复逻辑"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from app.utils.deepseek import _extract_json_objects

# 模拟截断的响应
truncated_response = """```json
[
    {
        "question_text": "1.题目1",
        "answer": "",
        "solution": "",
        "question_type": "fill_blank",
        "difficulty": "中等",
        "knowledge_point": "等差数列",
        "knowledge_category": "数论",
        "has_image": false
    },
    {
        "question_text": "2.题目2",
        "answer": "",
        "solution": "",
        "question_type": "fill_blank",
        "difficulty": "中等",
        "knowledge_point": "找规律",
        "knowledge_category": "其他",
        "has_image": false
    },
    {
        "question_text": "3.题目3被截断了",
        "answer": "",
        "solution":"""

print("测试截断响应的恢复:")
print("="*80)
print(truncated_response)
print("="*80)

# 提取 markdown 代码块内容
import re
match = re.search(r"```(?:json)?\s*([\s\S]*?)```", truncated_response)
if not match:
    match = re.search(r"```(?:json)?\s*([\s\S]*)", truncated_response)

if match:
    json_text = match.group(1).strip()
    print(f"\n提取的 JSON 文本长度: {len(json_text)}")
    print(f"前 200 字符: {json_text[:200]}")

    recovered = _extract_json_objects(json_text)
    print(f"\n恢复的对象数量: {len(recovered)}")
    for i, obj in enumerate(recovered, 1):
        print(f"{i}. {obj.get('question_text', 'N/A')}")
else:
    print("未找到 markdown 代码块")
