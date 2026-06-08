import difflib
import os
import re
from datetime import date
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..agents.memory import ensure_session, parse_actions, save_message, update_session_context
from ..agents.rate_limit import assistant_chat_limiter
from ..agents.service import chat_with_assistant
from ..agents.context import clean_attachment_questions
from ..agents.tools.parent_tools import build_parent_report_tool
from ..database import get_db
from ..models import (
    AgentInvocationLog,
    AssistantMessage,
    AssistantMessageRole,
    AssistantSession,
    Question,
    UserKnowledgeMastery,
    UserWrongQuestion,
    VectorSyncJob,
)
from ..schemas import AssistantChatRequest, AssistantChatResponse, AssistantMessageOut, AssistantSessionOut
from ..utils.auth import get_current_user_id
from ..utils.deepseek import call_text_llm, generate_answer, recognize_questions
from ..utils.knowledge_classifier import normalize_question_metadata
from ..utils.pdf_processor import pdf_to_images
from ..utils.pdf_to_markdown import extract_questions_from_markdown, pdf_to_markdown
from ..vector.client import vector_status
from ..vector.indexer import sync_all_questions
from ..vector.search import semantic_search_questions, similar_questions
from ..vector.sync import process_pending_jobs

router = APIRouter(prefix="/api/assistant", tags=["AI学习助手"])


class AssistantWrongQuestionRequest(BaseModel):
    question_text: str = Field(..., min_length=1)
    answer: str = ""
    solution: str = ""
    question_type: str = "other"
    difficulty: str = "中等"
    knowledge_point: str = ""
    knowledge_category: str = ""
    exam_name: str = "AI助手识别"
    error_type: str = "其他"
    notes: str = ""


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _generate_assistant_q_id(knowledge_point: str, db: Session) -> str:
    base = re.sub(r"[\s\-]+", "_", knowledge_point or "AI识别")[:18]
    base = base or "AI识别"
    prefix = f"AI_{base}"
    existing = db.query(Question.q_id).filter(Question.q_id.like(f"{prefix}_%")).all()
    numbers = []
    for row in existing:
        match = re.search(r"_(\d+)$", row[0] or "")
        if match:
            numbers.append(int(match.group(1)))
    return f"{prefix}_{max(numbers, default=0) + 1:04d}"


def _find_existing_question(question_text: str, db: Session) -> Question | None:
    normalized = _normalize_text(question_text)
    if len(normalized) < 8:
        return None

    candidates = []
    seen_ids = set()
    for length in (80, 50, 30):
        keyword = normalized[:length]
        if len(keyword) < 8:
            continue
        rows = db.query(Question).filter(Question.question_text.contains(keyword)).limit(20).all()
        for row in rows:
            if row.question_id not in seen_ids:
                seen_ids.add(row.question_id)
                candidates.append(row)
        if candidates:
            break

    best_question = None
    best_score = 0.0
    for candidate in candidates:
        score = difflib.SequenceMatcher(None, normalized, _normalize_text(candidate.question_text or "")).ratio()
        if score > best_score:
            best_score = score
            best_question = candidate
    return best_question if best_score >= 0.88 else None


def _update_assistant_mastery(user_id: int, knowledge_point: str, db: Session) -> None:
    if not knowledge_point:
        return
    mastery = (
        db.query(UserKnowledgeMastery)
        .filter(
            UserKnowledgeMastery.user_id == user_id,
            UserKnowledgeMastery.knowledge_point == knowledge_point,
        )
        .first()
    )
    if not mastery:
        mastery = UserKnowledgeMastery(
            user_id=user_id,
            knowledge_point=knowledge_point,
            total_practiced=0,
            correct_count=0,
            mastery_rate=0,
            last_practiced_date=date.today(),
        )
        db.add(mastery)

    mastery.total_practiced = (mastery.total_practiced or 0) + 1
    mastery.mastery_rate = round(((mastery.correct_count or 0) / max(mastery.total_practiced or 1, 1)) * 100, 1)
    mastery.last_practiced_date = date.today()
    mastery.is_weak_point = (mastery.mastery_rate or 0) < 60


def _create_or_get_assistant_question(req: AssistantWrongQuestionRequest, db: Session) -> Question:
    payload = {
        "question_text": req.question_text,
        "answer": req.answer,
        "solution": req.solution,
        "question_type": req.question_type,
        "difficulty": req.difficulty,
        "knowledge_point": req.knowledge_point,
        "knowledge_category": req.knowledge_category,
    }
    normalize_question_metadata(payload)

    existing = _find_existing_question(payload["question_text"], db)
    if existing:
        return existing

    question = Question(
        q_id=_generate_assistant_q_id(payload.get("knowledge_point") or "AI识别", db),
        knowledge_point=payload.get("knowledge_point") or "综合应用",
        knowledge_category=payload.get("knowledge_category") or "其他",
        question_type=payload.get("question_type") or "other",
        difficulty=payload.get("difficulty") or "中等",
        question_text=payload["question_text"],
        answer=payload.get("answer") or "",
        solution=payload.get("solution") or "",
        has_image=False,
        source_exam=req.exam_name or "AI助手识别",
        grade_level="六年级",
        verification_status="ai_generated",
    )
    db.add(question)
    db.flush()
    return question


def _add_question_to_wrong_book(
    *,
    req: AssistantWrongQuestionRequest,
    user_id: int,
    db: Session,
) -> Dict[str, Any]:
    question = _create_or_get_assistant_question(req, db)
    existing = (
        db.query(UserWrongQuestion)
        .filter(
            UserWrongQuestion.user_id == user_id,
            UserWrongQuestion.question_id == question.question_id,
        )
        .first()
    )
    if existing:
        db.commit()
        return {
            "created": False,
            "already_exists": True,
            "record_id": existing.record_id,
            "question_id": question.question_id,
            "message": "这道题已经在错题本里了",
        }

    record = UserWrongQuestion(
        user_id=user_id,
        question_id=question.question_id,
        exam_name=req.exam_name or "AI助手识别",
        exam_date=date.today(),
        error_type=req.error_type or "其他",
        notes=req.notes or "由 AI 学习助手识别添加",
    )
    db.add(record)
    _update_assistant_mastery(user_id, question.knowledge_point, db)
    db.commit()
    db.refresh(record)
    return {
        "created": True,
        "already_exists": False,
        "record_id": record.record_id,
        "question_id": question.question_id,
        "message": "已添加到错题本",
    }


def _detect_attachment_type(file: UploadFile) -> str:
    content_type = (file.content_type or "").lower()
    filename = (file.filename or "").lower()
    if content_type.startswith("image/") or filename.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
        return "image"
    if content_type == "application/pdf" or filename.endswith(".pdf"):
        return "pdf"
    if filename.endswith((".md", ".markdown", ".txt")) or content_type in {
        "text/plain",
        "text/markdown",
        "text/x-markdown",
    }:
        return "markdown"
    return ""


def _decode_text_file(file_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=400, detail="文件编码无法识别，请使用 UTF-8 或 GB18030 编码")


def _looks_like_attachment_heading(
    text: str,
    answer: str = "",
    solution: str = "",
    question_type: str = "",
) -> bool:
    if answer.strip() or solution.strip():
        return False

    compact = re.sub(r"[\s#*_`]+", "", text or "")
    compact = compact.strip("-—:：.。")
    if not compact:
        return True

    heading_keywords = (
        "提取题目",
        "综合练习",
        "错题练习",
        "练习单",
        "学生卷",
        "答案卷",
        "试卷",
        "题目列表",
        "题目解析",
        "参考答案",
        "答案解析",
    )
    if len(compact) <= 60 and any(keyword in compact for keyword in heading_keywords):
        return True

    section_pattern = r"^[一二三四五六七八九十\d]+[、.．](选择题|填空题|判断题|解答题|应用题|计算题|操作题).*$"
    if re.match(section_pattern, compact):
        return True

    return False


def _normalize_questions_payload(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for index, question in enumerate(questions or [], start=1):
        text = str(question.get("question_text") or question.get("stem") or "").strip()
        if not text:
            continue
        answer = str(question.get("answer") or "").strip()
        solution = str(question.get("solution") or question.get("analysis") or "").strip()
        question_type = question.get("question_type") or "other"
        if _looks_like_attachment_heading(text, answer, solution, question_type):
            continue

        source_question_no = str(question.get("question_no") or index)
        item = {
            "question_no": str(len(normalized) + 1),
            "page_no": question.get("page_no") or 1,
            "question_text": text,
            "answer": answer,
            "solution": solution,
            "question_type": question_type,
            "difficulty": question.get("difficulty") or "中等",
            "knowledge_point": question.get("knowledge_point") or "",
            "knowledge_category": question.get("knowledge_category") or "",
            "confidence": question.get("confidence"),
        }
        if source_question_no != item["question_no"]:
            item["source_question_no"] = source_question_no
        normalized.append(item)
    return clean_attachment_questions(normalized)


async def _recognize_assistant_attachment(file_type: str, file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    if file_type == "image":
        result = await recognize_questions(file_bytes, filename)
        questions = result.get("questions", []) if isinstance(result, dict) else result
        return _normalize_questions_payload(questions)

    if file_type == "markdown":
        text = _decode_text_file(file_bytes).strip()
        if len(text) > 2 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="文本文件内容不能超过 2MB")
        questions = await extract_questions_from_markdown(text, call_text_llm)
        return _normalize_questions_payload(questions)

    if file_type == "pdf":
        try:
            markdown_text, _used_ocr = pdf_to_markdown(file_bytes, max_pages=20)
            questions = await extract_questions_from_markdown(markdown_text, call_text_llm)
            normalized = _normalize_questions_payload(questions)
            if normalized:
                return normalized
        except Exception:
            pass

        page_images = pdf_to_images(file_bytes)
        all_questions: List[Dict[str, Any]] = []
        for page_index, image_bytes in enumerate(page_images[:12], start=1):
            result = await recognize_questions(image_bytes, f"{filename or 'assistant_pdf'}_p{page_index}.jpg")
            questions = result.get("questions", []) if isinstance(result, dict) else result
            for question in questions:
                question["page_no"] = page_index
            all_questions.extend(questions)
        return _normalize_questions_payload(all_questions)

    raise HTTPException(status_code=400, detail="暂不支持这种附件类型")


def _wants_attachment_explanation(message: str) -> bool:
    compact = "".join(str(message or "").split())
    return any(
        word in compact
        for word in ("讲解", "解析", "讲一下", "讲一讲", "怎么做", "答案", "解题", "分析")
    )


def _mentions_specific_attachment_question(message: str) -> bool:
    compact = "".join(str(message or "").split())
    return bool(re.search(r"(第[一二三四五六七八九十\d]+题|[一二三四五六七八九十\d]+号题)", compact))


def _wants_all_attachment_explanations(message: str) -> bool:
    compact = "".join(str(message or "").split())
    if _mentions_specific_attachment_question(message):
        return False
    all_words = (
        "所有题",
        "全部题",
        "每道题",
        "每一题",
        "每个题",
        "每个题目",
        "每一道题",
        "每一个题",
        "每一个题目",
        "每题",
        "各题",
        "各个题",
        "逐题",
        "所有题目",
        "全部题目",
        "这些题",
        "这几题",
        "图片里的题",
        "图片里面的题",
        "图片里的题目",
        "图片里面的题目",
        "文件里的题",
        "文件里面的题",
        "文件里的题目",
        "文件里面的题目",
        "附件里的题",
        "附件里面的题",
        "里面的题目",
        "全都",
    )
    explain_words = ("讲解", "解析", "解答", "答案", "怎么做", "详细")
    return any(word in compact for word in all_words) and any(word in compact for word in explain_words)


def _wants_add_to_wrong_book(message: str) -> bool:
    compact = "".join(str(message or "").split())
    add_words = ("添加", "加入", "放到", "放进", "保存到", "收进")
    wrong_words = ("错题本", "错题里", "错题里面", "错题")
    return any(word in compact for word in add_words) and any(word in compact for word in wrong_words)


def _wants_add_all_to_wrong_book(message: str) -> bool:
    compact = "".join(str(message or "").split())
    if _mentions_specific_attachment_question(message):
        return False
    all_words = (
        "所有题",
        "全部题",
        "每道题",
        "每一题",
        "每个题",
        "每个题目",
        "每一道题",
        "每一个题",
        "每一个题目",
        "每题",
        "各题",
        "各个题",
        "逐题",
        "这些题",
        "这几题",
        "图片里的题",
        "图片里面的题",
        "图片里的题目",
        "图片里面的题目",
        "文件里的题",
        "文件里面的题",
        "文件里的题目",
        "文件里面的题目",
        "附件里的题",
        "附件里面的题",
        "里面的题目",
        "全部",
        "全都",
    )
    return _wants_add_to_wrong_book(message) and any(word in compact for word in all_words)


def _question_to_wrong_request(question: Dict[str, Any]) -> AssistantWrongQuestionRequest:
    return AssistantWrongQuestionRequest(
        question_text=str(question.get("question_text") or question.get("stem") or "").strip(),
        answer=str(question.get("answer") or "").strip(),
        solution=str(question.get("solution") or question.get("analysis") or "").strip(),
        question_type=str(question.get("question_type") or "other").strip() or "other",
        difficulty=str(question.get("difficulty") or "中等").strip() or "中等",
        knowledge_point=str(question.get("knowledge_point") or "").strip(),
        knowledge_category=str(question.get("knowledge_category") or "").strip(),
        exam_name="AI助手识别",
        error_type="其他",
        notes="由 AI 学习助手识别添加",
    )


async def _build_attachment_explanation_action(question: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(question)
    if enriched.get("question_text") and (not enriched.get("answer") or not enriched.get("solution")):
        result = await generate_answer(
            enriched.get("question_text", ""),
            enriched.get("question_type", ""),
            enriched.get("knowledge_point", ""),
        )
        enriched["answer"] = enriched.get("answer") or result.get("answer", "")
        enriched["solution"] = enriched.get("solution") or result.get("solution", "")

    solution = enriched.get("solution") or "这道题目前只有识别出的题干，解析还不够完整，可以把更清晰的原图发给我再试。"
    enriched["explain_sections"] = [
        {"title": "题意理解", "content": "先找清楚题目给出的已知条件，以及最终要求的量。"},
        {"title": "解题步骤", "content": solution},
        {"title": "易错提醒", "content": "注意不要只看最后问法，要把题目中的数量关系先列清楚。"},
    ]
    return {"type": "show_question_explanation", "data": {"question": enriched}}


async def _build_attachment_explanation_actions(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    import asyncio

    semaphore = asyncio.Semaphore(3)

    async def explain_one(question: Dict[str, Any]) -> Dict[str, Any]:
        async with semaphore:
            return await _build_attachment_explanation_action(question)

    return await asyncio.gather(*(explain_one(question) for question in questions))


def _build_attachment_reply(
    filename: str,
    file_type: str,
    questions: List[Dict[str, Any]],
    wants_explanation: bool = False,
    wants_all_explanations: bool = False,
) -> str:
    if not questions:
        return f"我已经收到 {filename}，但暂时没有从里面识别出明确题目。你可以换一张更清晰的图片，或把题目文字直接发给我。"
    type_label = {"image": "图片", "pdf": "PDF", "markdown": "文本文件"}.get(file_type, "文件")
    if wants_all_explanations:
        return (
            f"我已经识别并解答了这个{type_label}：{filename}，共找到 {len(questions)} 道题。"
            "下面按题目顺序展示每道题的答案和解析。"
        )
    if wants_explanation:
        return (
            f"我已经识别并讲解了这个{type_label}：{filename}，共找到 {len(questions)} 道题。"
            "下面先展示识别结果和第 1 题讲解；如果还有多道题，你可以继续说“讲第 2 题”。"
        )
    return (
        f"我已经识别了这个{type_label}：{filename}，共找到 {len(questions)} 道题。"
        "你可以继续说“讲第 1 题”“用这些题生成练习单”，或者让我帮你找同类题。"
    )


@router.post("/chat", response_model=AssistantChatResponse)
async def assistant_chat(
    req: AssistantChatRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    assistant_chat_limiter.check(f"user:{user_id}")
    return await chat_with_assistant(req, user_id, db)


@router.post("/wrong-question")
def add_assistant_wrong_question(
    req: AssistantWrongQuestionRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return _add_question_to_wrong_book(req=req, user_id=user_id, db=db)


@router.post("/upload", response_model=AssistantChatResponse)
async def assistant_upload(
    file: UploadFile = File(...),
    session_id: str | None = Form(None),
    message: str = Form(""),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    assistant_chat_limiter.check(f"user:{user_id}")
    file_type = _detect_attachment_type(file)
    if not file_type:
        raise HTTPException(status_code=400, detail="仅支持图片、PDF、Markdown 和 TXT 文件")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="上传文件为空")

    max_size = 50 * 1024 * 1024 if file_type == "pdf" else 20 * 1024 * 1024
    if len(file_bytes) > max_size:
        raise HTTPException(status_code=400, detail="上传文件过大")

    filename = os.path.basename(file.filename or "未命名文件")
    session = ensure_session(db, user_id, session_id, f"上传：{filename}")
    user_content = f"上传了文件：{filename}"
    if message.strip():
        user_content += f"\n附加说明：{message.strip()}"
    save_message(
        db,
        user_id=user_id,
        session_id=session.session_id,
        role=AssistantMessageRole.user.value,
        content=user_content,
    )

    questions = await _recognize_assistant_attachment(file_type, file_bytes, filename)
    wants_explanation = _wants_attachment_explanation(message)
    wants_all_explanations = _wants_all_attachment_explanations(message)
    wants_add_wrong = _wants_add_to_wrong_book(message)
    wants_add_all_wrong = _wants_add_all_to_wrong_book(message)
    reply = _build_attachment_reply(
        filename,
        file_type,
        questions,
        wants_explanation=wants_explanation,
        wants_all_explanations=wants_all_explanations,
    )
    actions = [{
        "type": "show_attachment_questions",
        "data": {
            "file_name": filename,
            "file_type": file_type,
            "question_count": len(questions),
            "questions": questions,
        },
    }]
    if wants_all_explanations and questions:
        explanation_actions = await _build_attachment_explanation_actions(questions)
        actions.extend(explanation_actions)
        for index, explanation_action in enumerate(explanation_actions):
            explained = explanation_action.get("data", {}).get("question", {})
            if index < len(questions):
                questions[index]["answer"] = explained.get("answer", questions[index].get("answer", ""))
                questions[index]["solution"] = explained.get("solution", questions[index].get("solution", ""))
        suggestions = ["用这些题生成练习单", "推荐同类题", "再讲简单一点"]
    elif wants_explanation and questions:
        explanation_action = await _build_attachment_explanation_action(questions[0])
        actions.append(explanation_action)
        explained = explanation_action.get("data", {}).get("question", {})
        questions[0]["answer"] = explained.get("answer", questions[0].get("answer", ""))
        questions[0]["solution"] = explained.get("solution", questions[0].get("solution", ""))
        suggestions = ["再讲简单一点", "推荐同类题", "用这些题生成练习单"]
    else:
        suggestions = ["讲第 1 题", "用这些题生成练习单", "推荐同类题"]

    if wants_add_wrong and questions:
        target_questions = questions if wants_add_all_wrong else questions[:1]
        added_count = 0
        existed_count = 0
        for question in target_questions:
            if not str(question.get("question_text") or "").strip():
                continue
            result = _add_question_to_wrong_book(
                req=_question_to_wrong_request(question),
                user_id=user_id,
                db=db,
            )
            question["wrong_book_result"] = result
            if result.get("created"):
                added_count += 1
            elif result.get("already_exists"):
                existed_count += 1

        if added_count or existed_count:
            reply += f" 已处理错题本：新增 {added_count} 道，已存在 {existed_count} 道。"
            suggestions = ["去错题管理查看", "用这道题生成举一反三", "推荐同类题"]

    update_session_context(
        db,
        user_id,
        session.session_id,
        {
            "recent_attachment": {
                "file_name": filename,
                "file_type": file_type,
                "question_count": len(questions),
                "questions": clean_attachment_questions(questions),
            },
            "last_intent": "attachment_recognition",
            "last_action_types": ["show_attachment_questions"],
        },
    )

    save_message(
        db,
        user_id=user_id,
        session_id=session.session_id,
        role=AssistantMessageRole.assistant.value,
        content=reply,
        intent="attachment_recognition",
        tool_name="assistant_upload",
        tool_args={"file_name": filename, "file_type": file_type},
        tool_result={"question_count": len(questions)},
        actions=actions,
    )

    return AssistantChatResponse(
        session_id=session.session_id,
        reply=reply,
        intent="attachment_recognition",
        actions=actions,
        suggestions=suggestions,
    )


@router.get("/sessions", response_model=List[AssistantSessionOut])
def list_assistant_sessions(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return (
        db.query(AssistantSession)
        .filter(AssistantSession.user_id == user_id)
        .order_by(AssistantSession.updated_at.desc())
        .limit(50)
        .all()
    )


@router.get("/sessions/{session_id}/messages", response_model=List[AssistantMessageOut])
def list_assistant_messages(
    session_id: str,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    session = (
        db.query(AssistantSession)
        .filter(AssistantSession.session_id == session_id, AssistantSession.user_id == user_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    rows = (
        db.query(AssistantMessage)
        .filter(AssistantMessage.session_id == session_id, AssistantMessage.user_id == user_id)
        .order_by(AssistantMessage.created_at.asc())
        .all()
    )
    result = []
    for row in rows:
        result.append(AssistantMessageOut(
            message_id=row.message_id,
            session_id=row.session_id,
            role=row.role,
            content=row.content,
            intent=row.intent,
            actions=parse_actions(row.actions),
            created_at=row.created_at,
        ))
    return result


@router.delete("/sessions/{session_id}")
def delete_assistant_session(
    session_id: str,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    session = (
        db.query(AssistantSession)
        .filter(AssistantSession.session_id == session_id, AssistantSession.user_id == user_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    db.delete(session)
    db.commit()
    return {"success": True}


@router.get("/vector/status")
def assistant_vector_status(user_id: int = Depends(get_current_user_id)):
    return vector_status()


@router.get("/parent/report")
def assistant_parent_report(
    days: int = Query(7, ge=1, le=90),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return build_parent_report_tool(user_id, {"days": days}, db)


@router.post("/vector/sync-questions")
async def assistant_sync_question_vectors(
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    try:
        return await sync_all_questions(db, limit=limit, offset=offset)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"向量同步不可用：{exc}")


@router.post("/vector/process-jobs")
async def assistant_process_vector_jobs(
    limit: int = Query(50, ge=1, le=200),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return await process_pending_jobs(db, limit=limit)


@router.get("/vector/jobs")
def assistant_vector_jobs(
    limit: int = Query(20, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(VectorSyncJob)
        .order_by(VectorSyncJob.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "job_id": row.job_id,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "action": row.action,
                "status": row.status,
                "error_message": row.error_message,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            for row in rows
        ]
    }


@router.get("/logs")
def assistant_invocation_logs(
    limit: int = Query(30, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(AgentInvocationLog)
        .filter(AgentInvocationLog.user_id == user_id)
        .order_by(AgentInvocationLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "log_id": row.log_id,
                "session_id": row.session_id,
                "message_preview": row.message_preview,
                "intent": row.intent,
                "tool_name": row.tool_name,
                "elapsed_ms": row.elapsed_ms,
                "success": bool(row.success),
                "error_message": row.error_message,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }


@router.get("/vector/search")
async def assistant_vector_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=30),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return {"items": await semantic_search_questions(db, q, limit=limit)}


@router.get("/vector/similar/{question_id}")
async def assistant_similar_questions(
    question_id: int,
    limit: int = Query(10, ge=1, le=30),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return {"items": await similar_questions(db, question_id, limit=limit)}
