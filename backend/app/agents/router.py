from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from .constants import (
    FALLBACK,
    LEARNING_DIAGNOSIS,
    PRACTICE_GENERATE,
    QUESTION_EXPLAIN,
    SEMANTIC_QUESTION_SEARCH,
    SIMILAR_QUESTION_RECOMMEND,
    SMALLTALK,
    PARENT_REPORT,
    STUDY_PLAN,
    STUDY_SUMMARY,
    SYSTEM_HELP,
    WRONG_QUESTION_REVIEW,
)
from .conversation_memory import extract_user_name, is_name_query
from .state import AgentState


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def _extract_question_id(text: str) -> Optional[int]:
    match = re.search(r"(?:第\s*)?(\d+)\s*(?:题|号题|#)", text)
    if match:
        return int(match.group(1))
    hash_match = re.search(r"#\s*(\d+)", text)
    return int(hash_match.group(1)) if hash_match else None


def _extract_recent_days(text: str) -> Optional[int]:
    match = re.search(r"(?:最近|近|过去)?\s*(\d{1,3})\s*天", text)
    if match:
        return max(1, min(365, int(match.group(1))))
    if "本周" in text or "这一周" in text or "这周" in text:
        return 7
    if "本月" in text or "这个月" in text:
        return 30
    return None


def _is_pending_question_request(text: str) -> bool:
    pending_words = ["发给你", "发你", "等下发", "稍后发", "一会发", "我把题目", "我把图", "拍给你"]
    generic_words = ["一道题", "某道题", "这道题"]
    has_math_signal = bool(re.search(r"\d+\s*[\+\-\*/÷×=]|[ABCD][\.．、]|求|证明|已知|若|方程|面积|周长", text))
    return _contains_any(text, pending_words) or (_contains_any(text, generic_words) and not has_math_signal and len(text) < 36)


def _last_assistant_action(history: list[dict[str, Any]], action_types: set[str] | None = None) -> Optional[dict[str, Any]]:
    for item in reversed(history or []):
        if item.get("role") != "assistant":
            continue
        for action in reversed(item.get("actions") or []):
            if not action_types or action.get("type") in action_types:
                return action
    return None


def _last_attachment_questions(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    action = _last_assistant_action(history, {"show_attachment_questions"})
    data = action.get("data") if action else {}
    questions = data.get("questions") if isinstance(data, dict) else []
    return questions if isinstance(questions, list) else []


def _extract_requested_ordinal(text: str) -> Optional[int]:
    compact = _compact(text)
    match = re.search(r"第\s*(\d{1,3})\s*题", compact)
    if match:
        return int(match.group(1))
    match = re.search(r"讲\s*(\d{1,3})\s*题", compact)
    return int(match.group(1)) if match else None


def _wants_all_questions(text: str) -> bool:
    compact = _compact(text)
    all_words = ["所有题", "全部题", "每道题", "每一题", "所有题目", "全部题目", "每道题目", "全都"]
    detail_words = ["解析", "答案", "解答", "讲解", "详细"]
    return _contains_any(compact, all_words) and _contains_any(compact, detail_words)


def _history_waiting_for_question(history: list[dict[str, Any]]) -> bool:
    for item in reversed(history[:-1] if history else []):
        if item.get("role") != "assistant":
            continue
        content = item.get("content") or ""
        return "题目内容发给我" in content or "要讲解的题目" in content or "直接粘贴题干" in content
    return False


def route_message(state: AgentState) -> AgentState:
    text = (state.get("message") or "").strip()
    compact = _compact(text)
    history = state.get("history") or []
    intent = FALLBACK
    args: Dict[str, Any] = {}

    practice_words = ["生成练习", "出题", "组卷", "练习单", "专项练习", "错题重练", "举一反三", "再生成"]
    weak_words = ["薄弱", "掌握", "学情", "诊断", "哪里差", "哪里弱", "最弱", "不会的知识点"]
    explain_words = ["讲解", "解释", "为什么", "解析", "怎么做", "不会做", "讲一下"]
    similar_words = ["相似题", "同类题", "类似题", "举一反三题", "推荐同类"]
    search_words = ["搜索题目", "查找题目", "找题", "搜题", "搜索", "查找"]
    plan_words = ["学习计划", "复习计划", "安排学习", "制定计划", "怎么复习", "复习安排", "学习安排"]
    summary_words = ["学习总结", "本周总结", "周总结", "月总结", "学习报告", "复习总结", "最近表现"]
    parent_report_words = ["家长报告", "家长视角", "周报", "月报", "孩子练了多少", "是否改善", "下周建议", "陪练建议", "家长怎么看"]
    help_words = ["怎么", "如何", "上传", "使用", "入口", "功能"]

    last_question_action = _last_assistant_action(history, {"show_question_explanation"})
    last_related_action = _last_assistant_action(history, {"show_similar_questions", "show_wrong_question_list"})
    last_preview_action = _last_assistant_action(history, {"show_practice_preview"})
    attachment_questions = _last_attachment_questions(history)
    is_waiting_question = _history_waiting_for_question(history)

    introduced_name = extract_user_name(text)
    if introduced_name:
        intent = SMALLTALK
        args = {"remembered_name": introduced_name}
    elif is_name_query(text):
        intent = SMALLTALK
        args = {"memory_query": "name"}
    elif attachment_questions and _contains_any(compact, ["讲", "讲解", "解析", "答案", "怎么做", "不会"]):
        intent = QUESTION_EXPLAIN
        if _wants_all_questions(text):
            args = {
                "source": "attachment",
                "attachment_questions": attachment_questions,
                "explain_all": True,
            }
        else:
            ordinal = _extract_requested_ordinal(text) or 1
            question = attachment_questions[ordinal - 1] if 0 < ordinal <= len(attachment_questions) else attachment_questions[0]
            args = {
                "question_text": question.get("question_text") or "",
                "source": "attachment",
                "attachment_question_no": question.get("question_no") or ordinal,
            }
    elif _contains_any(compact, ["用这些题", "就这些题", "按这些题", "用上面这些", "按这个生成", "就按这个生成"]) and last_related_action:
        intent = PRACTICE_GENERATE
        args = {
            "prompt": text,
            "source_action": last_related_action,
        }
    elif _contains_any(compact, ["简单一点", "更简单", "降低难度", "容易一点"]) and last_preview_action:
        intent = PRACTICE_GENERATE
        args = {
            "prompt": "基于上一版练习单，重新生成一版更简单、基础题更多、计算压力更小的练习单。",
            "difficulty_hint": "easier",
        }
    elif _contains_any(compact, ["难一点", "更难", "提高难度", "挑战一点"]) and last_preview_action:
        intent = PRACTICE_GENERATE
        args = {
            "prompt": "基于上一版练习单，重新生成一版更有挑战、综合性更强的练习单。",
            "difficulty_hint": "harder",
        }
    elif _contains_any(compact, ["再来", "再推荐", "换一批", "再找"]) and last_question_action:
        question = (last_question_action.get("data") or {}).get("question") or {}
        intent = SIMILAR_QUESTION_RECOMMEND
        if question.get("question_id"):
            args["question_id"] = question["question_id"]
        else:
            args["query"] = question.get("question_text") or text
    elif _contains_any(compact, practice_words):
        intent = PRACTICE_GENERATE
        args = {"prompt": text}
    elif _contains_any(compact, weak_words):
        intent = LEARNING_DIAGNOSIS
    elif "错题" in compact and _contains_any(compact, ["看", "查", "最近", "哪些", "列表", "回顾", "分析", "统计"]):
        intent = WRONG_QUESTION_REVIEW
        recent_days = _extract_recent_days(compact)
        if recent_days:
            args["recent_days"] = recent_days
    elif _contains_any(compact, explain_words):
        intent = QUESTION_EXPLAIN
        qid = _extract_question_id(compact)
        if qid:
            args["question_id"] = qid
        elif _is_pending_question_request(compact):
            args["awaiting_question"] = True
        else:
            args["question_text"] = text
    elif _contains_any(compact, similar_words):
        intent = SIMILAR_QUESTION_RECOMMEND
        qid = _extract_question_id(compact)
        if qid:
            args["question_id"] = qid
        elif last_question_action:
            question = (last_question_action.get("data") or {}).get("question") or {}
            if question.get("question_id"):
                args["question_id"] = question["question_id"]
            else:
                args["query"] = question.get("question_text") or text
        else:
            args["query"] = text
    elif _contains_any(compact, search_words):
        intent = SEMANTIC_QUESTION_SEARCH
        args["query"] = text
    elif _contains_any(compact, parent_report_words):
        intent = PARENT_REPORT
        if "月报" in compact or "本月" in compact or "这个月" in compact:
            args["days"] = 30
        else:
            days = _extract_recent_days(compact)
            args["days"] = days or 7
    elif _contains_any(compact, plan_words):
        intent = STUDY_PLAN
        days = _extract_recent_days(compact)
        if days:
            args["days"] = days
    elif _contains_any(compact, summary_words):
        intent = STUDY_SUMMARY
        days = _extract_recent_days(compact)
        if days:
            args["days"] = days
    elif is_waiting_question and len(compact) >= 6:
        intent = QUESTION_EXPLAIN
        args["question_text"] = text
    elif _contains_any(compact, help_words):
        intent = SYSTEM_HELP
        args = {"topic": text}
    elif _contains_any(compact, ["你好", "您好", "谢谢", "在吗"]):
        intent = SMALLTALK

    state["intent"] = intent
    state["confidence"] = 0.85 if intent != FALLBACK else 0.3
    state["tool_args"] = args
    return state


def route_message_llm_prompt(message: str, history: list[dict[str, Any]]) -> str:
    return json.dumps({"message": message, "history": history[-5:]}, ensure_ascii=False)
