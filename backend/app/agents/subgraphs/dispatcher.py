from __future__ import annotations

from sqlalchemy.orm import Session

from ..context import trace_tool
from ..state import AgentState
from ..tools.dispatcher import dispatch_tool
from .chat_graph import run_chat_subgraph
from .diagnosis_graph import run_diagnosis_subgraph
from .practice_graph import run_practice_subgraph
from .question_graph import run_question_subgraph
from .search_graph import run_search_subgraph
from .wrong_graph import run_wrong_subgraph


async def run_business_subgraph(state: AgentState, db: Session) -> AgentState:
    graph_name = state.get("business_graph") or "legacy_subgraph"
    if graph_name == "question_subgraph":
        return await run_question_subgraph(state, db)
    if graph_name == "wrong_subgraph":
        return await run_wrong_subgraph(state, db)
    if graph_name == "practice_subgraph":
        return await run_practice_subgraph(state, db)
    if graph_name == "diagnosis_subgraph":
        return await run_diagnosis_subgraph(state, db)
    if graph_name == "search_subgraph":
        return await run_search_subgraph(state, db)
    if graph_name == "chat_subgraph":
        return await run_chat_subgraph(state, db)

    state = await dispatch_tool(state, db)
    state["business_graph"] = "legacy_subgraph"
    trace_tool(state, node="legacy_subgraph", tool_name=state.get("tool_name") or "dispatch_tool")
    return state
