"""
题库服务层 - 从v3_toolkit复用的业务逻辑
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models import Question, UserWrongQuestion, UserPracticeHistory, PracticeSheet


def get_stats(db: Session) -> dict:
    """获取题库统计"""
    total = db.query(func.count(Question.question_id)).scalar() or 0
    by_difficulty = {
        r[0]: r[1]
        for r in db.query(Question.difficulty, func.count(Question.question_id))
        .group_by(Question.difficulty).all()
        if r[0]
    }
    by_category = {
        r[0]: r[1]
        for r in db.query(Question.knowledge_category, func.count(Question.question_id))
        .group_by(Question.knowledge_category).all()
        if r[0]
    }
    verified = db.query(func.count(Question.question_id)).filter(
        Question.verification_status == "verified"
    ).scalar() or 0
    with_image = db.query(func.count(Question.question_id)).filter(
        Question.has_image == True
    ).scalar() or 0

    return {
        "total_questions": total,
        "by_difficulty": by_difficulty,
        "by_category": by_category,
        "verified_answers": verified,
        "with_image": with_image,
    }
