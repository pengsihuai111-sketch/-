"""PDF recognition helpers based on the vision model."""

from __future__ import annotations

import base64
import io
import json
import logging
import re
from typing import Dict, List

import fitz  # PyMuPDF
from PIL import Image

from .deepseek import call_vision_llm, _extract_json_objects, _fix_latex_json_escapes

logger = logging.getLogger(__name__)


def pdf_to_images(pdf_bytes: bytes, dpi: int = 200) -> List[Image.Image]:
    """Convert PDF pages to PIL images."""
    images: List[Image.Image] = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            images.append(img)
            logger.info(f"Converted page {page_num + 1}/{len(doc)} to image ({img.width}x{img.height})")
    finally:
        doc.close()
    return images


def image_to_base64(img: Image.Image, format: str = "PNG") -> str:
    """Convert a PIL image to base64."""
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _parse_questions_response(response: str) -> List[Dict]:
    """Parse vision-model output into a list of questions."""
    response = response.strip()
    if response.startswith("```"):
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response)
        if match:
            response = match.group(1).strip()

    response = _fix_latex_json_escapes(response)

    try:
        parsed = json.loads(response)
    except json.JSONDecodeError as exc:
        logger.warning(f"Direct JSON parse failed: {exc}, trying array extraction")
        match = re.search(r"\[[\s\S]*\]", response)
        if match:
            try:
                parsed = json.loads(_fix_latex_json_escapes(match.group(0)))
            except json.JSONDecodeError:
                parsed = None
        else:
            parsed = None

        if parsed is None:
            recovered = _extract_json_objects(response)
            if recovered:
                return recovered
            logger.error(f"Cannot recover valid JSON from response: {response[:500]}")
            raise ValueError(f"无法解析视觉模型返回的 JSON 格式: {exc}") from exc

    questions = parsed.get("questions", []) if isinstance(parsed, dict) else parsed
    if not isinstance(questions, list):
        questions = [questions] if questions else []
    return questions


async def recognize_page(img: Image.Image, page_num: int, total_pages: int) -> List[Dict]:
    """Recognize all questions from one PDF page."""
    img_base64 = image_to_base64(img)

    system_prompt = """你是小学数学题目识别助手。请从整页试卷图片中识别题目，并返回严格 JSON。

要求：
1. 识别该页所有题目。
2. 题目文字尽量完整。
3. 补充 answer 和 solution，尽量简洁。
4. 无法确认时允许留空，但 question_text 要保留。

返回数组：
[
  {
    "question_no": "1",
    "question_text": "完整题目内容",
    "answer": "答案",
    "solution": "简要解析",
    "question_type": "fill_blank|choice|calculation|problem_solving|other",
    "difficulty": "基础|中等|挑战",
    "knowledge_point": "知识点",
    "knowledge_category": "几何|计算|数论|方程与应用|逻辑|基础|其他",
    "is_complete": true,
    "confidence": 0.9
  }
]"""

    user_prompt = (
        f"这是试卷的第 {page_num}/{total_pages} 页。"
        "请识别这一页中的所有题目，并只返回 JSON 数组。"
    )

    logger.info(f"Calling vision model for page {page_num}/{total_pages}")
    response = await call_vision_llm(
        image_data=img_base64,
        prompt=user_prompt,
        system_prompt=system_prompt,
        timeout=120.0,
    )
    logger.info(f"Vision model response length: {len(response)} chars")

    questions = _parse_questions_response(response)
    for question in questions:
        question["page_no"] = page_num

    logger.info(f"Page {page_num} extracted {len(questions)} questions")
    return questions


async def recognize_pdf_with_vision(pdf_bytes: bytes, progress_callback=None, dpi: int = 200) -> List[Dict]:
    """Recognize all questions from a PDF using the vision model."""
    logger.info("Starting PDF vision recognition")
    images = pdf_to_images(pdf_bytes, dpi=dpi)
    total_pages = len(images)
    logger.info(f"PDF has {total_pages} pages")

    if progress_callback:
        progress_callback(f"PDF 共 {total_pages} 页，开始识别...")

    all_questions: List[Dict] = []
    for index, img in enumerate(images, start=1):
        try:
            if progress_callback:
                progress_callback(f"正在识别第 {index}/{total_pages} 页...")
            questions = await recognize_page(img, index, total_pages)
            all_questions.extend(questions)
            logger.info(f"Page {index}/{total_pages}: extracted {len(questions)} questions")
            if progress_callback:
                progress_callback(f"第 {index} 页识别完成，找到 {len(questions)} 道题")
        except Exception as exc:
            logger.warning(f"Page {index}/{total_pages} failed: {exc}, continuing")
            if progress_callback:
                progress_callback(f"第 {index} 页识别失败：{exc}")

    logger.info(f"Total extracted {len(all_questions)} questions from {total_pages} pages")
    if progress_callback:
        progress_callback(f"识别完成，共找到 {len(all_questions)} 道题")
    return all_questions
