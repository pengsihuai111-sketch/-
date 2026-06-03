from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from ...models import Question
from ...schemas import AIPracticePreviewRequest
from ...utils.practice_ai import build_ai_preview


def _serialize_selected_question(question: Question, reason: str = "来自上一轮助手推荐") -> dict[str, Any]:
    return {
        "question_id": question.question_id,
        "q_id": question.q_id,
        "knowledge_point": question.knowledge_point or "",
        "knowledge_category": question.knowledge_category,
        "question_type": question.question_type,
        "difficulty": question.difficulty,
        "question_text": question.question_text,
        "has_image": bool(question.has_image),
        "image_path": question.image_path,
        "selected_reason": reason,
    }


def _extract_question_ids_from_action(action: dict[str, Any]) -> List[int]:
    data = action.get("data") or {}
    ids: List[int] = []
    for key in ("items", "questions", "wrong_questions"):
        for item in data.get(key) or []:
            question_id = item.get("question_id")
            if question_id and int(question_id) not in ids:
                ids.append(int(question_id))
    for variant in data.get("variants") or []:
        for question_id in variant.get("question_ids") or []:
            if question_id and int(question_id) not in ids:
                ids.append(int(question_id))
    return ids


def _build_preview_from_question_ids(question_ids: List[int], db: Session, prompt: str = "") -> Dict[str, Any]:
    if not question_ids:
        return {}
    rows = db.query(Question).filter(Question.question_id.in_(question_ids[:24])).all()
    order = {qid: idx for idx, qid in enumerate(question_ids)}
    rows.sort(key=lambda question: order.get(question.question_id, 9999))
    selected = [_serialize_selected_question(question) for question in rows]
    if not selected:
        return {}

    knowledge_points = sorted({item["knowledge_point"] for item in selected if item["knowledge_point"]})
    knowledge_categories = sorted({item["knowledge_category"] for item in selected if item["knowledge_category"]})
    question_types = sorted({item["question_type"] for item in selected if item["question_type"]})
    difficulties = sorted({item["difficulty"] for item in selected if item["difficulty"]})
    parsed_requirement = {
        "sheet_name": "AI推荐题练习单",
        "sheet_type": "custom",
        "sheet_count": 1,
        "target_count": len(selected),
        "target_minutes": max(10, len(selected) * 3),
        "knowledge_categories": knowledge_categories,
        "knowledge_points": knowledge_points,
        "question_types": question_types,
        "question_type_counts": {},
        "exclude_question_types": [],
        "difficulties": difficulties,
        "difficulty_progression": True,
        "must_include_wrong_questions": False,
        "recent_days": None,
        "include_all_wrong_questions": False,
        "similar_question_count": 0,
        "avoid_recent_questions": False,
        "strategy_hint": "由上一轮助手推荐题目直接组卷，用户确认后才会保存。",
        "reasoning_summary": prompt or "使用上一轮推荐/错题列表生成可确认的练习单。",
        "learning_advice": "先完成这些题，再根据错因继续生成同类题。",
    }
    return {
        "parsed_requirement": parsed_requirement,
        "suggestion": {
            "summary": "已把上一轮题目整理成练习单草稿。",
            "selection_reason": "这些题来自上一轮助手推荐或错题回顾。",
            "ordering_reason": "默认按上一轮展示顺序排列。",
            "coverage_summary": "覆盖上一轮推荐中的主要知识点和题型。",
            "explanation_lines": ["这一步不会直接写入练习单，需要你点击确认生成。"],
            "review_summary": "建议先检查题目数量和难度，再确认生成。",
        },
        "variants": [{
            "variant_id": "assistant-followup-1",
            "sheet_name": "AI推荐题练习单",
            "selected_questions": selected,
            "estimated_time": max(10, len(selected) * 3),
            "composition_summary": "由上一轮助手结果组成。",
            "coverage_summary": "按推荐题/错题集中点覆盖。",
            "review_summary": "可继续换题、补题或确认生成。",
        }],
        "selected_questions": selected,
        "candidate_count": len(selected),
        "estimated_time": max(10, len(selected) * 3),
        "total_variants": 1,
    }


async def generate_practice_preview_tool(user_id: int, args: Dict[str, Any], db: Session) -> Dict[str, Any]:
    prompt = str(args.get("prompt") or "").strip()
    source_action = args.get("source_action") or {}
    if source_action:
        data = _build_preview_from_question_ids(_extract_question_ids_from_action(source_action), db, prompt)
        if data:
            return {
                "reply": "我已把上一轮这些题整理成练习单草稿，你确认后才会正式生成。",
                "actions": [{"type": "show_practice_preview", "data": data}],
                "suggestions": ["确认生成练习单", "再补几题", "换一批题"],
                "data": data,
            }

    difficulties = []
    if args.get("difficulty_hint") == "easier":
        difficulties = ["基础"]
    elif args.get("difficulty_hint") == "harder":
        difficulties = ["中等", "挑战"]
    req = AIPracticePreviewRequest(
        prompt=prompt,
        sheet_type="wrong_redo" if "错题" in prompt else "special_topic",
        difficulties=difficulties,
    )
    preview = await build_ai_preview(req, user_id, db)
    data = preview.model_dump()
    return {
        "reply": f"我已为你准备 {len(data.get('variants') or [])} 套练习单草稿，你可以先查看预览再确认生成。",
        "actions": [{"type": "show_practice_preview", "data": data}],
        "suggestions": ["按这个方向再生成一版", "降低难度再生成", "改成错题举一反三"],
        "data": data,
    }
