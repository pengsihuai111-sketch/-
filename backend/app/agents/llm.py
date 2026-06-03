from __future__ import annotations

import json
import re
from typing import Any, Dict

from .constants import (
    FALLBACK,
    FIRST_VERSION_INTENTS,
    LEARNING_DIAGNOSIS,
    PARENT_REPORT,
    PRACTICE_GENERATE,
    QUESTION_EXPLAIN,
    SEMANTIC_QUESTION_SEARCH,
    SIMILAR_QUESTION_RECOMMEND,
    SMALLTALK,
    STUDY_PLAN,
    STUDY_SUMMARY,
    SYSTEM_HELP,
    WRONG_QUESTION_REVIEW,
)
from .state import AgentState
from ..utils.deepseek import call_text_llm


ROUTER_TIMEOUT_SECONDS = 8.0
RESPONSE_TIMEOUT_SECONDS = 8.0

ALLOWED_INTENTS = set(FIRST_VERSION_INTENTS)


def _extract_json_object(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fenced:
        raw = fenced.group(1).strip()
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


def _safe_int(value: Any, default: int | None = None, min_value: int = 1, max_value: int = 365) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, number))


def _sanitize_router_result(result: Dict[str, Any], fallback: AgentState) -> AgentState:
    intent = str(result.get("intent") or "").strip()
    if intent not in ALLOWED_INTENTS:
        intent = fallback.get("intent") or FALLBACK

    args = result.get("tool_args") if isinstance(result.get("tool_args"), dict) else {}
    sanitized: Dict[str, Any] = {}

    if intent == PRACTICE_GENERATE:
        sanitized["prompt"] = str(args.get("prompt") or fallback.get("message") or "").strip()
        if args.get("difficulty_hint") in {"easier", "harder"}:
            sanitized["difficulty_hint"] = args["difficulty_hint"]
    elif intent == WRONG_QUESTION_REVIEW:
        days = _safe_int(args.get("recent_days") or args.get("days"), default=None, max_value=365)
        if days:
            sanitized["recent_days"] = days
    elif intent == QUESTION_EXPLAIN:
        question_id = _safe_int(args.get("question_id"), default=None, max_value=10_000_000)
        if question_id:
            sanitized["question_id"] = question_id
        elif args.get("awaiting_question"):
            sanitized["awaiting_question"] = True
        else:
            sanitized["question_text"] = str(args.get("question_text") or fallback.get("message") or "").strip()
    elif intent == SIMILAR_QUESTION_RECOMMEND:
        question_id = _safe_int(args.get("question_id"), default=None, max_value=10_000_000)
        if question_id:
            sanitized["question_id"] = question_id
        else:
            sanitized["query"] = str(args.get("query") or fallback.get("message") or "").strip()
    elif intent == SEMANTIC_QUESTION_SEARCH:
        sanitized["query"] = str(args.get("query") or fallback.get("message") or "").strip()
    elif intent in {STUDY_PLAN, STUDY_SUMMARY, PARENT_REPORT}:
        days = _safe_int(args.get("days") or args.get("recent_days"), default=None, max_value=90)
        if days:
            sanitized["days"] = days
    elif intent == SYSTEM_HELP:
        sanitized["topic"] = str(args.get("topic") or fallback.get("message") or "").strip()

    state: AgentState = dict(fallback)
    state["intent"] = intent
    state["confidence"] = float(result.get("confidence") or 0.75)
    state["tool_args"] = sanitized
    state["router_source"] = "llm"
    state["llm_router_reason"] = str(result.get("reason") or "")[:500]
    return state


def _history_brief(history: list[dict[str, Any]]) -> list[dict[str, str]]:
    brief = []
    for item in (history or [])[-6:]:
        brief.append({
            "role": str(item.get("role") or ""),
            "content": str(item.get("content") or "")[:400],
            "intent": str(item.get("intent") or ""),
        })
    return brief


async def route_message_with_llm(rule_state: AgentState) -> AgentState:
    message = rule_state.get("message") or ""
    system_prompt = (
        "你是小升初数学题库系统的意图路由器。"
        "你只负责理解用户需求并选择工具，不执行数据库查询，不编造数据。"
        "必须只输出 JSON 对象。"
    )
    user_payload = {
        "message": message,
        "history": _history_brief(rule_state.get("history") or []),
        "allowed_intents": sorted(ALLOWED_INTENTS),
        "intent_meaning": {
            PRACTICE_GENERATE: "生成练习单、组卷、错题举一反三",
            LEARNING_DIAGNOSIS: "查看薄弱点、掌握情况、学情诊断",
            WRONG_QUESTION_REVIEW: "查看或分析最近错题",
            QUESTION_EXPLAIN: "讲解题目、生成答案解析",
            SIMILAR_QUESTION_RECOMMEND: "推荐同类题、相似题、举一反三题",
            SEMANTIC_QUESTION_SEARCH: "在题库中语义搜索题目",
            STUDY_PLAN: "制定学习计划、复习安排",
            STUDY_SUMMARY: "学习总结、阶段复盘",
            PARENT_REPORT: "家长周报/月报、孩子是否改善、陪练建议",
            SYSTEM_HELP: "询问系统功能或如何使用",
            SMALLTALK: "问候或闲聊",
            FALLBACK: "无法判断",
        },
        "required_output": {
            "intent": "one allowed intent",
            "confidence": "0-1 number",
            "tool_args": {
                "prompt": "for practice_generate",
                "recent_days": "for wrong_question_review",
                "question_id": "for question_explain/similar when explicit id exists",
                "question_text": "for question_explain when user gives a stem",
                "query": "for search/similar by description",
                "days": "for study_plan/study_summary/parent_report",
                "topic": "for system_help",
                "awaiting_question": "true when user says they will send the question later",
            },
            "reason": "short Chinese reason",
        },
    }
    content = await call_text_llm(
        [{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}],
        system_prompt=system_prompt,
        max_tokens=800,
        timeout=ROUTER_TIMEOUT_SECONDS,
        json_output=True,
    )
    return _sanitize_router_result(_extract_json_object(content), rule_state)


def _compact_tool_result(result: Dict[str, Any]) -> Dict[str, Any]:
    if not result:
        return {}
    compact: Dict[str, Any] = {}
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    compact["reply"] = str(result.get("reply") or "")[:800]
    compact["action_types"] = [item.get("type") for item in result.get("actions") or [] if isinstance(item, dict)]
    if "stats" in data:
        compact["stats"] = data.get("stats")
    if "wrong_focus" in data:
        compact["wrong_focus"] = data.get("wrong_focus")[:5]
    if "weak_points" in data:
        compact["weak_points"] = data.get("weak_points")[:5]
    if "items" in data:
        compact["items_count"] = len(data.get("items") or [])
    if "variants" in data:
        compact["variants_count"] = len(data.get("variants") or [])
    if "question" in data:
        question = data.get("question") or {}
        compact["question"] = {
            "knowledge_point": question.get("knowledge_point"),
            "question_type": question.get("question_type"),
            "has_answer": bool(question.get("answer")),
            "has_solution": bool(question.get("solution")),
        }
    return compact


async def polish_reply_with_llm(state: AgentState) -> str | None:
    if not state.get("intent") or state.get("intent") == FALLBACK:
        return None
    system_prompt = (
        "你是小升初数学学习助手的回复编辑器。"
        "事实必须来自工具结果，不得编造数字、题目或数据库内容。"
        "用中文，简洁自然，面向学生或家长。"
        "可以利用 history 中的最近对话保持上下文，例如用户刚刚说过的名字、上一轮提到的题目或偏好。"
        "如果工具结果中有 actions/card，回复只做说明和下一步引导，不重复长列表。"
    )
    payload = {
        "user_message": state.get("message") or "",
        "history": _history_brief(state.get("history") or []),
        "intent": state.get("intent"),
        "tool_name": state.get("tool_name") or "",
        "tool_result": _compact_tool_result(state.get("tool_result") or {}),
        "current_reply": state.get("reply") or "",
        "suggestions": state.get("suggestions") or [],
    }
    content = await call_text_llm(
        [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        system_prompt=system_prompt,
        max_tokens=500,
        timeout=RESPONSE_TIMEOUT_SECONDS,
        json_output=False,
    )
    reply = (content or "").strip()
    return reply[:1200] if reply else None
