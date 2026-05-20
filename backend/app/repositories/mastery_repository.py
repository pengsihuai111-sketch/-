"""知识点掌握度Repository"""
from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import and_

from .base_repository import BaseRepository
from ..models import UserKnowledgeMastery


class MasteryRepository(BaseRepository[UserKnowledgeMastery]):
    """知识点掌握度数据访问层"""

    def __init__(self, db: Session):
        super().__init__(UserKnowledgeMastery, db)

    def get_by_user_and_kp(self, user_id: int, knowledge_point: str) -> Optional[UserKnowledgeMastery]:
        """根据用户ID和知识点获取掌握度记录"""
        return self.db.query(UserKnowledgeMastery).filter(
            and_(
                UserKnowledgeMastery.user_id == user_id,
                UserKnowledgeMastery.knowledge_point == knowledge_point
            )
        ).first()

    def get_user_mastery_list(self, user_id: int) -> List[UserKnowledgeMastery]:
        """获取用户所有知识点掌握度"""
        return self.db.query(UserKnowledgeMastery).filter(
            UserKnowledgeMastery.user_id == user_id
        ).order_by(UserKnowledgeMastery.mastery_rate.asc()).all()

    def get_weak_points(self, user_id: int, threshold: float = 60.0) -> List[UserKnowledgeMastery]:
        """获取用户薄弱知识点"""
        return self.db.query(UserKnowledgeMastery).filter(
            and_(
                UserKnowledgeMastery.user_id == user_id,
                UserKnowledgeMastery.mastery_rate < threshold
            )
        ).order_by(UserKnowledgeMastery.mastery_rate.asc()).all()

    def get_forgetting_risks(self, user_id: int, days_threshold: int = 7) -> List[UserKnowledgeMastery]:
        """获取有遗忘风险的知识点（长时间未练习）"""
        from datetime import timedelta
        threshold_date = date.today() - timedelta(days=days_threshold)

        return self.db.query(UserKnowledgeMastery).filter(
            and_(
                UserKnowledgeMastery.user_id == user_id,
                UserKnowledgeMastery.last_practiced_date < threshold_date,
                UserKnowledgeMastery.mastery_rate < 90  # 未完全掌握的
            )
        ).order_by(UserKnowledgeMastery.last_practiced_date.asc()).all()
