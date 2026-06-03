from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    user_id: int
    session_id: str
    message: str
    history: List[Dict[str, Any]]
    intent: str
    confidence: float
    tool_name: str
    tool_args: Dict[str, Any]
    tool_result: Dict[str, Any]
    router_source: str
    response_source: str
    llm_router_reason: str
    llm_router_error: str
    llm_response_error: str
    reply: str
    actions: List[Dict[str, Any]]
    suggestions: List[str]
    error: Optional[str]
