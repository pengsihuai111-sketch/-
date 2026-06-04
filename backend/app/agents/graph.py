from sqlalchemy.orm import Session

from .nodes.main_nodes import (
    business_dispatch_node,
    context_resolver_node,
    intent_router_node,
    load_context_node,
    memory_update_node,
    response_compose_node,
    task_planner_node,
)
from .state import AgentState

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover - fallback keeps dev server usable before dependency install
    END = None
    StateGraph = None


MAIN_GRAPH_NODES = [
    ("load_context_node", load_context_node),
    ("intent_router_node", intent_router_node),
    ("context_resolver_node", context_resolver_node),
    ("task_planner_node", task_planner_node),
    ("business_dispatch_node", business_dispatch_node),
    ("response_compose_node", response_compose_node),
    ("memory_update_node", memory_update_node),
]


async def run_agent_graph(initial_state: AgentState, db: Session) -> AgentState:
    """Run the assistant main graph and route into business subgraphs."""
    if StateGraph is None:
        state = initial_state
        for _, node in MAIN_GRAPH_NODES:
            state = await node(state, db)
        return state

    graph = StateGraph(AgentState)
    for node_name, node in MAIN_GRAPH_NODES:
        async def wrapper(state: AgentState, _node=node) -> AgentState:
            return await _node(state, db)

        graph.add_node(node_name, wrapper)

    graph.set_entry_point(MAIN_GRAPH_NODES[0][0])
    for (left, _), (right, _) in zip(MAIN_GRAPH_NODES, MAIN_GRAPH_NODES[1:]):
        graph.add_edge(left, right)
    graph.add_edge(MAIN_GRAPH_NODES[-1][0], END)
    app = graph.compile()
    return await app.ainvoke(initial_state)
