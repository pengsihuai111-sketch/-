"""
练习单服务
处理练习单生成、提交、批改等业务逻辑
"""
import logging
import random
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, date, timedelta
from collections import defaultdict

from ..models import (
    Question, PracticeSheet, SheetQuestion, UserPracticeHistory,
    UserWrongQuestion, UserKnowledgeMastery, PracticeType, SheetType
)
from ..repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class PracticeService:
    """练习单服务"""

    def __init__(self, db: Session):
        self.db = db
        self.sheet_repo = BaseRepository(PracticeSheet, db)
        self.question_repo = BaseRepository(Question, db)

    def generate_sheet(
        self,
        user_id: int,
        sheet_type: str = "daily",
        total_questions: int = 8,
        knowledge_points: Optional[List[str]] = None,
        difficulties: Optional[List[str]] = None,
        sheet_name: Optional[str] = None,
        question_ids: Optional[List[int]] = None,
        knowledge_group_counts: Optional[List[Dict]] = None
    ) -> PracticeSheet:
        """
        生成练习单

        Args:
            user_id: 用户ID
            sheet_type: 练习单类型
            total_questions: 题目总数
            knowledge_points: 知识点列表
            difficulties: 难度列表
            sheet_name: 练习单名称
            question_ids: 手动选择的题目ID列表
            knowledge_group_counts: 分组选题配置

        Returns:
            生成的练习单
        """
        logger.info(f"生成练习单: 用户={user_id}, 类型={sheet_type}, 数量={total_questions}")

        selected_questions = []

        # 手动选题模式
        if question_ids:
            selected_questions = self._select_by_ids(question_ids)

        # 分组选题模式
        elif knowledge_group_counts:
            selected_questions = self._select_by_groups(
                user_id, knowledge_group_counts, difficulties
            )

        # 自动选题模式
        else:
            selected_questions = self._select_auto(
                user_id, total_questions, knowledge_points, difficulties
            )

        if not selected_questions:
            raise ValueError("没有符合条件的题目")

        # 按题型分组排序
        selected_questions, sections = self._group_by_type(selected_questions)

        # 估算时间
        estimated_time = self._estimate_time(selected_questions)

        # 创建练习单
        sheet = PracticeSheet(
            user_id=user_id,
            sheet_name=sheet_name or f"{sheet_type}练习",
            sheet_type=sheet_type,
            total_questions=len(selected_questions),
            estimated_time=estimated_time,
            completed=False
        )
        sheet = self.sheet_repo.create(sheet)

        # 添加题目关联
        for order, question in enumerate(selected_questions, start=1):
            sheet_question = SheetQuestion(
                sheet_id=sheet.sheet_id,
                question_id=question.question_id,
                question_order=order
            )
            self.db.add(sheet_question)

        self.db.commit()
        self.db.refresh(sheet)

        logger.info(f"练习单生成成功: sheet_id={sheet.sheet_id}, 题目数={len(selected_questions)}")
        return sheet

    def generate_week_sheets(
        self,
        user_id: int,
        knowledge_points: List[str],
        questions_per_day: int = 8
    ) -> List[PracticeSheet]:
        """
        生成一周练习单

        Args:
            user_id: 用户ID
            knowledge_points: 知识点列表
            questions_per_day: 每天题目数

        Returns:
            生成的练习单列表
        """
        logger.info(f"生成一周练习单: 用户={user_id}, 知识点数={len(knowledge_points)}")

        # 将知识点分配到7天
        days_count = 7
        kps_per_day = max(1, len(knowledge_points) // days_count)

        sheets = []
        used_ids = set()

        for day in range(days_count):
            start_idx = day * kps_per_day
            end_idx = start_idx + kps_per_day if day < days_count - 1 else len(knowledge_points)
            day_kps = knowledge_points[start_idx:end_idx]

            if not day_kps:
                continue

            # 为这一天选题
            day_questions = self._select_day_questions(day_kps, used_ids, questions_per_day)

            if day_questions:
                sheet = self.generate_sheet(
                    user_id=user_id,
                    sheet_type="daily",
                    sheet_name=f"第{day + 1}天练习",
                    question_ids=[q.question_id for q in day_questions]
                )
                sheets.append(sheet)

                # 记录已使用的题目
                used_ids.update(q.question_id for q in day_questions)

        logger.info(f"一周练习单生成完成: 共{len(sheets)}份")
        return sheets

    def generate_redo_sheet(
        self,
        user_id: int,
        start_date: date,
        end_date: date,
        difficulty: Optional[List[str]] = None,
        question_types: Optional[List[str]] = None,
        only_unmastered: bool = True
    ) -> PracticeSheet:
        """
        生成错题重练单

        Args:
            user_id: 用户ID
            start_date: 开始日期
            end_date: 结束日期
            difficulty: 难度筛选
            question_types: 题型筛选
            only_unmastered: 仅未掌握的错题

        Returns:
            生成的练习单
        """
        logger.info(f"生成错题重练单: 用户={user_id}, 时间={start_date}~{end_date}")

        # 查询错题
        query = self.db.query(UserWrongQuestion).join(
            Question, UserWrongQuestion.question_id == Question.question_id
        ).filter(
            UserWrongQuestion.user_id == user_id,
            UserWrongQuestion.created_date >= start_date,
            UserWrongQuestion.created_date <= end_date
        )

        if only_unmastered:
            query = query.filter(UserWrongQuestion.mastered == False)

        if difficulty:
            query = query.filter(Question.difficulty.in_(difficulty))

        if question_types:
            query = query.filter(Question.question_type.in_(question_types))

        wrong_questions = query.all()

        if not wrong_questions:
            raise ValueError("没有符合条件的错题")

        # 提取题目ID
        question_ids = [wq.question_id for wq in wrong_questions]

        # 生成练习单
        sheet = self.generate_sheet(
            user_id=user_id,
            sheet_type="wrong_redo",
            sheet_name=f"错题重练 {start_date} ~ {end_date}",
            question_ids=question_ids
        )

        return sheet

    def submit_sheet(
        self,
        user_id: int,
        sheet_id: int,
        answers: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        提交练习单答案

        Args:
            user_id: 用户ID
            sheet_id: 练习单ID
            answers: 答案列表 [{"question_id": 1, "user_answer": "A"}]

        Returns:
            批改结果
        """
        logger.info(f"提交练习单: sheet_id={sheet_id}, 用户={user_id}")

        sheet = self.sheet_repo.get_by_id(sheet_id)
        if not sheet or sheet.user_id != user_id:
            raise ValueError("练习单不存在或无权访问")

        if sheet.completed:
            raise ValueError("练习单已完成，不能重复提交")

        # 获取练习单的所有题目
        sheet_questions = self.db.query(SheetQuestion).filter(
            SheetQuestion.sheet_id == sheet_id
        ).all()

        question_ids = [sq.question_id for sq in sheet_questions]
        questions = self.db.query(Question).filter(
            Question.question_id.in_(question_ids)
        ).all()

        question_map = {q.question_id: q for q in questions}

        # 批改答案
        results = []
        correct_count = 0
        wrong_question_ids = []

        for answer in answers:
            question_id = answer["question_id"]
            user_answer = answer["user_answer"]

            question = question_map.get(question_id)
            if not question:
                continue

            # 标准化答案
            normalized_user = self._normalize_answer(user_answer)
            normalized_correct = self._normalize_answer(question.answer or "")

            is_correct = normalized_user == normalized_correct

            if is_correct:
                correct_count += 1
            else:
                wrong_question_ids.append(question_id)

            # 记录练习历史
            history = UserPracticeHistory(
                user_id=user_id,
                question_id=question_id,
                sheet_id=sheet_id,
                is_correct=is_correct,
                user_answer=user_answer
            )
            self.db.add(history)

            # 更新知识点掌握度
            if question.knowledge_point:
                self._update_mastery(user_id, question.knowledge_point, is_correct)

            results.append({
                "question_id": question_id,
                "question_text": question.question_text,
                "knowledge_point": question.knowledge_point,
                "user_answer": user_answer,
                "correct_answer": question.answer,
                "is_correct": is_correct,
                "solution": question.solution
            })

        # 更新练习单状态
        sheet.completed = True
        sheet.completed_date = datetime.now()
        sheet.score = (correct_count / len(answers) * 100) if answers else 0

        self.db.commit()

        logger.info(f"练习单提交完成: 正确={correct_count}/{len(answers)}")

        return {
            "sheet_id": sheet_id,
            "total": len(answers),
            "correct_count": correct_count,
            "wrong_count": len(answers) - correct_count,
            "score": round(sheet.score, 2),
            "results": results,
            "wrong_question_ids": wrong_question_ids
        }

    def list_sheets(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        sheet_type: Optional[str] = None,
        completed: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        查询练习单列表

        Args:
            user_id: 用户ID
            page: 页码
            page_size: 每页数量
            sheet_type: 练习单类型筛选
            completed: 完成状态筛选

        Returns:
            分页结果
        """
        query = self.db.query(PracticeSheet).filter(
            PracticeSheet.user_id == user_id
        )

        if sheet_type:
            query = query.filter(PracticeSheet.sheet_type == sheet_type)

        if completed is not None:
            query = query.filter(PracticeSheet.completed == completed)

        total = query.count()

        offset = (page - 1) * page_size
        sheets = query.order_by(
            PracticeSheet.generated_date.desc()
        ).offset(offset).limit(page_size).all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "sheets": [self._sheet_to_dict(s) for s in sheets]
        }

    def get_sheet(self, user_id: int, sheet_id: int) -> Dict[str, Any]:
        """获取练习单详情"""
        sheet = self.sheet_repo.get_by_id(sheet_id)

        if not sheet or sheet.user_id != user_id:
            raise ValueError("练习单不存在或无权访问")

        # 获取题目
        sheet_questions = self.db.query(SheetQuestion).filter(
            SheetQuestion.sheet_id == sheet_id
        ).order_by(SheetQuestion.question_order).all()

        question_ids = [sq.question_id for sq in sheet_questions]
        questions = self.db.query(Question).filter(
            Question.question_id.in_(question_ids)
        ).all()

        question_map = {q.question_id: q for q in questions}

        # 按顺序组装题目
        ordered_questions = [
            question_map[sq.question_id]
            for sq in sheet_questions
            if sq.question_id in question_map
        ]

        return {
            "sheet": self._sheet_to_dict(sheet),
            "questions": [self._question_to_dict(q) for q in ordered_questions]
        }

    def delete_sheet(self, user_id: int, sheet_id: int) -> bool:
        """删除练习单"""
        sheet = self.sheet_repo.get_by_id(sheet_id)

        if not sheet or sheet.user_id != user_id:
            raise ValueError("练习单不存在或无权删除")

        # 删除关联的题目
        self.db.query(SheetQuestion).filter(
            SheetQuestion.sheet_id == sheet_id
        ).delete()

        # 删除练习单
        self.db.delete(sheet)
        self.db.commit()

        logger.info(f"删除练习单: sheet_id={sheet_id}")
        return True

    # ==================== 私有辅助方法 ====================

    def _select_by_ids(self, question_ids: List[int]) -> List[Question]:
        """根据ID列表选题"""
        questions = self.db.query(Question).filter(
            Question.question_id.in_(question_ids)
        ).all()

        # 保持传入的顺序
        id_order = {qid: i for i, qid in enumerate(question_ids)}
        questions.sort(key=lambda q: id_order.get(q.question_id, 999))

        return questions

    def _select_by_groups(
        self,
        user_id: int,
        groups: List[Dict],
        difficulties: Optional[List[str]] = None
    ) -> List[Question]:
        """分组选题"""
        selected = []
        used_ids = set()

        # 获取今天已练习的题目（去重）
        recent_ids = set(
            r[0] for r in self.db.query(UserPracticeHistory.question_id).filter(
                UserPracticeHistory.user_id == user_id,
                UserPracticeHistory.practice_date >= date.today()
            ).all()
        )

        for group in groups:
            count = group.get("count", 1)
            knowledge_points = group.get("knowledge_points", [])

            if count <= 0 or not knowledge_points:
                continue

            query = self.db.query(Question).filter(
                Question.knowledge_point.in_(knowledge_points)
            )

            if difficulties:
                query = query.filter(Question.difficulty.in_(difficulties))

            if recent_ids:
                query = query.filter(Question.question_id.notin_(recent_ids))

            candidates = [q for q in query.all() if q.question_id not in used_ids]

            if candidates:
                n = min(count, len(candidates))
                picked = random.sample(candidates, n)
                for q in picked:
                    used_ids.add(q.question_id)
                selected.extend(picked)

        return selected

    def _select_auto(
        self,
        user_id: int,
        total: int,
        knowledge_points: Optional[List[str]] = None,
        difficulties: Optional[List[str]] = None
    ) -> List[Question]:
        """自动选题"""
        query = self.db.query(Question)

        if knowledge_points:
            query = query.filter(Question.knowledge_point.in_(knowledge_points))

        if difficulties:
            query = query.filter(Question.difficulty.in_(difficulties))

        # 获取今天已练习的题目
        recent_ids = [
            r[0] for r in self.db.query(UserPracticeHistory.question_id).filter(
                UserPracticeHistory.user_id == user_id,
                UserPracticeHistory.practice_date >= date.today()
            ).all()
        ]

        if recent_ids:
            query = query.filter(Question.question_id.notin_(recent_ids))

        candidates = query.all()

        if len(candidates) < total:
            logger.warning(f"候选题目不足: 需要{total}, 实际{len(candidates)}")

        n = min(total, len(candidates))
        return random.sample(candidates, n) if candidates else []

    def _select_day_questions(
        self,
        knowledge_points: List[str],
        used_ids: set,
        count: int
    ) -> List[Question]:
        """为某一天选题"""
        query = self.db.query(Question).filter(
            Question.knowledge_point.in_(knowledge_points)
        )

        if used_ids:
            query = query.filter(Question.question_id.notin_(used_ids))

        candidates = query.all()

        n = min(count, len(candidates))
        return random.sample(candidates, n) if candidates else []

    def _group_by_type(self, questions: List[Question]) -> Tuple[List[Question], Dict]:
        """按题型分组排序"""
        type_groups = defaultdict(list)

        for q in questions:
            qtype = q.question_type or "其他"
            type_groups[qtype].append(q)

        # 排序：计算题 -> 填空题 -> 选择题 -> 应用题 -> 其他
        type_order = ["计算题", "填空题", "选择题", "应用题", "其他"]
        sorted_questions = []
        sections = {}

        for qtype in type_order:
            if qtype in type_groups:
                sorted_questions.extend(type_groups[qtype])
                sections[qtype] = len(type_groups[qtype])

        # 添加未在排序列表中的题型
        for qtype, qs in type_groups.items():
            if qtype not in type_order:
                sorted_questions.extend(qs)
                sections[qtype] = len(qs)

        return sorted_questions, sections

    def _estimate_time(self, questions: List[Question]) -> int:
        """估算完成时间（分钟）"""
        time_map = {
            "计算题": 2,
            "填空题": 3,
            "选择题": 1,
            "应用题": 5,
            "其他": 3
        }

        total_minutes = sum(
            time_map.get(q.question_type, 3) for q in questions
        )

        return total_minutes

    def _normalize_answer(self, text: str) -> str:
        """标准化答案"""
        import re
        text = re.sub(r'\s+', '', text or '')
        text = text.lower()
        return text

    def _update_mastery(self, user_id: int, knowledge_point: str, is_correct: bool):
        """更新知识点掌握度"""
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

    def _sheet_to_dict(self, sheet: PracticeSheet) -> Dict[str, Any]:
        """练习单转字典"""
        return {
            "sheet_id": sheet.sheet_id,
            "sheet_name": sheet.sheet_name,
            "sheet_type": sheet.sheet_type,
            "total_questions": sheet.total_questions,
            "estimated_time": sheet.estimated_time,
            "generated_date": sheet.generated_date.isoformat() if sheet.generated_date else None,
            "completed": sheet.completed,
            "completed_date": sheet.completed_date.isoformat() if sheet.completed_date else None,
            "score": round(sheet.score, 2) if sheet.score else None
        }

    def _question_to_dict(self, question: Question) -> Dict[str, Any]:
        """题目转字典"""
        return {
            "question_id": question.question_id,
            "q_id": question.q_id,
            "question_text": question.question_text,
            "answer": question.answer,
            "solution": question.solution,
            "knowledge_point": question.knowledge_point,
            "difficulty": question.difficulty,
            "question_type": question.question_type,
            "has_image": question.has_image,
            "image_path": question.image_path
        }
