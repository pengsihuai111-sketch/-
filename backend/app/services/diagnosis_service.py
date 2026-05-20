"""
诊断分析服务
处理错题诊断、知识点掌握度分析、薄弱点识别等业务逻辑
"""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta, date
from collections import defaultdict

from ..models import (
    UserWrongQuestion, Question, UserKnowledgeMastery,
    UserPracticeHistory, ErrorType
)
from ..repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class DiagnosisService:
    """诊断分析服务"""

    def __init__(self, db: Session):
        self.db = db
        self.mastery_repo = BaseRepository(UserKnowledgeMastery, db)
        self.wrong_question_repo = BaseRepository(UserWrongQuestion, db)

    def generate_diagnosis_report(
        self,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        生成诊断报告

        Args:
            user_id: 用户ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            诊断报告字典
        """
        logger.info(f"生成诊断报告: 用户={user_id}, 时间范围={start_date}~{end_date}")

        # 获取知识点掌握度数据
        mastery_query = self.db.query(UserKnowledgeMastery).filter(
            UserKnowledgeMastery.user_id == user_id
        )
        mastery_list = mastery_query.all()

        # 获取错题数据
        wrong_query = self.db.query(UserWrongQuestion).filter(
            UserWrongQuestion.user_id == user_id
        )
        if start_date:
            wrong_query = wrong_query.filter(UserWrongQuestion.created_date >= start_date)
        if end_date:
            wrong_query = wrong_query.filter(UserWrongQuestion.created_date <= end_date)

        wrong_questions = wrong_query.all()

        # 计算统计数据
        total_knowledge_points = len(mastery_list)
        weak_points = [m.knowledge_point for m in mastery_list if m.mastery_rate < 60]
        forgetting_risks = [
            m.knowledge_point for m in mastery_list
            if m.forgetting_risk_score and m.forgetting_risk_score > 70
        ]

        average_mastery_rate = (
            sum(m.mastery_rate for m in mastery_list) / total_knowledge_points
            if total_knowledge_points > 0 else 0.0
        )

        total_wrong = len(wrong_questions)

        # 分析趋势
        recent_trend = self._analyze_trend(user_id)

        # 构建掌握度详情
        mastery_details = [
            {
                "knowledge_point": m.knowledge_point,
                "total_practiced": m.total_practiced,
                "correct_count": m.correct_count,
                "mastery_rate": round(m.mastery_rate, 2),
                "is_weak_point": m.mastery_rate < 60,
                "forgetting_risk_score": m.forgetting_risk_score or 0,
                "last_practiced_date": (
                    m.last_practiced_date.isoformat()
                    if m.last_practiced_date else None
                )
            }
            for m in mastery_list
        ]

        return {
            "total_knowledge_points": total_knowledge_points,
            "weak_points": weak_points,
            "forgetting_risks": forgetting_risks,
            "average_mastery_rate": round(average_mastery_rate, 2),
            "total_wrong": total_wrong,
            "recent_trend": recent_trend,
            "mastery_details": mastery_details
        }

    def analyze_error_types(
        self,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        分析错误类型分布

        Args:
            user_id: 用户ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            错误类型分析结果
        """
        query = self.db.query(UserWrongQuestion).filter(
            UserWrongQuestion.user_id == user_id
        )

        if start_date:
            query = query.filter(UserWrongQuestion.created_date >= start_date)
        if end_date:
            query = query.filter(UserWrongQuestion.created_date <= end_date)

        wrong_questions = query.all()
        total = len(wrong_questions)

        if total == 0:
            return {
                "total": 0,
                "error_type_stats": [],
                "most_common_error": None
            }

        # 统计错误类型
        error_counts = defaultdict(int)
        for wq in wrong_questions:
            error_type = wq.error_type or "未分类"
            error_counts[error_type] += 1

        # 构建统计结果
        error_type_stats = [
            {
                "error_type": error_type,
                "count": count,
                "percentage": round(count / total * 100, 2)
            }
            for error_type, count in error_counts.items()
        ]

        # 按数量排序
        error_type_stats.sort(key=lambda x: x["count"], reverse=True)

        most_common_error = error_type_stats[0]["error_type"] if error_type_stats else None

        return {
            "total": total,
            "error_type_stats": error_type_stats,
            "most_common_error": most_common_error
        }

    def get_weak_point_suggestions(
        self,
        user_id: int,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        获取薄弱点建议

        Args:
            user_id: 用户ID
            limit: 返回数量限制

        Returns:
            薄弱点建议列表
        """
        # 查询掌握率低的知识点
        weak_masteries = self.db.query(UserKnowledgeMastery).filter(
            and_(
                UserKnowledgeMastery.user_id == user_id,
                UserKnowledgeMastery.mastery_rate < 60
            )
        ).order_by(UserKnowledgeMastery.mastery_rate.asc()).limit(limit).all()

        suggestions = []
        for m in weak_masteries:
            # 统计该知识点的错题数
            wrong_count = self.db.query(func.count(UserWrongQuestion.record_id)).join(
                Question, UserWrongQuestion.question_id == Question.question_id
            ).filter(
                and_(
                    UserWrongQuestion.user_id == user_id,
                    Question.knowledge_point == m.knowledge_point
                )
            ).scalar() or 0

            # 生成建议
            if m.mastery_rate < 30:
                priority = "高"
                suggestion = f"建议系统学习{m.knowledge_point}的基础知识，完成专项练习"
            elif m.mastery_rate < 50:
                priority = "中"
                suggestion = f"需要加强{m.knowledge_point}的练习，重点突破易错点"
            else:
                priority = "低"
                suggestion = f"继续巩固{m.knowledge_point}，保持练习频率"

            suggestions.append({
                "knowledge_point": m.knowledge_point,
                "mastery_rate": round(m.mastery_rate, 2),
                "wrong_count": wrong_count,
                "priority": priority,
                "suggestion": suggestion
            })

        return suggestions

    def get_mastery_trend(
        self,
        user_id: int,
        knowledge_point: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        获取知识点掌握度趋势

        Args:
            user_id: 用户ID
            knowledge_point: 知识点
            days: 天数

        Returns:
            趋势数据
        """
        start_date = datetime.now() - timedelta(days=days)

        # 查询练习历史
        practice_history = self.db.query(UserPracticeHistory).join(
            Question, UserPracticeHistory.question_id == Question.question_id
        ).filter(
            and_(
                UserPracticeHistory.user_id == user_id,
                Question.knowledge_point == knowledge_point,
                UserPracticeHistory.practice_date >= start_date
            )
        ).order_by(UserPracticeHistory.practice_date.asc()).all()

        # 按日期分组统计
        daily_stats = defaultdict(lambda: {"total": 0, "correct": 0})

        for ph in practice_history:
            date_key = ph.practice_date.date().isoformat()
            daily_stats[date_key]["total"] += 1
            if ph.is_correct:
                daily_stats[date_key]["correct"] += 1

        # 构建趋势数据
        trend_data = []
        for date_key in sorted(daily_stats.keys()):
            stats = daily_stats[date_key]
            mastery_rate = (
                stats["correct"] / stats["total"] * 100
                if stats["total"] > 0 else 0
            )
            trend_data.append({
                "date": date_key,
                "mastery_rate": round(mastery_rate, 2),
                "total_practiced": stats["total"],
                "correct_count": stats["correct"]
            })

        # 获取当前掌握度
        current_mastery = self.db.query(UserKnowledgeMastery).filter(
            and_(
                UserKnowledgeMastery.user_id == user_id,
                UserKnowledgeMastery.knowledge_point == knowledge_point
            )
        ).first()

        return {
            "knowledge_point": knowledge_point,
            "current_mastery_rate": (
                round(current_mastery.mastery_rate, 2)
                if current_mastery else 0.0
            ),
            "trend_data": trend_data,
            "days": days
        }

    def _analyze_trend(self, user_id: int) -> str:
        """
        分析最近的学习趋势

        Args:
            user_id: 用户ID

        Returns:
            趋势描述
        """
        # 获取最近7天和前7天的数据
        now = datetime.now()
        recent_start = now - timedelta(days=7)
        previous_start = now - timedelta(days=14)

        # 最近7天的正确率
        recent_history = self.db.query(UserPracticeHistory).filter(
            and_(
                UserPracticeHistory.user_id == user_id,
                UserPracticeHistory.practice_date >= recent_start
            )
        ).all()

        # 前7天的正确率
        previous_history = self.db.query(UserPracticeHistory).filter(
            and_(
                UserPracticeHistory.user_id == user_id,
                UserPracticeHistory.practice_date >= previous_start,
                UserPracticeHistory.practice_date < recent_start
            )
        ).all()

        if not recent_history:
            return "数据不足"

        recent_correct_rate = (
            sum(1 for h in recent_history if h.is_correct) / len(recent_history) * 100
            if recent_history else 0
        )

        if not previous_history:
            return f"最近正确率 {recent_correct_rate:.1f}%"

        previous_correct_rate = (
            sum(1 for h in previous_history if h.is_correct) / len(previous_history) * 100
            if previous_history else 0
        )

        diff = recent_correct_rate - previous_correct_rate

        if diff > 5:
            return f"进步明显 (↑{diff:.1f}%)"
        elif diff < -5:
            return f"需要加强 (↓{abs(diff):.1f}%)"
        else:
            return "保持稳定"

    def update_mastery(
        self,
        user_id: int,
        knowledge_point: str,
        is_correct: bool
    ):
        """
        更新知识点掌握度

        Args:
            user_id: 用户ID
            knowledge_point: 知识点
            is_correct: 是否正确
        """
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
