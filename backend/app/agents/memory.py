import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models import AssistantMessage, AssistantMessageRole, AssistantSession, AssistantSessionStatus

SESSION_TYPE_BY_INTENT = {
    "attachment_recognition": "attachment",
    "practice_generate": "practice",
    "learning_diagnosis": "diagnosis",
    "wrong_question_review": "wrong_review",
    "wrong_question_add": "wrong_review",
    "question_explain": "explanation",
    "similar_question_recommend": "search",
    "semantic_question_search": "search",
    "study_plan": "study_plan",
    "study_summary": "study_summary",
    "parent_report": "parent_report",
}

SESSION_TYPE_LABELS = {
    "attachment": "文件识别",
    "practice": "练习生成",
    "diagnosis": "薄弱诊断",
    "wrong_review": "错题回顾",
    "explanation": "题目讲解",
    "search": "找题推荐",
    "study_plan": "学习计划",
    "study_summary": "学习总结",
    "parent_report": "家长报告",
    "chat": "普通对话",
}


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


def _compact_question_for_context(question: Dict[str, Any]) -> Dict[str, Any]:
    allowed_keys = (
        "question_no",
        "source_question_no",
        "question_text",
        "answer",
        "solution",
        "question_type",
        "knowledge_point",
        "knowledge_category",
        "difficulty",
        "page_no",
    )
    compacted = {key: question.get(key) for key in allowed_keys if question.get(key) not in (None, "")}
    return compacted


def _compact_context_for_storage(context: Dict[str, Any]) -> Dict[str, Any]:
    compacted = dict(context or {})
    attachment = compacted.get("recent_attachment")
    if isinstance(attachment, dict):
        attachment = dict(attachment)
        questions = attachment.get("questions")
        if isinstance(questions, list):
            attachment["questions"] = [
                _compact_question_for_context(item)
                for item in questions[:60]
                if isinstance(item, dict)
            ]
            attachment["question_count"] = attachment.get("question_count") or len(questions)
        compacted["recent_attachment"] = attachment
    resolved_target = compacted.get("last_resolved_target")
    if isinstance(resolved_target, dict):
        resolved_target = dict(resolved_target)
        questions = resolved_target.get("questions")
        if isinstance(questions, list):
            resolved_target["questions"] = [
                _compact_question_for_context(item)
                for item in questions[:60]
                if isinstance(item, dict)
            ]
            resolved_target["count"] = resolved_target.get("count") or len(questions)
        question = resolved_target.get("question")
        if isinstance(question, dict):
            resolved_target["question"] = _compact_question_for_context(question)
        compacted["last_resolved_target"] = resolved_target
    return compacted


def _is_generic_session_title(title: str | None) -> bool:
    value = (title or "").strip()
    return not value or value in {"AI学习助手", "AI 学习助手", "新的对话已经开始。告诉我你的学习目标，我们从这里继续。"}


def _build_session_meta(context: Dict[str, Any]) -> Dict[str, str]:
    intent = str(context.get("last_intent") or "")
    session_type = str(context.get("session_type") or "") or SESSION_TYPE_BY_INTENT.get(intent, "chat")
    title = ""
    summary = ""

    attachment = context.get("recent_attachment")
    if isinstance(attachment, dict) and attachment.get("file_name"):
        filename = str(attachment.get("file_name") or "上传文件")
        question_count = int(attachment.get("question_count") or len(attachment.get("questions") or []))
        type_label = {"image": "图片", "pdf": "PDF", "markdown": "Markdown", "text": "文本"}.get(
            str(attachment.get("file_type") or ""),
            "文件",
        )
        session_type = "attachment"
        title = f"{filename} 识别"[:100]
        summary = f"{type_label} · 已识别 {question_count} 道题"

    if not summary and intent:
        label = SESSION_TYPE_LABELS.get(session_type, "AI 对话")
        summary = label

    return {
        "session_type": session_type or "chat",
        "title": title,
        "summary": summary[:200],
    }


def _json_for_storage(value: Any, fallback: Any) -> str:
    text = json.dumps(value if value is not None else fallback, ensure_ascii=False)
    # MySQL TEXT is 65,535 bytes; keep a safe margin for utf8mb4.
    if len(text.encode("utf-8")) <= 60000:
        return text
    return json.dumps({"truncated": True, "summary": "payload too large for assistant message storage"}, ensure_ascii=False)


def parse_json_dict(raw: str | None) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def get_session_context(db: Session, user_id: int, session_id: str) -> Dict[str, Any]:
    session = (
        db.query(AssistantSession)
        .filter(AssistantSession.user_id == user_id, AssistantSession.session_id == session_id)
        .first()
    )
    return parse_json_dict(session.context_json if session else None)


def update_session_context(
    db: Session,
    user_id: int,
    session_id: str,
    updates: Dict[str, Any],
) -> Dict[str, Any]:
    session = (
        db.query(AssistantSession)
        .filter(AssistantSession.user_id == user_id, AssistantSession.session_id == session_id)
        .first()
    )
    if not session:
        return {}
    context = parse_json_dict(session.context_json)
    context.update(updates or {})
    compacted = _compact_context_for_storage(context)
    meta = _build_session_meta(compacted)
    session.context_json = _json_for_storage(compacted, {})
    session.session_type = str(updates.get("session_type") or meta.get("session_type") or session.session_type or "chat")
    session.summary = str(updates.get("summary") or meta.get("summary") or session.summary or "")[:200]
    if meta.get("title") and (_is_generic_session_title(session.title) or str(session.title or "").startswith("上传：")):
        session.title = meta["title"]
    session.updated_at = datetime.now()
    db.commit()
    return compacted


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
        session_type="chat",
        summary="新的 AI 学习对话",
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
    session = (
        db.query(AssistantSession)
        .filter(AssistantSession.user_id == user_id, AssistantSession.session_id == session_id)
        .first()
    )
    if session:
        session.updated_at = datetime.now()
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
