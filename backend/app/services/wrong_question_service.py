"""
错题管理服务
处理错题的增删改查、反馈、去重等业务逻辑
"""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from datetime import datetime, date

from ..models import UserWrongQuestion, Question, UserKnowledgeMastery
from ..repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class WrongQuestionService:
    """错题管理服务"""

    def __init__(self, db: Session):
        self.db = db
        self.wrong_question_repo = BaseRepository(UserWrongQuestion, db)
        self.question_repo = BaseRepository(Question, db)

    def list_wrong_questions(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        knowledge_point: Optional[str] = None,
        difficulty: Optional[str] = None,
        error_type: Optional[str] = None,
        mastered: Optional[bool] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        查询错题列表（带分页和筛选）

        Args:
            user_id: 用户ID
            page: 页码
            page_size: 每页数量
            knowledge_point: 知识点筛选
            difficulty: 难度筛选
            error_type: 错误类型筛选
            mastered: 是否已掌握
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            分页结果字典
        """
        query = self.db.query(UserWrongQuestion).join(
            Question, UserWrongQuestion.question_id == Question.question_id
        ).filter(UserWrongQuestion.user_id == user_id)

        # 应用筛选条件
        if knowledge_point:
            query = query.filter(Question.knowledge_point == knowledge_point)

        if difficulty:
            query = query.filter(Question.difficulty == difficulty)

        if error_type:
            query = query.filter(UserWrongQuestion.error_type == error_type)

        if mastered is not None:
            query = query.filter(UserWrongQuestion.mastered == mastered)

        if start_date:
            query = query.filter(UserWrongQuestion.created_date >= start_date)

        if end_date:
            query = query.filter(UserWrongQuestion.created_date <= end_date)

        # 计算总数
        total = query.count()

        # 分页
        offset = (page - 1) * page_size
        wrong_questions = query.order_by(
            desc(UserWrongQuestion.created_date)
        ).offset(offset).limit(page_size).all()

        # 构建返回结果
        items = []
        for wq in wrong_questions:
            question = wq.question
            items.append({
                "record_id": wq.record_id,
                "question_id": wq.question_id,
                "question": {
                    "question_id": question.question_id,
                    "q_id": question.q_id,
                    "question_text": question.question_text,
                    "answer": question.answer,
                    "solution": question.solution,
                    "knowledge_point": question.knowledge_point,
                    "difficulty": question.difficulty,
                    "has_image": question.has_image,
                    "image_path": question.image_path
                },
                "exam_name": wq.exam_name,
                "exam_date": wq.exam_date.isoformat() if wq.exam_date else None,
                "error_type": wq.error_type,
                "notes": wq.notes,
                "mastered": wq.mastered,
                "created_date": wq.created_date.isoformat() if wq.created_date else None
            })

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items
        }

    def add_wrong_question(
        self,
        user_id: int,
        question_id: int,
        exam_name: Optional[str] = None,
        exam_date: Optional[date] = None,
        error_type: Optional[str] = None,
        notes: Optional[str] = None
    ) -> UserWrongQuestion:
        """
        添加错题

        Args:
            user_id: 用户ID
            question_id: 题目ID
            exam_name: 考试名称
            exam_date: 考试日期
            error_type: 错误类型
            notes: 备注

        Returns:
            创建的错题记录
        """
        # 检查题目是否存在
        question = self.question_repo.get_by_id(question_id)
        if not question:
            raise ValueError(f"题目不存在: {question_id}")

        # 检查是否已存在
        existing = self.db.query(UserWrongQuestion).filter(
            and_(
                UserWrongQuestion.user_id == user_id,
                UserWrongQuestion.question_id == question_id
            )
        ).first()

        if existing:
            logger.info(f"错题已存在: 用户={user_id}, 题目={question_id}")
            return existing

        # 创建错题记录
        wrong_question = UserWrongQuestion(
            user_id=user_id,
            question_id=question_id,
            exam_name=exam_name,
            exam_date=exam_date,
            error_type=error_type,
            notes=notes,
            mastered=False,
            is_correct=False
        )

        created = self.wrong_question_repo.create(wrong_question)
        logger.info(f"添加错题成功: record_id={created.record_id}")

        return created

    def delete_wrong_question(
        self,
        user_id: int,
        record_id: int
    ) -> bool:
        """
        删除错题

        Args:
            user_id: 用户ID
            record_id: 错题记录ID

        Returns:
            是否删除成功
        """
        wrong_question = self.wrong_question_repo.get_by_id(record_id)

        if not wrong_question:
            raise ValueError(f"错题记录不存在: {record_id}")

        if wrong_question.user_id != user_id:
            raise PermissionError("无权删除此错题")

        self.db.delete(wrong_question)
        self.db.commit()

        logger.info(f"删除错题成功: record_id={record_id}")
        return True

    def update_feedback(
        self,
        user_id: int,
        record_id: int,
        is_correct: bool,
        error_type: Optional[str] = None
    ) -> UserWrongQuestion:
        """
        更新错题反馈

        Args:
            user_id: 用户ID
            record_id: 错题记录ID
            is_correct: 是否答对
            error_type: 错误类型

        Returns:
            更新后的错题记录
        """
        wrong_question = self.wrong_question_repo.get_by_id(record_id)

        if not wrong_question:
            raise ValueError(f"错题记录不存在: {record_id}")

        if wrong_question.user_id != user_id:
            raise PermissionError("无权修改此错题")

        # 更新字段
        wrong_question.is_correct = is_correct
        if error_type:
            wrong_question.error_type = error_type

        # 如果答对，标记为已掌握
        if is_correct:
            wrong_question.mastered = True

        self.db.commit()
        self.db.refresh(wrong_question)

        # 更新知识点掌握度
        question = wrong_question.question
        if question and question.knowledge_point:
            self._update_mastery(user_id, question.knowledge_point, is_correct)

        logger.info(f"更新错题反馈: record_id={record_id}, is_correct={is_correct}")
        return wrong_question

    def check_duplicate(
        self,
        user_id: int,
        question_text: str
    ) -> Dict[str, Any]:
        """
        检查题目是否重复

        Args:
            user_id: 用户ID
            question_text: 题目文本

        Returns:
            去重检查结果
        """
        import re
        import difflib

        if not question_text.strip():
            return {
                "in_bank": False,
                "in_wrong_questions": False,
                "similarity": 0.0
            }

        # 标准化文本
        norm_text = re.sub(r'\s+', ' ', question_text).strip()

        # 在题库中搜索候选题目
        candidates = []
        seen_ids = set()

        for kw_len in [30, 50, 20]:
            kw = norm_text[:kw_len]
            if len(kw) < 8:
                continue

            questions = self.db.query(Question).filter(
                Question.question_text.contains(kw)
            ).limit(20).all()

            for q in questions:
                if q.question_id not in seen_ids:
                    seen_ids.add(q.question_id)
                    candidates.append(q)

            if candidates:
                break

        # 计算相似度
        best_match = None
        best_similarity = 0.0

        for q in candidates:
            q_text = re.sub(r'\s+', ' ', q.question_text or '').strip()
            similarity = difflib.SequenceMatcher(None, norm_text, q_text).ratio()

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = q

        # 如果找到高相似度匹配
        if best_match and best_similarity > 0.78:
            # 检查是否在错题本中
            in_wrong = self.db.query(UserWrongQuestion).filter(
                and_(
                    UserWrongQuestion.user_id == user_id,
                    UserWrongQuestion.question_id == best_match.question_id
                )
            ).first()

            return {
                "in_bank": True,
                "in_wrong_questions": in_wrong is not None,
                "matched_question_id": best_match.question_id,
                "matched_question": {
                    "question_id": best_match.question_id,
                    "q_id": best_match.q_id,
                    "question_text": best_match.question_text,
                    "answer": best_match.answer,
                    "knowledge_point": best_match.knowledge_point
                },
                "similarity": round(best_similarity, 2)
            }

        return {
            "in_bank": False,
            "in_wrong_questions": False,
            "similarity": round(best_similarity, 2)
        }

    def get_statistics(self, user_id: int) -> Dict[str, Any]:
        """
        获取错题统计信息

        Args:
            user_id: 用户ID

        Returns:
            统计信息字典
        """
        total = self.db.query(UserWrongQuestion).filter(
            UserWrongQuestion.user_id == user_id
        ).count()

        mastered = self.db.query(UserWrongQuestion).filter(
            and_(
                UserWrongQuestion.user_id == user_id,
                UserWrongQuestion.mastered == True
            )
        ).count()

        unmastered = total - mastered

        return {
            "total": total,
            "mastered": mastered,
            "unmastered": unmastered,
            "mastery_rate": round(mastered / total * 100, 2) if total > 0 else 0.0
        }

    def _update_mastery(
        self,
        user_id: int,
        knowledge_point: str,
        is_correct: bool
    ):
        """更新知识点掌握度（内部方法）"""
        mastery = self.db.query(UserKnowledgeMastery).filter(
            and_(
                UserKnowledgeMastery.user_id == user_id,
                UserKnowledgeMastery.knowledge_point == knowledge_point
            )
        ).first()

        if not mastery:
            mastery = UserKnowledgeMastery(
                user_id=user_id,
                knowledge_point=knowledge_point,
                total_practiced=0,
                correct_count=0,
                mastery_rate=0.0
            )
            self.db.add(mastery)

        mastery.total_practiced += 1
        if is_correct:
            mastery.correct_count += 1

        mastery.mastery_rate = (
            mastery.correct_count / mastery.total_practiced * 100
            if mastery.total_practiced > 0 else 0.0
        )
        mastery.last_practiced_date = datetime.now()

        self.db.commit()
