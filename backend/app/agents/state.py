from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    user_id: int
    session_id: str
    message: str
    history: List[Dict[str, Any]]
    session_context: Dict[str, Any]
    context: Dict[str, Any]
    memory: Dict[str, Any]
    intent: str
    sub_intent: str
    confidence: float
    business_graph: str
    resolved_target: Dict[str, Any]
    selected_questions: List[Dict[str, Any]]
    diagnosis_data: Dict[str, Any]
    search_results: List[Dict[str, Any]]
    plan_steps: List[Dict[str, Any]]
    tool_name: str
    tool_args: Dict[str, Any]
    tool_result: Dict[str, Any]
    tool_trace: List[Dict[str, Any]]
    node_trace: List[str]
    memory_updates: Dict[str, Any]
    router_source: str
    response_source: str
    llm_router_reason: str
    llm_router_error: str
    llm_response_error: str
    reply: str
    actions: List[Dict[str, Any]]
    suggestions: List[str]
    error: Optional[str]
