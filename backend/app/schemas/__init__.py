from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import date, datetime


# ===================== User =====================

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    email: Optional[str] = None
    phone: Optional[str] = None
    real_name: Optional[str] = None
    grade_level: Optional[str] = "六年级"


class UserLogin(BaseModel):
    username: str
    password: str


class UserProfile(BaseModel):
    user_id: int
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    real_name: Optional[str] = None
    grade_level: Optional[str] = None
    member_type: str = "free"
    member_expire_date: Optional[datetime] = None
    register_date: Optional[datetime] = None

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile


# ===================== Question =====================

class QuestionCreate(BaseModel):
    q_id: Optional[str] = None
    knowledge_point: str
    knowledge_category: Optional[str] = None
    question_type: Optional[str] = None
    difficulty: Optional[str] = "中等"
    question_text: str
    answer: Optional[str] = None
    solution: Optional[str] = None
    has_image: bool = False
    image_path: Optional[str] = None
    source_school: Optional[str] = None
    source_exam: Optional[str] = None
    source_number: Optional[str] = None
    exam_year: Optional[str] = "2025"
    grade_level: Optional[str] = "六年级"
    is_key_point: bool = False
    is_difficult: bool = False
    is_high_freq: bool = False


class BatchImportRequest(BaseModel):
    questions: List[QuestionCreate]
    auto_generate_id: bool = True

class QuestionOut(BaseModel):
    question_id: int
    q_id: str
    knowledge_point: str
    knowledge_category: Optional[str] = None
    question_type: Optional[str] = None
    difficulty: Optional[str] = None
    question_text: str
    answer: Optional[str] = None
    solution: Optional[str] = None
    has_image: bool = False
    image_path: Optional[str] = None
    source_school: Optional[str] = None
    source_exam: Optional[str] = None
    source_number: Optional[str] = None
    exam_year: Optional[str] = None
    grade_level: Optional[str] = "六年级"
    is_key_point: bool = False
    is_difficult: bool = False
    is_high_freq: bool = False
    verification_status: str = "pending"

    class Config:
        from_attributes = True


class QuestionListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    questions: List[QuestionOut]


class BatchDeleteRequest(BaseModel):
    question_ids: List[int]


# ===================== Wrong Question =====================

class WrongQuestionCreate(BaseModel):
    question_id: int
    exam_name: Optional[str] = None
    exam_date: Optional[date] = None
    error_type: Optional[str] = None
    notes: Optional[str] = None


class WrongQuestionFeedback(BaseModel):
    record_id: int
    is_correct: bool
    error_type: Optional[str] = None


# ===================== Practice Sheet =====================

class KnowledgeGroupCount(BaseModel):
    """按知识点分组指定选题数量"""
    knowledge_category: Optional[str] = None
    knowledge_points: List[str]
    count: int = 1


class GenerateSheetRequest(BaseModel):
    sheet_type: str = "daily"
    total_questions: int = 8
    knowledge_points: Optional[List[str]] = None
    difficulties: Optional[List[str]] = None
    sheet_name: Optional[str] = None
    question_ids: Optional[List[int]] = None
    knowledge_group_counts: Optional[List[KnowledgeGroupCount]] = None


class SubmitAnswer(BaseModel):
    question_id: int
    user_answer: str


class SubmitSheetRequest(BaseModel):
    answers: List[SubmitAnswer]


class GenerateWrongPeriodRequest(BaseModel):
    """按时间段生成错题练习单"""
    name: Optional[str] = None
    start_date: date
    end_date: date
    difficulty: Optional[List[str]] = None
    question_types: Optional[List[str]] = None
    only_unmastered: bool = True
    sheet_count: int = 1
    questions_per_sheet: Optional[int] = None
    type_counts: Optional[dict] = None  # {"calculation": 4, "fill_blank": 3, ...} 每卷各题型数量


class SmartRedoRequest(BaseModel):
    """智慧错题重练请求"""
    name: Optional[str] = None
    calculation_count: int = 2
    wrong_question_count: int = 3
    similar_question_count: int = 2
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    strategy: str = "smart"
    difficulty: Optional[List[str]] = None
    question_types: Optional[List[str]] = None
    only_unmastered: bool = True
    exclude_recent_days: int = 3


class QuestionResultOut(BaseModel):
    question_id: int
    question_order: int
    question_text: str
    knowledge_point: str
    difficulty: Optional[str] = None
    user_answer: str
    correct_answer: Optional[str] = None
    is_correct: bool
    solution: Optional[str] = None


class SubmitResultOut(BaseModel):
    sheet_id: int
    total: int
    correct_count: int
    wrong_count: int
    score: float
    results: List[QuestionResultOut]
    wrong_question_ids: List[int] = []


class MarkItem(BaseModel):
    question_id: int
    is_correct: bool
    error_type: Optional[str] = None


class MarkSheetRequest(BaseModel):
    marks: List[MarkItem]


class PracticeSheetOut(BaseModel):
    sheet_id: int
    sheet_name: Optional[str] = None
    sheet_type: str
    total_questions: int
    estimated_time: Optional[int] = None
    generated_date: Optional[datetime] = None
    completed: bool = False
    completed_date: Optional[datetime] = None
    score: Optional[float] = None
    questions: List[QuestionOut] = []

    class Config:
        from_attributes = True


# ===================== Member / Order =====================

class CreateOrderRequest(BaseModel):
    member_type: str = Field(..., pattern="^(basic|premium)$")
    duration_months: int = Field(..., ge=1, le=12)
    payment_method: str = Field(..., pattern="^(wechat|alipay)$")


class OrderOut(BaseModel):
    order_id: int
    order_no: str
    member_type: str
    duration_months: int
    amount: float
    payment_method: Optional[str] = None
    payment_status: str = "pending"
    created_date: Optional[datetime] = None
    paid_date: Optional[datetime] = None

    class Config:
        from_attributes = True


# ===================== Diagnosis =====================

class MasteryDetail(BaseModel):
    knowledge_point: str
    total_practiced: int = 0
    correct_count: int = 0
    mastery_rate: float = 0.0
    is_weak_point: bool = False
    forgetting_risk_score: int = 0
    last_practiced_date: Optional[str] = None

    class Config:
        from_attributes = True


class DiagnosisReport(BaseModel):
    total_knowledge_points: int = 0
    weak_points: List[str] = []
    forgetting_risks: List[str] = []
    average_mastery_rate: float = 0.0
    total_wrong: int = 0
    recent_trend: str = "数据不足"
    mastery_details: List[MasteryDetail] = []


class ErrorTypeStat(BaseModel):
    error_type: str
    count: int
    percentage: float = 0.0


class WeakPointSuggestion(BaseModel):
    knowledge_point: str
    mastery_rate: float
    total_practiced: int
    error_count: int
    main_issue: str = ""
    suggestion: str = ""
    key_method: str = ""


class MasteryTrend(BaseModel):
    knowledge_point: str
    current_rate: float
    history: List[dict] = []


class ErrorAnalysisReport(BaseModel):
    total_wrong: int = 0
    error_type_stats: List[ErrorTypeStat] = []
    knowledge_heatmap: List[dict] = []
    weak_point_details: List[WeakPointSuggestion] = []
    trend_data: List[MasteryTrend] = []


# ===================== Week Practice =====================

class DaySheetOut(BaseModel):
    day_label: str
    sheet: PracticeSheetOut


class GenerateWeekResponse(BaseModel):
    week_start: str
    week_end: str
    total_questions: int
    total_time: int
    sheets: List[DaySheetOut]


# ===================== Answer Generation & Dedup =====================

class AnswerGenerateRequest(BaseModel):
    question_text: str
    question_type: Optional[str] = None
    knowledge_point: Optional[str] = None


class AnswerGenerateResponse(BaseModel):
    answer: str = ""
    solution: str = ""


class DupCheckRequest(BaseModel):
    question_text: str


class DupCheckResponse(BaseModel):
    in_bank: bool = False
    in_wrong_questions: bool = False
    matched_question_id: Optional[int] = None
    matched_question: Optional[QuestionOut] = None
    similarity: float = 0.0


# ===================== Advanced Recognition =====================

class RecognizeAdvancedRequest(BaseModel):
    recognition_mode: str = "auto"  # normal, corrected_paper, auto
    use_ai_model: bool = True
    remove_correction_marks: bool = True
    segment_questions: bool = True
    match_question_bank: bool = True
    exam_name: Optional[str] = None
    exam_date: Optional[str] = None


class AiResultOut(BaseModel):
    question_text: str = ""
    answer: str = ""
    solution: str = ""
    question_type: str = ""
    knowledge_points: List[str] = []
    difficulty: str = ""
    keywords: List[str] = []
    has_diagram: bool = False
    diagram_description: str = ""
    is_complete: bool = True
    unclear_parts: List[str] = []
    confidence: float = 0.0


class MatchedQuestionOut(BaseModel):
    question_id: int
    similarity: float = 0.0
    question_text: str = ""
    knowledge_point: str = ""
    difficulty: str = ""


class RecognitionBlockOut(BaseModel):
    block_id: str = ""
    page_no: int = 1
    question_no: str = ""
    bbox: List[float] = []
    crop_image_url: str = ""
    clean_crop_image_url: str = ""
    ai_result: Optional[AiResultOut] = None
    ai_answer: str = ""
    ai_solution: str = ""
    matched_questions: List[MatchedQuestionOut] = []
    suggested_action: str = "need_confirm"
    need_manual_confirm: bool = True


class RecognitionPageOut(BaseModel):
    page_no: int = 1
    image_url: str = ""
    clean_image_url: str = ""
    questions: List[RecognitionBlockOut] = []


class RecognizeAdvancedResponse(BaseModel):
    task_id: int = 0
    status: str = "need_confirm"
    file_type: str = ""
    page_count: int = 0
    pages: List[RecognitionPageOut] = []


class ConfirmItem(BaseModel):
    block_id: str = ""
    matched_question_id: Optional[int] = None
    error_type: Optional[str] = None
    remark: Optional[str] = None
    exam_name: Optional[str] = None
    exam_date: Optional[str] = None


class ConfirmRecognitionRequest(BaseModel):
    items: List[ConfirmItem]


class RecognitionTaskOut(BaseModel):
    id: int
    user_id: int
    file_url: str
    file_type: Optional[str] = None
    recognition_mode: Optional[str] = None
    status: str = "pending"
    page_count: int = 1
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


# ===================== AI Practice =====================

class AIPracticePreviewRequest(BaseModel):
    prompt: str = Field("", max_length=2000)
    sheet_name: str = ""
    sheet_type: str = "special_topic"
    sheet_count: int = Field(1, ge=1, le=5)
    target_count: int = Field(8, ge=4, le=24)
    target_minutes: Optional[int] = Field(None, ge=10, le=120)
    knowledge_categories: List[str] = Field(default_factory=list)
    knowledge_points: List[str] = Field(default_factory=list)
    question_types: List[str] = Field(default_factory=list)
    question_type_counts: Dict[str, int] = Field(default_factory=dict)
    exclude_question_types: List[str] = Field(default_factory=list)
    difficulties: List[str] = Field(default_factory=list)
    difficulty_progression: bool = True
    must_include_wrong_questions: bool = False
    avoid_recent_questions: bool = True


class AIParsedRequirement(BaseModel):
    sheet_name: str = ""
    sheet_type: str = "special_topic"
    sheet_count: int = 1
    target_count: int = 8
    target_minutes: Optional[int] = None
    knowledge_categories: List[str] = Field(default_factory=list)
    knowledge_points: List[str] = Field(default_factory=list)
    question_types: List[str] = Field(default_factory=list)
    question_type_counts: Dict[str, int] = Field(default_factory=dict)
    exclude_question_types: List[str] = Field(default_factory=list)
    difficulties: List[str] = Field(default_factory=list)
    difficulty_progression: bool = True
    must_include_wrong_questions: bool = False
    avoid_recent_questions: bool = True
    strategy_hint: str = ""
    reasoning_summary: str = ""
    learning_advice: str = ""


class AIPracticeSuggestion(BaseModel):
    summary: str = ""
    selection_reason: str = ""
    ordering_reason: str = ""
    coverage_summary: str = ""
    explanation_lines: List[str] = Field(default_factory=list)
    review_summary: str = ""


class AISelectedQuestion(BaseModel):
    question_id: int
    q_id: str
    knowledge_point: str
    knowledge_category: Optional[str] = None
    question_type: Optional[str] = None
    difficulty: Optional[str] = None
    question_text: str
    has_image: bool = False
    image_path: Optional[str] = None
    selected_reason: str = ""


class AIPracticeVariant(BaseModel):
    variant_id: str
    sheet_name: str = ""
    selected_questions: List[AISelectedQuestion] = Field(default_factory=list)
    estimated_time: int = 0
    composition_summary: str = ""
    coverage_summary: str = ""
    review_summary: str = ""


class AIPracticePreviewResponse(BaseModel):
    parsed_requirement: AIParsedRequirement
    suggestion: AIPracticeSuggestion
    variants: List[AIPracticeVariant] = Field(default_factory=list)
    selected_questions: List[AISelectedQuestion] = Field(default_factory=list)
    candidate_count: int = 0
    estimated_time: int = 0
    total_variants: int = 1


class AIPracticeConfirmVariant(BaseModel):
    variant_id: Optional[str] = None
    sheet_name: Optional[str] = None
    question_ids: List[int] = Field(default_factory=list, min_length=1)


class AIPracticeConfirmRequest(BaseModel):
    sheet_name: Optional[str] = None
    sheet_type: str = "special_topic"
    question_ids: List[int] = Field(default_factory=list)
    variants: List[AIPracticeConfirmVariant] = Field(default_factory=list)


class AIPracticeConfirmResponse(BaseModel):
    created_count: int = 0
    sheets: List["PracticeSheetOut"] = Field(default_factory=list)


class AIPracticeReplaceRequest(BaseModel):
    parsed_requirement: AIParsedRequirement
    current_question_ids: List[int] = Field(default_factory=list)
    replace_question_id: int
    replace_mode: str = "balanced"


class AIPracticeSupplementRequest(BaseModel):
    parsed_requirement: AIParsedRequirement
    current_question_ids: List[int] = Field(default_factory=list)


class AIPracticeAdjustResponse(BaseModel):
    question: AISelectedQuestion
    estimated_time: int = 0
    review_hint: str = ""
