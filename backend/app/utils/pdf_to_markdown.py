"""PDF to Markdown conversion for question extraction.

Converts PDF to structured markdown text, then uses LLM to extract questions.
This approach is more accurate and cost-effective than image-based recognition.
"""
import logging
import re
from typing import List, Dict, Optional, Tuple
import fitz  # PyMuPDF
from PIL import Image
from io import BytesIO

logger = logging.getLogger(__name__)

# Try to import OCR libraries
try:
    import pytesseract
    # Configure Tesseract path for Windows
    # If Tesseract is installed in default location, set the path
    import os
    if os.name == 'nt':  # Windows
        tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        if os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract not available - OCR fallback disabled")


def pdf_to_markdown(pdf_bytes: bytes, max_pages: int = 30, use_ocr_fallback: bool = True) -> Tuple[str, bool]:
    """Convert PDF to markdown text with enhanced text extraction.

    Extracts text from PDF and structures it as markdown.
    Preserves layout, formatting, and mathematical expressions.
    If PDF is scanned (no text layer), falls back to OCR.

    Args:
        pdf_bytes: Raw PDF file bytes
        max_pages: Maximum number of pages to process
        use_ocr_fallback: Whether to use OCR when no text is found

    Returns:
        Tuple of (markdown_text, used_ocr)
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = min(len(doc), max_pages) if max_pages > 0 else len(doc)

    if total_pages == 0:
        raise ValueError("PDF 文件为空")

    markdown_parts = []
    pages_with_text = 0
    used_ocr = False

    for page_num in range(total_pages):
        page = doc[page_num]

        # Try multiple extraction methods for better accuracy
        # Method 1: Extract with layout preservation (best for structured documents)
        text_blocks = page.get_text("blocks", sort=True)

        # Method 2: Also get plain text as fallback
        plain_text = page.get_text("text", sort=True)

        if not text_blocks and not plain_text.strip():
            logger.warning(f"Page {page_num + 1} has no text content")

            # Try OCR as fallback for scanned pages
            if use_ocr_fallback and TESSERACT_AVAILABLE:
                logger.info(f"Attempting OCR on page {page_num + 1}")
                try:
                    ocr_text = _ocr_page(page)
                    if ocr_text and len(ocr_text.strip()) > 10:
                        logger.info(f"OCR extracted {len(ocr_text)} chars from page {page_num + 1}")
                        plain_text = ocr_text
                        used_ocr = True
                    else:
                        logger.warning(f"OCR returned insufficient text for page {page_num + 1}")
                        continue
                except Exception as e:
                    logger.error(f"OCR failed on page {page_num + 1}: {e}")
                    continue
            else:
                continue

        pages_with_text += 1

        # Add page marker
        markdown_parts.append(f"\n\n---\n**第 {page_num + 1} 页**\n---\n\n")

        # Process text blocks for better structure
        if text_blocks and not used_ocr:
            structured_text = _process_text_blocks(text_blocks)
            markdown_parts.append(structured_text)
            logger.info(f"Page {page_num + 1}/{total_pages}: extracted {len(structured_text)} chars from blocks")
        else:
            # Fallback to plain text (or OCR text)
            cleaned_text = _clean_and_structure_text(plain_text)
            markdown_parts.append(cleaned_text)
            logger.info(f"Page {page_num + 1}/{total_pages}: extracted {len(plain_text)} chars from {'OCR' if used_ocr else 'plain text'}")

    doc.close()

    if pages_with_text == 0:
        logger.error(f"PDF has {total_pages} pages but none contain extractable text")
        if not use_ocr_fallback or not TESSERACT_AVAILABLE:
            raise ValueError("PDF是扫描件或图片格式，无法提取文本。请安装 Tesseract OCR 或使用图片识别方式。")
        else:
            raise ValueError("PDF是扫描件且 OCR 识别失败，无法提取文本")

    markdown_content = "".join(markdown_parts)
    logger.info(f"PDF converted to markdown: {len(markdown_content)} chars total from {pages_with_text}/{total_pages} pages (OCR: {used_ocr})")

    return markdown_content, used_ocr


def _ocr_page(page) -> str:
    """Extract text from a PDF page using OCR.

    Args:
        page: PyMuPDF page object

    Returns:
        Extracted text
    """
    if not TESSERACT_AVAILABLE:
        raise RuntimeError("Tesseract OCR not available")

    # Ensure Tesseract path is configured (especially important for Windows)
    import os
    if os.name == 'nt':  # Windows
        tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        if os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path

    # Render page to image at high resolution for better OCR
    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))  # 2x scale for better quality
    img_bytes = pix.tobytes("png")

    # Convert to PIL Image
    pil_image = Image.open(BytesIO(img_bytes))

    # Perform OCR (Chinese + English)
    ocr_text = pytesseract.image_to_string(pil_image, lang="chi_sim+eng")

    return ocr_text


def _process_text_blocks(blocks: list) -> str:
    """Process text blocks from PDF for better structure preservation.

    Text blocks contain position information which helps preserve layout.
    """
    lines = []
    prev_y = None

    for block in blocks:
        # block format: (x0, y0, x1, y1, "text", block_no, block_type)
        if len(block) < 5:
            continue

        x0, y0, x1, y1, text = block[:5]

        # Skip empty blocks
        if not text or not text.strip():
            continue

        text = text.strip()

        # Detect vertical spacing (new paragraph)
        if prev_y is not None and y0 - prev_y > 20:
            lines.append("")  # Add blank line for paragraph break

        # Format question numbers
        text = _format_question_numbers(text)

        lines.append(text)
        prev_y = y1

    return "\n".join(lines)


def _format_question_numbers(text: str) -> str:
    """Format question numbers with markdown bold."""
    # Patterns for question numbers
    patterns = [
        (r'^(\d+)[.、]\s*', r'**\1.** '),  # 1. or 1、
        (r'^([一二三四五六七八九十百]+)[、.]\s*', r'**\1、** '),  # 一、
        (r'^\((\d+)\)\s*', r'**(\1)** '),  # (1)
        (r'^([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳])\s*', r'**\1** '),  # ①
    ]

    for pattern, replacement in patterns:
        if re.match(pattern, text):
            text = re.sub(pattern, replacement, text)
            break

    return text


def _clean_and_structure_text(text: str) -> str:
    """Clean and structure extracted text (fallback method).

    - Remove excessive whitespace
    - Preserve line breaks for readability
    - Detect and format question numbers
    - Preserve mathematical expressions
    """
    # Remove excessive blank lines (more than 2 consecutive)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove page numbers and headers/footers (common patterns)
    text = re.sub(r'^\s*第?\s*\d+\s*页\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*-\s*\d+\s*-\s*$', '', text, flags=re.MULTILINE)

    lines = text.split('\n')
    formatted_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            formatted_lines.append('')
            continue

        # Format question numbers
        line = _format_question_numbers(line)

        formatted_lines.append(line)

    return '\n'.join(formatted_lines)


async def extract_questions_from_markdown(
    markdown_text: str,
    llm_caller,
    pdf_images: Optional[Dict[int, List[bytes]]] = None,
) -> List[Dict]:
    """Extract structured questions from markdown text using LLM.

    Args:
        markdown_text: Markdown-formatted text from PDF
        llm_caller: Async function to call text LLM
        pdf_images: Deprecated parameter, no longer used (kept for compatibility)

    Returns:
        List of question dicts with question_text, answer, solution, etc.
    """
    # Split markdown by pages to process in smaller chunks
    pages = markdown_text.split('---\n**第')

    # If only one page or small content, process all at once
    if len(pages) <= 2 or len(markdown_text) < 3000:
        return await _extract_questions_single_batch(markdown_text, llm_caller)

    # Process each page separately for large documents
    logger.info(f"Large document detected ({len(markdown_text)} chars, {len(pages)} pages), processing in batches")
    all_questions = []

    for i, page_content in enumerate(pages):
        if i == 0 and not page_content.strip():
            continue  # Skip empty first split

        # Reconstruct page marker
        if i > 0:
            page_content = '---\n**第' + page_content

        if not page_content.strip():
            continue

        logger.info(f"Processing batch {i}/{len(pages)-1}: {len(page_content)} chars")
        try:
            questions = await _extract_questions_single_batch(page_content, llm_caller)
            all_questions.extend(questions)
            logger.info(f"Batch {i} extracted {len(questions)} questions")
        except Exception as e:
            logger.warning(f"Batch {i} failed: {e}, continuing with next batch")
            continue

    logger.info(f"Total extracted {len(all_questions)} questions from {len(pages)} batches")
    return all_questions


async def _extract_questions_single_batch(markdown_text: str, llm_caller) -> List[Dict]:
    """Extract questions from a single batch of markdown text."""
    system_prompt = """你是小学数学题目提取助手。从试卷文本中提取所有题目并解答。

任务：
1. 识别所有题目（通过题号：1. 2. 3. 或 一、二、三、或 (1) (2) 或 ① ② 等）
2. 提取每道题的完整内容（题干+所有子问题）
3. 给出答案和解析（简洁明了即可）
4. 判断题型、知识点、难度
5. 记录题目所在的页码（从页面标记"第 X 页"中识别）

重要规则：
1. 文本中有几道题就提取几道，不能遗漏
2. 多个子问题（(1)(2)或①②）合并为一道大题
3. 题目内容必须完整，从题号开始到下一题号或页面结束
4. 公式用 LaTeX 格式：\\frac{1}{2}、\\sqrt{3}、x^2
5. 答案必须包含单位（米、千克、元等）
6. 解析要简洁，说明关键步骤即可
7. 多子问答案用分号分隔："(1)答案1; (2)答案2"
8. 如果题目文字不完整或被截断，设置 is_complete=false
9. 忽略页眉、页脚、页码等无关内容
10. 从文本中的"第 X 页"标记识别题目所在页码，记录到 page_no 字段

特别注意：
- 题目可能跨越多行，要完整提取
- 注意识别数学符号：×（乘号）、÷（除号）、≈（约等于）、≥（大于等于）等
- 分数可能写成"1/2"或"二分之一"，统一转换为 LaTeX: \\frac{1}{2}
- 百分数如"50%"保持原样
- 单位要保留：米、千克、元、平方米等
- 页码从"---\n**第 X 页**\n---"标记中提取，如果题目在"第 3 页"标记之后，page_no 就是 3
- **答案和解析要简洁，避免冗长描述，确保JSON不会太长**

输出纯 JSON：
{
  "questions": [
    {
      "question_no": "题号",
      "question_text": "完整题目内容",
      "page_no": 1,
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
}"""

    user_prompt = f"""以下是从数学试卷PDF中提取的文本内容，请识别并提取所有题目：

{markdown_text}

请严格按照JSON格式输出所有题目。注意：
1. 仔细识别题号，不要遗漏任何题目
2. 题目内容要完整，包括所有子问题
3. 答案和解析要简洁"""

    try:
        logger.info(f"Calling LLM with markdown text ({len(markdown_text)} chars)")
        response = await llm_caller(
            messages=[{"role": "user", "content": user_prompt}],
            system_prompt=system_prompt,
            max_tokens=16384,  # Increased for longer responses
            timeout=180.0,
        )

        logger.info(f"LLM response length: {len(response)} chars")
        logger.debug(f"LLM response preview: {response[:500]}...")

        # Parse JSON response
        import json
        from .deepseek import _fix_latex_json_escapes, _parse_response

        response = _fix_latex_json_escapes(response)
        questions = _parse_response(response)

        logger.info(f"Extracted {len(questions)} questions from batch")
        return questions

    except Exception as e:
        logger.error(f"Failed to extract questions from batch: {e}")
        logger.debug(f"Markdown text length: {len(markdown_text)} chars")
        logger.debug(f"LLM response (if available): {response[:1000] if 'response' in locals() else 'N/A'}")
        raise


def _attach_images_to_questions(questions: List[Dict], pdf_images: Dict[int, List[bytes]]) -> List[Dict]:
    """Attach extracted PDF images to questions based on page number.

    Args:
        questions: List of question dicts (must include page_no field)
        pdf_images: Dict mapping page_num (0-indexed) -> list of image bytes

    Returns:
        Updated questions with image_urls field
    """
    from ..config import IMAGE_DIR
    import os
    import uuid

    os.makedirs(IMAGE_DIR, exist_ok=True)

    # Attach images to questions based on their page number
    for q in questions:
        if not q.get("has_image"):
            continue

        # Get question page number (1-indexed from LLM, convert to 0-indexed)
        page_no = q.get("page_no", 1) - 1

        # Collect images from the question's page
        question_images = []

        # Check if the page has images
        if page_no in pdf_images:
            for img_idx, img_bytes in enumerate(pdf_images[page_no]):
                img_name = f"pdf_img_{uuid.uuid4().hex[:8]}_p{page_no+1}_{img_idx+1}.png"
                img_path = os.path.join(IMAGE_DIR, img_name)
                with open(img_path, "wb") as f:
                    f.write(img_bytes)
                question_images.append(f"/uploads/images/{img_name}")
                logger.info(f"Saved image for question {q.get('question_no')} (page {page_no+1}): {img_name}")

        # If no images found on the question's page, check adjacent pages (for cross-page questions)
        if not question_images and page_no + 1 in pdf_images:
            logger.info(f"Question {q.get('question_no')} has no images on page {page_no+1}, checking next page")
            for img_idx, img_bytes in enumerate(pdf_images[page_no + 1]):
                img_name = f"pdf_img_{uuid.uuid4().hex[:8]}_p{page_no+2}_{img_idx+1}.png"
                img_path = os.path.join(IMAGE_DIR, img_name)
                with open(img_path, "wb") as f:
                    f.write(img_bytes)
                question_images.append(f"/uploads/images/{img_name}")
                logger.info(f"Saved image for question {q.get('question_no')} (page {page_no+2}): {img_name}")

        if question_images:
            q["image_urls"] = question_images
            logger.info(f"Attached {len(question_images)} images to question {q.get('question_no')} (page {page_no+1})")
        else:
            logger.warning(f"Question {q.get('question_no')} marked has_image=true but no images found on page {page_no+1}")

    return questions


def detect_has_images(pdf_bytes: bytes, max_pages: int = 30) -> Dict[int, bool]:
    """Detect which pages contain images/diagrams.

    Returns dict mapping page_num -> has_images
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = min(len(doc), max_pages) if max_pages > 0 else len(doc)

    page_images = {}

    for page_num in range(total_pages):
        page = doc[page_num]
        images = page.get_images()
        page_images[page_num] = len(images) > 0

        if images:
            logger.info(f"Page {page_num + 1} contains {len(images)} images")

    doc.close()
    return page_images


def extract_images_from_pdf(pdf_bytes: bytes, max_pages: int = 30, min_size: int = 5000) -> Dict[int, List[bytes]]:
    """Extract all images from PDF pages, filtering out small decorative images.

    Args:
        pdf_bytes: Raw PDF file bytes
        max_pages: Maximum number of pages to process
        min_size: Minimum image size in bytes (default 5KB to filter decorations)

    Returns:
        Dict mapping page_num -> list of image bytes
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = min(len(doc), max_pages) if max_pages > 0 else len(doc)

    page_images = {}

    for page_num in range(total_pages):
        page = doc[page_num]
        images = page.get_images()

        if not images:
            continue

        page_images[page_num] = []

        for img_index, img_info in enumerate(images):
            try:
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]

                # Filter out small images (likely decorations, icons, logos)
                if len(image_bytes) < min_size:
                    logger.info(f"Skipped small image on page {page_num + 1}: {len(image_bytes)} bytes")
                    continue

                # Check image dimensions
                img_width = base_image.get("width", 0)
                img_height = base_image.get("height", 0)
                if img_width < 50 or img_height < 50:
                    logger.info(f"Skipped tiny image on page {page_num + 1}: {img_width}x{img_height}px")
                    continue

                page_images[page_num].append(image_bytes)
                logger.info(
                    f"Extracted image {img_index + 1} from page {page_num + 1}: "
                    f"{len(image_bytes)} bytes, {img_width}x{img_height}px"
                )
            except Exception as e:
                logger.warning(f"Failed to extract image {img_index + 1} from page {page_num + 1}: {e}")

    doc.close()
    return page_images
