from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

from .state import AgentState


QUESTION_ACTION_TYPES = {"show_question_explanation"}
ATTACHMENT_ACTION_TYPES = {"show_attachment_questions"}
PRACTICE_ACTION_TYPES = {"show_practice_preview"}
WRONG_ACTION_TYPES = {"show_wrong_question_list"}


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def trace_node(state: AgentState, node_name: str) -> None:
    state.setdefault("node_trace", []).append(node_name)


def trace_tool(state: AgentState, *, node: str, tool_name: str = "", status: str = "ok", detail: Any = None) -> None:
    item: Dict[str, Any] = {"node": node, "status": status}
    if tool_name:
        item["tool_name"] = tool_name
    if detail is not None:
        item["detail"] = detail
    state.setdefault("tool_trace", []).append(item)


def _iter_assistant_actions(history: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for item in reversed(list(history or [])):
        if item.get("role") != "assistant":
            continue
        for action in reversed(item.get("actions") or []):
            if isinstance(action, dict):
                yield action


def _first_action(history: List[Dict[str, Any]], action_types: set[str]) -> Dict[str, Any]:
    for action in _iter_assistant_actions(history):
        if action.get("type") in action_types:
            return action
    return {}


def _action_data(action: Dict[str, Any]) -> Dict[str, Any]:
    data = action.get("data") if isinstance(action, dict) else {}
    return data if isinstance(data, dict) else {}


def _questions_from_practice_preview(action: Dict[str, Any]) -> List[Dict[str, Any]]:
    data = _action_data(action)
    questions: List[Dict[str, Any]] = []
    for variant in data.get("variants") or []:
        for question in variant.get("selected_questions") or []:
            if isinstance(question, dict):
                questions.append(question)
    return questions


def _looks_like_attachment_heading_question(question: Dict[str, Any]) -> bool:
    text = str(question.get("question_text") or question.get("stem") or "").strip()
    answer = str(question.get("answer") or "").strip()
    solution = str(question.get("solution") or question.get("analysis") or "").strip()
    question_type = str(question.get("question_type") or "other")
    if answer or solution:
        return False

    compact = re.sub(r"[\s#*_`]+", "", text)
    compact = compact.strip("-—:：.。")
    if not compact:
        return True

    heading_keywords = (
        "提取题目",
        "综合练习",
        "错题练习",
        "练习单",
        "学生卷",
        "答案卷",
        "试卷",
        "题目列表",
        "题目解析",
        "参考答案",
        "答案解析",
    )
    if len(compact) <= 60 and any(keyword in compact for keyword in heading_keywords):
        return True

    section_pattern = r"^[一二三四五六七八九十\d]+[、.．](选择题|填空题|判断题|解答题|应用题|计算题|操作题).*$"
    if re.match(section_pattern, compact):
        return True

    return False


def clean_attachment_questions(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []
    for index, question in enumerate(questions or [], start=1):
        if not isinstance(question, dict) or _looks_like_attachment_heading_question(question):
            continue
        item = dict(question)
        source_question_no = str(item.get("question_no") or index)
        item["question_no"] = str(len(cleaned) + 1)
        if source_question_no != item["question_no"]:
            item.setdefault("source_question_no", source_question_no)
        cleaned.append(item)
    return cleaned


def load_agent_context(state: AgentState) -> AgentState:
    history = state.get("history") or []
    session_context = state.get("session_context") or {}
    attachment_action = _first_action(history, ATTACHMENT_ACTION_TYPES)
    question_action = _first_action(history, QUESTION_ACTION_TYPES)
    practice_action = _first_action(history, PRACTICE_ACTION_TYPES)
    wrong_action = _first_action(history, WRONG_ACTION_TYPES)

    attachment_data = _action_data(attachment_action)
    session_attachment = session_context.get("recent_attachment") if isinstance(session_context, dict) else {}
    if isinstance(session_attachment, dict) and session_attachment.get("questions"):
        attachment_data = session_attachment
    question_data = _action_data(question_action)
    practice_data = _action_data(practice_action)
    wrong_data = _action_data(wrong_action)

    context = {
        "recent_attachment": attachment_data,
        "recent_attachment_questions": clean_attachment_questions(attachment_data.get("questions") or []),
        "recent_question": question_data.get("question") or {},
        "recent_practice_preview": practice_data,
        "recent_practice_questions": _questions_from_practice_preview(practice_action),
        "recent_wrong_questions": wrong_data.get("wrong_questions") or [],
        "last_action_types": [action.get("type") for action in list(_iter_assistant_actions(history))[:8]],
        "session_memory": session_context,
    }
    state["context"] = context
    state["memory"] = {
        "has_recent_attachment": bool(context["recent_attachment_questions"]),
        "has_recent_question": bool(context["recent_question"]),
        "has_recent_practice": bool(context["recent_practice_preview"]),
        "has_recent_wrong_questions": bool(context["recent_wrong_questions"]),
    }
    return state


def requested_ordinal(message: str) -> int | None:
    compact = compact_text(message)
    zh_digits = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    match = re.search(r"第(\d{1,3})题", compact)
    if match:
        return int(match.group(1))
    match = re.search(r"第([一二两三四五六七八九十])题", compact)
    if match:
        return zh_digits.get(match.group(1))
    match = re.search(r"讲(\d{1,3})题", compact)
    if match:
        return int(match.group(1))
    return None


def wants_all_referenced_questions(message: str) -> bool:
    compact = compact_text(message)
    all_words = (
        "全部题",
        "所有题",
        "每道题",
        "每一题",
        "每个题",
        "每个题目",
        "每一道题",
        "每一个题",
        "每一个题目",
        "每题",
        "各题",
        "各个题",
        "逐题",
        "这些题",
        "这几题",
        "图片里的题",
        "图片里面的题",
        "文件里的题",
        "文件里面的题",
        "附件里的题",
        "附件里面的题",
        "里面的题目",
        "全都",
    )
    return any(word in compact for word in all_words)


def resolve_context_references(state: AgentState) -> AgentState:
    message = state.get("message") or ""
    context = state.get("context") or {}
    args = dict(state.get("tool_args") or {})
    target: Dict[str, Any] = {}

    attachment_questions = context.get("recent_attachment_questions") or []
    recent_question = context.get("recent_question") or {}
    recent_wrong_questions = context.get("recent_wrong_questions") or []

    if attachment_questions and wants_all_referenced_questions(message):
        target = {
            "type": "attachment_questions",
            "mode": "all",
            "questions": attachment_questions,
            "count": len(attachment_questions),
        }
    elif attachment_questions:
        ordinal = requested_ordinal(message)
        if ordinal:
            index = max(0, min(len(attachment_questions) - 1, ordinal - 1))
            target = {
                "type": "attachment_question",
                "mode": "single",
                "ordinal": ordinal,
                "question": attachment_questions[index],
            }
    elif recent_question and any(word in compact_text(message) for word in ("这题", "这道题", "刚才那题")):
        target = {"type": "recent_question", "mode": "single", "question": recent_question}
    elif recent_wrong_questions and wants_all_referenced_questions(message):
        target = {
            "type": "wrong_questions",
            "mode": "all",
            "questions": recent_wrong_questions,
            "count": len(recent_wrong_questions),
        }

    if target:
        state["resolved_target"] = target
        if state.get("intent") == "question_explain":
            if target.get("mode") == "all":
                args["source"] = target["type"]
                args["attachment_questions"] = target.get("questions") or []
                args["explain_all"] = True
            elif target.get("question"):
                question = target["question"]
                args["source"] = target["type"]
                args["question_text"] = question.get("question_text") or question.get("stem") or ""
                args["attachment_question_no"] = question.get("question_no") or target.get("ordinal")
        elif state.get("intent") == "practice_generate":
            if target.get("mode") == "all":
                args["resolved_questions"] = target.get("questions") or []
        elif state.get("intent") == "wrong_question_add":
            if target.get("mode") == "all":
                args["attachment_questions"] = target.get("questions") or []
                args["add_all"] = True
                args["source"] = target["type"]
            elif target.get("question"):
                question = target["question"]
                args["question_text"] = question.get("question_text") or question.get("stem") or ""
                args["source"] = target["type"]
        state["tool_args"] = args
    else:
        state["resolved_target"] = {}

    return state
