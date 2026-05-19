import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.utils.deepseek import recognize_questions

async def test():
    img_path = "d:\\project\\题库管理\\题目图片\\测试图片.png"
    with open(img_path, "rb") as f:
        img = f.read()
    print(f"Image: {len(img)} bytes")
    qs = await recognize_questions(img, "test.png")
    print(f"OK: {len(qs)} questions")
    for i, q in enumerate(qs):
        print(f"  {i+1}. [{q.get('question_type','')}] {q.get('question_text','')[:60]}")

asyncio.run(test())
