from __future__ import annotations

from typing import Any, Dict, List

from .constants import (
    FALLBACK,
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
    WRONG_QUESTION_ADD,
)
from .context import compact_text
from .state import AgentState


def _step(name: str, **kwargs: Any) -> Dict[str, Any]:
    item = {"step": name}
    item.update({key: value for key, value in kwargs.items() if value is not None})
    return item


def select_business_graph(intent: str) -> str:
    if intent == QUESTION_EXPLAIN:
        return "question_subgraph"
    if intent in {WRONG_QUESTION_REVIEW, WRONG_QUESTION_ADD}:
        return "wrong_subgraph"
    if intent == PRACTICE_GENERATE:
        return "practice_subgraph"
    if intent in {LEARNING_DIAGNOSIS, PARENT_REPORT, STUDY_PLAN, STUDY_SUMMARY}:
        return "diagnosis_subgraph"
    if intent in {SIMILAR_QUESTION_RECOMMEND, SEMANTIC_QUESTION_SEARCH}:
        return "search_subgraph"
    if intent in {SYSTEM_HELP, SMALLTALK, FALLBACK}:
        return "chat_subgraph"
    return "legacy_subgraph"


def build_task_plan(state: AgentState) -> AgentState:
    intent = state.get("intent") or FALLBACK
    message = state.get("message") or ""
    compact = compact_text(message)
    resolved = state.get("resolved_target") or {}
    steps: List[Dict[str, Any]]

    if intent == QUESTION_EXPLAIN:
        if resolved.get("mode") == "all" or (state.get("tool_args") or {}).get("explain_all"):
            steps = [
                _step("resolve_question_context", source=resolved.get("type")),
                _step("extract_questions"),
                _step("solve_questions", mode="batch"),
                _step("explain_questions", mode="batch"),
                _step("validate_question_outputs"),
                _step("compose_question_response"),
            ]
        else:
            steps = [
                _step("resolve_question_context", source=resolved.get("type")),
                _step("extract_question"),
                _step("solve_question"),
                _step("explain_question"),
                _step("validate_question_output"),
                _step("compose_question_response"),
            ]
    elif intent == WRONG_QUESTION_REVIEW:
        steps = [
            _step("load_wrong_question_scope", days=(state.get("tool_args") or {}).get("recent_days")),
            _step("query_wrong_questions"),
            _step("analyze_wrong_question_focus"),
            _step("compose_wrong_response"),
        ]
    elif intent == WRONG_QUESTION_ADD:
        target_count = (state.get("resolved_target") or {}).get("count")
        steps = [
            _step("resolve_wrong_question_source", count=target_count),
            _step("dedupe_question_bank"),
            _step("add_questions_to_wrong_book"),
            _step("compose_wrong_response"),
        ]
    elif intent == PRACTICE_GENERATE:
        source = "resolved_questions" if (state.get("tool_args") or {}).get("resolved_questions") else "natural_language"
        steps = [
            _step("parse_practice_requirement"),
            _step("resolve_practice_source", source=source),
            _step("select_or_generate_questions"),
            _step("validate_practice_preview"),
            _step("compose_practice_preview"),
        ]
    elif intent in {LEARNING_DIAGNOSIS, PARENT_REPORT, STUDY_PLAN, STUDY_SUMMARY}:
        steps = [
            _step("collect_learning_data"),
            _step("analyze_learning_status"),
            _step("build_parent_or_study_output"),
            _step("compose_diagnosis_response"),
        ]
    elif intent in {SIMILAR_QUESTION_RECOMMEND, SEMANTIC_QUESTION_SEARCH}:
        steps = [
            _step("build_search_query"),
            _step("semantic_search"),
            _step("mysql_filter"),
            _step("rerank_results"),
            _step("compose_search_response"),
        ]
    elif intent in {SMALLTALK, SYSTEM_HELP}:
        steps = [_step("build_direct_reply")]
    else:
        steps = [_step("clarify_user_intent")]

    if "错题" in compact and any(word in compact for word in ("加入", "添加", "放到", "保存到")):
        steps.insert(-1 if len(steps) > 1 else len(steps), _step("add_questions_to_wrong_book"))

    state["business_graph"] = select_business_graph(intent)
    state["plan_steps"] = steps
    return state
