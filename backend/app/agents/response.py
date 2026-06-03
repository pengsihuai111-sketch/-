from .constants import FALLBACK, SMALLTALK
from .conversation_memory import build_memory_reply
from .state import AgentState


def build_response(state: AgentState) -> AgentState:
    if state.get("reply"):
        return state

    if state.get("intent") == SMALLTALK:
        memory_reply = build_memory_reply(
            state.get("message") or "",
            state.get("history") or [],
            state.get("tool_args") or {},
        )
        if memory_reply:
            state["reply"] = memory_reply
            state["response_source"] = "memory"
            state["suggestions"] = ["帮我看看薄弱点", "生成一套错题练习", "制定 7 天学习计划"]
            return state
        state["reply"] = "我在的。你可以直接告诉我想练什么、哪里不会，或者让我帮你看最近错题。"
        state["suggestions"] = ["帮我看看薄弱点", "生成一套错题练习", "怎么上传错题"]
        return state

    if state.get("intent") == FALLBACK:
        state["reply"] = "我还没完全理解你的意思。你可以说：生成练习单、查看薄弱点、查看最近错题、讲解某道题，或询问系统怎么用。"
        state["suggestions"] = ["生成一套几何练习", "我最近哪里最薄弱", "帮我看看最近错题"]
        return state

    state["reply"] = "我已经处理完成。"
    state["suggestions"] = ["继续生成练习", "查看错题", "查看薄弱点"]
    return state
