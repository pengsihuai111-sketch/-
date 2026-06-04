from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from ..constants import SEMANTIC_QUESTION_SEARCH, SIMILAR_QUESTION_RECOMMEND
from ..context import trace_node, trace_tool
from ..guardrails import safe_tool_args
from ..state import AgentState
from ..tools.vector_tools import semantic_search_tool, similar_questions_tool
from .common import run_linear_subgraph


def _extract_items(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    if isinstance(data.get("items"), list):
        return [item for item in data["items"] if isinstance(item, dict)]
    for action in result.get("actions") or []:
        action_data = action.get("data") if isinstance(action, dict) else {}
        if isinstance(action_data, dict) and isinstance(action_data.get("items"), list):
            return [item for item in action_data["items"] if isinstance(item, dict)]
    return []


def _dedupe_and_rank(items: List[Dict[str, Any]], limit: int = 8) -> List[Dict[str, Any]]:
    seen = set()
    deduped = []
    for item in sorted(items, key=lambda row: float(row.get("score") or 0), reverse=True):
        key = item.get("question_id") or item.get("q_id") or (item.get("question_text") or "")[:60]
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


async def search_query_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "search_query_node")
    args = dict(state.get("tool_args") or {})
    if not args.get("query") and not args.get("question_id"):
        recent_question = (state.get("context") or {}).get("recent_question") or {}
        args["query"] = recent_question.get("question_text") or state.get("message") or ""
    args["limit"] = max(1, min(20, int(args.get("limit") or 8)))
    state["tool_args"] = args
    return state


async def semantic_search_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "semantic_search_node")
    user_id = int(state["user_id"])
    args = safe_tool_args(state.get("tool_args"))
    if state.get("intent") == SIMILAR_QUESTION_RECOMMEND:
        result = await similar_questions_tool(user_id, args, db)
        tool_name = "similar_questions_tool"
    elif state.get("intent") == SEMANTIC_QUESTION_SEARCH:
        result = await semantic_search_tool(user_id, args, db)
        tool_name = "semantic_search_tool"
    else:
        result = {"reply": "暂时没有匹配到搜索任务。", "actions": [], "suggestions": ["搜索题目", "推荐同类题"], "data": {"items": []}}
        tool_name = "search_noop"

    items = _extract_items(result)
    state["tool_name"] = tool_name
    state["tool_result"] = result
    state["search_results"] = items
    trace_tool(state, node="semantic_search_node", tool_name=tool_name, detail={"raw_count": len(items)})
    return state


async def mysql_filter_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "mysql_filter_node")
    limit = int((state.get("tool_args") or {}).get("limit") or 8)
    state["search_results"] = _dedupe_and_rank(state.get("search_results") or [], limit=limit)
    trace_tool(state, node="mysql_filter_node", status="ok", detail={"filtered_count": len(state["search_results"])})
    return state


async def rerank_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "rerank_node")
    items = state.get("search_results") or []
    source_counter = Counter(str(item.get("source") or "unknown") for item in items)
    for index, item in enumerate(items, start=1):
        item["rank"] = index
    result = dict(state.get("tool_result") or {})
    result["data"] = {
        **(result.get("data") if isinstance(result.get("data"), dict) else {}),
        "items": items,
        "search_meta": {
            "business_graph": "search_subgraph",
            "query": (state.get("tool_args") or {}).get("query") or "",
            "question_id": (state.get("tool_args") or {}).get("question_id"),
            "source_counts": dict(source_counter),
            "result_count": len(items),
        },
    }
    result["actions"] = [{"type": "show_similar_questions", "data": {
        "items": items,
        "query": (state.get("tool_args") or {}).get("query") or "",
        "question_id": (state.get("tool_args") or {}).get("question_id"),
    }}]
    state["tool_result"] = result
    return state


async def search_response_node(state: AgentState, db: Session) -> AgentState:
    trace_node(state, "search_response_node")
    result = state.get("tool_result") or {}
    count = len(state.get("search_results") or [])
    if state.get("intent") == SIMILAR_QUESTION_RECOMMEND:
        reply = f"我找到了 {count} 道同类题，并按相似度和知识点匹配度排好了顺序。"
        suggestions = ["用这些题生成练习单", "再找更难一点", "再找简单一点"]
    else:
        reply = f"我按语义帮你找到了 {count} 道相关题，并做了去重和排序。"
        suggestions = ["换一批同类题", "用这些题生成练习单", "再缩小范围"]
    state["reply"] = result.get("reply") or reply
    state["actions"] = result.get("actions", [])
    state["suggestions"] = result.get("suggestions") or suggestions
    state["sub_intent"] = state.get("intent") or "search"
    return state


async def run_search_subgraph(state: AgentState, db: Session) -> AgentState:
    return await run_linear_subgraph(
        state=state,
        db=db,
        graph_name="search_subgraph",
        nodes=[
            ("search_query_node", search_query_node),
            ("semantic_search_node", semantic_search_node),
            ("mysql_filter_node", mysql_filter_node),
            ("rerank_node", rerank_node),
            ("search_response_node", search_response_node),
        ],
    )
