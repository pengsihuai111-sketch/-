from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from ...models import PracticeSheet, Question, UserKnowledgeMastery, UserPracticeHistory, UserWrongQuestion


def _safe_days(args: Dict[str, Any], default: int = 7) -> int:
    try:
        return max(1, min(90, int(args.get("days") or args.get("recent_days") or default)))
    except (TypeError, ValueError):
        return default


def _period_start(days: int) -> date:
    return date.today() - timedelta(days=days)


def _as_date_start(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time())


def _accuracy(records: Iterable[UserPracticeHistory]) -> float | None:
    items = list(records)
    correct = sum(1 for item in items if item.is_correct is True)
    wrong = sum(1 for item in items if item.is_correct is False)
    return round(correct / (correct + wrong) * 100, 1) if correct + wrong else None


def _practice_stats(user_id: int, db: Session, start_day: date, end_day: date | None = None) -> dict:
    query = db.query(UserPracticeHistory).filter(
        UserPracticeHistory.user_id == user_id,
        UserPracticeHistory.practice_date >= start_day,
    )
    if end_day:
        query = query.filter(UserPracticeHistory.practice_date < end_day)
    records = query.all()
    correct = sum(1 for item in records if item.is_correct is True)
    wrong = sum(1 for item in records if item.is_correct is False)
    accuracy = round(correct / (correct + wrong) * 100, 1) if correct + wrong else None
    return {
        "total_practiced": len(records),
        "correct": correct,
        "wrong": wrong,
        "accuracy": accuracy,
        "active_days": len({item.practice_date for item in records}),
        "total_minutes": round(sum((item.time_spent or 0) for item in records) / 60, 1),
    }


def _sheet_stats(user_id: int, db: Session, start_day: date) -> dict:
    rows = (
        db.query(PracticeSheet)
        .filter(PracticeSheet.user_id == user_id, PracticeSheet.generated_date >= _as_date_start(start_day))
        .all()
    )
    completed = [item for item in rows if item.completed]
    avg_score = None
    scores = [float(item.score) for item in completed if item.score is not None]
    if scores:
        avg_score = round(sum(scores) / len(scores), 1)
    return {
        "generated": len(rows),
        "completed": len(completed),
        "avg_score": avg_score,
        "estimated_minutes": sum(item.estimated_time or 0 for item in rows),
    }


def _wrong_focus(user_id: int, db: Session, start_day: date, limit: int = 6) -> List[dict]:
    rows = (
        db.query(UserWrongQuestion, Question)
        .join(Question, Question.question_id == UserWrongQuestion.question_id)
        .filter(UserWrongQuestion.user_id == user_id, UserWrongQuestion.created_date >= _as_date_start(start_day))
        .all()
    )
    counter = Counter()
    category_by_point: dict[str, Counter] = {}
    error_counter = Counter()
    for wrong, question in rows:
        point = question.knowledge_point or "未标注知识点"
        category = question.knowledge_category or "其他"
        counter[point] += 1
        category_by_point.setdefault(point, Counter())[category] += 1
        if wrong.error_type:
            error_counter[wrong.error_type] += 1
    return [
        {
            "knowledge_point": point,
            "knowledge_category": category_by_point.get(point, Counter()).most_common(1)[0][0],
            "wrong_count": count,
            "parent_explanation": _parent_explanation(point),
        }
        for point, count in counter.most_common(limit)
    ]


def _weak_points(user_id: int, db: Session, limit: int = 6) -> List[dict]:
    rows = (
        db.query(UserKnowledgeMastery)
        .filter(UserKnowledgeMastery.user_id == user_id)
        .order_by(UserKnowledgeMastery.is_weak_point.desc(), UserKnowledgeMastery.mastery_rate.asc())
        .limit(limit)
        .all()
    )
    return [
        {
            "knowledge_point": row.knowledge_point,
            "mastery_rate": float(row.mastery_rate or 0),
            "total_practiced": row.total_practiced or 0,
            "correct_count": row.correct_count or 0,
            "forgetting_risk_score": row.forgetting_risk_score or 0,
            "parent_explanation": _parent_explanation(row.knowledge_point or ""),
        }
        for row in rows
        if row.knowledge_point
    ]


def _parent_explanation(point: str) -> str:
    text = point or ""
    if any(word in text for word in ["方程", "和差倍", "年龄"]):
        return "这类问题重点不是会不会算，而是能不能把文字条件翻译成等量关系。陪练时先让孩子说“谁和谁相等”。"
    if any(word in text for word in ["行程", "速度", "相遇", "追及"]):
        return "这类题容易错在关系图没有画清楚。先固定速度、时间、路程三件事，再列式。"
    if any(word in text for word in ["面积", "几何", "周长", "体积", "表面积"]):
        return "这类题不是单纯套公式，关键是能不能拆图、补图、找到对应的底和高。"
    if any(word in text for word in ["浓度", "溶液", "盐水"]):
        return "这类题要盯住不变量，通常是盐、糖或纯酒精的量不变，不要只看浓度百分比。"
    if any(word in text for word in ["利润", "经济", "折扣"]):
        return "这类题要分清成本价、售价、利润和利润率，先画一条价格关系线会更稳。"
    if any(word in text for word in ["分数", "百分数", "比例"]):
        return "这类题要先确认单位“1”是谁。孩子错题多半不是计算错，而是参照量找错。"
    if any(word in text for word in ["规律", "排列", "组合", "逻辑"]):
        return "这类题考的是分类和枚举完整性。陪练时重点问“有没有漏掉或重复”。"
    return "先让孩子复述题意，再说第一步为什么这么做，比直接看答案更能暴露问题。"


def _trend(current: dict, previous: dict) -> dict:
    current_accuracy = current.get("accuracy")
    previous_accuracy = previous.get("accuracy")
    if current_accuracy is None or previous_accuracy is None:
        accuracy_delta = None
    else:
        accuracy_delta = round(current_accuracy - previous_accuracy, 1)
    return {
        "accuracy_delta": accuracy_delta,
        "practice_delta": current.get("total_practiced", 0) - previous.get("total_practiced", 0),
        "wrong_delta": current.get("wrong", 0) - previous.get("wrong", 0),
    }


def _overall_judgement(stats: dict, trend: dict, weak_points: List[dict], wrong_focus: List[dict]) -> str:
    if stats.get("total_practiced", 0) == 0:
        return "最近练习数据不足，建议先建立稳定的每日练习记录，再判断真实薄弱点。"
    if trend.get("accuracy_delta") is not None and trend["accuracy_delta"] >= 5:
        return "整体有改善，建议保持当前节奏，把重点放在高频错题的复盘。"
    if weak_points or wrong_focus:
        return "当前主要问题集中在少数知识点，适合用“错题复盘 + 同类题巩固”的方式处理。"
    return "整体状态平稳，可以增加少量综合题，检查知识迁移能力。"


def _build_parent_tasks(days: int, focus_items: List[dict]) -> List[dict]:
    focus_names = [item["knowledge_point"] for item in focus_items] or ["计算准确率", "应用题审题", "错题复盘"]
    task_count = 5 if days <= 7 else 7
    tasks = []
    for index in range(task_count):
        focus = focus_names[index % len(focus_names)]
        tasks.append({
            "day": index + 1,
            "focus": focus,
            "minutes": 20 if index < task_count - 1 else 30,
            "parent_action": f"先让孩子讲一遍 {focus} 的错因，再做 3-5 道同类题。",
            "check_result": "看孩子是否能独立说出第一步，而不是只看最终答案。",
        })
    return tasks


def build_parent_report_tool(user_id: int, args: Dict[str, Any], db: Session) -> Dict[str, Any]:
    days = _safe_days(args, default=7)
    start_day = _period_start(days)
    previous_start = _period_start(days * 2)

    stats = _practice_stats(user_id, db, start_day)
    previous_stats = _practice_stats(user_id, db, previous_start, start_day)
    sheets = _sheet_stats(user_id, db, start_day)
    wrong_focus = _wrong_focus(user_id, db, start_day)
    weak_points = _weak_points(user_id, db)
    trend = _trend(stats, previous_stats)
    focus_items = wrong_focus or weak_points

    data = {
        "days": days,
        "title": f"最近 {days} 天学习报告",
        "stats": stats,
        "previous_stats": previous_stats,
        "trend": trend,
        "sheets": sheets,
        "wrong_focus": wrong_focus,
        "weak_points": weak_points,
        "overall_judgement": _overall_judgement(stats, trend, weak_points, wrong_focus),
        "parent_tasks": _build_parent_tasks(days, focus_items),
        "parent_tips": [
            "每天只盯一个主要问题，避免把错题全部摊开导致孩子抵触。",
            "讲题时先问“你第一步想做什么”，不要先问“答案是多少”。",
            "连续两次错同类题时，先回到例题和概念，不要直接加难题。",
        ],
        "practice_prompt": f"根据最近 {days} 天错题，生成一套包含原错题和同类巩固题的练习单",
    }
    return {
        "reply": f"已整理最近 {days} 天的家长视角学习报告，重点包括练习量、错题集中点、变化趋势和可执行陪练任务。",
        "actions": [{"type": "show_parent_report", "data": data}],
        "suggestions": [
            "按这个报告生成练习单",
            "生成未来 7 天学习计划",
            "解释最薄弱的知识点",
        ],
        "data": data,
    }
