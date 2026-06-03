from typing import Any, Dict

from sqlalchemy.orm import Session

from ...models import UserKnowledgeMastery


def get_weak_points_tool(user_id: int, args: Dict[str, Any], db: Session) -> Dict[str, Any]:
    rows = (
        db.query(UserKnowledgeMastery)
        .filter(UserKnowledgeMastery.user_id == user_id)
        .order_by(UserKnowledgeMastery.is_weak_point.desc(), UserKnowledgeMastery.mastery_rate.asc())
        .limit(8)
        .all()
    )
    weak_points = [
        {
            "knowledge_point": row.knowledge_point,
            "mastery_rate": float(row.mastery_rate or 0),
            "total_practiced": row.total_practiced or 0,
            "correct_count": row.correct_count or 0,
            "forgetting_risk_score": row.forgetting_risk_score or 0,
            "is_weak_point": bool(row.is_weak_point),
        }
        for row in rows
    ]
    if not weak_points:
        return {
            "reply": "目前还没有足够的练习记录来判断薄弱点。建议先完成几套练习单，我再帮你分析。",
            "actions": [{"type": "show_weak_points", "data": {"weak_points": []}}],
            "suggestions": ["生成一套基础练习", "查看错题本"],
        }
    names = "、".join(item["knowledge_point"] for item in weak_points[:3])
    return {
        "reply": f"根据现有练习记录，你目前需要优先关注：{names}。",
        "actions": [{"type": "show_weak_points", "data": {"weak_points": weak_points}}],
        "suggestions": ["基于薄弱点生成练习", "查看最近错题"],
    }

