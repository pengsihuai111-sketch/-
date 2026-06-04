from __future__ import annotations

from sqlalchemy.orm import Session

from ..context import load_agent_context, resolve_context_references, trace_node, trace_tool
from ..llm import polish_reply_with_llm, route_message_with_llm
from ..planner import build_task_plan
from ..response import build_response
from ..router import route_message
from ..state import AgentState
from ..subgraphs.dispatcher import run_business_subgraph


async def load_context_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "load_context_node")
    return load_agent_context(state)


async def intent_router_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "intent_router_node")
    rule_state = route_message(state)
    if (rule_state.get("tool_args") or {}).get("source") == "attachment":
        rule_state["router_source"] = "rule_attachment"
        return rule_state
    try:
        return await route_message_with_llm(rule_state)
    except Exception as exc:
        rule_state["router_source"] = "rule_fallback"
        rule_state["llm_router_error"] = str(exc)[:500]
        trace_tool(rule_state, node="intent_router_node", status="fallback", detail=str(exc)[:200])
        return rule_state


async def context_resolver_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "context_resolver_node")
    return resolve_context_references(state)


async def task_planner_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "task_planner_node")
    return build_task_plan(state)


async def business_dispatch_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "business_dispatch_node")
    return await run_business_subgraph(state, db)


async def response_compose_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "response_compose_node")
    state = build_response(state)
    if state.get("error") or state.get("response_source") == "memory":
        return state
    try:
        polished = await polish_reply_with_llm(state)
        if polished:
            state["reply"] = polished
            state["response_source"] = "llm"
    except Exception as exc:
        state["response_source"] = "tool_fallback"
        state["llm_response_error"] = str(exc)[:500]
        trace_tool(state, node="response_compose_node", status="fallback", detail=str(exc)[:200])
    return state


async def memory_update_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "memory_update_node")
    updates = {
        "last_intent": state.get("intent") or "",
        "last_business_graph": state.get("business_graph") or "",
        "last_action_types": [action.get("type") for action in state.get("actions") or [] if isinstance(action, dict)],
    }
    if state.get("resolved_target"):
        updates["last_resolved_target"] = state["resolved_target"]
    state["memory_updates"] = updates
    return state
