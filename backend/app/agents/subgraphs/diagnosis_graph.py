from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from ..constants import LEARNING_DIAGNOSIS, PARENT_REPORT, STUDY_PLAN, STUDY_SUMMARY
from ..context import trace_node, trace_tool
from ..guardrails import safe_tool_args
from ..state import AgentState
from ..tools.diagnosis_tools import get_weak_points_tool
from ..tools.parent_tools import build_parent_report_tool
from ..tools.study_tools import build_study_plan_tool, build_study_summary_tool
from .common import run_linear_subgraph


def _safe_days(args: Dict[str, Any], default: int = 7) -> int:
    try:
        return max(1, min(90, int(args.get("days") or args.get("recent_days") or default)))
    except (TypeError, ValueError):
        return default


def _action_types(result: Dict[str, Any]) -> list[str]:
    return [action.get("type") for action in result.get("actions") or [] if isinstance(action, dict)]


async def diagnosis_collect_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "diagnosis_collect_node")
    args = dict(state.get("tool_args") or {})
    if state.get("intent") in {PARENT_REPORT, STUDY_PLAN, STUDY_SUMMARY}:
        args["days"] = _safe_days(args, default=7)
    state["tool_args"] = args
    state["diagnosis_data"] = {
        "scope": {
            "intent": state.get("intent") or "",
            "days": args.get("days") or args.get("recent_days"),
            "has_recent_wrong_context": bool((state.get("context") or {}).get("recent_wrong_questions")),
            "has_recent_practice_context": bool((state.get("context") or {}).get("recent_practice_preview")),
        }
    }
    return state


async def diagnosis_analyze_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "diagnosis_analyze_node")
    user_id = int(state["user_id"])
    args = safe_tool_args(state.get("tool_args"))
    intent = state.get("intent")

    if intent == LEARNING_DIAGNOSIS:
        result = get_weak_points_tool(user_id, args, db)
        tool_name = "get_weak_points_tool"
    elif intent == PARENT_REPORT:
        result = build_parent_report_tool(user_id, args, db)
        tool_name = "build_parent_report_tool"
    elif intent == STUDY_PLAN:
        result = build_study_plan_tool(user_id, args, db)
        tool_name = "build_study_plan_tool"
    elif intent == STUDY_SUMMARY:
        result = build_study_summary_tool(user_id, args, db)
        tool_name = "build_study_summary_tool"
    else:
        result = {
            "reply": "暂时没有匹配到学情分析任务。",
            "actions": [],
            "suggestions": ["查看薄弱点", "生成家长周报"],
            "data": {},
        }
        tool_name = "diagnosis_noop"

    state["tool_name"] = tool_name
    state["tool_result"] = result
    state["diagnosis_data"] = {
        **(state.get("diagnosis_data") or {}),
        "analysis": {
            "tool_name": tool_name,
            "action_types": _action_types(result),
            "has_data": bool(result.get("data") or result.get("actions")),
        },
    }
    trace_tool(state, node="diagnosis_analyze_node", tool_name=tool_name)
    return state


async def diagnosis_output_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "diagnosis_output_node")
    result = dict(state.get("tool_result") or {})
    meta = {
        "business_graph": "diagnosis_subgraph",
        "intent": state.get("intent") or "",
        "scope": (state.get("diagnosis_data") or {}).get("scope") or {},
        "analysis": (state.get("diagnosis_data") or {}).get("analysis") or {},
    }
    result.setdefault("data", {})
    if isinstance(result["data"], dict):
        result["data"].setdefault("diagnosis_meta", meta)
    state["tool_result"] = result
    state["reply"] = result.get("reply", "")
    state["actions"] = result.get("actions", [])
    state["suggestions"] = result.get("suggestions", [])
    return state


async def diagnosis_response_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "diagnosis_response_node")
    state["sub_intent"] = state.get("intent") or "diagnosis"
    return state


async def run_diagnosis_subgraph(state: AgentState, db: Session) -> AgentState:
    return await run_linear_subgraph(
        state=state,
        db=db,
        graph_name="diagnosis_subgraph",
        nodes=[
            ("diagnosis_collect_node", diagnosis_collect_node),
            ("diagnosis_analyze_node", diagnosis_analyze_node),
            ("diagnosis_output_node", diagnosis_output_node),
            ("diagnosis_response_node", diagnosis_response_node),
        ],
    )
