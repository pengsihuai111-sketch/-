from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from ..context import trace_node, trace_tool
from ..state import AgentState
from ..tools.question_tools import _build_easy_mistakes
from ...models import Question
from ...utils.deepseek import generate_answer
from .common import run_linear_subgraph


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _question_from_dict(item: Dict[str, Any], *, fallback_no: int = 1) -> Dict[str, Any]:
    return {
        "question_id": item.get("question_id"),
        "question_no": str(item.get("question_no") or item.get("source_number") or fallback_no),
        "question_text": _clean_text(item.get("question_text") or item.get("stem")),
        "answer": _clean_text(item.get("answer")),
        "solution": _clean_text(item.get("solution") or item.get("analysis")),
        "knowledge_point": _clean_text(item.get("knowledge_point")),
        "question_type": _clean_text(item.get("question_type")),
        "difficulty": _clean_text(item.get("difficulty")),
        "source": _clean_text(item.get("source")),
    }


def _question_from_model(question: Question, *, fallback_no: int = 1) -> Dict[str, Any]:
    return {
        "question_id": question.question_id,
        "question_no": str(question.source_number or fallback_no),
        "question_text": question.question_text or "",
        "answer": question.answer or "",
        "solution": question.solution or "",
        "knowledge_point": question.knowledge_point or "",
        "question_type": question.question_type or "",
        "difficulty": question.difficulty or "",
        "source": "question_bank",
    }


def _build_explain_sections(question: Dict[str, Any]) -> List[Dict[str, str]]:
    mistakes = question.get("easy_mistakes") or _build_easy_mistakes(
        question.get("question_text") or "",
        question.get("question_type") or "",
        question.get("knowledge_point") or "",
    )
    return [
        {"title": "题意理解", "content": "先找清楚已知条件、要求的量，以及是否存在单位、比例或图形关系。"},
        {"title": "关键条件", "content": "把题干中的数量关系转化成算式、方程、表格或图形关系。"},
        {"title": "解题步骤", "content": question.get("solution") or "这道题目前没有详细解析，建议补充更完整题干后再生成。"},
        {"title": "易错提醒", "content": "；".join(mistakes)},
    ]


async def question_context_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "question_context_node")
    args = dict(state.get("tool_args") or {})
    resolved = state.get("resolved_target") or {}
    if resolved.get("mode") == "all" and resolved.get("questions"):
        args["attachment_questions"] = resolved["questions"]
        args["explain_all"] = True
        args["source"] = resolved.get("type") or "resolved_context"
    elif resolved.get("question") and not args.get("question_text"):
        question = resolved["question"]
        args["question_text"] = question.get("question_text") or question.get("stem") or ""
        args["attachment_question_no"] = question.get("question_no") or resolved.get("ordinal")
        args["source"] = resolved.get("type") or "resolved_context"
    state["tool_args"] = args
    return state


async def question_extract_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "question_extract_node")
    args = state.get("tool_args") or {}
    selected: List[Dict[str, Any]] = []

    if args.get("awaiting_question"):
        state["selected_questions"] = []
        state["sub_intent"] = "awaiting_question"
        return state

    attachment_questions = args.get("attachment_questions") or []
    if isinstance(attachment_questions, list) and attachment_questions:
        selected = [
            _question_from_dict(item, fallback_no=index + 1)
            for index, item in enumerate(attachment_questions)
            if isinstance(item, dict)
        ]
    elif args.get("question_id"):
        question = db.query(Question).filter(Question.question_id == int(args["question_id"])).first()
        if question:
            selected = [_question_from_model(question)]
    elif args.get("question_text"):
        selected = [_question_from_dict({
            "question_text": args.get("question_text"),
            "question_no": args.get("attachment_question_no") or 1,
        })]

    state["selected_questions"] = [item for item in selected if item.get("question_text")]
    trace_tool(state, node="question_extract_node", status="ok", detail={"count": len(state["selected_questions"])})
    return state


async def question_solve_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "question_solve_node")
    questions = state.get("selected_questions") or []
    if not questions:
        return state

    semaphore = asyncio.Semaphore(3)

    async def solve_one(question: Dict[str, Any]) -> Dict[str, Any]:
        if question.get("answer") and question.get("solution"):
            return question
        async with semaphore:
            result = await generate_answer(
                question.get("question_text") or "",
                question.get("question_type") or "",
                question.get("knowledge_point") or "",
            )
        solved = dict(question)
        solved["answer"] = solved.get("answer") or result.get("answer", "")
        solved["solution"] = solved.get("solution") or result.get("solution", "")
        return solved

    state["selected_questions"] = await asyncio.gather(*(solve_one(question) for question in questions))
    trace_tool(state, node="question_solve_node", tool_name="generate_answer", detail={"count": len(questions)})
    return state


async def question_explain_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "question_explain_node")
    actions = []
    for index, question in enumerate(state.get("selected_questions") or []):
        enriched = dict(question)
        enriched["question_no"] = enriched.get("question_no") or str(index + 1)
        enriched["easy_mistakes"] = _build_easy_mistakes(
            enriched.get("question_text") or "",
            enriched.get("question_type") or "",
            enriched.get("knowledge_point") or "",
        )
        enriched["explain_sections"] = _build_explain_sections(enriched)
        enriched["explain_order"] = index + 1
        actions.append({"type": "show_question_explanation", "data": {"question": enriched}})

    state["actions"] = actions
    state["tool_result"] = {
        "data": {
            "question_count": len(actions),
            "questions": [action["data"]["question"] for action in actions],
        },
        "actions": actions,
    }
    return state


async def question_validate_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "question_validate_node")
    actions = state.get("actions") or []
    seen_texts = set()
    for index, action in enumerate(actions):
        if action.get("type") != "show_question_explanation":
            continue
        question = ((action.get("data") or {}).get("question") or {})
        text_key = (question.get("question_text") or "")[:80]
        has_required = bool(question.get("question_text") and question.get("answer") and question.get("solution"))
        duplicate = text_key in seen_texts if text_key else False
        if text_key:
            seen_texts.add(text_key)
        question["validation_status"] = "ok" if has_required and not duplicate else "needs_user_review"
        question["validation_note"] = (
            "题目、答案和解析已按同一题序生成。"
            if question["validation_status"] == "ok"
            else "这道题的答案解析可能不完整或与其他题重复，建议人工确认。"
        )
        question["explain_order"] = index + 1
    return state


async def question_response_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "question_response_node")
    actions = state.get("actions") or []
    if state.get("sub_intent") == "awaiting_question":
        state["reply"] = "可以，把题目内容发给我就行。你可以直接粘贴题干，也可以上传图片。"
        state["suggestions"] = ["我直接粘贴题目", "上传题目图片", "先看最近错题"]
        state["tool_name"] = "question_context_waiting"
        return state
    if not actions:
        state["reply"] = "请把要讲解的题目发给我，或者告诉我题库里的题号。我会按“题意、关键条件、步骤、易错点”来讲。"
        state["suggestions"] = ["讲解第 1 题", "我粘贴一道题给你", "查看最近错题"]
        state["tool_name"] = "question_extract_node"
        return state

    count = len(actions)
    state["tool_name"] = "question_subgraph"
    state["sub_intent"] = "explain_attachment_questions" if count > 1 else "explain_question"
    state["reply"] = (
        f"我把这 {count} 道题分别整理成答案解析了。"
        if count > 1
        else "我按“题意、关键条件、步骤、易错点”整理好了这道题。"
    )
    state["suggestions"] = ["用这些题生成练习单", "推荐同类题", "再讲简单一点"]
    state["tool_result"]["reply"] = state["reply"]
    state["tool_result"]["suggestions"] = state["suggestions"]
    return state


async def run_question_subgraph(state: AgentState, db: Session) -> AgentState:
    return await run_linear_subgraph(
        state=state,
        db=db,
        graph_name="question_subgraph",
        nodes=[
            ("question_context_node", question_context_node),
            ("question_extract_node", question_extract_node),
            ("question_solve_node", question_solve_node),
            ("question_explain_node", question_explain_node),
            ("question_validate_node", question_validate_node),
            ("question_response_node", question_response_node),
        ],
    )
