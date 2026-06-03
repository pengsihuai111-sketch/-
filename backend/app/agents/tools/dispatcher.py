from typing import Awaitable, Callable

from sqlalchemy.orm import Session

from ..constants import (
    LEARNING_DIAGNOSIS,
    PRACTICE_GENERATE,
    QUESTION_EXPLAIN,
    SEMANTIC_QUESTION_SEARCH,
    SIMILAR_QUESTION_RECOMMEND,
    PARENT_REPORT,
    STUDY_PLAN,
    STUDY_SUMMARY,
    SYSTEM_HELP,
    WRONG_QUESTION_REVIEW,
)
from ..guardrails import safe_tool_args
from ..state import AgentState
from .diagnosis_tools import get_weak_points_tool
from .parent_tools import build_parent_report_tool
from .practice_tools import generate_practice_preview_tool
from .question_tools import explain_question_tool
from .study_tools import build_study_plan_tool, build_study_summary_tool
from .system_tools import get_system_help_tool
from .vector_tools import semantic_search_tool, similar_questions_tool
from .wrong_tools import get_recent_wrong_questions_tool


async def dispatch_tool(state: AgentState, db: Session) -> AgentState:
    intent = state.get("intent")
    args = safe_tool_args(state.get("tool_args"))
    user_id = int(state["user_id"])

    try:
        if intent == PRACTICE_GENERATE:
            result = await generate_practice_preview_tool(user_id, args, db)
            tool_name = "generate_practice_preview_tool"
        elif intent == LEARNING_DIAGNOSIS:
            result = get_weak_points_tool(user_id, args, db)
            tool_name = "get_weak_points_tool"
        elif intent == WRONG_QUESTION_REVIEW:
            result = get_recent_wrong_questions_tool(user_id, args, db)
            tool_name = "get_recent_wrong_questions_tool"
        elif intent == QUESTION_EXPLAIN:
            result = await explain_question_tool(user_id, args, db)
            tool_name = "explain_question_tool"
        elif intent == SIMILAR_QUESTION_RECOMMEND:
            result = await similar_questions_tool(user_id, args, db)
            tool_name = "similar_questions_tool"
        elif intent == SEMANTIC_QUESTION_SEARCH:
            result = await semantic_search_tool(user_id, args, db)
            tool_name = "semantic_search_tool"
        elif intent == PARENT_REPORT:
            result = build_parent_report_tool(user_id, args, db)
            tool_name = "build_parent_report_tool"
        elif intent == STUDY_PLAN:
            result = build_study_plan_tool(user_id, args, db)
            tool_name = "build_study_plan_tool"
        elif intent == STUDY_SUMMARY:
            result = build_study_summary_tool(user_id, args, db)
            tool_name = "build_study_summary_tool"
        elif intent == SYSTEM_HELP:
            result = get_system_help_tool(user_id, args, db)
            tool_name = "get_system_help_tool"
        else:
            return state

        state["tool_name"] = tool_name
        state["tool_result"] = result
        state["reply"] = result.get("reply", "")
        state["actions"] = result.get("actions", [])
        state["suggestions"] = result.get("suggestions", [])
    except Exception as exc:
        state["error"] = str(exc)
        state["reply"] = f"这次处理时遇到问题：{exc}"
        state["actions"] = []
        state["suggestions"] = ["换一种说法再试", "查看系统帮助"]
    return state
