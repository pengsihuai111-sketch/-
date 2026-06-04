from __future__ import annotations

import difflib
import re
from datetime import date
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from ..constants import WRONG_QUESTION_ADD
from ..context import trace_node, trace_tool
from ..guardrails import safe_tool_args
from ..state import AgentState
from ..tools.wrong_tools import get_recent_wrong_questions_tool
from ...models import Question, UserKnowledgeMastery, UserWrongQuestion
from ...utils.knowledge_classifier import normalize_question_metadata
from .common import run_linear_subgraph


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _generate_q_id(knowledge_point: str, db: Session) -> str:
    base = re.sub(r"[\s\-]+", "_", knowledge_point or "AI错题")[:18] or "AI错题"
    prefix = f"AI_{base}"
    existing = db.query(Question.q_id).filter(Question.q_id.like(f"{prefix}_%")).all()
    numbers = []
    for row in existing:
        match = re.search(r"_(\d+)$", row[0] or "")
        if match:
            numbers.append(int(match.group(1)))
    return f"{prefix}_{max(numbers, default=0) + 1:04d}"


def _find_existing_question(question_text: str, db: Session) -> Question | None:
    normalized = _normalize_text(question_text)
    if len(normalized) < 8:
        return None
    keyword = normalized[: min(80, len(normalized))]
    candidates = db.query(Question).filter(Question.question_text.like(f"%{keyword[:30]}%")).limit(30).all()
    for question in candidates:
        ratio = difflib.SequenceMatcher(None, normalized, _normalize_text(question.question_text or "")).ratio()
        if ratio >= 0.88:
            return question
    return None


def _question_payload_from_item(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "question_text": str(item.get("question_text") or item.get("stem") or "").strip(),
        "answer": str(item.get("answer") or "").strip(),
        "solution": str(item.get("solution") or item.get("analysis") or "").strip(),
        "question_type": str(item.get("question_type") or "other").strip() or "other",
        "difficulty": str(item.get("difficulty") or "中等").strip() or "中等",
        "knowledge_point": str(item.get("knowledge_point") or "").strip(),
        "knowledge_category": str(item.get("knowledge_category") or "").strip(),
    }


def _create_or_get_question(payload: Dict[str, Any], db: Session) -> Question:
    existing = _find_existing_question(payload["question_text"], db)
    if existing:
        return existing

    normalized = normalize_question_metadata({
        "question_text": payload["question_text"],
        "question_type": payload.get("question_type") or "other",
        "difficulty": payload.get("difficulty") or "中等",
        "knowledge_point": payload.get("knowledge_point") or "",
        "knowledge_category": payload.get("knowledge_category") or "",
        "answer": payload.get("answer") or "",
        "solution": payload.get("solution") or "",
    })
    question = Question(
        q_id=_generate_q_id(normalized.get("knowledge_point") or "AI错题", db),
        question_text=normalized["question_text"],
        answer=normalized.get("answer") or "",
        solution=normalized.get("solution") or "",
        question_type=normalized.get("question_type") or "other",
        difficulty=normalized.get("difficulty") or "中等",
        knowledge_point=normalized.get("knowledge_point") or "待确认",
        knowledge_category=normalized.get("knowledge_category") or "其他",
        grade_level="六年级",
        source_exam="AI学习助手",
        verification_status="needs_review",
    )
    db.add(question)
    db.flush()
    return question


def _ensure_mastery(user_id: int, question: Question, db: Session) -> None:
    mastery = (
        db.query(UserKnowledgeMastery)
        .filter(
            UserKnowledgeMastery.user_id == user_id,
            UserKnowledgeMastery.knowledge_point == question.knowledge_point,
        )
        .first()
    )
    if mastery:
        return
    db.add(UserKnowledgeMastery(
        user_id=user_id,
        knowledge_point=question.knowledge_point,
        total_practiced=0,
        correct_count=0,
        mastery_rate=0,
        is_weak_point=True,
    ))


def _add_payload_to_wrong_book(user_id: int, payload: Dict[str, Any], db: Session) -> Dict[str, Any]:
    if not payload.get("question_text"):
        return {"created": False, "skipped": True, "message": "题干为空，已跳过"}

    question = _create_or_get_question(payload, db)
    _ensure_mastery(user_id, question, db)
    existing = (
        db.query(UserWrongQuestion)
        .filter(UserWrongQuestion.user_id == user_id, UserWrongQuestion.question_id == question.question_id)
        .first()
    )
    if existing:
        return {
            "created": False,
            "already_exists": True,
            "record_id": existing.record_id,
            "question_id": question.question_id,
            "message": "这道题已经在错题本里",
        }

    record = UserWrongQuestion(
        user_id=user_id,
        question_id=question.question_id,
        error_type="其他",
        mastered=False,
        redo_count=0,
        exam_date=date.today(),
        exam_name="AI学习助手",
        notes="由 AI 学习助手加入错题本",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "created": True,
        "already_exists": False,
        "record_id": record.record_id,
        "question_id": question.question_id,
        "message": "已加入错题本",
    }


def _collect_wrong_add_items(state: AgentState) -> List[Dict[str, Any]]:
    args = state.get("tool_args") or {}
    resolved = state.get("resolved_target") or {}
    if args.get("attachment_questions"):
        return [item for item in args["attachment_questions"] if isinstance(item, dict)]
    if resolved.get("questions"):
        return [item for item in resolved["questions"] if isinstance(item, dict)]
    if resolved.get("question"):
        return [resolved["question"]]
    if args.get("question_text"):
        return [{"question_text": args.get("question_text")}]
    recent_question = (state.get("context") or {}).get("recent_question") or {}
    if recent_question:
        return [recent_question]
    return []


async def wrong_context_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "wrong_context_node")
    return state


async def wrong_tool_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "wrong_tool_node")
    user_id = int(state["user_id"])
    if state.get("intent") == WRONG_QUESTION_ADD:
        results = []
        for item in _collect_wrong_add_items(state)[:20]:
            results.append(_add_payload_to_wrong_book(user_id, _question_payload_from_item(item), db))
        created = sum(1 for item in results if item.get("created"))
        existed = sum(1 for item in results if item.get("already_exists"))
        skipped = sum(1 for item in results if item.get("skipped"))
        result = {
            "reply": f"已处理错题本：新增 {created} 道，已存在 {existed} 道，跳过 {skipped} 道。",
            "actions": [{
                "type": "show_wrong_add_result",
                "data": {"created": created, "already_exists": existed, "skipped": skipped, "results": results},
            }],
            "suggestions": ["查看最近错题", "用这些错题生成练习单", "推荐同类题"],
            "data": {"created": created, "already_exists": existed, "skipped": skipped, "results": results},
        }
        state["tool_name"] = "add_questions_to_wrong_book_tool"
    else:
        result = get_recent_wrong_questions_tool(user_id, safe_tool_args(state.get("tool_args")), db)
        state["tool_name"] = "get_recent_wrong_questions_tool"

    state["tool_result"] = result
    state["reply"] = result.get("reply", "")
    state["actions"] = result.get("actions", [])
    state["suggestions"] = result.get("suggestions", [])
    trace_tool(state, node="wrong_tool_node", tool_name=state["tool_name"])
    return state


async def wrong_response_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "wrong_response_node")
    state["sub_intent"] = "add_wrong_questions" if state.get("intent") == WRONG_QUESTION_ADD else "review_wrong_questions"
    return state


async def run_wrong_subgraph(state: AgentState, db: Session) -> AgentState:
    return await run_linear_subgraph(
        state=state,
        db=db,
        graph_name="wrong_subgraph",
        nodes=[
            ("wrong_context_node", wrong_context_node),
            ("wrong_tool_node", wrong_tool_node),
            ("wrong_response_node", wrong_response_node),
        ],
    )
