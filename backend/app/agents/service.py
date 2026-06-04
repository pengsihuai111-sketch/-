import asyncio
import time

from sqlalchemy.orm import Session

from ..models import AgentInvocationLog, AssistantMessageRole
from ..schemas import AssistantChatRequest, AssistantChatResponse
from .graph import run_agent_graph
from .memory import ensure_session, get_recent_history, save_message
from .state import AgentState

AGENT_TIMEOUT_SECONDS = 75


async def chat_with_assistant(req: AssistantChatRequest, user_id: int, db: Session) -> AssistantChatResponse:
    started = time.perf_counter()
    session = ensure_session(db, user_id, req.session_id, req.message)
    save_message(
        db,
        user_id=user_id,
        session_id=session.session_id,
        role=AssistantMessageRole.user.value,
        content=req.message,
    )
    history = get_recent_history(db, user_id, session.session_id)
    initial_state: AgentState = {
        "user_id": user_id,
        "session_id": session.session_id,
        "message": req.message,
        "history": history,
        "actions": [],
        "suggestions": [],
    }
    try:
        final_state = await asyncio.wait_for(
            run_agent_graph(initial_state, db),
            timeout=AGENT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        final_state = {
            **initial_state,
            "intent": "timeout",
            "tool_name": "",
            "tool_args": {},
            "tool_result": {},
            "reply": "这次处理时间过长，系统已自动停止。你可以把需求拆小一点，或稍后重试。",
            "actions": [],
            "suggestions": ["生成家长周报", "查看最近错题", "制定 7 天学习计划"],
            "error": f"assistant request timeout after {AGENT_TIMEOUT_SECONDS}s",
        }
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    persisted_tool_result = final_state.get("tool_result") or {}
    if isinstance(persisted_tool_result, dict):
        persisted_tool_result = {
            **persisted_tool_result,
            "_agent_trace": {
                "business_graph": final_state.get("business_graph") or "",
                "sub_intent": final_state.get("sub_intent") or "",
                "node_trace": final_state.get("node_trace") or [],
                "tool_trace": final_state.get("tool_trace") or [],
                "plan_steps": final_state.get("plan_steps") or [],
                "resolved_target": final_state.get("resolved_target") or {},
            },
        }

    save_message(
        db,
        user_id=user_id,
        session_id=session.session_id,
        role=AssistantMessageRole.assistant.value,
        content=final_state.get("reply", ""),
        intent=final_state.get("intent", ""),
        tool_name=final_state.get("tool_name", ""),
        tool_args=final_state.get("tool_args") or {},
        tool_result=persisted_tool_result,
        actions=final_state.get("actions") or [],
        error_message=final_state.get("error") or "",
    )
    db.add(AgentInvocationLog(
        session_id=session.session_id,
        user_id=user_id,
        message_preview=(req.message or "")[:300],
        intent=final_state.get("intent", ""),
        tool_name=final_state.get("tool_name", ""),
        elapsed_ms=elapsed_ms,
        success=not bool(final_state.get("error")),
        error_message=final_state.get("error") or "",
    ))
    db.commit()
    return AssistantChatResponse(
        session_id=session.session_id,
        reply=final_state.get("reply", ""),
        intent=final_state.get("intent", "fallback"),
        actions=final_state.get("actions") or [],
        suggestions=final_state.get("suggestions") or [],
    )
