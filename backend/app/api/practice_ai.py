"""
AI智能生成练习单的API路由
独立文件，降低被意外覆盖的风险
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    AIPracticePreviewRequest, AIPracticePreviewResponse,
    AIPracticeConfirmRequest, AIPracticeConfirmResponse,
    AIPracticeReplaceRequest, AIPracticeSupplementRequest,
    AIPracticeAdjustResponse
)
from ..utils.auth import get_current_user_id
from ..utils.practice_ai import (
    build_ai_preview, confirm_ai_sheets,
    replace_ai_question, supplement_ai_question
)

router = APIRouter(prefix="/api/practice", tags=["AI智能生成"])


@router.post("/ai-generate-preview", response_model=AIPracticePreviewResponse)
async def ai_generate_preview(
    req: AIPracticePreviewRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """AI生成练习单预览"""
    return await build_ai_preview(req, user_id, db)


@router.post("/ai-generate-confirm", response_model=AIPracticeConfirmResponse)
def ai_generate_confirm(
    req: AIPracticeConfirmRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """确认并创建AI生成的练习单"""
    return confirm_ai_sheets(req, user_id, db)


@router.post("/ai-replace-question", response_model=AIPracticeAdjustResponse)
def ai_replace_question_endpoint(
    req: AIPracticeReplaceRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """替换AI练习单中的某道题"""
    return replace_ai_question(req, user_id, db)


@router.post("/ai-supplement-question", response_model=AIPracticeAdjustResponse)
def ai_supplement_question_endpoint(
    req: AIPracticeSupplementRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """为AI练习单补充题目"""
    return supplement_ai_question(req, user_id, db)
