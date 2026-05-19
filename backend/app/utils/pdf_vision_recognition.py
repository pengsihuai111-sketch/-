"""
PDF recognition using vision model.

This module provides a robust PDF recognition pipeline:
1. Convert PDF pages to high-quality images
2. Use vision model (glm-4.6v) to recognize each page
3. Extract structured questions from each page
4. Merge results from all pages
"""
import logging
import base64
import io
from typing import List, Dict, Optional
from PIL import Image
import fitz  # PyMuPDF

from .deepseek import call_vision_llm

logger = logging.getLogger(__name__)


def pdf_to_images(pdf_bytes: bytes, dpi: int = 200) -> List[Image.Image]:
    """Convert PDF pages to PIL images.

    Args:
        pdf_bytes: PDF file bytes
        dpi: Resolution for rendering (default 200 for good quality)

    Returns:
        List of PIL Image objects, one per page
    """
    images = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for page_num in range(len(doc)):
        page = doc[page_num]
        # Render at specified DPI
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)

        # Convert to PIL Image
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        images.append(img)

        logger.info(f"Converted page {page_num + 1}/{len(doc)} to image ({img.width}x{img.height})")

    doc.close()
    return images


def image_to_base64(img: Image.Image, format: str = "PNG") -> str:
    """Convert PIL Image to base64 string.

    Args:
        img: PIL Image object
        format: Image format (PNG, JPEG, etc.)

    Returns:
        Base64 encoded image string
    """
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


async def recognize_page(
    img: Image.Image,
    page_num: int,
    total_pages: int,
) -> List[Dict]:
    """Recognize questions from a single PDF page using vision model.

    Args:
        img: PIL Image of the page
        page_num: Page number (1-indexed)
        total_pages: Total number of pages

    Returns:
        List of question dicts extracted from this page
    """
    # Convert image to base64
    img_base64 = image_to_base64(img)

    system_prompt = """你是小学数学题目识别助手。从试卷图片中识别所有题目并解答。

任务：
1. 识别图片中的所有题目（通过题号：1. 2. 3. 或 一、二、三、或 (1) (2) 或 ① ② 等）
2. 提取每道题的完整内容（题干+所有子问题）
3. 给出答案和解析（简洁明了）
4. 判断题型、知识点、难度

重要规则：
1. 图片中有几道题就提取几道，不能遗漏
2. 多个子问题（(1)(2)或①②）合并为一道大题
3. 题目内容必须完整准确
4. 数学公式用 LaTeX 格式：\\frac{1}{2}、\\sqrt{3}、x^2
5. 答案必须包含单位（米、千克、元等）
6. 解析要简洁，说明关键步骤
7. 多子问答案用分号分隔："(1)答案1; (2)答案2"
8. 如果题目不完整或看不清，设置 is_complete=false

输出纯 JSON 数组格式：
[
  {
    "question_no": "题号",
    "question_text": "完整题目内容",
    "answer": "答案",
    "solution": "简洁解析",
    "question_type": "fill_blank|choice|calculation|problem_solving|other",
    "difficulty": "基础|中等|挑战",
    "knowledge_point": "知识点",
    "knowledge_category": "几何|计算|数论|方程与应用|逻辑|基础|其他",
    "is_complete": true,
    "confidence": 0.95
  }
]

注意：
- 直接输出JSON数组，不要包裹在其他对象中
- 如果页面没有题目，返回空数组 []
- 答案和解析要简洁，避免过长"""

    user_prompt = f"""这是试卷的第 {page_num}/{total_pages} 页，请识别并提取这一页中的所有题目。

要求：
1. 仔细识别题号，不要遗漏任何题目
2. 题目内容要完整准确，包括所有子问题
3. 数学公式要用LaTeX格式
4. 答案和解析要简洁

请直接输出JSON数组格式的题目列表。"""

    try:
        logger.info(f"Calling vision model for page {page_num}/{total_pages}")

        response = await call_vision_llm(
            image_data=img_base64,
            prompt=user_prompt,
            system_prompt=system_prompt,
            timeout=120.0,
        )

        logger.info(f"Vision model response length: {len(response)} chars")

        # Parse JSON response
        import json
        import re

        # Try to extract JSON array from response
        response = response.strip()

        # Remove markdown code blocks if present
        if response.startswith("```"):
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response)
            if match:
                response = match.group(1).strip()

        # Parse JSON
        try:
            questions = json.loads(response)
        except json.JSONDecodeError as e:
            logger.warning(f"Direct JSON parse failed: {e}, trying to extract array")
            # Try to find JSON array in the response
            match = re.search(r'\[[\s\S]*\]', response)
            if match:
                questions = json.loads(match.group(0))
            else:
                logger.error(f"Cannot find valid JSON array in response: {response[:500]}")
                raise ValueError(f"无法解析视觉模型返回的JSON格式: {str(e)}")

        # Ensure it's a list
        if not isinstance(questions, list):
            logger.warning(f"Response is not a list, wrapping it")
            questions = [questions] if questions else []

        # Add page_no to each question
        for q in questions:
            q['page_no'] = page_num

        logger.info(f"Page {page_num} extracted {len(questions)} questions")
        return questions

    except Exception as e:
        logger.error(f"Failed to recognize page {page_num}: {e}")
        raise


async def recognize_pdf_with_vision(
    pdf_bytes: bytes,
    progress_callback=None,
    dpi: int = 200,
) -> List[Dict]:
    """Recognize all questions from PDF using vision model.

    Args:
        pdf_bytes: PDF file bytes
        progress_callback: Optional callback for progress updates
        dpi: Resolution for rendering pages

    Returns:
        List of all questions from all pages
    """
    logger.info(f"Starting PDF vision recognition")

    # Convert PDF to images
    images = pdf_to_images(pdf_bytes, dpi=dpi)
    total_pages = len(images)
    logger.info(f"PDF has {total_pages} pages")

    if progress_callback:
        progress_callback(f"PDF共{total_pages}页，开始识别...")

    # Recognize each page
    all_questions = []
    for i, img in enumerate(images):
        page_num = i + 1
        try:
            if progress_callback:
                progress_callback(f"正在识别第{page_num}/{total_pages}页...")

            questions = await recognize_page(img, page_num, total_pages)
            all_questions.extend(questions)
            logger.info(f"Page {page_num}/{total_pages}: extracted {len(questions)} questions")

            if progress_callback:
                progress_callback(f"第{page_num}页识别完成，找到{len(questions)}道题")
        except Exception as e:
            logger.warning(f"Page {page_num}/{total_pages} failed: {e}, continuing with next page")
            if progress_callback:
                progress_callback(f"第{page_num}页识别失败: {str(e)}")
            continue

    logger.info(f"Total extracted {len(all_questions)} questions from {total_pages} pages")
    if progress_callback:
        progress_callback(f"识别完成！共找到{len(all_questions)}道题")

    return all_questions
