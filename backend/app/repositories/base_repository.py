"""基础Repository类 - 提供通用CRUD操作"""
from typing import TypeVar, Generic, Type, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, select

T = TypeVar('T')


class BaseRepository(Generic[T]):
    """
    通用Repository基类，提供标准CRUD操作

    使用示例:
        class QuestionRepository(BaseRepository[Question]):
            def __init__(self, db: Session):
                super().__init__(Question, db)
    """

    def __init__(self, model: Type[T], db: Session):
        """
        初始化Repository

        Args:
            model: SQLAlchemy模型类
            db: 数据库会话
        """
        self.model = model
        self.db = db

    def get_by_id(self, id: int) -> Optional[T]:
        """根据ID获取单个对象"""
        return self.db.query(self.model).filter(self.model.id == id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """
        获取所有对象（分页）

        Args:
            skip: 跳过的记录数
            limit: 返回的最大记录数
        """
        return self.db.query(self.model).offset(skip).limit(limit).all()

    def create(self, obj: T) -> T:
        """
        创建新对象

        Args:
            obj: 要创建的对象实例

        Returns:
            创建后的对象（包含生成的ID）
        """
        self.db.add(obj)
        self.db.flush()
        self.db.refresh(obj)
        return obj

    def update(self, obj: T) -> T:
        """
        更新对象

        Args:
            obj: 要更新的对象实例

        Returns:
            更新后的对象
        """
        self.db.flush()
        self.db.refresh(obj)
        return obj

    def delete(self, obj: T) -> None:
        """
        删除对象

        Args:
            obj: 要删除的对象实例
        """
        self.db.delete(obj)
        self.db.flush()

    def delete_by_id(self, id: int) -> bool:
        """
        根据ID删除对象

        Args:
            id: 对象ID

        Returns:
            是否成功删除
        """
        obj = self.get_by_id(id)
        if obj:
            self.delete(obj)
            return True
        return False

    def count(self) -> int:
        """获取总记录数"""
        return self.db.query(func.count(self.model.id)).scalar()

    def exists(self, id: int) -> bool:
        """检查ID是否存在"""
        return self.db.query(
            self.db.query(self.model).filter(self.model.id == id).exists()
        ).scalar()

    def bulk_create(self, objects: List[T]) -> List[T]:
        """
        批量创建对象

        Args:
            objects: 对象列表

        Returns:
            创建后的对象列表
        """
        self.db.add_all(objects)
        self.db.flush()
        for obj in objects:
            self.db.refresh(obj)
        return objects

    def bulk_delete(self, ids: List[int]) -> int:
        """
        批量删除对象

        Args:
            ids: ID列表

        Returns:
            删除的记录数
        """
        count = self.db.query(self.model).filter(self.model.id.in_(ids)).delete(synchronize_session=False)
        self.db.flush()
        return count
