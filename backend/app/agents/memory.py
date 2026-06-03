import json
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models import AssistantMessage, AssistantMessageRole, AssistantSession, AssistantSessionStatus


def _compact_preview_data(data: Dict[str, Any]) -> Dict[str, Any]:
    variants = []
    for variant in data.get("variants") or []:
        questions = variant.get("selected_questions") or variant.get("questions") or []
        variants.append({
            "variant_id": variant.get("variant_id"),
            "sheet_name": variant.get("sheet_name"),
            "estimated_time": variant.get("estimated_time"),
            "question_ids": [item.get("question_id") for item in questions if item.get("question_id")],
            "question_count": len(questions),
        })
    return {
        "parsed_requirement": data.get("parsed_requirement") or {},
        "candidate_count": data.get("candidate_count", 0),
        "estimated_time": data.get("estimated_time", 0),
        "total_variants": data.get("total_variants", len(variants)),
        "variants": variants,
    }


def _compact_actions_for_storage(actions: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
    compacted: List[Dict[str, Any]] = []
    for action in actions or []:
        if action.get("type") == "show_practice_preview":
            compacted.append({
                "type": action.get("type"),
                "data": _compact_preview_data(action.get("data") or {}),
            })
        else:
            compacted.append(action)
    return compacted


def _compact_tool_result_for_storage(result: Dict[str, Any] | None) -> Dict[str, Any]:
    if not result:
        return {}
    compacted = dict(result)
    if "actions" in compacted:
        compacted["actions"] = _compact_actions_for_storage(compacted.get("actions") or [])
    if isinstance(compacted.get("data"), dict) and compacted.get("actions"):
        compacted["data"] = {"summary": "large payload omitted; see compacted actions"}
    return compacted


def _json_for_storage(value: Any, fallback: Any) -> str:
    text = json.dumps(value if value is not None else fallback, ensure_ascii=False)
    # MySQL TEXT is 65,535 bytes; keep a safe margin for utf8mb4.
    if len(text.encode("utf-8")) <= 60000:
        return text
    return json.dumps({"truncated": True, "summary": "payload too large for assistant message storage"}, ensure_ascii=False)


def ensure_session(db: Session, user_id: int, session_id: Optional[str], title_seed: str = "") -> AssistantSession:
    if session_id:
        existing = (
            db.query(AssistantSession)
            .filter(AssistantSession.session_id == session_id, AssistantSession.user_id == user_id)
            .first()
        )
        if existing:
            return existing

    title = (title_seed or "AI学习助手").strip().replace("\n", " ")[:40]
    session = AssistantSession(
        session_id=uuid.uuid4().hex,
        user_id=user_id,
        title=title or "AI学习助手",
        status=AssistantSessionStatus.active.value,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def save_message(
    db: Session,
    user_id: int,
    session_id: str,
    role: str,
    content: str = "",
    intent: str = "",
    tool_name: str = "",
    tool_args: Dict[str, Any] | None = None,
    tool_result: Dict[str, Any] | None = None,
    actions: List[Dict[str, Any]] | None = None,
    error_message: str = "",
) -> AssistantMessage:
    message = AssistantMessage(
        session_id=session_id,
        user_id=user_id,
        role=role,
        content=content,
        intent=intent or None,
        tool_name=tool_name or None,
        tool_args=_json_for_storage(tool_args or {}, {}),
        tool_result=_json_for_storage(_compact_tool_result_for_storage(tool_result), {}),
        actions=_json_for_storage(_compact_actions_for_storage(actions), []),
        error_message=error_message or None,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def get_recent_history(db: Session, user_id: int, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    rows = (
        db.query(AssistantMessage)
        .filter(AssistantMessage.user_id == user_id, AssistantMessage.session_id == session_id)
        .order_by(AssistantMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "role": row.role,
            "content": row.content or "",
            "intent": row.intent or "",
            "actions": parse_actions(row.actions),
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in reversed(rows)
    ]


def parse_actions(raw: str | None) -> List[Dict[str, Any]]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else []
    except Exception:
        return []
