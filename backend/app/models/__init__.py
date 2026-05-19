from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, DECIMAL, Date, ForeignKey, func
from sqlalchemy.orm import relationship
from ..database import Base
import enum


# ===================== Enums =====================

class MemberType(str, enum.Enum):
    free = "free"
    basic = "basic"
    premium = "premium"

class UserStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"

class QuestionType(str, enum.Enum):
    fill_blank = "fill_blank"
    choice = "choice"
    problem_solving = "problem_solving"
    calculation = "calculation"

class Difficulty(str, enum.Enum):
    basic = "基础"
    medium = "中等"
    hard = "挑战"

class VerificationStatus(str, enum.Enum):
    pending = "pending"
    ai_generated = "ai_generated"
    verified = "verified"
    needs_review = "needs_review"

class ErrorType(str, enum.Enum):
    concept = "概念错误"
    calculation = "计算错误"
    reading = "审题错误"
    method = "方法错误"
    other = "其他"

class PracticeType(str, enum.Enum):
    daily = "daily"
    wrong_redo = "wrong_redo"
    special_topic = "special_topic"
    exam = "exam"

class SheetType(str, enum.Enum):
    daily = "daily"
    wrong_redo = "wrong_redo"
    special_topic = "special_topic"
    custom = "custom"

class PaymentMethod(str, enum.Enum):
    wechat = "wechat"
    alipay = "alipay"
    balance = "balance"

class PaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"
    refunded = "refunded"


# ===================== Models =====================

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True)
    phone = Column(String(20))
    real_name = Column(String(50))
    grade_level = Column(String(20))
    member_type = Column(String(20), default=MemberType.free.value)
    member_expire_date = Column(DateTime)
    register_date = Column(DateTime, server_default=func.now())
    last_login = Column(DateTime)
    status = Column(String(20), default=UserStatus.active.value)

    wrong_questions = relationship("UserWrongQuestion", back_populates="user")
    knowledge_mastery = relationship("UserKnowledgeMastery", back_populates="user")
    practice_history = relationship("UserPracticeHistory", back_populates="user")
    practice_sheets = relationship("PracticeSheet", back_populates="user")
    orders = relationship("MemberOrder", back_populates="user")


class Question(Base):
    __tablename__ = "questions"

    question_id = Column(Integer, primary_key=True, autoincrement=True)
    q_id = Column(String(50), unique=True, nullable=False)
    knowledge_point = Column(String(100), nullable=False)
    knowledge_category = Column(String(50))
    question_type = Column(String(30))
    difficulty = Column(String(10))
    question_text = Column(Text, nullable=False)
    answer = Column(Text)
    solution = Column(Text)
    has_image = Column(Boolean, default=False)
    image_path = Column(String(255))
    image_caption = Column(String(255))
    source_school = Column(String(100))
    source_exam = Column(String(100))
    source_number = Column(String(50))
    exam_year = Column(String(10))
    grade_level = Column(String(20), default="六年级")
    is_key_point = Column(Boolean, default=False)
    is_difficult = Column(Boolean, default=False)
    is_high_freq = Column(Boolean, default=False)
    is_classic = Column(Boolean, default=False)
    verification_status = Column(String(20), default=VerificationStatus.pending.value)
    variation_of = Column(Integer)
    created_date = Column(DateTime, server_default=func.now())
    updated_date = Column(DateTime, onupdate=func.now())
    global_usage_count = Column(Integer, default=0)

    wrong_questions = relationship("UserWrongQuestion", back_populates="question")
    practice_history = relationship("UserPracticeHistory", back_populates="question")
    sheet_questions = relationship("SheetQuestion", back_populates="question")


class UserWrongQuestion(Base):
    __tablename__ = "user_wrong_questions"

    record_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.question_id"), nullable=False)
    exam_name = Column(String(100))
    exam_date = Column(Date)
    is_correct = Column(Boolean, default=False)
    error_type = Column(String(20))
    redo_count = Column(Integer, default=0)
    last_redo_date = Column(Date)
    mastered = Column(Boolean, default=False)
    notes = Column(Text)
    created_date = Column(DateTime, server_default=func.now())
    # 识别增强字段
    original_image_url = Column(String(500))
    clean_image_url = Column(String(500))
    crop_image_url = Column(String(500))
    recognition_task_id = Column(Integer)
    ai_confidence = Column(Integer)  # 0-100

    user = relationship("User", back_populates="wrong_questions")
    question = relationship("Question", back_populates="wrong_questions")


class WrongQuestionRecognitionTask(Base):
    """错题识别任务表"""
    __tablename__ = "wrong_question_recognition_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    file_url = Column(String(500), nullable=False)
    file_type = Column(String(30))
    recognition_mode = Column(String(50))
    status = Column(String(30), default="pending")
    page_count = Column(Integer, default=1)
    raw_result = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    blocks = relationship("WrongQuestionRecognitionBlock", back_populates="task",
                          cascade="all, delete-orphan")


class WrongQuestionRecognitionBlock(Base):
    """识别题块表 - 每道题一个块"""
    __tablename__ = "wrong_question_recognition_blocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("wrong_question_recognition_tasks.id", ondelete="CASCADE"), nullable=False)
    page_no = Column(Integer, default=1)
    question_no = Column(String(20))
    bbox = Column(String(200))  # JSON array
    crop_image_url = Column(String(500))
    clean_crop_image_url = Column(String(500))
    question_image_urls = Column(Text)  # JSON array - images embedded in the question itself
    ai_question_text = Column(Text)
    ai_answer = Column(Text)  # AI generated answer
    ai_solution = Column(Text)  # AI generated solution/explanation
    ai_question_type = Column(String(50))
    ai_knowledge_points = Column(String(500))  # JSON array
    ai_difficulty = Column(String(20))
    ai_keywords = Column(String(500))  # JSON array
    ai_confidence = Column(Integer)
    matched_question_id = Column(Integer)
    match_confidence = Column(Integer)
    status = Column(String(30), default="need_confirm")
    created_at = Column(DateTime, server_default=func.now())

    task = relationship("WrongQuestionRecognitionTask", back_populates="blocks")


class UserKnowledgeMastery(Base):
    __tablename__ = "user_knowledge_mastery"

    mastery_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    knowledge_point = Column(String(100), nullable=False)
    total_practiced = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    mastery_rate = Column(DECIMAL(5, 2))
    last_practiced_date = Column(Date)
    forgetting_risk_score = Column(Integer, default=0)
    is_weak_point = Column(Boolean, default=False)
    updated_date = Column(DateTime, onupdate=func.now())

    user = relationship("User", back_populates="knowledge_mastery")


class UserPracticeHistory(Base):
    __tablename__ = "user_practice_history"

    history_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.question_id"), nullable=False)
    practice_date = Column(Date, nullable=False)
    is_correct = Column(Boolean)
    time_spent = Column(Integer)
    practice_type = Column(String(20))
    sheet_id = Column(Integer)

    user = relationship("User", back_populates="practice_history")
    question = relationship("Question", back_populates="practice_history")


class PracticeSheet(Base):
    __tablename__ = "practice_sheets"

    sheet_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    sheet_name = Column(String(100))
    sheet_type = Column(String(30))
    total_questions = Column(Integer)
    estimated_time = Column(Integer)
    generated_date = Column(DateTime, server_default=func.now())
    completed = Column(Boolean, default=False)
    completed_date = Column(DateTime)
    score = Column(DECIMAL(5, 2))
    sections_json = Column(Text)

    user = relationship("User", back_populates="practice_sheets")
    sheet_questions = relationship("SheetQuestion", back_populates="sheet")


class SheetQuestion(Base):
    __tablename__ = "sheet_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sheet_id = Column(Integer, ForeignKey("practice_sheets.sheet_id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.question_id"), nullable=False)
    question_order = Column(Integer)
    is_correct = Column(Boolean)
    user_answer = Column(Text)

    sheet = relationship("PracticeSheet", back_populates="sheet_questions")
    question = relationship("Question", back_populates="sheet_questions")


class MemberOrder(Base):
    __tablename__ = "member_orders"

    order_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    order_no = Column(String(50), unique=True, nullable=False)
    member_type = Column(String(20))
    duration_months = Column(Integer)
    amount = Column(DECIMAL(10, 2))
    payment_method = Column(String(20))
    payment_status = Column(String(20), default=PaymentStatus.pending.value)
    transaction_id = Column(String(100))
    created_date = Column(DateTime, server_default=func.now())
    paid_date = Column(DateTime)

    user = relationship("User", back_populates="orders")
