from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from ...models import Question
from ...utils.deepseek import generate_answer


def _build_easy_mistakes(question_text: str, question_type: str, knowledge_point: str) -> list[str]:
    text = question_text or ""
    mistakes = []
    if any(word in text for word in ["多少", "几", "求"]):
        mistakes.append("先确认题目最终问的是什么，不要只算中间量。")
    if any(word in text for word in ["比例", "百分", "%", "浓度"]):
        mistakes.append("比例、百分数和单位要统一后再列式。")
    if any(word in text for word in ["面积", "周长", "体积", "表面积"]):
        mistakes.append("几何题要先分清求面积、周长、体积还是表面积。")
    if question_type == "calculation" or "计算" in (knowledge_point or ""):
        mistakes.append("计算题建议保留关键步骤，方便检查符号和进位。")
    if not mistakes:
        mistakes.append("把关键条件圈出来，再判断用哪一种方法。")
    return mistakes[:3]


async def explain_question_tool(user_id: int, args: Dict[str, Any], db: Session) -> Dict[str, Any]:
    question = None
    question_id = args.get("question_id")
    if question_id:
        question = db.query(Question).filter(Question.question_id == int(question_id)).first()

    if args.get("awaiting_question") and not question:
        return {
            "reply": "可以，把题目内容发给我就行。你可以直接粘贴题干，也可以说“讲解第 12 题”。如果题目有图，先把图里的文字或关键条件发我。",
            "actions": [],
            "suggestions": ["我直接粘贴题目", "讲解题库里的某一题", "先看最近错题"],
        }

    question_text = str(args.get("question_text") or "").strip()
    if question:
        question_text = question.question_text or question_text
        answer = question.answer or ""
        solution = question.solution or ""
        knowledge_point = question.knowledge_point or ""
        question_type = question.question_type or ""
    else:
        answer = ""
        solution = ""
        knowledge_point = ""
        question_type = ""

    if not question_text:
        return {
            "reply": "请把要讲解的题目发给我，或者告诉我题库里的题号。我会按“题意、关键条件、步骤、易错点”来讲。",
            "actions": [],
            "suggestions": ["讲解第 1 题", "我粘贴一道题给你", "查看最近错题"],
        }

    if not answer or not solution:
        result = await generate_answer(question_text, question_type, knowledge_point)
        answer = answer or result.get("answer", "")
        solution = solution or result.get("solution", "")

    easy_mistakes = _build_easy_mistakes(question_text, question_type, knowledge_point)
    data = {
        "question": {
            "question_id": question.question_id if question else None,
            "question_text": question_text,
            "answer": answer,
            "solution": solution,
            "knowledge_point": knowledge_point,
            "question_type": question_type,
            "easy_mistakes": easy_mistakes,
            "explain_sections": [
                {"title": "题意理解", "content": "先找清楚已知条件、要求的量，以及是否存在单位或比例关系。"},
                {"title": "关键条件", "content": "把题干中的数量关系转化成算式、方程或图形关系。"},
                {"title": "解题步骤", "content": solution or "这道题目前没有详细解析，建议先补充题目条件后再生成。"},
                {"title": "易错提醒", "content": "；".join(easy_mistakes)},
            ],
        }
    }
    return {
        "reply": "我按“题意、关键条件、步骤、易错点”整理好了这道题。",
        "actions": [{"type": "show_question_explanation", "data": data}],
        "suggestions": ["推荐同类题", "用同类题生成练习单", "再讲简单一点"],
        "data": data,
    }
