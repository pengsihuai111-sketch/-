from sqlalchemy.orm import Session

from .llm import polish_reply_with_llm, route_message_with_llm
from .response import build_response
from .router import route_message
from .state import AgentState
from .tools.dispatcher import dispatch_tool

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover - fallback keeps dev server usable before dependency install
    END = None
    StateGraph = None


async def run_agent_graph(initial_state: AgentState, db: Session) -> AgentState:
    """Run the assistant graph. Uses LangGraph when installed, otherwise same node order fallback."""
    if StateGraph is None:
        state = await _route_node(initial_state)
        state = await dispatch_tool(state, db)
        state = build_response(state)
        return await _response_node(state)

    async def router_node(state: AgentState) -> AgentState:
        return await _route_node(state)

    async def tool_node(state: AgentState) -> AgentState:
        return await dispatch_tool(state, db)

    async def response_node(state: AgentState) -> AgentState:
        state = build_response(state)
        return await _response_node(state)

    graph = StateGraph(AgentState)
    graph.add_node("router_node", router_node)
    graph.add_node("tool_node", tool_node)
    graph.add_node("response_node", response_node)
    graph.set_entry_point("router_node")
    graph.add_edge("router_node", "tool_node")
    graph.add_edge("tool_node", "response_node")
    graph.add_edge("response_node", END)
    app = graph.compile()
    return await app.ainvoke(initial_state)


async def _route_node(state: AgentState) -> AgentState:
    rule_state = route_message(state)
    if (rule_state.get("tool_args") or {}).get("source") == "attachment":
        rule_state["router_source"] = "rule_attachment"
        return rule_state
    try:
        return await route_message_with_llm(rule_state)
    except Exception as exc:
        rule_state["router_source"] = "rule_fallback"
        rule_state["llm_router_error"] = str(exc)[:500]
        return rule_state


async def _response_node(state: AgentState) -> AgentState:
    if state.get("error"):
        return state
    if state.get("response_source") == "memory":
        return state
    try:
        polished = await polish_reply_with_llm(state)
        if polished:
            state["reply"] = polished
            state["response_source"] = "llm"
    except Exception as exc:
        state["response_source"] = "tool_fallback"
        state["llm_response_error"] = str(exc)[:500]
    return state
