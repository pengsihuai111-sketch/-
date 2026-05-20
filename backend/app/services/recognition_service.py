"""
错题识别服务
处理图片/PDF识别、题目匹配、去重等业务逻辑
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from datetime import datetime

from ..models import (
    Question, UserWrongQuestion, WrongQuestionRecognitionTask,
    WrongQuestionRecognitionBlock
)
from ..utils.deepseek import (
    recognize_questions, recognize_single_question,
    match_question_candidates, analyze_page_structure
)
from ..utils.pdf_processor import pdf_to_images
from ..utils.image_processing import (
    remove_red_marks, preprocess_for_ocr, detect_correction_marks,
    save_image, crop_bbox
)
from ..repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class RecognitionService:
    """错题识别服务"""

    def __init__(self, db: Session):
        self.db = db
        self.task_repo = BaseRepository(WrongQuestionRecognitionTask, db)
        self.block_repo = BaseRepository(WrongQuestionRecognitionBlock, db)

    async def recognize_image(
        self,
        image_bytes: bytes,
        filename: str,
        user_id: int
    ) -> Dict[str, Any]:
        """
        识别单张图片中的错题

        Args:
            image_bytes: 图片字节数据
            filename: 文件名
            user_id: 用户ID

        Returns:
            识别结果字典，包含questions、warnings、enhanced等字段
        """
        logger.info(f"开始识别图片: {filename}, 用户: {user_id}")

        try:
            result = await recognize_questions(image_bytes, filename)
            questions = result.get("questions", [])

            # 为每个识别的题目搜索匹配
            for q in questions:
                question_text = q.get("question_text", "")
                if question_text:
                    matches = self._search_matches(question_text, limit=5)
                    q["matches"] = matches

            logger.info(f"识别完成: 找到 {len(questions)} 道题目")
            return result

        except Exception as e:
            logger.error(f"识别失败: {str(e)}", exc_info=True)
            raise

    async def recognize_pdf(
        self,
        pdf_bytes: bytes,
        filename: str,
        user_id: int
    ) -> Dict[str, Any]:
        """
        识别PDF文件中的错题

        Args:
            pdf_bytes: PDF字节数据
            filename: 文件名
            user_id: 用户ID

        Returns:
            识别结果字典
        """
        logger.info(f"开始识别PDF: {filename}, 用户: {user_id}")

        # 转换PDF为图片
        page_images = pdf_to_images(pdf_bytes)
        total_pages = len(page_images)

        if total_pages == 0:
            raise ValueError("PDF中没有页面")

        # 处理每一页
        all_questions = []
        page_results = []
        all_warnings = []
        any_enhanced = False

        for page_num, img_bytes in enumerate(page_images):
            try:
                result = await recognize_questions(img_bytes, f"page_{page_num + 1}.jpg")
                questions = result.get("questions", [])
                warnings = result.get("warnings", [])
                enhanced = result.get("enhanced", False)

                # 为每个题目搜索匹配
                for q in questions:
                    question_text = q.get("question_text", "")
                    if question_text:
                        matches = self._search_matches(question_text, limit=5)
                        q["matches"] = matches

                all_questions.extend(questions)
                page_results.append({
                    "page": page_num + 1,
                    "status": "ok",
                    "count": len(questions)
                })

                if warnings:
                    all_warnings.extend([f"第{page_num + 1}页: {w}" for w in warnings])
                if enhanced:
                    any_enhanced = True

            except Exception as e:
                logger.error(f"处理第{page_num + 1}页失败: {str(e)}")
                page_results.append({
                    "page": page_num + 1,
                    "status": "error",
                    "error": str(e)
                })

        return {
            "questions": all_questions,
            "page_results": page_results,
            "warnings": all_warnings,
            "enhanced": any_enhanced,
            "total_pages": total_pages
        }

    async def recognize_advanced(
        self,
        image_bytes: bytes,
        filename: str,
        user_id: int,
        has_correction_marks: bool = False
    ) -> Dict[str, Any]:
        """
        高级识别：支持批改痕迹检测和去除

        Args:
            image_bytes: 图片字节数据
            filename: 文件名
            user_id: 用户ID
            has_correction_marks: 是否包含批改痕迹

        Returns:
            识别结果字典
        """
        logger.info(f"开始高级识别: {filename}, 用户: {user_id}, 批改痕迹: {has_correction_marks}")

        enhanced = False
        warnings = []

        # 如果有批改痕迹，先去除
        if has_correction_marks:
            try:
                cleaned_bytes = remove_red_marks(image_bytes)
                image_bytes = cleaned_bytes
                enhanced = True
                warnings.append("已自动去除红色批改痕迹")
            except Exception as e:
                logger.warning(f"去除批改痕迹失败: {str(e)}")
                warnings.append(f"去除批改痕迹失败: {str(e)}")

        # 识别题目
        result = await recognize_questions(image_bytes, filename)
        questions = result.get("questions", [])

        # 为每个题目搜索匹配
        for q in questions:
            question_text = q.get("question_text", "")
            if question_text:
                matches = self._search_matches(question_text, limit=5)
                q["matches"] = matches

        result["enhanced"] = enhanced
        result["warnings"] = warnings + result.get("warnings", [])

        return result

    def _search_matches(
        self,
        question_text: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        在题库中搜索匹配的题目

        Args:
            question_text: 题目文本
            limit: 返回结果数量限制

        Returns:
            匹配的题目列表
        """
        if not question_text or len(question_text) < 5:
            return []

        # 标准化文本
        norm_text = self._normalize_text(question_text)

        # 先尝试精确匹配
        best_match = self._find_best_match(norm_text)
        if best_match:
            return [best_match]

        # 模糊搜索
        questions = self.db.query(Question).limit(1000).all()
        matches = []

        for q in questions:
            q_norm = self._normalize_text(q.question_text)
            ratio = self._similarity_ratio(norm_text, q_norm)

            if ratio > 0.6:  # 相似度阈值
                matches.append({
                    "question_id": q.question_id,
                    "q_id": q.q_id,
                    "question_text": q.question_text,
                    "knowledge_point": q.knowledge_point,
                    "similarity": round(ratio, 2)
                })

        # 按相似度排序
        matches.sort(key=lambda x: x["similarity"], reverse=True)
        return matches[:limit]

    def _normalize_text(self, text: str) -> str:
        """标准化文本：去除空白、标点等"""
        import re
        text = re.sub(r'\s+', '', text)
        text = re.sub(r'[，。！？、；：""''（）【】《》\.,!?;:()\[\]<>"\']', '', text)
        return text.lower()

    def _find_best_match(self, norm_text: str) -> Optional[Dict[str, Any]]:
        """查找最佳匹配（精确匹配）"""
        questions = self.db.query(Question).limit(1000).all()

        for q in questions:
            q_norm = self._normalize_text(q.question_text)
            if q_norm == norm_text:
                return {
                    "question_id": q.question_id,
                    "q_id": q.q_id,
                    "question_text": q.question_text,
                    "knowledge_point": q.knowledge_point,
                    "similarity": 1.0
                }
        return None

    def _similarity_ratio(self, text1: str, text2: str) -> float:
        """计算两个文本的相似度"""
        import difflib
        return difflib.SequenceMatcher(None, text1, text2).ratio()

    async def batch_generate_and_dedup(
        self,
        questions: List[Dict[str, Any]],
        user_id: int
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        批量生成答案并去重

        Args:
            questions: 识别的题目列表
            user_id: 用户ID

        Returns:
            (去重后的题目列表, 警告信息列表)
        """
        from ..utils.deepseek import generate_answer

        warnings = []
        unique_questions = []
        seen_texts = set()

        for q in questions:
            question_text = q.get("question_text", "")
            norm_text = self._normalize_text(question_text)

            # 去重
            if norm_text in seen_texts:
                warnings.append(f"跳过重复题目: {question_text[:30]}...")
                continue

            seen_texts.add(norm_text)

            # 生成答案（如果没有）
            if not q.get("answer") and question_text:
                try:
                    answer_result = await generate_answer(question_text)
                    q["answer"] = answer_result.get("answer", "")
                    q["solution"] = answer_result.get("solution", "")
                except Exception as e:
                    logger.warning(f"生成答案失败: {str(e)}")
                    warnings.append(f"生成答案失败: {question_text[:30]}...")

            unique_questions.append(q)

        return unique_questions, warnings

    def create_recognition_task(
        self,
        user_id: int,
        file_url: str,
        file_type: str,
        page_count: int,
        recognition_mode: str = "advanced"
    ) -> WrongQuestionRecognitionTask:
        """
        创建识别任务

        Args:
            user_id: 用户ID
            file_url: 文件URL
            file_type: 文件类型
            page_count: 页数
            recognition_mode: 识别模式

        Returns:
            创建的任务对象
        """
        task = WrongQuestionRecognitionTask(
            user_id=user_id,
            file_url=file_url,
            file_type=file_type,
            page_count=page_count,
            recognition_mode=recognition_mode,
            status="pending"
        )
        return self.task_repo.create(task)

    def get_task(self, task_id: int) -> Optional[WrongQuestionRecognitionTask]:
        """获取识别任务"""
        return self.task_repo.get_by_id(task_id)

    def update_task_status(
        self,
        task_id: int,
        status: str,
        error_message: Optional[str] = None
    ):
        """更新任务状态"""
        task = self.get_task(task_id)
        if task:
            task.status = status
            if error_message:
                task.error_message = error_message
            self.db.commit()
