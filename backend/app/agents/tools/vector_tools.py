from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from ...vector.search import semantic_search_questions, similar_questions


async def semantic_search_tool(user_id: int, args: Dict[str, Any], db: Session) -> Dict[str, Any]:
    query = str(args.get("query") or "").strip()
    if not query:
        return {
            "reply": "你想找哪类题？可以说“找几何面积中等题”或“搜索浓度问题”。",
            "actions": [],
            "suggestions": ["搜索行程问题", "搜索几何面积题", "搜索浓度应用题"],
        }
    items = await semantic_search_questions(db, query, limit=int(args.get("limit") or 8))
    return {
        "reply": f"我按语义帮你找到了 {len(items)} 道相关题。若 Qdrant 暂不可用，系统会自动用题干和知识点关键词兜底。",
        "actions": [{"type": "show_similar_questions", "data": {"items": items, "query": query}}],
        "suggestions": ["换一批同类题", "用这些题生成练习单", "再缩小范围"],
        "data": {"items": items},
    }


async def similar_questions_tool(user_id: int, args: Dict[str, Any], db: Session) -> Dict[str, Any]:
    question_id = args.get("question_id")
    if question_id:
        items = await similar_questions(db, int(question_id), limit=int(args.get("limit") or 8))
        reply = f"我找到了 {len(items)} 道和第 {question_id} 题相近的题。"
    else:
        query = str(args.get("query") or "").strip()
        items = await semantic_search_questions(db, query, limit=int(args.get("limit") or 8)) if query else []
        reply = f"我按你的描述找到了 {len(items)} 道同类题。"

    return {
        "reply": reply,
        "actions": [{"type": "show_similar_questions", "data": {"items": items, "question_id": question_id}}],
        "suggestions": ["用这些题生成练习单", "再找更难一点", "再找简单一点"],
        "data": {"items": items},
    }
