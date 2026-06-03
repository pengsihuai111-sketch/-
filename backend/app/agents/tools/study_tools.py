from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from typing import Any, Dict, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from ...models import PracticeSheet, Question, UserKnowledgeMastery, UserPracticeHistory, UserWrongQuestion


def _safe_days(args: Dict[str, Any], default: int = 7) -> int:
    try:
        return max(1, min(90, int(args.get("days") or default)))
    except (TypeError, ValueError):
        return default


def _get_weak_points(user_id: int, db: Session, limit: int = 6) -> List[dict]:
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
        }
        for row in rows
        if row.knowledge_point
    ]


def _get_recent_wrong_focus(user_id: int, db: Session, days: int, limit: int = 6) -> List[dict]:
    start_day = date.today() - timedelta(days=days)
    rows = (
        db.query(UserWrongQuestion, Question)
        .join(Question, Question.question_id == UserWrongQuestion.question_id)
        .filter(UserWrongQuestion.user_id == user_id, UserWrongQuestion.created_date >= start_day)
        .all()
    )
    counter = Counter()
    category_counter = Counter()
    for wrong, question in rows:
        counter[question.knowledge_point or "未标注知识点"] += 1
        category_counter[question.knowledge_category or "其他"] += 1
    return [
        {
            "knowledge_point": point,
            "wrong_count": count,
            "category": category_counter.most_common(1)[0][0] if category_counter else "其他",
        }
        for point, count in counter.most_common(limit)
    ]


def build_study_plan_tool(user_id: int, args: Dict[str, Any], db: Session) -> Dict[str, Any]:
    days = _safe_days(args, default=7)
    weak_points = _get_weak_points(user_id, db)
    wrong_focus = _get_recent_wrong_focus(user_id, db, days)
    focus_pool = []
    for item in wrong_focus:
        if item["knowledge_point"] not in focus_pool:
            focus_pool.append(item["knowledge_point"])
    for item in weak_points:
        if item["knowledge_point"] not in focus_pool:
            focus_pool.append(item["knowledge_point"])
    if not focus_pool:
        focus_pool = ["计算准确率", "应用题审题", "几何基础"]

    plan_days = min(7, max(3, days))
    tasks = []
    for index in range(plan_days):
        focus = focus_pool[index % len(focus_pool)]
        tasks.append({
            "day": index + 1,
            "focus": focus,
            "minutes": 25 if index < plan_days - 1 else 35,
            "tasks": [
                f"复盘 {focus} 的错题 2-3 道",
                f"完成 {focus} 同类练习 4-6 道",
                "记录一个易错提醒，第二天先回看",
            ],
        })

    data = {
        "days": plan_days,
        "weak_points": weak_points,
        "wrong_focus": wrong_focus,
        "tasks": tasks,
        "parent_tips": [
            "每天只盯一个重点，避免题量太多导致孩子抵触。",
            "先让孩子讲思路，再看答案，能更快暴露薄弱点。",
            "连续两天错同类题时，优先回到概念和例题，不急着刷难题。",
        ],
    }
    return {
        "reply": f"我按最近 {days} 天错题和薄弱点，整理了一份 {plan_days} 天学习计划。",
        "actions": [{"type": "show_study_plan", "data": data}],
        "suggestions": ["按这个计划生成练习单", "计划再轻松一点", "查看学习总结"],
        "data": data,
    }


def build_study_summary_tool(user_id: int, args: Dict[str, Any], db: Session) -> Dict[str, Any]:
    days = _safe_days(args, default=7)
    start_day = date.today() - timedelta(days=days)

    practiced = (
        db.query(UserPracticeHistory)
        .filter(UserPracticeHistory.user_id == user_id, UserPracticeHistory.practice_date >= start_day)
        .all()
    )
    total_practiced = len(practiced)
    correct = sum(1 for item in practiced if item.is_correct is True)
    wrong = sum(1 for item in practiced if item.is_correct is False)
    accuracy = round(correct / (correct + wrong) * 100, 1) if correct + wrong else None

    wrong_count = (
        db.query(func.count(UserWrongQuestion.record_id))
        .filter(UserWrongQuestion.user_id == user_id, UserWrongQuestion.created_date >= start_day)
        .scalar()
        or 0
    )
    completed_sheets = (
        db.query(func.count(PracticeSheet.sheet_id))
        .filter(
            PracticeSheet.user_id == user_id,
            PracticeSheet.generated_date >= start_day,
            PracticeSheet.completed == True,
        )
        .scalar()
        or 0
    )
    weak_points = _get_weak_points(user_id, db, limit=5)
    wrong_focus = _get_recent_wrong_focus(user_id, db, days, limit=5)

    highlights = []
    if total_practiced:
        highlights.append(f"最近 {days} 天共练习 {total_practiced} 道题。")
    if accuracy is not None:
        highlights.append(f"已批改题目的正确率约 {accuracy}%。")
    if completed_sheets:
        highlights.append(f"完成了 {completed_sheets} 套练习单。")
    if not highlights:
        highlights.append("最近练习记录还不多，可以先从错题回顾和轻量练习开始。")

    data = {
        "days": days,
        "stats": {
            "total_practiced": total_practiced,
            "correct": correct,
            "wrong": wrong,
            "accuracy": accuracy,
            "wrong_count": wrong_count,
            "completed_sheets": completed_sheets,
        },
        "weak_points": weak_points,
        "wrong_focus": wrong_focus,
        "highlights": highlights,
        "next_actions": [
            "优先处理错题最多的 1-2 个知识点。",
            "每次练习后立刻订正，并让孩子复述错因。",
            "用 3 天做巩固，最后 1 天做混合检测。",
        ],
    }
    return {
        "reply": f"我整理了最近 {days} 天的学习总结，重点看练习量、错题集中点和下一步动作。",
        "actions": [{"type": "show_study_summary", "data": data}],
        "suggestions": ["制定下一周学习计划", "根据薄弱点生成练习", "查看最近错题"],
        "data": data,
    }
