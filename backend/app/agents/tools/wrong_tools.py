from datetime import date, timedelta
from typing import Any, Dict

from sqlalchemy.orm import Session

from ...models import Question, UserWrongQuestion


def get_recent_wrong_questions_tool(user_id: int, args: Dict[str, Any], db: Session) -> Dict[str, Any]:
    recent_days = int(args.get("recent_days") or 7)
    start_day = date.today() - timedelta(days=max(1, min(365, recent_days)))
    rows = (
        db.query(UserWrongQuestion)
        .filter(UserWrongQuestion.user_id == user_id, UserWrongQuestion.created_date >= start_day)
        .order_by(UserWrongQuestion.created_date.desc())
        .limit(20)
        .all()
    )
    items = []
    for row in rows:
        question = db.query(Question).filter(Question.question_id == row.question_id).first()
        if not question:
            continue
        items.append({
            "record_id": row.record_id,
            "question_id": question.question_id,
            "question_text": question.question_text,
            "knowledge_point": question.knowledge_point,
            "knowledge_category": question.knowledge_category,
            "question_type": question.question_type,
            "difficulty": question.difficulty,
            "error_type": row.error_type,
            "mastered": bool(row.mastered),
            "created_at": row.created_date.isoformat() if row.created_date else "",
        })

    if not items:
        return {
            "reply": f"最近 {recent_days} 天暂时没有错题记录。",
            "actions": [{"type": "show_wrong_question_list", "data": {"wrong_questions": []}}],
            "suggestions": ["生成一套练习", "查看薄弱点"],
        }

    unmastered = sum(1 for item in items if not item["mastered"])
    return {
        "reply": f"最近 {recent_days} 天共有 {len(items)} 道错题，其中 {unmastered} 道还未掌握。",
        "actions": [{"type": "show_wrong_question_list", "data": {"wrong_questions": items, "recent_days": recent_days}}],
        "suggestions": ["把这些错题生成练习", "生成举一反三"],
    }

