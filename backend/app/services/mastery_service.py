"""知识点掌握度Service"""
from typing import List, Optional
from datetime import date, timedelta
from sqlalchemy.orm import Session

from ..repositories.mastery_repository import MasteryRepository
from ..models import UserKnowledgeMastery


class MasteryService:
    """知识点掌握度业务逻辑层"""

    def __init__(self, mastery_repo: MasteryRepository, db: Session):
        self.mastery_repo = mastery_repo
        self.db = db

    def update_mastery(
        self,
        user_id: int,
        knowledge_point: str,
        is_correct: bool
    ) -> UserKnowledgeMastery:
        """
        更新知识点掌握度

        Args:
            user_id: 用户ID
            knowledge_point: 知识点名称
            is_correct: 本次练习是否正确

        Returns:
            更新后的掌握度记录
        """
        mastery = self.mastery_repo.get_by_user_and_kp(user_id, knowledge_point)

        if not mastery:
            # 创建新记录
            mastery = UserKnowledgeMastery(
                user_id=user_id,
                knowledge_point=knowledge_point,
                total_practiced=0,
                correct_count=0,
                mastery_rate=0,
                last_practiced_date=date.today(),
            )
            self.db.add(mastery)

        # 更新统计数据
        mastery.total_practiced = (mastery.total_practiced or 0) + 1
        if is_correct:
            mastery.correct_count = (mastery.correct_count or 0) + 1

        # 计算掌握率
        total = mastery.total_practiced or 1
        correct = mastery.correct_count or 0
        mastery.mastery_rate = round(correct / total * 100, 1)
        mastery.last_practiced_date = date.today()
        mastery.is_weak_point = (mastery.mastery_rate or 0) < 60

        self.db.flush()
        return mastery

    def batch_update_mastery(
        self,
        user_id: int,
        results: List[tuple[str, bool]]
    ) -> None:
        """
        批量更新知识点掌握度

        Args:
            user_id: 用户ID
            results: [(knowledge_point, is_correct), ...] 列表
        """
        for knowledge_point, is_correct in results:
            self.update_mastery(user_id, knowledge_point, is_correct)

    def get_user_mastery(self, user_id: int) -> List[UserKnowledgeMastery]:
        """获取用户所有知识点掌握度"""
        return self.mastery_repo.get_user_mastery_list(user_id)

    def get_weak_points(
        self,
        user_id: int,
        threshold: float = 60.0
    ) -> List[UserKnowledgeMastery]:
        """
        获取用户薄弱知识点

        Args:
            user_id: 用户ID
            threshold: 掌握率阈值（低于此值视为薄弱）

        Returns:
            薄弱知识点列表，按掌握率升序排列
        """
        return self.mastery_repo.get_weak_points(user_id, threshold)

    def get_forgetting_risks(
        self,
        user_id: int,
        days_threshold: int = 7
    ) -> List[UserKnowledgeMastery]:
        """
        获取有遗忘风险的知识点

        Args:
            user_id: 用户ID
            days_threshold: 天数阈值（超过此天数未练习视为有遗忘风险）

        Returns:
            有遗忘风险的知识点列表
        """
        return self.mastery_repo.get_forgetting_risks(user_id, days_threshold)

    def calculate_forgetting_risk(self, mastery: UserKnowledgeMastery) -> int:
        """
        计算遗忘风险分数（0-100，越高越容易遗忘）

        Args:
            mastery: 掌握度记录

        Returns:
            遗忘风险分数
        """
        if not mastery.last_practiced_date:
            return 100

        # 计算距离上次练习的天数
        days_since_practice = (date.today() - mastery.last_practiced_date).days

        # 基础遗忘风险：天数越多风险越高
        time_risk = min(days_since_practice * 5, 50)  # 最多50分

        # 掌握率风险：掌握率越低风险越高
        mastery_risk = 100 - (mastery.mastery_rate or 0)
        mastery_risk = mastery_risk * 0.5  # 最多50分

        total_risk = int(time_risk + mastery_risk)
        return min(total_risk, 100)

    def update_forgetting_scores(self, user_id: int) -> None:
        """更新用户所有知识点的遗忘风险分数"""
        mastery_list = self.get_user_mastery(user_id)
        for mastery in mastery_list:
            # 这里可以添加forgetting_score字段到模型中
            # mastery.forgetting_score = self.calculate_forgetting_risk(mastery)
            pass
        self.db.flush()
