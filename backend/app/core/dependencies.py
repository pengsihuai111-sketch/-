"""依赖注入配置 - FastAPI依赖项"""
from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..repositories.mastery_repository import MasteryRepository
from ..services.mastery_service import MasteryService


# 数据库会话依赖
def get_db_session() -> Generator[Session, None, None]:
    """获取数据库会话（别名，用于依赖注入）"""
    yield from get_db()


# Repository依赖
def get_mastery_repository(db: Session = Depends(get_db)) -> MasteryRepository:
    """获取MasteryRepository实例"""
    return MasteryRepository(db)


# Service依赖
def get_mastery_service(
    mastery_repo: MasteryRepository = Depends(get_mastery_repository),
    db: Session = Depends(get_db)
) -> MasteryService:
    """获取MasteryService实例"""
    return MasteryService(mastery_repo, db)


# 其他Repository和Service依赖将在后续阶段添加
