from __future__ import annotations

from sqlalchemy.orm import Session

from ..context import trace_node
from ..response import build_response
from ..state import AgentState
from .common import run_linear_subgraph


async def chat_reply_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "chat_reply_node")
    state = build_response(state)
    state["sub_intent"] = state.get("intent") or "chat"
    return state


async def run_chat_subgraph(state: AgentState, db: Session) -> AgentState:
    return await run_linear_subgraph(
        state=state,
        db=db,
        graph_name="chat_subgraph",
        nodes=[("chat_reply_node", chat_reply_node)],
    )
