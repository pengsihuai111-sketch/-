import logging
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional, List
import re, os, uuid, traceback

from ..database import get_db
from ..models import Question, UserWrongQuestion, UserWrongQuestion as WrongQuestion, UserPracticeHistory, SheetQuestion
from ..schemas import QuestionOut, QuestionListResponse, QuestionCreate, BatchImportRequest, WrongQuestionCreate, BatchDeleteRequest
from ..utils.auth import get_current_user_id
from ..utils.deepseek import recognize_questions
from ..utils.pdf_processor import pdf_to_images
from ..config import IMAGE_DIR

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/questions", tags=["题库"])


@router.get("")
def list_questions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    knowledge_point: Optional[str] = None,
    knowledge_category: Optional[str] = None,
    difficulty: Optional[str] = None,
    question_type: Optional[str] = None,
    grade_level: Optional[str] = None,
    keyword: Optional[str] = None,
    sort_by: Optional[str] = Query("question_id"),
    sort_order: Optional[str] = Query("asc"),
    db: Session = Depends(get_db),
):
    query = db.query(Question)

    if knowledge_point:
        query = query.filter(Question.knowledge_point == knowledge_point)
    if knowledge_category:
        query = query.filter(Question.knowledge_category == knowledge_category)
    if difficulty:
        query = query.filter(Question.difficulty == difficulty)
    if question_type:
        query = query.filter(Question.question_type == question_type)
    if grade_level:
        query = query.filter(Question.grade_level == grade_level)
    if keyword:
        query = query.filter(Question.question_text.contains(keyword))

    # 排序
    if sort_by not in ("question_id", "q_id"):
        sort_by = "question_id"
    if sort_order not in ("asc", "desc"):
        sort_order = "asc"
    order_col = Question.question_id if sort_by == "question_id" else Question.q_id
    if sort_order == "desc":
        order_col = order_col.desc()

    total = query.count()
    questions = query.order_by(order_col).offset((page - 1) * page_size).limit(page_size).all()

    return QuestionListResponse(
        total=total,
        page=page,
        page_size=page_size,
        questions=[QuestionOut.model_validate(q) for q in questions],
    )


@router.post("/recognize-pdf")
async def recognize_questions_from_pdf(
    file: UploadFile = File(...),
    use_markdown: bool = True,
    user_id: int = Depends(get_current_user_id),
):
    """上传 PDF，识别题目

    Args:
        file: PDF文件
        use_markdown: 是否使用Markdown方式（推荐）。
                     True: PDF→文本→LLM提取（更准确、更快、更便宜）
                     False: PDF→图片→视觉识别（适合扫描件、手写）
    """
    logger.info(f"PDF recognize request: file={file.filename}, use_markdown={use_markdown}, user_id={user_id}")

    if file.content_type not in ("application/pdf", "application/octet-stream"):
        # Allow octet-stream since some browsers send that for PDFs
        if not (file.filename and file.filename.lower().endswith(".pdf")):
            raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    # Read PDF
    pdf_bytes = await file.read()
    logger.info(f"PDF read: {len(pdf_bytes)} bytes")

    if len(pdf_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="PDF 大小不能超过 50MB")

    # Method 1: Markdown-based extraction (recommended)
    if use_markdown:
        try:
            from ..utils.pdf_to_markdown import (
                pdf_to_markdown,
                extract_questions_from_markdown,
                detect_has_images,
            )
            from ..utils.deepseek import _call_text_llm

            logger.info("Using markdown-based PDF extraction")

            # Convert PDF to markdown
            markdown_text = pdf_to_markdown(pdf_bytes)
            logger.info(f"PDF converted to markdown: {len(markdown_text)} chars")

            # Detect if PDF contains images
            page_images = detect_has_images(pdf_bytes)
            has_images = any(page_images.values())

            if has_images:
                logger.warning(f"PDF contains images on {sum(page_images.values())} pages - may need manual review")

            # Extract questions from markdown using LLM
            questions = await extract_questions_from_markdown(markdown_text, _call_text_llm)
            logger.info(f"Extracted {len(questions)} questions from markdown")

            # Collect quality metrics
            quality_warnings = []
            low_confidence_count = 0
            incomplete_count = 0

            for q in questions:
                if not q.get("is_complete", True):
                    incomplete_count += 1
                if q.get("confidence", 1.0) < 0.7:
                    low_confidence_count += 1
                if q.get("quality_issues"):
                    quality_warnings.extend(q["quality_issues"])

            return {
                "message": f"识别完成，共 {len(questions)} 道题",
                "method": "markdown",
                "questions": questions,
                "has_images": has_images,
                "quality_summary": {
                    "total_questions": len(questions),
                    "incomplete_questions": incomplete_count,
                    "low_confidence_questions": low_confidence_count,
                    "has_quality_issues": len(quality_warnings) > 0,
                    "pdf_has_images": has_images,
                },
                "quality_warnings": list(set(quality_warnings)) if quality_warnings else [],
            }

        except Exception as e:
            logger.error(f"Markdown-based extraction failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"PDF 文本提取失败: {str(e)}")

    # Method 2: Image-based recognition (fallback for scanned PDFs)
    else:
        try:
            page_images = pdf_to_images(pdf_bytes)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"PDF processing error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"PDF 处理失败: {str(e)}")

        total_pages = len(page_images)
        logger.info(f"PDF converted: {total_pages} pages")

        # Process each page through AI
        all_questions = []
        page_results = []
        has_error = False
        total_quality_issues = 0

        for page_num, img_bytes in enumerate(page_images):
            logger.info(f"Processing page {page_num + 1}/{total_pages}...")
            try:
                questions = await recognize_questions(img_bytes, f"page_{page_num + 1}.jpg")
                n = len(questions)
                logger.info(f"Page {page_num + 1}: {n} questions found")

                # Collect quality metrics for this page
                page_quality_issues = 0
                low_confidence = 0
                incomplete = 0

                for q in questions:
                    if q.get("quality_issues"):
                        page_quality_issues += len(q["quality_issues"])
                    if not q.get("is_complete", True):
                        incomplete += 1
                    if q.get("confidence", 1.0) < 0.7:
                        low_confidence += 1

                all_questions.extend(questions)
                total_quality_issues += page_quality_issues

                page_results.append({
                    "page": page_num + 1,
                    "status": "ok",
                    "count": n,
                    "quality_metrics": {
                        "incomplete_questions": incomplete,
                        "low_confidence_questions": low_confidence,
                        "quality_issues_count": page_quality_issues,
                    }
                })

            except ValueError as e:
                logger.warning(f"Page {page_num + 1} parse error: {e}")
                page_results.append({
                    "page": page_num + 1,
                    "status": "parse_error",
                    "error": str(e)[:200],
                    "count": 0,
                })
            except RuntimeError as e:
                logger.error(f"Page {page_num + 1} API error: {e}")
                has_error = True
                page_results.append({
                    "page": page_num + 1,
                    "status": "api_error",
                    "error": str(e)[:200],
                    "count": 0,
                })
                break  # Stop on API error

        return {
            "message": f"识别完成，共处理 {total_pages} 页，识别 {len(all_questions)} 道题",
            "method": "image",
            "total_pages": total_pages,
            "page_results": page_results,
            "questions": all_questions,
            "has_error": has_error,
            "quality_summary": {
                "total_questions": len(all_questions),
                "total_quality_issues": total_quality_issues,
                "pages_with_errors": sum(1 for p in page_results if p["status"] != "ok"),
            }
        }


@router.get("/stats")
def get_question_stats(db: Session = Depends(get_db)):
    """题库统计数据"""
    total = db.query(Question).count()
    verified = db.query(Question).filter(Question.verification_status == "verified").count()
    with_image = db.query(Question).filter(Question.has_image == True).count()

    by_difficulty = {}
    diff_rows = db.query(Question.difficulty, func.count()).group_by(Question.difficulty).all()
    for d, c in diff_rows:
        key = {"基础": "basic", "中等": "medium", "挑战": "hard"}.get(d, d)
        by_difficulty[key] = c

    return {
        "total_questions": total,
        "verified_answers": verified,
        "with_image": with_image,
        "by_difficulty": by_difficulty,
    }


@router.get("/{question_id}")
def get_question(question_id: int, db: Session = Depends(get_db)):
    q = db.query(Question).filter(Question.question_id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")
    return QuestionOut.model_validate(q)


@router.get("/knowledge-points/list")
def list_knowledge_points(db: Session = Depends(get_db)):
    results = db.query(
        Question.knowledge_point,
        Question.knowledge_category,
    ).distinct().all()

    kp_list = {}
    for kp, cat in results:
        if cat not in kp_list:
            kp_list[cat] = []
        kp_list[cat].append(kp)

    return {"knowledge_points": kp_list}


@router.get("/categories/list")
def list_categories(db: Session = Depends(get_db)):
    results = db.query(Question.knowledge_category).distinct().all()
    categories = [r[0] for r in results if r[0]]
    return {"categories": categories}


@router.get("/grades/list")
def list_grades(db: Session = Depends(get_db)):
    results = db.query(Question.grade_level).distinct().order_by(Question.grade_level).all()
    grades = [r[0] for r in results if r[0]]
    return {"grades": grades}


def _generate_q_id(knowledge_point: str, db: Session) -> str:
    """自动生成 q_id，格式: KP_序号"""
    prefix = re.sub(r'[\s\-]', '_', knowledge_point)[:10]
    existing = db.query(Question.q_id).filter(
        Question.q_id.like(f"{prefix}%")
    ).all()
    nums = []
    for eid in existing:
        m = re.search(r'_(\d+)$', eid[0])
        if m:
            nums.append(int(m.group(1)))
    next_num = max(nums) + 1 if nums else 1
    return f"{prefix}_{next_num}"


@router.post("")
def create_question(
    req: QuestionCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """录入单道题目"""
    q_id = req.q_id
    if not q_id:
        q_id = _generate_q_id(req.knowledge_point, db)

    # 检查 q_id 是否已存在
    existing = db.query(Question).filter(Question.q_id == q_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"题目编号 {q_id} 已存在")

    q = Question(
        q_id=q_id,
        knowledge_point=req.knowledge_point,
        knowledge_category=req.knowledge_category,
        question_type=req.question_type,
        difficulty=req.difficulty or "中等",
        question_text=req.question_text,
        answer=req.answer,
        solution=req.solution,
        has_image=req.has_image,
        image_path=req.image_path,
        source_school=req.source_school,
        source_exam=req.source_exam,
        source_number=req.source_number,
        exam_year=req.exam_year or "2025",
        grade_level=req.grade_level or "六年级",
        is_key_point=req.is_key_point,
        is_difficult=req.is_difficult,
        is_high_freq=req.is_high_freq,
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return QuestionOut.model_validate(q)


@router.post("/batch")
def batch_import(
    req: BatchImportRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """批量导入题目"""
    created = []
    errors = []

    for i, item in enumerate(req.questions):
        try:
            q_id = item.q_id
            if not q_id or req.auto_generate_id:
                q_id = _generate_q_id(item.knowledge_point, db)

            existing = db.query(Question).filter(Question.q_id == q_id).first()
            if existing:
                errors.append({"index": i, "q_id": q_id, "error": "编号已存在"})
                continue

            q = Question(
                q_id=q_id,
                knowledge_point=item.knowledge_point,
                knowledge_category=item.knowledge_category,
                question_type=item.question_type,
                difficulty=item.difficulty or "中等",
                question_text=item.question_text,
                answer=item.answer,
                solution=item.solution,
                has_image=item.has_image,
                image_path=item.image_path,
                source_school=item.source_school,
                source_exam=item.source_exam,
                source_number=item.source_number,
                exam_year=item.exam_year or "2025",
                grade_level=item.grade_level or "六年级",
                is_key_point=item.is_key_point,
                is_difficult=item.is_difficult,
                is_high_freq=item.is_high_freq,
            )
            db.add(q)
            db.flush()
            created.append(QuestionOut.model_validate(q))
        except Exception as e:
            errors.append({"index": i, "q_id": q_id, "error": str(e)})

    db.commit()
    return {
        "total": len(req.questions),
        "success_count": len(created),
        "error_count": len(errors),
        "questions": created,
        "errors": errors,
    }


@router.post("/upload-image")
async def upload_question_image(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
):
    """上传题目图片，返回图片访问 URL"""
    try:
        logger.info(f"收到图片上传请求: filename={file.filename}, content_type={file.content_type}")

        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="仅支持图片文件")

        image_bytes = await file.read()
        logger.info(f"读取图片数据: size={len(image_bytes)} bytes")

        if len(image_bytes) > 20 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="图片大小不能超过 20MB")

        import uuid
        os.makedirs(IMAGE_DIR, exist_ok=True)
        ext = os.path.splitext(file.filename or "image.png")[1] or ".png"
        saved_name = f"qimg_{uuid.uuid4().hex[:8]}{ext}"
        saved_path = os.path.join(IMAGE_DIR, saved_name)

        logger.info(f"保存图片到: {saved_path}")
        with open(saved_path, "wb") as f:
            f.write(image_bytes)

        logger.info(f"图片上传成功: {saved_name}")
        return {
            "url": f"/uploads/images/{saved_name}",
            "filename": saved_name,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"图片上传失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"图片上传失败: {str(e)}")


@router.delete("/{question_id}")
def delete_question(
    question_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """删除单道题目（同时清理关联的错题记录、练习记录等）"""
    q = db.query(Question).filter(Question.question_id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")
    # 先清理关联记录避免外键约束
    db.query(UserWrongQuestion).filter(UserWrongQuestion.question_id == question_id).delete(synchronize_session=False)
    db.query(UserPracticeHistory).filter(UserPracticeHistory.question_id == question_id).delete(synchronize_session=False)
    db.query(SheetQuestion).filter(SheetQuestion.question_id == question_id).delete(synchronize_session=False)
    db.delete(q)
    db.commit()
    return {"message": "题目已删除"}


@router.post("/batch-delete")
def batch_delete_questions(
    req: BatchDeleteRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """批量删除题目（同时清理关联记录）"""
    qids = req.question_ids
    if not qids:
        raise HTTPException(status_code=400, detail="请指定要删除的题目ID")
    # 先清理关联记录
    db.query(UserWrongQuestion).filter(UserWrongQuestion.question_id.in_(qids)).delete(synchronize_session=False)
    db.query(UserPracticeHistory).filter(UserPracticeHistory.question_id.in_(qids)).delete(synchronize_session=False)
    db.query(SheetQuestion).filter(SheetQuestion.question_id.in_(qids)).delete(synchronize_session=False)
    deleted = db.query(Question).filter(Question.question_id.in_(qids)).delete(synchronize_session=False)
    db.commit()
    return {"message": f"已删除 {deleted} 道题目"}
