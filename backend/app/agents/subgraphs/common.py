from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import List

from sqlalchemy.orm import Session

from ..context import trace_node
from ..state import AgentState

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover
    END = None
    StateGraph = None

SubgraphNode = Callable[[AgentState, Session], Awaitable[AgentState]]


async def run_linear_subgraph(
    *,
    state: AgentState,
    db: Session,
    graph_name: str,
    nodes: List[tuple[str, SubgraphNode]],
) -> AgentState:
    state["business_graph"] = graph_name
    trace_node(state, f"{graph_name}:start")

    if StateGraph is None:
        for _, node in nodes:
            state = await node(state, db)
        trace_node(state, f"{graph_name}:end")
        return state

    graph = StateGraph(AgentState)
    for node_name, node in nodes:
        async def wrapper(inner_state: AgentState, _node=node) -> AgentState:
            return await _node(inner_state, db)

        graph.add_node(node_name, wrapper)

    graph.set_entry_point(nodes[0][0])
    for (left, _), (right, _) in zip(nodes, nodes[1:]):
        graph.add_edge(left, right)
    graph.add_edge(nodes[-1][0], END)
    app = graph.compile()
    result = await app.ainvoke(state)
    trace_node(result, f"{graph_name}:end")
    return result
