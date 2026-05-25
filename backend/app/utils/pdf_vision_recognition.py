"""PDF recognition helpers based on the vision model."""

from __future__ import annotations

import base64
import io
import json
import logging
import re
from typing import Dict, List, Optional, Set, Tuple

import fitz  # PyMuPDF
from PIL import Image

from .deepseek import call_vision_llm, _extract_json_objects, _fix_latex_json_escapes

logger = logging.getLogger(__name__)


def pdf_to_images(
    pdf_bytes: bytes,
    dpi: int = 200,
    page_numbers: Optional[Set[int]] = None,
) -> List[Tuple[int, Image.Image]]:
    """Convert selected PDF pages to PIL images."""
    images: List[Tuple[int, Image.Image]] = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        selected_pages = set(page_numbers or range(1, len(doc) + 1))
        for page_index in range(len(doc)):
            page_no = page_index + 1
            if page_no not in selected_pages:
                continue

            page = doc[page_index]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            images.append((page_no, img))
            logger.info(
                "Converted page %s/%s to image (%sx%s)",
                page_no,
                len(doc),
                img.width,
                img.height,
            )
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
        logger.warning("Direct JSON parse failed: %s, trying recovery", exc)
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
            logger.error("Cannot recover valid JSON from response: %s", response[:500])
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
1. 识别该页所有题目，不要漏掉页首、页尾或分栏中的题。
2. question_text 必须只包含原题题干、选项和必要图表文字，不要把答案或解析写进 question_text。
3. 题目文字必须完整；如果题目跨行、跨栏，请合并成一个完整 question_text。
4. answer 只写最终答案，尽量短，例如“75度”“3:5”“A”，不要写推导过程。
5. solution 只写解析过程，和 answer 严格分开。
6. 无法确认答案时允许 answer/solution 留空，但 question_text 必须保留。
7. 只输出 JSON，不要 Markdown 代码块。

返回格式：
{
  "questions": [
    {
      "question_no": "1",
      "question_text": "完整题目内容",
      "answer": "最终答案，不含解析",
      "solution": "简要解析，不含最终答案标签",
      "question_type": "fill_blank|choice|calculation|problem_solving|other",
      "difficulty": "基础|中等|挑战",
      "knowledge_point": "知识点",
      "knowledge_category": "行程|工程|经济|浓度|几何|计算|数论|方程与应用|逻辑推理|统计|基础|其他",
      "is_complete": true,
      "confidence": 0.9
    }
  ]
}"""

    user_prompt = (
        f"这是试卷的第 {page_num}/{total_pages} 页。"
        "请识别这一页中的所有题目，并只返回 JSON。"
    )

    logger.info("Calling vision model for page %s/%s", page_num, total_pages)
    response = await call_vision_llm(
        image_data=img_base64,
        prompt=user_prompt,
        system_prompt=system_prompt,
        timeout=120.0,
    )
    logger.info("Vision model response length: %s chars", len(response))

    questions = _parse_questions_response(response)
    for question in questions:
        question["page_no"] = page_num

    logger.info("Page %s extracted %s questions", page_num, len(questions))
    return questions


async def recognize_pdf_with_vision(
    pdf_bytes: bytes,
    progress_callback=None,
    dpi: int = 200,
    page_numbers: Optional[Set[int]] = None,
) -> List[Dict]:
    """Recognize questions from a full PDF or selected pages using the vision model."""
    logger.info("Starting PDF vision recognition")
    images = pdf_to_images(pdf_bytes, dpi=dpi, page_numbers=page_numbers)
    total_pages = max(page_numbers) if page_numbers else len(images)
    selected_count = len(images)
    logger.info(
        "PDF vision selected %s page(s), total marker %s",
        selected_count,
        total_pages,
    )

    if progress_callback:
        progress_callback(f"PDF 视觉识别准备处理 {selected_count} 页...")

    all_questions: List[Dict] = []
    for order, (page_no, img) in enumerate(images, start=1):
        try:
            if progress_callback:
                progress_callback(f"正在视觉补识别第 {page_no} 页（{order}/{selected_count}）...")
            questions = await recognize_page(img, page_no, total_pages)
            all_questions.extend(questions)
            logger.info("Page %s/%s: extracted %s questions", page_no, total_pages, len(questions))
            if progress_callback:
                progress_callback(f"第 {page_no} 页视觉补识别完成，找到 {len(questions)} 道题")
        except Exception as exc:
            logger.warning("Page %s/%s failed: %s, continuing", page_no, total_pages, exc)
            if progress_callback:
                progress_callback(f"第 {page_no} 页视觉补识别失败：{exc}")

    logger.info("Total extracted %s questions from %s selected pages", len(all_questions), selected_count)
    if progress_callback:
        progress_callback(f"视觉识别完成，共找到 {len(all_questions)} 道题")
    return all_questions
