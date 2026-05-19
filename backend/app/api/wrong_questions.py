import logging
import os
import uuid
import difflib
import json
import asyncio
import numpy as np
from io import BytesIO
from threading import Lock
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, timedelta
from PIL import Image
import fitz

from ..database import get_db, SessionLocal
from ..models import (
    UserWrongQuestion, Question, UserKnowledgeMastery, UserPracticeHistory,
    WrongQuestionRecognitionTask, WrongQuestionRecognitionBlock,
)
from ..schemas import (
    WrongQuestionCreate, WrongQuestionFeedback, QuestionOut,
    DiagnosisReport, MasteryDetail, ErrorTypeStat, WeakPointSuggestion,
    ErrorAnalysisReport, MasteryTrend,
    AnswerGenerateRequest, AnswerGenerateResponse,
    DupCheckRequest, DupCheckResponse,
    RecognizeAdvancedRequest, RecognizeAdvancedResponse,
    RecognitionPageOut, RecognitionBlockOut, AiResultOut, MatchedQuestionOut,
    ConfirmRecognitionRequest, ConfirmItem, RecognitionTaskOut,
)
from ..models import ErrorType
from ..utils.auth import get_current_user_id
from ..utils.deepseek import recognize_questions, generate_answer, analyze_page_structure, recognize_single_question, match_question_candidates, call_text_llm
from ..utils.recognition_config import RecognitionStrategy
from ..utils.pdf_processor import pdf_to_images
from ..utils.pdf_to_markdown import pdf_to_markdown, extract_questions_from_markdown
from ..utils.image_processing import (
    remove_red_marks, preprocess_for_ocr, detect_correction_marks,
    save_image, crop_bbox, ensure_dirs,
)
from ..config import IMAGE_DIR, UPLOAD_DIR

logger = logging.getLogger(__name__)


def convert_numpy_types(obj):
    """递归转换numpy类型为Python原生类型"""
    # 必须先检查numpy类型，因为numpy.bool_不是bool的子类
    if isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_numpy_types(item) for item in obj]
    return obj

router = APIRouter(prefix="/api/wrong-questions", tags=["错题管理"])


# ==================== Progress Tracking ====================

class ProgressStore:
    """Thread-safe in-memory progress store for recognition tasks."""

    def __init__(self):
        self._store: dict = {}
        self._lock = Lock()

    def init(self, task_id: int, total_pages: int):
        with self._lock:
            self._store[task_id] = {
                "status": "processing",
                "current_page": 0,
                "total_pages": total_pages,
                "questions_found": 0,
                "message": "准备开始识别...",
            }

    def update(self, task_id: int, **kwargs):
        with self._lock:
            if task_id in self._store:
                self._store[task_id].update(kwargs)

    def get(self, task_id: int) -> dict | None:
        with self._lock:
            return self._store.get(task_id)

    def remove(self, task_id: int):
        with self._lock:
            self._store.pop(task_id, None)


progress_store = ProgressStore()


# ===================== Dedup helpers =====================

import re as _re


def _normalize_text(t: str) -> str:
    """去除多余空白，便于比对"""
    return _re.sub(r'\s+', ' ', t or '').strip()


def _find_best_match(norm_text: str, db: Session):
    """在题库中查找最佳匹配，返回 (question, similarity)"""
    norm_text = _normalize_text(norm_text)
    if not norm_text or len(norm_text) < 8:
        return None, 0.0

    # 尝试多种长度作为 LIKE 关键词
    candidates = []
    seen_ids = set()
    for length in [30, 50, 20]:
        kw = norm_text[:length]
        if len(kw) < 8:
            continue
        qs = (
            db.query(Question)
            .filter(Question.question_text.contains(kw))
            .limit(15)
            .all()
        )
        for q in qs:
            if q.question_id not in seen_ids:
                seen_ids.add(q.question_id)
                candidates.append(q)
        if candidates:
            break

    # difflib 比对
    best_q = None
    best_sim = 0.0
    for q in candidates:
        sim = difflib.SequenceMatcher(
            None, norm_text, _normalize_text(q.question_text or "")
        ).ratio()
        if sim > best_sim:
            best_sim = sim
            best_q = q
    return best_q, best_sim


def _search_matches(question_text: str, db: Session, limit: int = 10):
    """搜索候选题供用户手动选择，按相似度排序"""
    norm_text = _normalize_text(question_text)
    if not norm_text:
        return []

    seen_ids = set()
    all_candidates = []
    for kw_len in [50, 30, 20]:
        kw = norm_text[:kw_len]
        if len(kw) < 8:
            continue
        qs = db.query(Question).filter(Question.question_text.contains(kw)).limit(limit).all()
        for q in qs:
            if q.question_id not in seen_ids:
                seen_ids.add(q.question_id)
                sim = difflib.SequenceMatcher(
                    None, norm_text, _normalize_text(q.question_text or "")
                ).ratio()
                if sim > 0.3:
                    all_candidates.append((sim, q))
        if all_candidates:
            break

    all_candidates.sort(key=lambda x: -x[0])
    return [QuestionOut.model_validate(q) for _, q in all_candidates]


@router.get("")
def list_wrong_questions(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
):
    total = (
        db.query(UserWrongQuestion)
        .filter(UserWrongQuestion.user_id == user_id)
        .count()
    )
    records = (
        db.query(UserWrongQuestion)
        .filter(UserWrongQuestion.user_id == user_id)
        .order_by(UserWrongQuestion.created_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    result = []
    for r in records:
        q = db.query(Question).filter(Question.question_id == r.question_id).first()

        # Try to get AI-generated answer and solution from recognition block
        ai_answer = None
        ai_solution = None
        if r.recognition_task_id:
            block = (
                db.query(WrongQuestionRecognitionBlock)
                .filter(
                    WrongQuestionRecognitionBlock.task_id == r.recognition_task_id,
                    WrongQuestionRecognitionBlock.matched_question_id == r.question_id
                )
                .first()
            )
            if block:
                ai_answer = block.ai_answer
                ai_solution = block.ai_solution

        created_date = r.created_date.isoformat() if r.created_date else None

        result.append({
            "record_id": r.record_id,
            "question_id": r.question_id,
            "created_date": created_date,
            "created_at": created_date,
            "createdDate": created_date,
            "exam_name": r.exam_name,
            "exam_date": r.exam_date.isoformat() if r.exam_date else None,
            "error_type": r.error_type if r.error_type else None,
            "redo_count": r.redo_count,
            "last_redo_date": r.last_redo_date.isoformat() if r.last_redo_date else None,
            "mastered": r.mastered,
            "notes": r.notes,
            "question": QuestionOut.model_validate(q) if q else None,
            "ai_answer": ai_answer,  # AI generated answer from recognition
            "ai_solution": ai_solution,  # AI generated solution from recognition
        })

    return {"wrong_questions": result, "total": total}


@router.post("")
def add_wrong_question(
    req: WrongQuestionCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    q = db.query(Question).filter(Question.question_id == req.question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")

    existing = (
        db.query(UserWrongQuestion)
        .filter(
            UserWrongQuestion.user_id == user_id,
            UserWrongQuestion.question_id == req.question_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="该题已在错题本中")

    record = UserWrongQuestion(
        user_id=user_id,
        question_id=req.question_id,
        exam_name=req.exam_name,
        exam_date=req.exam_date or date.today(),
        error_type=req.error_type,
        notes=req.notes,
    )
    db.add(record)

    # 更新知识点掌握度
    _update_mastery(user_id, q.knowledge_point, False, db)

    db.commit()


    return {"message": "已添加到错题本", "record_id": record.record_id}


# ===================== Batch processing helper =====================

async def _batch_generate_and_dedup(
    questions: list,
    db: Session,
    user_id: int,
    generate_missing_answers: bool = False,
) -> tuple:
    """补全已知答案 + 顺序查重，就地修改 questions。

    返回 (generated_answer, generated_solution, dedup_status, matched_question_id)。
    """
    # Phase 1: 可选并行生成答案。默认关闭，避免识别链路在视觉模型
    # 已经给出答案后又额外等待一轮文本模型。
    async def _gen(q):
        if not generate_missing_answers or not q.get("question_text", "").strip() or q.get("answer"):
            return None
        try:
            return await generate_answer(
                q["question_text"],
                q.get("question_type", ""),
                q.get("knowledge_point", ""),
            )
        except Exception:
            return None

    ans_results = await asyncio.gather(*[_gen(q) for q in questions])

    # Phase 2: 顺序查重（DB session 不能并发使用）
    generated_answer = questions[0].get("answer", "") if questions else ""
    generated_solution = questions[0].get("solution", "") if questions else ""
    dedup_status = "new"
    matched_question_id = None

    for qi, q in enumerate(questions):
        if not q.get("question_text", "").strip():
            continue

        ans_result = ans_results[qi]
        if ans_result:
            ai_answer = ans_result.get("answer", "")
            ai_solution = ans_result.get("solution", "")
            if ai_answer:
                q["answer"] = ai_answer
            if ai_solution:
                q["solution"] = ai_solution
            if qi == 0:
                generated_answer = ai_answer or q.get("answer", "")
                generated_solution = ai_solution or q.get("solution", "")

        # 查重
        best_q, best_sim = _find_best_match(q.get("question_text", ""), db)
        if best_q and best_sim > 0.78:
            q["_matched_question_id"] = best_q.question_id
            in_wrong = (
                db.query(UserWrongQuestion)
                .filter(
                    UserWrongQuestion.user_id == user_id,
                    UserWrongQuestion.question_id == best_q.question_id,
                )
                .first()
            )
            if qi == 0:
                matched_question_id = best_q.question_id
                dedup_status = "in_wrong" if in_wrong else "in_bank"
            if not q.get("answer"):
                q["answer"] = best_q.answer
            if not q.get("solution"):
                q["solution"] = best_q.solution

    return generated_answer, generated_solution, dedup_status, matched_question_id


def _needs_answer_backfill(question: Optional[Question]) -> bool:
    """Whether the question still needs AI answer/solution backfill."""
    if not question:
        return False
    if not (question.question_text or "").strip():
        return False
    return not (question.answer or "").strip() or not (question.solution or "").strip()


async def _backfill_question_answers_background(task_id: int, question_ids: List[int]):
    """Generate missing answer/solution after user confirms recognized questions."""
    if not question_ids:
        return

    db = SessionLocal()
    try:
        unique_ids = []
        seen = set()
        for question_id in question_ids:
            if question_id and question_id not in seen:
                seen.add(question_id)
                unique_ids.append(question_id)

        logger.info(
            "Starting async answer backfill for task %s: %s question(s)",
            task_id,
            len(unique_ids),
        )

        for question_id in unique_ids:
            question = (
                db.query(Question)
                .filter(Question.question_id == question_id)
                .first()
            )
            if not _needs_answer_backfill(question):
                continue

            try:
                result = await generate_answer(
                    question.question_text,
                    question.question_type or "",
                    question.knowledge_point or "",
                )
            except Exception as e:
                logger.warning(
                    "Async answer backfill failed for question %s: %s",
                    question_id,
                    e,
                )
                continue

            answer = (result or {}).get("answer", "").strip()
            solution = (result or {}).get("solution", "").strip()
            if not answer and not solution:
                continue

            changed = False
            if answer and not (question.answer or "").strip():
                question.answer = answer
                changed = True
            if solution and not (question.solution or "").strip():
                question.solution = solution
                changed = True

            blocks = (
                db.query(WrongQuestionRecognitionBlock)
                .filter(
                    WrongQuestionRecognitionBlock.task_id == task_id,
                    WrongQuestionRecognitionBlock.matched_question_id == question_id,
                )
                .all()
            )
            for block in blocks:
                if answer and not (block.ai_answer or "").strip():
                    block.ai_answer = answer
                    changed = True
                if solution and not (block.ai_solution or "").strip():
                    block.ai_solution = solution
                    changed = True

            if changed:
                db.commit()
                logger.info(
                    "Async answer backfill completed for question %s (task %s)",
                    question_id,
                    task_id,
                )

    except Exception as e:
        db.rollback()
        logger.error(
            "Async answer backfill task failed for recognition task %s: %s",
            task_id,
            e,
            exc_info=True,
        )
    finally:
        db.close()


def _parse_knowledge_points(raw_value) -> List[str]:
    """Parse stored knowledge points JSON/string into a clean list."""
    if not raw_value:
        return []
    if isinstance(raw_value, list):
        return [str(item).strip() for item in raw_value if str(item).strip()]
    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except (json.JSONDecodeError, TypeError):
            pass
        return [part.strip() for part in _re.split(r"[,，;；]", raw_value) if part.strip()]
    return []


def _parse_json_from_llm_text(content: str):
    """Extract JSON payload from raw LLM text."""
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        match = _re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                return None
    return None


def _chunk_items(items: list, chunk_size: int) -> List[list]:
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


async def _generate_answers_for_blocks_batch(items: List[dict]) -> dict:
    """Generate answers/solutions for multiple questions in a single LLM call."""
    if not items:
        return {}

    payload_items = []
    for item in items:
        payload_items.append({
            "block_id": item["block_id"],
            "question_text": item["question_text"],
            "question_type": item.get("question_type", ""),
            "knowledge_point": item.get("knowledge_point", ""),
        })

    prompt = (
        "请为下面这些小学数学题批量生成答案和解析。\n"
        "要求：\n"
        "1. 严格按输入中的每个 block_id 返回结果，不能遗漏，不能新增。\n"
        "2. answer 要简洁准确，包含单位；多小问请分点或分号区分。\n"
        "3. solution 用中文分步说明，适合家长和小学生复核。\n"
        "4. 如果题目依赖配图或条件不足无法确定，请如实写“需要结合原图判断”。\n"
        "5. 只输出 JSON，不要 markdown。\n\n"
        "输入：\n"
        f"{json.dumps(payload_items, ensure_ascii=False)}\n\n"
        "输出格式：\n"
        "{\n"
        '  "results": [\n'
        '    {"block_id": 1, "answer": "", "solution": ""}\n'
        "  ]\n"
        "}"
    )

    content = await call_text_llm(
        messages=[{"role": "user", "content": prompt}],
        system_prompt="你是一位资深小学数学老师。请输出严格 JSON，不要 markdown 包裹，不要解释性文字。",
        max_tokens=8192,
        timeout=120.0,
    )
    parsed = _parse_json_from_llm_text(content)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("results"), list):
        raise ValueError("批量答案生成返回格式无效")

    result_map = {}
    for row in parsed.get("results", []):
        if not isinstance(row, dict):
            continue
        block_id = row.get("block_id")
        if block_id in (None, ""):
            continue
        try:
            block_id = int(block_id)
        except (TypeError, ValueError):
            continue
        result_map[block_id] = {
            "answer": (row.get("answer") or "").strip(),
            "solution": (row.get("solution") or "").strip(),
        }
    return result_map


async def _generate_answers_for_blocks_batch_brief(items: List[dict]) -> dict:
    """Generate answers and short solutions for multiple questions in one LLM call."""
    if not items:
        return {}

    payload_items = []
    for item in items:
        payload_items.append({
            "block_id": item["block_id"],
            "question_text": item["question_text"],
            "question_type": item.get("question_type", ""),
            "knowledge_point": item.get("knowledge_point", ""),
        })

    prompt = (
        "请为下面这些小学数学题批量生成答案和简短解析。\n"
        "要求：\n"
        "1. 严格按输入中的每个 block_id 返回结果，不能遗漏，不能新增。\n"
        "2. answer 必须直接给最终答案，尽量简洁准确，包含单位；多小问请用分号分隔。\n"
        "3. solution 只写 1 到 3 句简短解析，突出关键思路，不要展开成长篇分步讲解。\n"
        "4. 如果题目依赖配图或条件不足无法确定，请在 answer 和 solution 中如实说明“需要结合原图判断”。\n"
        "5. 只输出 JSON，不要 markdown，不要额外解释。\n\n"
        "输入：\n"
        f"{json.dumps(payload_items, ensure_ascii=False)}\n\n"
        "输出格式：\n"
        "{\n"
        '  "results": [\n'
        '    {"block_id": 1, "answer": "", "solution": ""}\n'
        "  ]\n"
        "}"
    )

    content = await call_text_llm(
        messages=[{"role": "user", "content": prompt}],
        system_prompt="你是一位资深小学数学老师。输出严格 JSON。优先给出准确答案，并保持解析简短清晰。",
        max_tokens=4096,
        timeout=90.0,
    )
    parsed = _parse_json_from_llm_text(content)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("results"), list):
        raise ValueError("批量答案生成返回格式无效")

    result_map = {}
    for row in parsed.get("results", []):
        if not isinstance(row, dict):
            continue
        block_id = row.get("block_id")
        if block_id in (None, ""):
            continue
        try:
            block_id = int(block_id)
        except (TypeError, ValueError):
            continue
        result_map[block_id] = {
            "answer": (row.get("answer") or "").strip(),
            "solution": (row.get("solution") or "").strip(),
        }
    return result_map


async def _generate_answer_brief(question_text: str, question_type: str = "", knowledge_point: str = "") -> dict:
    """Generate one answer with a short explanation."""
    prompt = (
        "请为下面这道小学数学题生成最终答案和简短解析。\n"
        f"题目：{question_text}\n"
        f"题型：{question_type or '未知'}\n"
        f"知识点：{knowledge_point or '未知'}\n\n"
        "要求：\n"
        "1. answer 直接给最终答案，尽量简洁准确，包含单位。\n"
        "2. solution 只写 1 到 3 句简短解析，不要长篇分步展开。\n"
        "3. 如果依赖配图或条件不足无法确定，请如实说明“需要结合原图判断”。\n"
        "4. 只输出 JSON，不要 markdown。\n\n"
        "输出格式：\n"
        '{ "answer": "", "solution": "" }'
    )

    content = await call_text_llm(
        messages=[{"role": "user", "content": prompt}],
        system_prompt="你是一位资深小学数学老师。输出严格 JSON。优先给出准确答案，并保持解析简短清晰。",
        max_tokens=1024,
        timeout=60.0,
    )
    parsed = _parse_json_from_llm_text(content)
    if not isinstance(parsed, dict):
        return {"answer": "", "solution": ""}
    return {
        "answer": (parsed.get("answer") or "").strip(),
        "solution": (parsed.get("solution") or "").strip(),
    }


async def _generate_answers_for_blocks_batch_detailed(items: List[dict]) -> dict:
    """Generate answers and moderately detailed solutions for multiple questions."""
    if not items:
        return {}

    payload_items = []
    for item in items:
        payload_items.append({
            "block_id": item["block_id"],
            "question_text": item["question_text"],
            "question_type": item.get("question_type", ""),
            "knowledge_point": item.get("knowledge_point", ""),
        })

    prompt = (
        "请为下面这些小学数学题批量生成答案和较详细解析。\n"
        "要求：\n"
        "1. 严格按输入中的每个 block_id 返回结果，不能遗漏，不能新增。\n"
        "2. answer 直接给最终答案，尽量准确，包含单位；多小问请按顺序分号分隔。\n"
        "3. solution 要比简短解析更详细，建议写 3 到 6 句，说明关键步骤和思路，但不要写成特别冗长的大段文字。\n"
        "4. 如果题目依赖配图或条件不足无法确定，请在 answer 和 solution 中如实说明“需要结合原图判断”。\n"
        "5. 只输出 JSON，不要 markdown，不要额外解释。\n\n"
        "输入：\n"
        f"{json.dumps(payload_items, ensure_ascii=False)}\n\n"
        "输出格式：\n"
        "{\n"
        '  "results": [\n'
        '    {"block_id": 1, "answer": "", "solution": ""}\n'
        "  ]\n"
        "}"
    )

    content = await call_text_llm(
        messages=[{"role": "user", "content": prompt}],
        system_prompt="你是一位资深小学数学老师。输出严格 JSON。答案要准确，解析要清楚、完整但不过度冗长。",
        max_tokens=8192,
        timeout=120.0,
    )
    parsed = _parse_json_from_llm_text(content)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("results"), list):
        raise ValueError("批量详细答案生成返回格式无效")

    result_map = {}
    for row in parsed.get("results", []):
        if not isinstance(row, dict):
            continue
        block_id = row.get("block_id")
        if block_id in (None, ""):
            continue
        try:
            block_id = int(block_id)
        except (TypeError, ValueError):
            continue
        result_map[block_id] = {
            "answer": (row.get("answer") or "").strip(),
            "solution": (row.get("solution") or "").strip(),
        }
    return result_map


async def _populate_question_answers_before_confirm(questions: list, task_id: int) -> dict:
    """Fill answer/solution on recognition results before task enters need_confirm."""
    pending = []
    for index, q in enumerate(questions, 1):
        if not (q.get("question_text") or "").strip():
            continue
        if (q.get("answer") or "").strip() and (q.get("solution") or "").strip():
            continue
        pending.append({
            "block_id": index,
            "question_ref": q,
            "question_text": q.get("question_text", ""),
            "question_type": q.get("question_type", ""),
            "knowledge_point": q.get("knowledge_point", ""),
        })

    if not pending:
        return {"generated": 0, "failed": 0, "total": 0}

    generated = 0
    failed = 0
    for batch in _chunk_items(pending, 4):
        batch_result_map = {}
        try:
            batch_result_map = await _generate_answers_for_blocks_batch_detailed(batch)
        except Exception as e:
            logger.warning("Task %s detailed batch answer generation failed, fallback to single question mode: %s", task_id, e)

        for item in batch:
            result = batch_result_map.get(item["block_id"])
            if result is None:
                try:
                    result = await generate_answer(
                        item["question_text"],
                        item["question_type"],
                        item["knowledge_point"],
                    )
                except Exception as e:
                    failed += 1
                    logger.warning("Task %s answer generation failed for question %s: %s", task_id, item["block_id"], e)
                    continue

            answer = (result or {}).get("answer", "").strip()
            solution = (result or {}).get("solution", "").strip()
            if answer:
                item["question_ref"]["answer"] = answer
            if solution:
                item["question_ref"]["solution"] = solution
            if answer or solution:
                generated += 1
            else:
                failed += 1

    return {"generated": generated, "failed": failed, "total": len(pending)}


async def _generate_missing_block_answers(task_id: int, db: Session) -> dict:
    """Fill missing block answers for a recognition task before confirmation."""
    blocks = (
        db.query(WrongQuestionRecognitionBlock)
        .filter(WrongQuestionRecognitionBlock.task_id == task_id)
        .order_by(WrongQuestionRecognitionBlock.page_no, WrongQuestionRecognitionBlock.question_no)
        .all()
    )

    pending = []
    for block in blocks:
        if not (block.ai_question_text or "").strip():
            continue
        if (block.ai_answer or "").strip() and (block.ai_solution or "").strip():
            continue
        pending.append({
            "block_id": block.id,
            "question_text": block.ai_question_text or "",
            "question_type": block.ai_question_type or "",
            "knowledge_point": (_parse_knowledge_points(block.ai_knowledge_points) or [""])[0],
        })

    if not pending:
        return {"generated": 0, "failed": 0, "total": 0}

    block_map = {block.id: block for block in blocks}
    generated = 0
    failed = 0

    batches = _chunk_items(pending, 6)
    for batch in batches:
        batch_result_map = {}
        batch_failed_ids = set()
        try:
            batch_result_map = await _generate_answers_for_blocks_batch_brief(batch)
        except Exception as e:
            logger.warning("Batch answer generation failed, falling back to per-question mode: %s", e)
            batch_failed_ids = {item["block_id"] for item in batch}

        for item in batch:
            block_id = item["block_id"]
            result = batch_result_map.get(block_id)
            if result is None:
                try:
                    result = await _generate_answer_brief(
                        item["question_text"],
                        item["question_type"],
                        item["knowledge_point"],
                    )
                except Exception as e:
                    failed += 1
                    logger.warning("Prepare-confirmation answer generation failed for block %s: %s", block_id, e)
                    continue
            elif block_id in batch_failed_ids:
                failed += 1
                continue

            block = block_map.get(block_id)
            if not block:
                continue
            answer = (result or {}).get("answer", "").strip()
            solution = (result or {}).get("solution", "").strip()
            if answer and not (block.ai_answer or "").strip():
                block.ai_answer = answer
            if solution and not (block.ai_solution or "").strip():
                block.ai_solution = solution
            if answer or solution:
                generated += 1

    if generated:
        db.commit()
    else:
        db.rollback()

    return {"generated": generated, "failed": failed, "total": len(pending)}


def _extract_questions_from_recognition_result(result) -> list:
    """Normalize recognize_questions output to a list of question dicts."""
    if isinstance(result, dict):
        questions = result.get("questions", [])
    elif isinstance(result, list):
        questions = result
    else:
        questions = []
    return [q for q in questions if isinstance(q, dict) and q.get("question_text", "").strip()]


def _get_pdf_page_count(pdf_bytes: bytes, max_pages: int = 30) -> int:
    """Return PDF page count capped to the system processing limit."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        total = len(doc)
    finally:
        doc.close()
    if total <= 0:
        raise ValueError("PDF 文件为空")
    return min(total, max_pages) if max_pages > 0 else total


def _question_quality_score(q: dict) -> float:
    """Heuristic quality score used to decide whether a page needs vision fallback."""
    score = 0.0
    text = (q.get("question_text") or "").strip()
    answer = (q.get("answer") or "").strip()
    solution = (q.get("solution") or "").strip()
    extraction_only = q.get("_source") in {"markdown", "markdown_ocr", "vision"}
    confidence = q.get("confidence", 0.0)
    if isinstance(confidence, (int, float)):
        score += min(max(float(confidence), 0.0), 1.0) * 0.30

    if len(text) >= 40:
        score += 0.35
    elif len(text) >= 20:
        score += 0.28
    elif len(text) >= 8:
        score += 0.12
    if not extraction_only and answer:
        score += 0.10
    if not extraction_only and len(solution) >= 10:
        score += 0.10
    if q.get("knowledge_point"):
        score += 0.10
    if q.get("question_type"):
        score += 0.05
    if q.get("is_complete", True):
        score += 0.10

    uncertain_text = f"{text} {answer} {solution}"
    if any(token in uncertain_text for token in ["无法确定", "看不清", "不完整", "unclear", "未知"]):
        score -= 0.20
    return max(0.0, min(1.0, score))


def _normalize_pdf_question(q: dict, page_no: int = 1, index: int = 1, source: str = "") -> dict:
    """Normalize Markdown/Vision PDF question output to the block storage shape."""
    normalized = dict(q)
    try:
        normalized["page_no"] = int(normalized.get("page_no") or page_no or 1)
    except (TypeError, ValueError):
        normalized["page_no"] = page_no or 1
    normalized["question_no"] = str(normalized.get("question_no") or index)
    normalized["question_text"] = (normalized.get("question_text") or "").strip()
    normalized["answer"] = (normalized.get("answer") or "").strip()
    normalized["solution"] = (normalized.get("solution") or "").strip()
    normalized["question_type"] = normalized.get("question_type") or "other"
    normalized["difficulty"] = normalized.get("difficulty") or "中等"
    normalized["knowledge_point"] = normalized.get("knowledge_point") or "未知"
    normalized["knowledge_category"] = normalized.get("knowledge_category") or "其他"
    confidence = normalized.get("confidence", 0.8)
    if isinstance(confidence, (int, float)):
        confidence = float(confidence)
        normalized["confidence"] = confidence / 100 if confidence > 1 else confidence
    else:
        normalized["confidence"] = 0.8
    normalized["_source"] = source
    normalized["_quality_score"] = _question_quality_score(normalized)
    return normalized


def _page_quality(questions: list) -> float:
    if not questions:
        return 0.0
    return sum(q.get("_quality_score", _question_quality_score(q)) for q in questions) / len(questions)


def _split_markdown_by_page(markdown_text: str, total_pages: int) -> dict:
    """Split generated markdown into page-numbered chunks."""
    marker_re = _re.compile(r"---\s*\n\*\*第\s*(\d+)\s*页\*\*\s*\n---", _re.MULTILINE)
    matches = list(marker_re.finditer(markdown_text or ""))
    if not matches:
        return {1: markdown_text or ""}

    pages = {}
    for i, match in enumerate(matches):
        page_no = int(match.group(1))
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown_text)
        if 1 <= page_no <= total_pages:
            pages[page_no] = markdown_text[start:end]
    return pages


def _estimate_question_count_from_text(text: str) -> int:
    """Estimate question count from extracted page text to catch missed questions."""
    if not text:
        return 0
    patterns = [
        r"(?m)^\s*(?:\*\*)?\d{1,2}\s*[\.、．](?:\*\*)?\s*",
        r"(?m)^\s*(?:\*\*)?[一二三四五六七八九十]{1,3}\s*[、.．](?:\*\*)?\s*",
    ]
    starts = []
    for pattern in patterns:
        starts.extend(match.start() for match in _re.finditer(pattern, text))
    return len(set(starts))


def _questions_are_similar(a: dict, b: dict) -> bool:
    """Return True when two extracted blocks likely describe the same question."""
    no_a = str(a.get("question_no") or "").strip()
    no_b = str(b.get("question_no") or "").strip()
    if no_a and no_b and no_a == no_b:
        return True
    text_a = _normalize_text(a.get("question_text", ""))[:160]
    text_b = _normalize_text(b.get("question_text", ""))[:160]
    if len(text_a) < 12 or len(text_b) < 12:
        return False
    return difflib.SequenceMatcher(None, text_a, text_b).ratio() >= 0.72


def _better_pdf_question(a: dict, b: dict) -> dict:
    """Choose the stronger extraction, preserving answer/solution when useful."""
    score_a = a.get("_quality_score", _question_quality_score(a))
    score_b = b.get("_quality_score", _question_quality_score(b))
    best, other = (a, b) if score_a >= score_b else (b, a)
    merged = dict(best)
    for field in ["answer", "solution", "knowledge_point", "knowledge_category", "question_type", "difficulty"]:
        if not merged.get(field) and other.get(field):
            merged[field] = other[field]
    if other.get("image_urls") and not merged.get("image_urls"):
        merged["image_urls"] = other["image_urls"]
    merged["_quality_score"] = _question_quality_score(merged)
    return merged


def _merge_pdf_questions(markdown_questions: list, vision_by_page: dict) -> list:
    """Merge Markdown and vision results instead of replacing one with the other."""
    merged_by_page = {}
    for q in markdown_questions:
        merged_by_page.setdefault(int(q.get("page_no") or 1), []).append(q)

    for page_no, vision_questions in vision_by_page.items():
        page_questions = merged_by_page.setdefault(page_no, [])
        for vq in vision_questions:
            match_idx = next(
                (idx for idx, existing in enumerate(page_questions) if _questions_are_similar(existing, vq)),
                None,
            )
            if match_idx is None:
                page_questions.append(vq)
            else:
                page_questions[match_idx] = _better_pdf_question(page_questions[match_idx], vq)

    final_questions = []
    for page_no in sorted(merged_by_page):
        final_questions.extend(merged_by_page[page_no])
    final_questions.sort(key=lambda q: (int(q.get("page_no") or 1), str(q.get("question_no") or "")))
    return final_questions


def _pdf_pages_to_images(pdf_bytes: bytes, page_numbers: list, dpi: int = 200) -> dict:
    """Render only selected PDF pages to JPEG bytes for faster vision fallback."""
    page_set = sorted({int(p) for p in page_numbers if int(p) > 0})
    if not page_set:
        return {}

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        images = {}
        for page_no in page_set:
            if page_no > len(doc):
                continue
            page = doc[page_no - 1]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=90, optimize=False)
            images[page_no] = buf.getvalue()
            logger.info(
                f"Rendered PDF page {page_no}/{len(doc)} for vision fallback: "
                f"{pix.width}x{pix.height}, {len(images[page_no]) / 1024:.0f}KB"
            )
        return images
    finally:
        doc.close()


def _unique_question_no(page_no: int, question_no: str, seen: set) -> str:
    base = str(question_no or len(seen) + 1).strip()
    key = (page_no, base)
    if key not in seen:
        seen.add(key)
        return base
    suffix = 2
    while (page_no, f"{base}-{suffix}") in seen:
        suffix += 1
    unique = f"{base}-{suffix}"
    seen.add((page_no, unique))
    return unique


def _save_recognition_blocks(
    task_id: int,
    questions: list,
    db: Session,
    match_question_bank: bool = True,
) -> int:
    """Persist normalized recognition questions as confirmation blocks."""
    seen_question_numbers = set()
    saved_count = 0

    for i, q in enumerate(questions, 1):
        text = (q.get("question_text") or "").strip()
        if not text:
            continue

        page_no = int(q.get("page_no") or 1)
        question_no = _unique_question_no(page_no, q.get("question_no") or str(i), seen_question_numbers)
        matched_question_id = None
        match_confidence = 0

        if match_question_bank:
            best_q, best_sim = _find_best_match(text, db)
            if best_q and best_sim > 0.78:
                matched_question_id = best_q.question_id
                match_confidence = int(best_sim * 100)

        block = WrongQuestionRecognitionBlock(
            task_id=task_id,
            page_no=page_no,
            question_no=question_no,
            bbox=json.dumps([]),
            crop_image_url="",
            clean_crop_image_url="",
            question_image_urls=json.dumps(q.get("image_urls", []), ensure_ascii=False) if q.get("image_urls") else None,
            ai_question_text=text,
            ai_answer=q.get("answer", ""),
            ai_solution=q.get("solution", ""),
            ai_question_type=q.get("question_type", "other"),
            ai_knowledge_points=json.dumps([q.get("knowledge_point", "未知")], ensure_ascii=False),
            ai_difficulty=q.get("difficulty", "中等"),
            ai_keywords=json.dumps([q.get("_source", "")], ensure_ascii=False),
            ai_confidence=int(q.get("confidence", 0.8) * 100) if isinstance(q.get("confidence"), (int, float)) else 80,
            matched_question_id=matched_question_id,
            match_confidence=match_confidence,
            status="need_confirm",
        )
        db.add(block)
        saved_count += 1

    return saved_count


@router.post("/recognize")
async def recognize_wrong_question_image(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """上传错题图片或PDF，通过 AI 识别题目内容，并搜索题库中可能的匹配"""
    print(f"========== 收到错题识别请求 ==========")
    print(f"文件名: {file.filename}")
    print(f"Content-Type: {file.content_type}")
    print(f"用户ID: {user_id}")
    logger.info(f"Wrong question recognize: file={file.filename}, content_type={file.content_type}")

    is_pdf = file.content_type == "application/pdf" or (
        file.content_type == "application/octet-stream" and file.filename and file.filename.lower().endswith(".pdf")
    )

    if not is_pdf and (not file.content_type or not file.content_type.startswith("image/")):
        raise HTTPException(status_code=400, detail="仅支持图片和PDF文件")

    image_bytes = await file.read()

    if is_pdf:
        if len(image_bytes) > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="PDF 大小不能超过 50MB")
        try:
            page_images = pdf_to_images(image_bytes)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF 处理失败: {str(e)}")

        total_pages = len(page_images)
        if total_pages == 0:
            raise HTTPException(status_code=400, detail="PDF 中没有页面")

        # Process each page
        all_questions = []
        page_results = []
        all_warnings = []
        any_enhanced = False

        for page_num, img_bytes in enumerate(page_images):
            try:
                result = await recognize_questions(
                    img_bytes,
                    f"page_{page_num + 1}.jpg",
                    strategy=RecognitionStrategy.SINGLE_STAGE,
                )
                questions = _extract_questions_from_recognition_result(result)
                warnings = result.get("warnings", [])
                enhanced = result.get("enhanced", False)

                all_questions.extend(questions)
                page_results.append({"page": page_num + 1, "status": "ok", "count": len(questions)})

                if warnings:
                    all_warnings.extend([f"第{page_num + 1}页: {w}" for w in warnings])
                if enhanced:
                    any_enhanced = True

            except ValueError as e:
                page_results.append({"page": page_num + 1, "status": "error", "error": str(e)[:200]})
            except RuntimeError as e:
                raise HTTPException(status_code=502, detail=f"AI 服务调用失败 (第{page_num+1}页): {str(e)}")

        if not all_questions:
            raise HTTPException(status_code=400, detail="AI 未能从PDF中识别出题目")

        # Filter out empty questions
        all_questions = [q for q in all_questions if q.get("question_text", "").strip()]
        if not all_questions:
            raise HTTPException(status_code=400, detail="AI 未能从PDF中识别出有效题目文本，请确保图片清晰")

        # Save first page image for reference
        os.makedirs(IMAGE_DIR, exist_ok=True)
        saved_name = f"wrong_{uuid.uuid4().hex[:8]}.jpg"
        with open(os.path.join(IMAGE_DIR, saved_name), "wb") as f:
            f.write(page_images[0])

        # Search matches for the first recognized question
        first_q = all_questions[0]
        matches = _search_matches(first_q.get("question_text", ""), db) if first_q.get("question_text") else []

        # 并行生成答案 + 顺序查重
        generated_answer, generated_solution, dedup_status, matched_question_id = (
            await _batch_generate_and_dedup(all_questions, db, user_id)
        )

        result = {
            "recognized": first_q,
            "matches": matches,
            "match_count": len(matches),
            "questions": all_questions,
            "total_pages": total_pages,
            "page_results": page_results,
            "image_url": f"/uploads/images/{saved_name}",
            "generated_answer": generated_answer,
            "generated_solution": generated_solution,
            "dedup_status": dedup_status,
            "matched_question_id": matched_question_id,
            "warnings": all_warnings,
            "enhanced": any_enhanced,
        }
        return JSONResponse(content=convert_numpy_types(result))
    else:
        if len(image_bytes) > 20 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="图片大小不能超过 20MB")

        # Save image
        os.makedirs(IMAGE_DIR, exist_ok=True)
        ext = os.path.splitext(file.filename or "image.png")[1] or ".png"
        saved_name = f"wrong_{uuid.uuid4().hex[:8]}{ext}"
        saved_path = os.path.join(IMAGE_DIR, saved_name)
        with open(saved_path, "wb") as f:
            f.write(image_bytes)

        # Call AI API
        try:
            logger.info(f"开始调用 AI 识别，图片大小: {len(image_bytes)} bytes")
            result = await recognize_questions(
                image_bytes,
                file.filename or "",
                strategy=RecognitionStrategy.SINGLE_STAGE,
            )
            logger.info(f"AI 识别完成，结果: {result.keys() if result else 'None'}")
            questions = _extract_questions_from_recognition_result(result)
            quality_info = result.get("quality_info", {})
            warnings = result.get("warnings", [])
            enhanced = result.get("enhanced", False)

            if not questions:
                raise ValueError("AI 未能从图片中识别出题目")
            recognized = questions[0]
            # Validate recognized text is not empty
            if not recognized.get("question_text", "").strip():
                raise ValueError("AI 未能从图片中识别出有效题目文本，请确保图片清晰且包含完整的题目")
        except ValueError as e:
            logger.error(f"识别验证失败: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            logger.error(f"AI 服务调用失败: {e}")
            raise HTTPException(status_code=502, detail=f"AI 服务调用失败: {str(e)}")
        except Exception as e:
            logger.error(f"Recognition error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"识别失败: {str(e)}")

        # Search for potential matches in the question bank (for manual selection)
        matches = _search_matches(recognized.get("question_text", ""), db) if recognized.get("question_text") else []

        # 并行生成答案 + 顺序查重
        generated_answer, generated_solution, dedup_status, matched_question_id = (
            await _batch_generate_and_dedup(questions, db, user_id)
        )

        result = {
            "recognized": recognized,
            "matches": matches,
            "match_count": len(matches),
            "questions": questions,
            "image_url": f"/uploads/images/{saved_name}",
            "generated_answer": generated_answer,
            "generated_solution": generated_solution,
            "dedup_status": dedup_status,
            "matched_question_id": matched_question_id,
            "quality_info": quality_info,
            "warnings": warnings,
            "enhanced": enhanced,
        }
        return JSONResponse(content=convert_numpy_types(result))


# ===================== Advanced Recognition Endpoints =====================


@router.post("/recognize-advanced")
async def recognize_advanced(
    file: UploadFile = File(...),
    recognition_mode: str = Form("auto"),
    remove_correction_marks: bool = Form(True),
    segment_questions: bool = Form(True),
    match_question_bank: bool = Form(True),
    exam_name: Optional[str] = Form(None),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """高级错题识别 — 支持带批改痕迹的试卷图片。

    流程:
    1. 保存原图
    2. PDF 转图片
    3. 图片预处理（旋转/去阴影/增强）
    4. 检测批改痕迹
    5. 去除红色批改痕迹
    6. AI 分析页面结构（找题号/区域）
    7. 每道题单独识别
    8. 题库匹配
    9. 返回候选题
    """
    ensure_dirs()
    is_pdf = file.content_type == "application/pdf" or (
        file.content_type == "application/octet-stream" and file.filename and file.filename.lower().endswith(".pdf")
    )

    if not is_pdf and (not file.content_type or not file.content_type.startswith("image/")):
        raise HTTPException(status_code=400, detail="仅支持图片和PDF文件")

    image_bytes = await file.read()

    if is_pdf:
        if len(image_bytes) > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="PDF 大小不能超过 50MB")
        try:
            page_images = pdf_to_images(image_bytes)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF 处理失败: {str(e)}")
        total_pages = len(page_images)
        if total_pages == 0:
            raise HTTPException(status_code=400, detail="PDF 中没有页面")
    else:
        if len(image_bytes) > 20 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="图片大小不能超过 20MB")
        page_images = [image_bytes]
        total_pages = 1

    # Save original and create task
    orig_url = save_image(page_images[0], "images", "adv")
    task = WrongQuestionRecognitionTask(
        user_id=user_id,
        file_url=orig_url,
        file_type="pdf" if is_pdf else "image",
        recognition_mode=recognition_mode,
        status="processing",
        page_count=total_pages,
    )
    db.add(task)
    db.flush()
    task_id = task.id

    try:
        pages_result = []
        for page_num, img_bytes in enumerate(page_images):
            page_no = page_num + 1

            # 1. Basic preprocessing
            preprocessed = preprocess_for_ocr(img_bytes)

            # 2. Detect correction marks
            detection = detect_correction_marks(img_bytes)
            has_correction = detection["has_correction_marks"]

            # Determine actual mode
            actual_mode = recognition_mode
            if actual_mode == "auto":
                actual_mode = "corrected_paper" if has_correction else "normal"

            # Save clean image (with red marks removed for corrected_paper mode)
            clean_bytes = None
            clean_url = orig_url
            if actual_mode == "corrected_paper" and remove_correction_marks:
                # Remove red marks from preprocessed image
                clean_bytes = remove_red_marks(preprocessed)
                clean_url = save_image(clean_bytes, "clean", f"p{page_no}")
            else:
                clean_bytes = preprocessed
                clean_url = save_image(clean_bytes, "clean", f"p{page_no}")

            # Save page image
            page_url = save_image(img_bytes, "images", f"p{page_no}")

            # 3. AI analyze page structure
            page_analysis = await analyze_page_structure(clean_bytes or preprocessed,
                                                          f"page_{page_no}.jpg")
            ai_questions = page_analysis.get("questions", [])

            # Check if any detected question has a valid (non-zero) bounding box
            _has_valid_bbox = any(
                q.get("bbox") and len(q.get("bbox", [])) == 4
                and q["bbox"][2] > q["bbox"][0] and q["bbox"][3] > q["bbox"][1]
                for q in ai_questions
            ) if ai_questions else False

            # Fallback: if page analysis finds no questions or no valid bboxes,
            # use full-image recognition to get question texts
            _fallback_results = []
            if not ai_questions or not _has_valid_bbox:
                logger.info(
                    "Page analysis returned no valid bboxes, falling back to full-image recognition"
                )
                try:
                    fallback_result = await recognize_questions(
                        clean_bytes or preprocessed,
                        f"page_{page_no}.jpg",
                        strategy=RecognitionStrategy.SINGLE_STAGE,
                    )
                    fallback_questions = _extract_questions_from_recognition_result(fallback_result)
                    if fallback_questions:
                        ai_questions = [{
                            "question_no": str(i + 1),
                            "bbox": [0, 0, 0, 0],
                            "visible_text_summary": q.get("question_text", "")[:50],
                            "confidence": q.get("confidence", 0.5) if isinstance(q.get("confidence"), (int, float)) else 0.5,
                        } for i, q in enumerate(fallback_questions)]
                        # Store fallback results for later use
                        _fallback_results = fallback_questions
                    else:
                        _fallback_results = []
                except Exception as fallback_err:
                    logger.warning(f"Fallback recognition also failed: {fallback_err}")
                    _fallback_results = []
            else:
                _fallback_results = []

            # 4. Process each detected question
            blocks_result = []
            for qi, q_info in enumerate(ai_questions):
                q_no = q_info.get("question_no", str(qi + 1))
                bbox = q_info.get("bbox", [0, 0, 100, 100])

                # Detect normalized coordinates (0-1 range) and convert to pixels
                if bbox and max(bbox) <= 1.0 and bbox[2] > bbox[0] and bbox[3] > bbox[1]:
                    # AI returned normalized coordinates — scale to image dimensions
                    pil_img = Image.open(BytesIO(clean_bytes or preprocessed))
                    img_w, img_h = pil_img.size
                    bbox = [
                        int(bbox[0] * img_w),
                        int(bbox[1] * img_h),
                        int(bbox[2] * img_w),
                        int(bbox[3] * img_h),
                    ]
                else:
                    # Convert float bbox to int (AI may return fractional pixel coords)
                    bbox = [int(round(v)) for v in bbox]

                # Crop from clean image (if bbox is valid)
                crop_bytes = None
                crop_url = ""
                clean_crop_url = ""
                if bbox and bbox[2] > bbox[0] and bbox[3] > bbox[1]:
                    try:
                        crop_bytes = crop_bbox(clean_bytes or preprocessed, tuple(bbox))
                        crop_url = save_image(crop_bytes, "crops", f"p{page_no}_q{q_no}")
                        clean_crop_url = crop_url
                    except Exception as e:
                        logger.warning(f"Crop failed for q{q_no}: {e}")

                # AI recognize: prefer fallback data if available, else per-question recognition
                ai_single = {"question_text": "", "question_type": "other",
                             "knowledge_points": [], "difficulty": "中等",
                             "keywords": [], "confidence": 0.0}
                if _fallback_results and qi < len(_fallback_results):
                    # Use fallback full-image recognition result
                    fb = _fallback_results[qi]
                    ai_single = {
                        "question_text": fb.get("question_text", ""),
                        "question_type": fb.get("question_type", "other"),
                        "knowledge_points": fb.get("knowledge_points", []),
                        "difficulty": fb.get("difficulty", "中等"),
                        "keywords": fb.get("keywords", []),
                        "has_diagram": fb.get("has_image", False),
                        "diagram_description": "",
                        "is_complete": True,
                        "unclear_parts": [],
                        "confidence": fb.get("confidence", 0.0) if isinstance(fb.get("confidence"), (int, float)) else 0.0,
                    }
                elif crop_bytes:
                    ai_single = await recognize_single_question(crop_bytes, q_no)
                else:
                    # No valid bbox and no fallback — use full page image
                    logger.info(f"No valid bbox for q{q_no}, using full page image")
                    ai_single = await recognize_single_question(
                        clean_bytes or preprocessed, q_no
                    )

                # Build AiResultOut
                ai_result = AiResultOut(
                    question_text=ai_single.get("question_text", ""),
                    question_type=ai_single.get("question_type", "other"),
                    knowledge_points=ai_single.get("knowledge_points", []),
                    difficulty=ai_single.get("difficulty", "中等"),
                    keywords=ai_single.get("keywords", []),
                    has_diagram=ai_single.get("has_diagram", False),
                    diagram_description=ai_single.get("diagram_description", ""),
                    is_complete=ai_single.get("is_complete", True),
                    unclear_parts=ai_single.get("unclear_parts", []),
                    confidence=ai_single.get("confidence", 0.0),
                )

                # Search question bank for matches
                matched_qs = []
                if match_question_bank and ai_result.question_text:
                    norm_text = ai_result.question_text.strip()
                    keyword = norm_text[:40]
                    candidates = (
                        db.query(Question)
                        .filter(Question.question_text.contains(keyword))
                        .limit(10)
                        .all()
                    )
                    for cq in candidates:
                        sim = difflib.SequenceMatcher(
                            None, norm_text, (cq.question_text or "").strip()
                        ).ratio()
                        if sim > 0.3:  # Show candidates above 0.3
                            matched_qs.append(MatchedQuestionOut(
                                question_id=cq.question_id,
                                similarity=round(sim, 2),
                                question_text=cq.question_text[:100],
                                knowledge_point=cq.knowledge_point or "",
                                difficulty=cq.difficulty or "",
                            ))
                    matched_qs.sort(key=lambda x: x.similarity, reverse=True)
                    matched_qs = matched_qs[:5]

                # Auto-determine suggested action
                suggested_action = "need_confirm"
                need_manual = True
                if ai_result.confidence >= 0.85 and matched_qs and matched_qs[0].similarity >= 0.90:
                    suggested_action = "confirm_match"
                    need_manual = False

                block_id = f"p{page_no}_q{q_no}"
                block = RecognitionBlockOut(
                    block_id=block_id,
                    page_no=page_no,
                    question_no=q_no,
                    bbox=bbox,
                    crop_image_url=crop_url,
                    clean_crop_image_url=clean_crop_url,
                    ai_result=ai_result,
                    matched_questions=matched_qs,
                    suggested_action=suggested_action,
                    need_manual_confirm=need_manual,
                )
                blocks_result.append(block)

                # Save recognition block to DB
                db_block = WrongQuestionRecognitionBlock(
                    task_id=task_id,
                    page_no=page_no,
                    question_no=q_no,
                    bbox=json.dumps(bbox),
                    crop_image_url=crop_url,
                    clean_crop_image_url=clean_crop_url,
                    ai_question_text=ai_result.question_text,
                    ai_question_type=ai_result.question_type,
                    ai_knowledge_points=json.dumps(ai_result.knowledge_points, ensure_ascii=False),
                    ai_difficulty=ai_result.difficulty,
                    ai_keywords=json.dumps(ai_result.keywords, ensure_ascii=False),
                    ai_confidence=int(ai_result.confidence * 100) if ai_result.confidence else 0,
                    matched_question_id=matched_qs[0].question_id if matched_qs else None,
                    match_confidence=int(matched_qs[0].similarity * 100) if matched_qs else 0,
                    status="need_confirm",
                )
                db.add(db_block)

            page_out = RecognitionPageOut(
                page_no=page_no,
                image_url=page_url,
                clean_image_url=clean_url,
                questions=blocks_result,
            )
            pages_result.append(page_out)

        # Update task status
        task.status = "need_confirm"
        task.raw_result = json.dumps({
            "detection": detection,
            "actual_mode": actual_mode,
            "total_pages": total_pages,
        }, ensure_ascii=False)
        db.commit()

        # Convert numpy types before returning
        response_data = {
            "task_id": task_id,
            "status": "need_confirm",
            "file_type": "pdf" if is_pdf else "image",
            "page_count": total_pages,
            "pages": [page.dict() for page in pages_result],
        }
        response_data = convert_numpy_types(response_data)

        return RecognizeAdvancedResponse(**response_data)

    except Exception as e:
        task.status = "failed"
        db.commit()
        logger.error(f"Advanced recognition failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"识别失败: {str(e)}")


# ==================== Shared Page Processing Helper ====================

async def _process_page(
    img_bytes: bytes,
    page_no: int,
    task_id: int,
    recognition_mode: str,
    remove_correction_marks: bool,
    match_question_bank: bool,
    db: Session,
) -> tuple:
    """Process a single page: preprocess, analyze, recognize, match.

    Returns (RecognitionPageOut, detection dict).
    Used by both sync recognize-advanced and async recognize-pdf.
    """
    # 1. Basic preprocessing
    preprocessed = preprocess_for_ocr(img_bytes)

    # 2. Detect correction marks
    detection = detect_correction_marks(img_bytes)
    has_correction = detection["has_correction_marks"]

    # Determine actual mode
    actual_mode = recognition_mode
    if actual_mode == "auto":
        actual_mode = "corrected_paper" if has_correction else "normal"

    # Save clean image
    clean_bytes = None
    if actual_mode == "corrected_paper" and remove_correction_marks:
        clean_bytes = remove_red_marks(preprocessed)
        clean_url = save_image(clean_bytes, "clean", f"p{page_no}")
    else:
        clean_bytes = preprocessed
        clean_url = save_image(clean_bytes, "clean", f"p{page_no}")

    # Save page image
    page_url = save_image(img_bytes, "images", f"p{page_no}")

    # 3. AI analyze page structure
    page_analysis = await analyze_page_structure(clean_bytes or preprocessed,
                                                  f"page_{page_no}.jpg")
    ai_questions = page_analysis.get("questions", [])

    # Check if any detected question has a valid (non-zero) bounding box
    _has_valid_bbox = any(
        q.get("bbox") and len(q.get("bbox", [])) == 4
        and q["bbox"][2] > q["bbox"][0] and q["bbox"][3] > q["bbox"][1]
        for q in ai_questions
    ) if ai_questions else False

    # Fallback: if page analysis finds no questions or no valid bboxes,
    # use full-image recognition to get question texts
    _fallback_results = []
    if not ai_questions or not _has_valid_bbox:
        logger.info(f"Page {page_no}: no valid bboxes from structure analysis, falling back to full-image recognition")
        try:
            fallback_result = await recognize_questions(
                clean_bytes or preprocessed,
                f"page_{page_no}.jpg",
                strategy=RecognitionStrategy.SINGLE_STAGE,
            )
            fallback_questions = _extract_questions_from_recognition_result(fallback_result)
            if fallback_questions:
                ai_questions = [{
                    "question_no": str(i + 1),
                    "bbox": [0, 0, 0, 0],
                    "visible_text_summary": q.get("question_text", "")[:50],
                    "confidence": q.get("confidence", 0.5) if isinstance(q.get("confidence"), (int, float)) else 0.5,
                } for i, q in enumerate(fallback_questions)]
                _fallback_results = fallback_questions
        except Exception as fallback_err:
            logger.warning(f"Page {page_no} fallback recognition also failed: {fallback_err}")

    # 4. Process each detected question
    blocks_result = []
    for qi, q_info in enumerate(ai_questions):
        q_no = q_info.get("question_no", str(qi + 1))
        bbox = q_info.get("bbox", [0, 0, 100, 100])

        # Detect normalized coordinates (0-1 range) and convert to pixels
        if bbox and max(bbox) <= 1.0 and bbox[2] > bbox[0] and bbox[3] > bbox[1]:
            pil_img = Image.open(BytesIO(clean_bytes or preprocessed))
            img_w, img_h = pil_img.size
            bbox = [
                int(bbox[0] * img_w),
                int(bbox[1] * img_h),
                int(bbox[2] * img_w),
                int(bbox[3] * img_h),
            ]
        else:
            bbox = [int(round(v)) for v in bbox]

        # Crop from clean image
        crop_bytes = None
        crop_url = ""
        if bbox and bbox[2] > bbox[0] and bbox[3] > bbox[1]:
            try:
                crop_bytes = crop_bbox(clean_bytes or preprocessed, tuple(bbox))
                crop_url = save_image(crop_bytes, "crops", f"p{page_no}_q{q_no}")
            except Exception as e:
                logger.warning(f"Crop failed for p{page_no}_q{q_no}: {e}")

        # AI recognize single question
        ai_single = {"question_text": "", "question_type": "other",
                     "knowledge_points": [], "difficulty": "中等",
                     "keywords": [], "confidence": 0.0}
        if _fallback_results and qi < len(_fallback_results):
            fb = _fallback_results[qi]
            ai_single = {
                "question_text": fb.get("question_text", ""),
                "question_type": fb.get("question_type", "other"),
                "knowledge_points": fb.get("knowledge_points", []),
                "difficulty": fb.get("difficulty", "中等"),
                "keywords": fb.get("keywords", []),
                "has_diagram": fb.get("has_image", False),
                "diagram_description": "",
                "is_complete": True,
                "unclear_parts": [],
                "confidence": fb.get("confidence", 0.0) if isinstance(fb.get("confidence"), (int, float)) else 0.0,
            }
        elif crop_bytes:
            ai_single = await recognize_single_question(crop_bytes, q_no)
        else:
            logger.info(f"No valid bbox for p{page_no}_q{q_no}, using full page image")
            ai_single = await recognize_single_question(
                clean_bytes or preprocessed, q_no
            )

        ai_result = AiResultOut(
            question_text=ai_single.get("question_text", ""),
            question_type=ai_single.get("question_type", "other"),
            knowledge_points=ai_single.get("knowledge_points", []),
            difficulty=ai_single.get("difficulty", "中等"),
            keywords=ai_single.get("keywords", []),
            has_diagram=ai_single.get("has_diagram", False),
            diagram_description=ai_single.get("diagram_description", ""),
            is_complete=ai_single.get("is_complete", True),
            unclear_parts=ai_single.get("unclear_parts", []),
            confidence=ai_single.get("confidence", 0.0),
        )

        # Search question bank
        matched_qs = []
        if match_question_bank and ai_result.question_text:
            norm_text = ai_result.question_text.strip()
            keyword = norm_text[:40]
            candidates = (
                db.query(Question)
                .filter(Question.question_text.contains(keyword))
                .limit(10)
                .all()
            )
            for cq in candidates:
                sim = difflib.SequenceMatcher(
                    None, norm_text, (cq.question_text or "").strip()
                ).ratio()
                if sim > 0.3:
                    matched_qs.append(MatchedQuestionOut(
                        question_id=cq.question_id,
                        similarity=round(sim, 2),
                        question_text=cq.question_text[:100],
                        knowledge_point=cq.knowledge_point or "",
                        difficulty=cq.difficulty or "",
                    ))
            matched_qs.sort(key=lambda x: x.similarity, reverse=True)
            matched_qs = matched_qs[:5]

        suggested_action = "need_confirm"
        need_manual = True
        if ai_result.confidence >= 0.85 and matched_qs and matched_qs[0].similarity >= 0.90:
            suggested_action = "confirm_match"
            need_manual = False

        block_id = f"p{page_no}_q{q_no}"
        block = RecognitionBlockOut(
            block_id=block_id,
            page_no=page_no,
            question_no=q_no,
            bbox=bbox,
            crop_image_url=crop_url,
            clean_crop_image_url=crop_url,
            ai_result=ai_result,
            matched_questions=matched_qs,
            suggested_action=suggested_action,
            need_manual_confirm=need_manual,
        )
        blocks_result.append(block)

        # Save to DB
        db_block = WrongQuestionRecognitionBlock(
            task_id=task_id,
            page_no=page_no,
            question_no=q_no,
            bbox=json.dumps(bbox),
            crop_image_url=crop_url,
            clean_crop_image_url=crop_url,
            ai_question_text=ai_result.question_text,
            ai_question_type=ai_result.question_type,
            ai_knowledge_points=json.dumps(ai_result.knowledge_points, ensure_ascii=False),
            ai_difficulty=ai_result.difficulty,
            ai_keywords=json.dumps(ai_result.keywords, ensure_ascii=False),
            ai_confidence=int(ai_result.confidence * 100) if ai_result.confidence else 0,
            matched_question_id=matched_qs[0].question_id if matched_qs else None,
            match_confidence=int(matched_qs[0].similarity * 100) if matched_qs else 0,
            status="need_confirm",
        )
        db.add(db_block)

    page_out = RecognitionPageOut(
        page_no=page_no,
        image_url=page_url,
        clean_image_url=clean_url,
        questions=blocks_result,
    )
    return page_out, detection, actual_mode


# ==================== Async PDF Recognition with Progress ====================

async def _run_pdf_recognition_background(
    task_id: int,
    user_id: int,
    page_paths: list,
    recognition_mode: str,
    remove_correction_marks: bool,
    match_question_bank: bool,
):
    """Background task: process each PDF page and update progress."""
    db = SessionLocal()
    try:
        total_pages = len(page_paths)
        progress_store.update(task_id, message=f"开始识别，共 {total_pages} 页...")

        for page_num, img_path in enumerate(page_paths):
            page_no = page_num + 1
            progress_store.update(
                task_id,
                current_page=page_no,
                message=f"正在识别第 {page_no}/{total_pages} 页...",
            )

            # Read page image from disk
            with open(img_path, "rb") as f:
                img_bytes = f.read()

            # Process page
            await _process_page(
                img_bytes=img_bytes,
                page_no=page_no,
                task_id=task_id,
                recognition_mode=recognition_mode,
                remove_correction_marks=remove_correction_marks,
                match_question_bank=match_question_bank,
                db=db,
            )

            # Count blocks found so far
            blocks_count = (
                db.query(WrongQuestionRecognitionBlock)
                .filter(WrongQuestionRecognitionBlock.task_id == task_id)
                .count()
            )

            progress_store.update(
                task_id,
                questions_found=blocks_count,
                message=f"第 {page_no}/{total_pages} 页完成，已发现 {blocks_count} 道题",
            )

            db.flush()

        # Mark task complete
        task = db.query(WrongQuestionRecognitionTask).filter(
            WrongQuestionRecognitionTask.id == task_id
        ).first()
        if task:
            task.status = "need_confirm"
            task.raw_result = json.dumps({
                "recognition_mode": recognition_mode,
                "total_pages": total_pages,
                "completed": True,
            }, ensure_ascii=False)
            db.commit()

        final_blocks = (
            db.query(WrongQuestionRecognitionBlock)
            .filter(WrongQuestionRecognitionBlock.task_id == task_id)
            .count()
        )
        progress_store.update(
            task_id,
            status="need_confirm",
            current_page=total_pages,
            message=f"识别完成，共 {final_blocks} 道题",
        )

    except Exception as e:
        logger.error(f"Background PDF task {task_id} failed: {e}", exc_info=True)
        try:
            task = db.query(WrongQuestionRecognitionTask).filter(
                WrongQuestionRecognitionTask.id == task_id
            ).first()
            if task:
                task.status = "failed"
                task.raw_result = json.dumps({"error": str(e)}, ensure_ascii=False)
                db.commit()
        except Exception:
            pass
        progress_store.update(
            task_id,
            status="failed",
            message=f"识别失败: {str(e)[:150]}",
        )
    finally:
        db.close()


async def _run_pdf_hybrid_recognition_background(
    task_id: int,
    user_id: int,
    pdf_path: str,
    recognition_mode: str,
    remove_correction_marks: bool,
    match_question_bank: bool,
):
    """Hybrid PDF pipeline: Markdown first, vision only for missing/low-quality pages."""
    db = SessionLocal()
    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        task = db.query(WrongQuestionRecognitionTask).filter(
            WrongQuestionRecognitionTask.id == task_id,
            WrongQuestionRecognitionTask.user_id == user_id,
        ).first()
        if not task:
            raise ValueError("识别任务不存在")

        total_pages = task.page_count or _get_pdf_page_count(pdf_bytes)
        mode = (recognition_mode or "auto").lower()
        progress_store.update(
            task_id,
            status="processing",
            current_page=0,
            total_pages=total_pages,
            questions_found=0,
            message="正在分析 PDF 类型...",
        )

        markdown_questions = []
        markdown_error = ""
        vision_pages = set()
        vision_failed_pages = []
        vision_by_page = {}

        should_try_markdown = mode not in ("vision", "image", "visual")
        if should_try_markdown:
            try:
                progress_store.update(task_id, message="正在提取 PDF 文本并转换为 Markdown...")
                markdown_text, used_ocr = await asyncio.to_thread(
                    pdf_to_markdown,
                    pdf_bytes,
                    30,
                    False,  # OCR for scanned PDFs is slower and less reliable than vision fallback.
                )
                effective_chars = len(_re.sub(r"\s+", "", markdown_text))
                if effective_chars < 100:
                    raise ValueError("Markdown 有效文本过少，疑似扫描版 PDF")

                progress_store.update(task_id, message="正在用 Markdown 快速拆题...")
                from ..utils.deepseek import call_text_llm

                extracted = await extract_questions_from_markdown(
                    markdown_text,
                    call_text_llm,
                    pdf_images=None,
                    include_answers=False,
                )
                markdown_questions = [
                    _normalize_pdf_question(q, page_no=q.get("page_no", 1), index=i + 1, source="markdown_ocr" if used_ocr else "markdown")
                    for i, q in enumerate(extracted)
                    if isinstance(q, dict) and (q.get("question_text") or "").strip()
                ]
                progress_store.update(
                    task_id,
                    questions_found=len(markdown_questions),
                    message=f"Markdown 已识别 {len(markdown_questions)} 道题，正在做质量检查...",
                )

                markdown_pages = _split_markdown_by_page(markdown_text, total_pages)
                questions_by_page = {}
                for q in markdown_questions:
                    questions_by_page.setdefault(int(q.get("page_no") or 1), []).append(q)

                for page_no in range(1, total_pages + 1):
                    page_questions = questions_by_page.get(page_no, [])
                    estimated_count = _estimate_question_count_from_text(markdown_pages.get(page_no, ""))
                    missed_questions = estimated_count > 0 and len(page_questions) < max(1, estimated_count)
                    low_quality = page_questions and _page_quality(page_questions) < 0.45
                    if not page_questions or missed_questions or low_quality:
                        vision_pages.add(page_no)

                if mode in ("accurate", "high_accuracy", "high-accuracy"):
                    vision_pages = set(range(1, total_pages + 1))
                elif mode == "fast" and markdown_questions:
                    vision_pages = set()

            except Exception as e:
                markdown_error = str(e)
                logger.warning(f"PDF Markdown recognition failed, using vision fallback: {e}")
                vision_pages = set(range(1, total_pages + 1))
        else:
            vision_pages = set(range(1, total_pages + 1))

        if not markdown_questions and not vision_pages:
            vision_pages = set(range(1, total_pages + 1))

        if vision_pages:
            progress_store.update(
                task_id,
                message=f"正在渲染 PDF 页面，准备视觉补识别 {len(vision_pages)} 页...",
            )
            page_images = await asyncio.to_thread(
                _pdf_pages_to_images,
                pdf_bytes,
                sorted(vision_pages),
                200,
            )
            semaphore = asyncio.Semaphore(2)
            completed = 0

            async def _recognize_one_page(page_no: int):
                async with semaphore:
                    try:
                        if page_no not in page_images:
                            raise ValueError("页面渲染失败")
                        result = await recognize_questions(
                            page_images[page_no],
                            f"pdf_page_{page_no}.jpg",
                            strategy=RecognitionStrategy.SINGLE_STAGE,
                            include_answers=False,
                        )
                        questions = [
                            _normalize_pdf_question(q, page_no=page_no, index=i + 1, source="vision")
                            for i, q in enumerate(_extract_questions_from_recognition_result(result))
                        ]
                        return page_no, questions, None
                    except Exception as e:
                        return page_no, [], str(e)

            tasks = [_recognize_one_page(p) for p in sorted(vision_pages)]
            for done in asyncio.as_completed(tasks):
                page_no, questions, error = await done
                completed += 1
                if error:
                    vision_failed_pages.append(page_no)
                    logger.warning(f"PDF vision fallback page {page_no} failed: {error}")
                else:
                    vision_by_page[page_no] = questions

                found = len(markdown_questions) + sum(len(v) for v in vision_by_page.values())
                progress_store.update(
                    task_id,
                    current_page=page_no,
                    questions_found=found,
                    message=f"视觉补识别进度 {completed}/{len(tasks)} 页，当前共发现 {found} 道题",
                )

        # Merge Markdown and vision results. Vision can improve weak pages, but it
        # must not shrink a page that Markdown already extracted more completely.
        final_questions = _merge_pdf_questions(markdown_questions, vision_by_page)
        if not final_questions:
            raise ValueError(markdown_error or "未能从 PDF 中识别出题目")

        progress_store.update(
            task_id,
            current_page=total_pages,
            total_pages=total_pages,
            questions_found=len(final_questions),
            message=f"题目识别完成，正在生成 {len(final_questions)} 道题的答案解析...",
        )
        answer_stats = await _populate_question_answers_before_confirm(final_questions, task_id)

        saved_count = _save_recognition_blocks(
            task_id=task_id,
            questions=final_questions,
            db=db,
            match_question_bank=match_question_bank,
        )
        if saved_count == 0:
            raise ValueError("识别结果为空，无法生成确认题目")

        task.status = "partial_failed" if vision_failed_pages else "need_confirm"
        task.raw_result = json.dumps({
            "recognition_mode": mode,
            "pipeline": "markdown_first_vision_fallback",
            "markdown_count": len(markdown_questions),
            "vision_pages": sorted(vision_pages),
            "vision_failed_pages": vision_failed_pages,
            "final_count": saved_count,
            "answer_generated_count": answer_stats.get("generated", 0),
            "answer_failed_count": answer_stats.get("failed", 0),
            "markdown_error": markdown_error,
        }, ensure_ascii=False)
        db.commit()

        message = f"识别完成，共 {saved_count} 道题"
        if vision_failed_pages:
            message += f"，其中 {len(vision_failed_pages)} 页补识别失败，可先确认已识别题目"
        progress_store.update(
            task_id,
            status=task.status,
            current_page=total_pages,
            total_pages=total_pages,
            questions_found=saved_count,
            message=message,
        )

    except Exception as e:
        logger.error(f"Hybrid PDF task {task_id} failed: {e}", exc_info=True)
        try:
            task = db.query(WrongQuestionRecognitionTask).filter(
                WrongQuestionRecognitionTask.id == task_id,
                WrongQuestionRecognitionTask.user_id == user_id,
            ).first()
            if task:
                task.status = "failed"
                task.raw_result = json.dumps({"error": str(e)}, ensure_ascii=False)
                db.commit()
        except Exception:
            db.rollback()
        progress_store.update(
            task_id,
            status="failed",
            message=f"识别失败: {str(e)[:150]}",
        )
    finally:
        try:
            os.remove(pdf_path)
        except Exception:
            pass
        db.close()


@router.post("/recognize-pdf")
async def recognize_pdf_async(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    use_markdown: bool = Form(False),  # Changed default to False (use vision model)
    recognition_mode: str = Form("auto"),
    remove_correction_marks: bool = Form(True),
    match_question_bank: bool = Form(True),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """上传 PDF 进行异步整卷识别。

    Args:
        use_markdown: 是否使用Markdown方式（不推荐）。
                     False (默认): PDF→图片→视觉模型识别（推荐，准确率高）
                     True: PDF→文本→LLM提取（仅适合纯文本PDF）

    返回 task_id，前端轮询 GET /recognition-tasks/{task_id}/progress 获取进度。
    识别完成后调用 GET /recognition-tasks/{task_id} 获取完整结果。
    """
    ensure_dirs()

    is_pdf = file.content_type == "application/pdf" or (
        file.content_type == "application/octet-stream"
        and file.filename
        and file.filename.lower().endswith(".pdf")
    )
    if not is_pdf:
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="PDF 大小不能超过 50MB")

    # Save PDF to temp file for processing
    temp_pdf_path = os.path.join(UPLOAD_DIR, "temp", f"pdf_{uuid.uuid4().hex[:12]}.pdf")
    os.makedirs(os.path.dirname(temp_pdf_path), exist_ok=True)
    with open(temp_pdf_path, "wb") as f:
        f.write(pdf_bytes)

    try:
        page_count = _get_pdf_page_count(pdf_bytes, max_pages=30)
    except Exception as e:
        try:
            os.remove(temp_pdf_path)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=f"PDF 处理失败: {str(e)}")

    effective_mode = "fast" if use_markdown else (recognition_mode or "auto")
    task = WrongQuestionRecognitionTask(
        user_id=user_id,
        file_url="",
        file_type="pdf",
        recognition_mode=effective_mode,
        status="processing",
        page_count=page_count,
    )
    db.add(task)
    db.flush()
    task_id = task.id
    db.commit()

    progress_store.init(task_id, page_count)
    progress_store.update(
        task_id,
        message="PDF 已上传，正在启动 Markdown 优先的混合识别...",
    )

    background_tasks.add_task(
        _run_pdf_hybrid_recognition_background,
        task_id=task_id,
        user_id=user_id,
        pdf_path=temp_pdf_path,
        recognition_mode=effective_mode,
        remove_correction_marks=remove_correction_marks,
        match_question_bank=match_question_bank,
    )

    return {
        "task_id": task_id,
        "status": "processing",
        "file_type": "pdf",
        "page_count": page_count,
        "message": f"识别任务已创建，共 {page_count} 页，正在后台处理",
    }

    # Default: Vision-based recognition (recommended)
    if not use_markdown:
        logger.info("Using vision-based recognition for PDF (recommended)")
        try:
            from ..utils.pdf_vision_recognition import recognize_pdf_with_vision

            # Recognize PDF using vision model
            def progress_update(msg: str):
                progress_store.update(task_id, message=msg)

            questions = await recognize_pdf_with_vision(
                pdf_bytes,
                progress_callback=progress_update,
                dpi=200
            )
            logger.info(f"Vision recognition extracted {len(questions)} questions")

            if not questions:
                raise ValueError("未能从PDF中识别出题目")

            # Create task
            task = WrongQuestionRecognitionTask(
                user_id=user_id,
                file_url="",
                file_type="pdf",
                recognition_mode="vision",
                status="completed",
                page_count=len(set(q.get("page_no", 1) for q in questions)),
                raw_result=json.dumps(questions, ensure_ascii=False),
            )
            db.add(task)
            db.flush()
            task_id = task.id

            # Create blocks for each question
            for i, q in enumerate(questions):
                block = WrongQuestionRecognitionBlock(
                    task_id=task_id,
                    page_no=q.get("page_no", 1),
                    question_no=q.get("question_no", str(i + 1)),
                    ai_question_text=q.get("question_text", ""),
                    ai_answer=q.get("answer", ""),
                    ai_solution=q.get("solution", ""),
                    ai_question_type=q.get("question_type", ""),
                    ai_knowledge_points=json.dumps([q.get("knowledge_point", "")], ensure_ascii=False),
                    ai_difficulty=q.get("difficulty", "中等"),
                    ai_confidence=int(q.get("confidence", 0.9) * 100),
                    status="need_confirm",
                )
                db.add(block)

            db.commit()

            # Clean up temp file
            try:
                os.remove(temp_pdf_path)
            except:
                pass

            logger.info(f"PDF vision task {task_id} completed: {len(questions)} questions")
            return {
                "task_id": task_id,
                "status": "completed",
                "file_type": "pdf",
                "page_count": task.page_count,
                "questions_found": len(questions),
                "message": f"识别完成，共识别出 {len(questions)} 道题目（使用视觉模型）",
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Vision PDF recognition failed: {e}", exc_info=True)
            db.rollback()
            # Clean up temp file
            try:
                os.remove(temp_pdf_path)
            except:
                pass
            raise HTTPException(
                status_code=500,
                detail=f"PDF识别失败：{str(e)}。请检查PDF格式或稍后重试。"
            )

    # Method 2: Markdown-based extraction (legacy, not recommended)
    if use_markdown:
        try:
            # Convert PDF to markdown (with OCR fallback for scanned PDFs)
            logger.info("Starting PDF to markdown conversion...")
            markdown_text, used_ocr = pdf_to_markdown(pdf_bytes, max_pages=30, use_ocr_fallback=True)
            logger.info(f"PDF converted to markdown: {len(markdown_text)} chars (OCR: {used_ocr})")

            # Check if PDF has extractable text
            if len(markdown_text.strip()) < 50:
                logger.warning("PDF has insufficient extractable text, falling back to image recognition")
                raise ValueError("PDF文本内容不足，切换到图片识别方式")

            # Extract questions using LLM (no image extraction, pure markdown mode)
            logger.info("Extracting questions from markdown using LLM...")
            from ..utils.deepseek import call_text_llm
            questions = await extract_questions_from_markdown(markdown_text, call_text_llm, pdf_images=None)
            logger.info(f"Extracted {len(questions)} questions from markdown")

            if not questions:
                logger.warning("No questions extracted from markdown, falling back to image recognition")
                raise ValueError("未能从文本中提取题目，切换到图片识别方式")

            # Create task
            task = WrongQuestionRecognitionTask(
                user_id=user_id,
                file_url="",  # No thumbnail for markdown mode
                file_type="pdf",
                recognition_mode="markdown_ocr" if used_ocr else "markdown",
                status="completed",
                page_count=1,
                raw_result=json.dumps(questions, ensure_ascii=False),
            )
            db.add(task)
            db.flush()
            task_id = task.id

            # Create blocks for each question
            for i, q in enumerate(questions):
                # Save image URLs as JSON if present
                image_urls_json = json.dumps(q.get("image_urls", []), ensure_ascii=False) if q.get("image_urls") else None

                block = WrongQuestionRecognitionBlock(
                    task_id=task_id,
                    page_no=1,
                    question_no=str(i + 1),
                    ai_question_text=q.get("question_text", ""),
                    ai_answer=q.get("answer", ""),
                    ai_solution=q.get("solution", ""),
                    ai_question_type=q.get("question_type", ""),
                    ai_knowledge_points=json.dumps([q.get("knowledge_point", "")], ensure_ascii=False),
                    ai_difficulty=q.get("difficulty", "中等"),
                    ai_confidence=90,
                    question_image_urls=image_urls_json,
                    status="need_confirm",
                )
                db.add(block)

            db.commit()

            logger.info(f"PDF markdown task {task_id} completed: {len(questions)} questions (OCR: {used_ocr})")
            return {
                "task_id": task_id,
                "status": "completed",
                "file_type": "pdf",
                "page_count": 1,
                "questions_found": len(questions),
                "message": f"识别完成，共识别出 {len(questions)} 道题目" + (" (使用OCR)" if used_ocr else ""),
            }

        except HTTPException:
            raise
        except ValueError as e:
            # PDF is scanned or has no extractable text - return error instead of fallback
            logger.warning(f"Markdown extraction failed: {e}")
            db.rollback()
            error_msg = str(e)
            if "OCR" in error_msg or "tesseract" in error_msg.lower():
                detail = "PDF是扫描件，需要OCR识别但OCR功能未安装。建议：1) 使用截图识别功能对单个题目进行识别；2) 或联系管理员安装Tesseract OCR以支持扫描版PDF识别。"
            else:
                detail = f"PDF识别失败：{error_msg}。建议使用截图识别功能对单个题目进行识别。"
            raise HTTPException(
                status_code=400,
                detail=detail
            )
        except Exception as e:
            logger.error(f"Markdown PDF recognition failed: {e}", exc_info=True)
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"PDF识别失败：{str(e)}。请检查PDF格式或使用截图识别功能。"
            )

    # Method 2: Image-based recognition (only when use_markdown=False)
    if not use_markdown:
        logger.info("Using image-based recognition for PDF (user explicitly requested)")
        try:
            page_images = pdf_to_images(pdf_bytes)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF 处理失败: {str(e)}")

        total_pages = len(page_images)
        if total_pages == 0:
            raise HTTPException(status_code=400, detail="PDF 中没有页面")

        # Save page images to a task-specific directory
        task_dir_name = f"task_{uuid.uuid4().hex[:12]}"
        task_dir = os.path.join(UPLOAD_DIR, "tasks", task_dir_name)
        os.makedirs(task_dir, exist_ok=True)
        page_paths = []
        for i, img_bytes in enumerate(page_images):
            path = os.path.join(task_dir, f"page_{i + 1}.jpg")
            with open(path, "wb") as f:
                f.write(img_bytes)
            page_paths.append(path)

        # Save thumbnail
        thumb_url = save_image(page_images[0], "images", "pdf_task")

        # Create task
        task = WrongQuestionRecognitionTask(
            user_id=user_id,
            file_url=thumb_url,
            file_type="pdf",
            recognition_mode=recognition_mode,
            status="processing",
            page_count=total_pages,
        )
        db.add(task)
        db.flush()
        task_id = task.id
        db.commit()

        # Init progress tracking
        progress_store.init(task_id, total_pages)

        # Start background processing
        background_tasks.add_task(
            _run_pdf_recognition_background,
            task_id=task_id,
            user_id=user_id,
            page_paths=page_paths,
            recognition_mode=recognition_mode,
            remove_correction_marks=remove_correction_marks,
            match_question_bank=match_question_bank,
        )

        logger.info(f"PDF async task {task_id} started: {total_pages} pages")
        return {
            "task_id": task_id,
            "status": "processing",
            "file_type": "pdf",
            "page_count": total_pages,
            "message": f"识别任务已创建，共 {total_pages} 页，正在后台处理",
        }
    else:
        # use_markdown=True but we reached here - should not happen
        raise HTTPException(
            status_code=400,
            detail="PDF Markdown识别模式已启用，但未能成功识别。请检查PDF格式。"
        )


@router.get("/recognition-tasks/{task_id}/progress")
def get_recognition_progress(
    task_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """轮询识别任务进度"""
    # Verify task belongs to user
    task = (
        db.query(WrongQuestionRecognitionTask)
        .filter(
            WrongQuestionRecognitionTask.id == task_id,
            WrongQuestionRecognitionTask.user_id == user_id,
        )
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # Check in-memory progress first
    progress = progress_store.get(task_id)
    if progress:
        return {"task_id": task_id, **progress}

    # Fallback: build from DB state
    blocks_count = (
        db.query(WrongQuestionRecognitionBlock)
        .filter(WrongQuestionRecognitionBlock.task_id == task_id)
        .count()
    )
    return {
        "task_id": task_id,
        "status": task.status or "unknown",
        "current_page": task.page_count if task.status in ("need_confirm", "partial_failed", "confirmed") else 0,
        "total_pages": task.page_count or 0,
        "questions_found": blocks_count,
        "message": (
            "识别已完成" if task.status == "need_confirm"
            else "部分页面识别失败，可先确认已识别题目" if task.status == "partial_failed"
            else "识别失败" if task.status == "failed"
            else "已确认" if task.status == "confirmed"
            else "等待处理"
        ),
    }


@router.get("/recognition-tasks/{task_id}")
def get_recognition_task(
    task_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """获取识别任务状态和结果"""
    task = db.query(WrongQuestionRecognitionTask).filter(
        WrongQuestionRecognitionTask.id == task_id,
        WrongQuestionRecognitionTask.user_id == user_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    blocks = db.query(WrongQuestionRecognitionBlock).filter(
        WrongQuestionRecognitionBlock.task_id == task_id,
    ).order_by(WrongQuestionRecognitionBlock.page_no,
               WrongQuestionRecognitionBlock.question_no).all()

    # Reconstruct pages from blocks
    pages_map = {}
    for b in blocks:
        pno = b.page_no
        if pno not in pages_map:
            pages_map[pno] = RecognitionPageOut(
                page_no=pno,
                image_url="",
                clean_image_url="",
                questions=[],
            )
        try:
            bbox = json.loads(b.bbox) if b.bbox else []
        except (json.JSONDecodeError, TypeError):
            bbox = []
        try:
            kps = json.loads(b.ai_knowledge_points) if b.ai_knowledge_points else []
        except (json.JSONDecodeError, TypeError):
            kps = []
        try:
            kws = json.loads(b.ai_keywords) if b.ai_keywords else []
        except (json.JSONDecodeError, TypeError):
            kws = []
        try:
            question_image_urls = json.loads(b.question_image_urls) if b.question_image_urls else []
        except (json.JSONDecodeError, TypeError):
            question_image_urls = []

        matched_qs = []
        if b.ai_question_text:
            for mq in _search_matches(b.ai_question_text, db, limit=5):
                sim = difflib.SequenceMatcher(
                    None,
                    _normalize_text(b.ai_question_text),
                    _normalize_text(mq.question_text or ""),
                ).ratio()
                matched_qs.append(MatchedQuestionOut(
                    question_id=mq.question_id,
                    similarity=round(sim, 2),
                    question_text=(mq.question_text or "")[:100],
                    knowledge_point=mq.knowledge_point or "",
                    difficulty=mq.difficulty or "",
                ))
        if b.matched_question_id and not any(mq.question_id == b.matched_question_id for mq in matched_qs):
            matched = db.query(Question).filter(Question.question_id == b.matched_question_id).first()
            if matched:
                matched_qs.insert(0, MatchedQuestionOut(
                    question_id=matched.question_id,
                    similarity=round((b.match_confidence or 0) / 100.0, 2),
                    question_text=(matched.question_text or "")[:100],
                    knowledge_point=matched.knowledge_point or "",
                    difficulty=matched.difficulty or "",
                ))

        pages_map[pno].questions.append(RecognitionBlockOut(
            block_id=f"p{b.page_no}_q{b.question_no}",
            page_no=b.page_no,
            question_no=b.question_no or "",
            bbox=bbox,
            crop_image_url=b.crop_image_url or "",
            clean_crop_image_url=b.clean_crop_image_url or "",
            question_image_urls=question_image_urls,
            ai_result=AiResultOut(
                question_text=b.ai_question_text or "",
                question_type=b.ai_question_type or "other",
                knowledge_points=kps,
                difficulty=b.ai_difficulty or "中等",
                keywords=kws,
                confidence=(b.ai_confidence or 0) / 100.0,
            ),
            ai_answer=b.ai_answer or "",
            ai_solution=b.ai_solution or "",
            matched_questions=matched_qs,
            suggested_action="need_confirm",
            need_manual_confirm=not (b.matched_question_id and (b.match_confidence or 0) >= 90),
        ))

    # Try to get page URLs from the first block's task
    pages = list(pages_map.values())

    return RecognizeAdvancedResponse(
        task_id=task.id,
        status=task.status,
        file_type=task.file_type or "",
        page_count=task.page_count or 1,
        pages=pages,
    )


@router.post("/recognition-tasks/{task_id}/prepare-confirmation")
async def prepare_recognition_confirmation(
    task_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Generate missing answers/solutions so the user can confirm with full context."""
    task = db.query(WrongQuestionRecognitionTask).filter(
        WrongQuestionRecognitionTask.id == task_id,
        WrongQuestionRecognitionTask.user_id == user_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    stats = await _generate_missing_block_answers(task_id, db)
    return {
        "task_id": task_id,
        "generated": stats.get("generated", 0),
        "failed": stats.get("failed", 0),
        "total": stats.get("total", 0),
    }


@router.post("/recognition-tasks/{task_id}/confirm")
def confirm_recognition_task(
    task_id: int,
    req: ConfirmRecognitionRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """确认识别结果，将选中的题目加入错题本"""
    task = db.query(WrongQuestionRecognitionTask).filter(
        WrongQuestionRecognitionTask.id == task_id,
        WrongQuestionRecognitionTask.user_id == user_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    results = []
    pending_answer_backfill_ids = set()
    for item in req.items:
        block_id = item.block_id
        # Parse block_id to find the block
        try:
            parts = block_id.split("_q")
            page_str = parts[0].replace("p", "")
            page_no = int(page_str)
            question_no = parts[1] if len(parts) > 1 else ""
        except (ValueError, IndexError):
            continue

        block = db.query(WrongQuestionRecognitionBlock).filter(
            WrongQuestionRecognitionBlock.task_id == task_id,
            WrongQuestionRecognitionBlock.page_no == page_no,
            WrongQuestionRecognitionBlock.question_no == question_no,
        ).first()

        if not block:
            continue

        matched_q_id = item.matched_question_id or block.matched_question_id

        if not matched_q_id:
            # No match — skip (user should create question first)
            results.append({"block_id": block_id, "status": "skipped", "reason": "未匹配题库"})
            continue

        block.matched_question_id = matched_q_id
        q = db.query(Question).filter(Question.question_id == matched_q_id).first()
        if _needs_answer_backfill(q):
            pending_answer_backfill_ids.add(matched_q_id)

        # Check if already in wrong questions
        existing = (
            db.query(UserWrongQuestion)
            .filter(
                UserWrongQuestion.user_id == user_id,
                UserWrongQuestion.question_id == matched_q_id,
            )
            .first()
        )
        if existing:
            results.append({"block_id": block_id, "status": "skipped", "reason": "已在错题本中"})
            block.status = "confirmed"
            continue

        # Add to wrong questions
        record = UserWrongQuestion(
            user_id=user_id,
            question_id=matched_q_id,
            exam_name=item.exam_name,
            exam_date=date.today(),
            error_type=item.error_type,
            notes=item.remark,
            original_image_url=task.file_url,
            clean_image_url="",
            crop_image_url=block.crop_image_url,
            recognition_task_id=task_id,
            ai_confidence=block.ai_confidence,
        )
        db.add(record)
        db.flush()

        # Update knowledge mastery
        if q:
            _update_mastery(user_id, q.knowledge_point, False, db)

        block.status = "confirmed"
        results.append({"block_id": block_id, "status": "confirmed", "record_id": record.record_id})

    # Check if all blocks are confirmed
    remaining = db.query(WrongQuestionRecognitionBlock).filter(
        WrongQuestionRecognitionBlock.task_id == task_id,
        WrongQuestionRecognitionBlock.status != "confirmed",
    ).count()

    if remaining == 0:
        task.status = "confirmed"

    db.commit()
    queued_backfill_count = len(pending_answer_backfill_ids)
    if queued_backfill_count and background_tasks is not None:
        background_tasks.add_task(
            _backfill_question_answers_background,
            task_id=task_id,
            question_ids=list(pending_answer_backfill_ids),
        )

    return {"message": f"已处理 {len(results)} 道题", "results": results}


@router.put("/feedback")
def feedback_wrong_question(
    req: WrongQuestionFeedback,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    record = (
        db.query(UserWrongQuestion)
        .filter(
            UserWrongQuestion.record_id == req.record_id,
            UserWrongQuestion.user_id == user_id,
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    record.is_correct = req.is_correct
    record.redo_count = (record.redo_count or 0) + 1
    record.last_redo_date = date.today()
    if req.error_type:
        record.error_type = req.error_type

    q = db.query(Question).filter(Question.question_id == record.question_id).first()
    if q:
        _update_mastery(user_id, q.knowledge_point, req.is_correct, db)

    db.commit()
    return {"message": "反馈已记录"}


@router.delete("/{record_id}")
def delete_wrong_question(
    record_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    record = (
        db.query(UserWrongQuestion)
        .filter(
            UserWrongQuestion.record_id == record_id,
            UserWrongQuestion.user_id == user_id,
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    db.delete(record)
    db.commit()
    return {"message": "已从错题本移除"}


@router.post("/generate-answer")
async def generate_answer_for_question(
    req: AnswerGenerateRequest,
    user_id: int = Depends(get_current_user_id),
):
    """用 DeepSeek 自动生成题目答案和解析"""
    result = await generate_answer(req.question_text, req.question_type or "", req.knowledge_point or "")
    return AnswerGenerateResponse(**result)


@router.post("/check-duplicate")
def check_wrong_question_duplicate(
    req: DupCheckRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """检查题目是否已在题库或错题本中"""
    if not req.question_text.strip():
        return DupCheckResponse()

    # Normalize input text
    norm_text = _re.sub(r'\s+', ' ', req.question_text or '').strip()

    # Find candidates in question bank using multiple prefix lengths
    candidates = []
    seen_ids = set()
    for kw_len in [30, 50, 20]:
        kw = norm_text[:kw_len]
        if len(kw) < 8:
            continue
        qs = (
            db.query(Question)
            .filter(Question.question_text.contains(kw))
            .limit(20)
            .all()
        )
        for q in qs:
            if q.question_id not in seen_ids:
                seen_ids.add(q.question_id)
                candidates.append(q)
        if candidates:
            break

    best_match = None
    best_similarity = 0.0

    for q in candidates:
        q_text = _re.sub(r'\s+', ' ', q.question_text or '').strip()
        similarity = difflib.SequenceMatcher(None, norm_text, q_text).ratio()
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = q

    if best_match and best_similarity > 0.78:
        # Check if in wrong questions
        in_wrong = (
            db.query(UserWrongQuestion)
            .filter(
                UserWrongQuestion.user_id == user_id,
                UserWrongQuestion.question_id == best_match.question_id,
            )
            .first()
        )
        return DupCheckResponse(
            in_bank=True,
            in_wrong_questions=in_wrong is not None,
            matched_question_id=best_match.question_id,
            matched_question=QuestionOut.model_validate(best_match),
            similarity=round(best_similarity, 2),
        )

    return DupCheckResponse(similarity=round(best_similarity, 2))


@router.get("/diagnosis")
def get_diagnosis(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """获取学情诊断报告（增强版）"""
    mastery_list = (
        db.query(UserKnowledgeMastery)
        .filter(UserKnowledgeMastery.user_id == user_id)
        .all()
    )

    if not mastery_list:
        return DiagnosisReport()

    weak_points = [m for m in mastery_list if m.is_weak_point]
    forgetting = [m for m in mastery_list if (m.forgetting_risk_score or 0) >= 60]
    avg_rate = sum(float(m.mastery_rate or 0) for m in mastery_list) / len(mastery_list)
    total_wrong = db.query(UserWrongQuestion).filter(
        UserWrongQuestion.user_id == user_id,
        UserWrongQuestion.is_correct == False,
        UserWrongQuestion.mastered == False,
    ).count()

    # 错误类型统计
    error_type_counts = {}
    for et in ErrorType:
        cnt = db.query(UserWrongQuestion).filter(
            UserWrongQuestion.user_id == user_id,
            UserWrongQuestion.error_type == et.value,
            UserWrongQuestion.mastered == False,
        ).count()
        if cnt > 0:
            error_type_counts[et.value] = cnt
    total_err = sum(error_type_counts.values()) or 1
    error_type_stats = [
        ErrorTypeStat(error_type=et, count=cnt, percentage=round(cnt / total_err * 100, 1))
        for et, cnt in error_type_counts.items()
    ]

    # 薄弱知识点详情（含建议）
    weak_detail = []
    for wp in weak_points:
        wrong_count = db.query(UserWrongQuestion).filter(
            UserWrongQuestion.user_id == user_id,
            UserWrongQuestion.question_id.in_(
                db.query(Question.question_id).filter(
                    Question.knowledge_point == wp.knowledge_point
                )
            ),
            UserWrongQuestion.mastered == False,
        ).count()
        suggestion, main_issue, key_method = _get_weak_point_advice(wp.knowledge_point, float(wp.mastery_rate or 0))
        weak_detail.append(WeakPointSuggestion(
            knowledge_point=wp.knowledge_point,
            mastery_rate=round(float(wp.mastery_rate or 0), 1),
            total_practiced=wp.total_practiced or 0,
            error_count=wrong_count,
            main_issue=main_issue,
            suggestion=suggestion,
            key_method=key_method,
        ))

    # 趋势判断
    trend = _compute_trend(mastery_list, db, user_id)

    return {
        "total_knowledge_points": len(mastery_list),
        "weak_points": [m.knowledge_point for m in weak_points],
        "forgetting_risks": [m.knowledge_point for m in forgetting],
        "average_mastery_rate": round(avg_rate, 1),
        "total_wrong": total_wrong,
        "recent_trend": trend,
        "mastery_details": [
            MasteryDetail(
                knowledge_point=m.knowledge_point,
                total_practiced=m.total_practiced or 0,
                correct_count=m.correct_count or 0,
                mastery_rate=float(m.mastery_rate or 0),
                is_weak_point=m.is_weak_point or False,
                forgetting_risk_score=m.forgetting_risk_score or 0,
                last_practiced_date=str(m.last_practiced_date) if m.last_practiced_date else None,
            )
            for m in mastery_list
        ],
        "error_type_stats": [s.model_dump() for s in error_type_stats],
        "weak_point_details": [w.model_dump() for w in weak_detail],
    }


@router.get("/error-analysis")
def get_error_analysis(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """错误深度分析"""
    wrong_records = db.query(UserWrongQuestion).filter(
        UserWrongQuestion.user_id == user_id,
        UserWrongQuestion.mastered == False,
    ).all()
    total_wrong = len(wrong_records)

    # 1. 错误类型统计
    error_type_counts = {}
    for et in ErrorType:
        cnt = db.query(UserWrongQuestion).filter(
            UserWrongQuestion.user_id == user_id,
            UserWrongQuestion.error_type == et.value,
            UserWrongQuestion.mastered == False,
        ).count()
        if cnt > 0:
            error_type_counts[et.value] = cnt
    total_err = sum(error_type_counts.values()) or 1
    error_type_stats = [
        ErrorTypeStat(error_type=et, count=cnt, percentage=round(cnt / total_err * 100, 1))
        for et, cnt in error_type_counts.items()
    ]

    # 2. 知识点错误热力图
    kp_heatmap = []
    mastery_map = {
        m.knowledge_point: m for m in db.query(UserKnowledgeMastery).filter(
            UserKnowledgeMastery.user_id == user_id
        ).all()
    }
    for rec in wrong_records:
        q = db.query(Question).filter(Question.question_id == rec.question_id).first()
        if q and q.knowledge_point:
            kp = q.knowledge_point
            existing = next((x for x in kp_heatmap if x["knowledge_point"] == kp), None)
            if existing:
                existing["wrong_count"] += 1
            else:
                m = mastery_map.get(kp)
                kp_heatmap.append({
                    "knowledge_point": kp,
                    "wrong_count": 1,
                    "mastery_rate": round(float(m.mastery_rate or 0), 1) if m else 0,
                })
    kp_heatmap.sort(key=lambda x: x["wrong_count"], reverse=True)

    # 3. 薄弱知识点详细建议
    mastery_list = list(mastery_map.values())
    weak_points = [m for m in mastery_list if m.is_weak_point]
    weak_detail = []
    for wp in weak_points:
        wrong_count = sum(1 for x in kp_heatmap if x["knowledge_point"] == wp.knowledge_point and x["wrong_count"])
        suggestion, main_issue, key_method = _get_weak_point_advice(wp.knowledge_point, float(wp.mastery_rate or 0))
        weak_detail.append(WeakPointSuggestion(
            knowledge_point=wp.knowledge_point,
            mastery_rate=round(float(wp.mastery_rate or 0), 1),
            total_practiced=wp.total_practiced or 0,
            error_count=wrong_count or 0,
            main_issue=main_issue,
            suggestion=suggestion,
            key_method=key_method,
        ))

    # 4. 趋势数据（近30天 vs 之前）
    thirty_days_ago = date.today() - timedelta(days=30)
    trend_data = []
    for m in mastery_list:
        recent_total = db.query(UserPracticeHistory).join(
            Question, UserPracticeHistory.question_id == Question.question_id
        ).filter(
            UserPracticeHistory.user_id == user_id,
            Question.knowledge_point == m.knowledge_point,
            UserPracticeHistory.practice_date >= thirty_days_ago,
        ).count()
        trend_data.append(MasteryTrend(
            knowledge_point=m.knowledge_point,
            current_rate=round(float(m.mastery_rate or 0), 1),
            history=[{"period": "近30天", "count": recent_total}],
        ))

    return ErrorAnalysisReport(
        total_wrong=total_wrong,
        error_type_stats=error_type_stats,
        knowledge_heatmap=kp_heatmap,
        weak_point_details=weak_detail,
        trend_data=trend_data,
    )


def _get_weak_point_advice(knowledge_point: str, mastery_rate: float):
    """生成薄弱知识点的诊断建议"""
    advice_map = {
        "分数应用题": ("找错单位\"1\"，量率不对应", "做题前先画线段图标出单位\"1\"，牢记量÷率=单位1", "画线段图 → 标单位\"1\" → 量率对应"),
        "行程问题": ("相遇/追及公式混淆", "牢记：相遇→速度和×时间=路程；追及→速度差×时间=路程差", "画路程图 → 判断相遇或追及 → 选公式"),
        "工程问题": ("工作效率概念不清", "设总量为1，工作效率=1÷时间，合作效率=效率和", "设总量→求效率→列方程"),
        "几何面积": ("割补法/辅助线思路缺失", "遇到阴影面积想：割补法→平移→旋转→总面积减空白", "割补平移旋转 → 化不规则为规则"),
        "圆柱与圆锥": ("体积公式混淆", "V圆柱=πr²h，V圆锥=⅓πr²h，等底等高时圆锥是圆柱的⅓", "先判断柱/锥 → 选公式 → 代入计算"),
        "立体几何": ("空间想象不足", "多画展开图，从二维还原三维", "画展开图 → 标已知 → 还原立体"),
        "简便运算": ("凑整/提取公因数不熟练", "熟记：125×8=1000，25×4=100，提取公因数", "观察数字特征 → 选择凑整/分配/提公因数"),
        "解方程": ("去括号/移项易错", "去括号注意变号，移项要变号，合并同类项", "去分母→去括号→移项→合并→系数化1"),
        "比和比例": ("份数法/抓不变量不熟", "统一份数法：找到公共量，统一其份数", "找公共量 → 统一份数 → 求每份"),
        "浓度问题": ("溶质/溶液/浓度关系不清", "浓度=溶质÷溶液，混合前后溶质总量不变", "列溶质守恒方程 → 求未知量"),
        "经济问题": ("成本/定价/折扣关系乱", "成本×(1+利润率)=定价，售价=定价×折扣", "找成本→算定价→乘折扣"),
        "定义新运算": ("不按规则代入，套用旧运算律", "严格按定义代入，不套用加乘交换律", "按定义代数字 → 注意运算顺序"),
        "鸡兔同笼": ("假设法运用不熟练", "假设全是某一种，算出差值，除以单差", "假设→求差→除以单差"),
        "牛吃草问题": ("生长量/原有量分不清", "先求每天生长量，再求原有量", "求日生长→求原有量→列式"),
        "逻辑推理": ("条件关系梳理不清", "用表格法或假设法，逐步排除", "列表 → 标✓✗ → 推理"),
        "找规律": ("等差/等比/周期规律分辨不清", "先作差看是否等差，再作商看是否等比", "作差→作商→找周期→验证"),
        "因数与倍数": ("质数/合数/因数倍数概念混淆", "牢记质数定义，短除法分解质因数", "短除法 → 分解质因数"),
        "GCD与LCM": ("最大公因/最小公倍方法混淆", "短除法：左边乘=GCD，左+下乘=LCM", "短除法 → 左乘=GCD → 左+下乘=LCM"),
    }
    default = ("基础概念不扎实", "建议回顾课本相关章节，多做基础练习题", "回归课本 → 做基础题 → 逐步提升")
    result = advice_map.get(knowledge_point, default)
    return result


def _compute_trend(mastery_list, db, user_id):
    """根据近期数据判断掌握度趋势"""
    if len(mastery_list) < 3:
        return "数据不足"

    avg_rate = sum(float(m.mastery_rate or 0) for m in mastery_list) / len(mastery_list)

    # 最近7天的练习量
    recent = db.query(UserPracticeHistory).filter(
        UserPracticeHistory.user_id == user_id,
        UserPracticeHistory.practice_date >= date.today() - timedelta(days=7),
    ).count()

    if recent == 0:
        return "近期未练习"

    # 判断趋势
    weak_count = sum(1 for m in mastery_list if m.is_weak_point)
    total = len(mastery_list)
    weak_ratio = weak_count / total if total > 0 else 0

    if weak_ratio < 0.2 and avg_rate > 70:
        return "稳步提升"
    elif weak_ratio < 0.4:
        return "总体向好，仍有提升空间"
    else:
        return "薄弱知识点较多，建议加强针对性练习"


def _update_mastery(user_id: int, knowledge_point: str, is_correct: bool, db: Session):
    """更新知识点掌握度"""
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
    if is_correct:
        mastery.correct_count = (mastery.correct_count or 0) + 1

    total = mastery.total_practiced or 1
    correct = mastery.correct_count or 0
    mastery.mastery_rate = round(correct / total * 100, 1)
    mastery.last_practiced_date = date.today()

    # 掌握度 < 60% 标记为薄弱点
    mastery.is_weak_point = (mastery.mastery_rate or 0) < 60

    # 遗忘风险: 距上次练习天数越多风险越高
    if mastery.last_practiced_date:
        days_since = (date.today() - mastery.last_practiced_date).days
        mastery.forgetting_risk_score = min(100, max(0, days_since * 10))
