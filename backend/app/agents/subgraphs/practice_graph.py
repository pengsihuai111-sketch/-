from __future__ import annotations

from sqlalchemy.orm import Session

from ..context import trace_node, trace_tool
from ..guardrails import safe_tool_args
from ..state import AgentState
from ..tools.practice_tools import generate_practice_preview_tool
from .common import run_linear_subgraph


async def practice_requirement_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "practice_requirement_node")
    args = dict(state.get("tool_args") or {})
    if "prompt" not in args:
        args["prompt"] = state.get("message") or ""
    state["tool_args"] = args
    return state


async def practice_source_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "practice_source_node")
    args = dict(state.get("tool_args") or {})
    resolved_questions = args.get("resolved_questions") or []
    if resolved_questions and not args.get("source_action"):
        args["source_action"] = {
            "type": "resolved_questions",
            "data": {"questions": resolved_questions},
        }
    state["tool_args"] = args
    return state


async def practice_tool_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "practice_tool_node")
    result = await generate_practice_preview_tool(int(state["user_id"]), safe_tool_args(state.get("tool_args")), db)
    state["tool_name"] = "generate_practice_preview_tool"
    state["tool_result"] = result
    state["reply"] = result.get("reply", "")
    state["actions"] = result.get("actions", [])
    state["suggestions"] = result.get("suggestions", [])
    trace_tool(state, node="practice_tool_node", tool_name="generate_practice_preview_tool")
    return state


async def practice_validate_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "practice_validate_node")
    for action in state.get("actions") or []:
        if action.get("type") == "show_practice_preview":
            data = action.get("data") or {}
            data.setdefault("validation_status", "preview_only")
            data.setdefault("validation_note", "这是预览草稿，用户确认后才会生成正式练习单。")
    return state


async def practice_preview_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "practice_preview_node")
    state["sub_intent"] = "practice_preview"
    return state


async def run_practice_subgraph(state: AgentState, db: Session) -> AgentState:
    return await run_linear_subgraph(
        state=state,
        db=db,
        graph_name="practice_subgraph",
        nodes=[
            ("practice_requirement_node", practice_requirement_node),
            ("practice_source_node", practice_source_node),
            ("practice_tool_node", practice_tool_node),
            ("practice_validate_node", practice_validate_node),
            ("practice_preview_node", practice_preview_node),
        ],
    )
