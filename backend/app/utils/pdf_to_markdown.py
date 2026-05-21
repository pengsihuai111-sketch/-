"""PDF and markdown parsing helpers for wrong-question recognition."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from io import BytesIO
from typing import Callable, Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

logger = logging.getLogger(__name__)
_rapid_ocr_engine = None

PAGE_MARKER_TEMPLATE = "\n\n---\n**PAGE {page_no}**\n---\n\n"
PAGE_MARKER_REGEX = re.compile(
    r"---\s*\n\*\*(?:PAGE|Page|page|第)?\s*(\d+).*?\*\*\s*\n---\s*\n*",
    re.MULTILINE,
)
QUESTION_START_REGEX = re.compile(
    r"^\s*(?:题目|第)?\s*(\d+)\s*(?:题|[.．、:：)]|\))\s*(.+)?$",
    re.IGNORECASE,
)
MARKDOWN_PREFIX_REGEX = re.compile(r"^\s*(?:#{1,6}\s+|[-*+]\s+|>\s*)?")
HEADING_REGEX = re.compile(r"^\s{0,3}#{1,6}\s+")
DIVIDER_REGEX = re.compile(r"^[-*_]{3,}$")
ANSWER_HEADING_REGEX = re.compile(r"^\s*\*{0,2}\s*(?:答案|解答|解析)\s*[:：]?\s*\*{0,2}\s*$")
SECTION_DIVIDER_REGEX = re.compile(r"(?m)^\s*---+\s*$")


try:
    import pytesseract

    if os.name == "nt":
        tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract not available - OCR fallback disabled")


def _get_rapid_ocr_engine():
    global _rapid_ocr_engine
    if _rapid_ocr_engine is None:
        _rapid_ocr_engine = RapidOCR()
    return _rapid_ocr_engine


def _ocr_page_with_rapidocr(page) -> str:
    """Extract text from a PDF page using RapidOCR."""
    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
    img_bytes = pix.tobytes("png")
    engine = _get_rapid_ocr_engine()
    result, _ = engine(img_bytes)
    if not result:
        return ""
    lines = []
    for item in result:
        if len(item) < 2:
            continue
        text = str(item[1]).strip()
        if text:
            lines.append(text)
    return "\n".join(lines).strip()


def pdf_to_markdown(
    pdf_bytes: bytes,
    max_pages: int = 30,
    use_ocr_fallback: bool = True,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Tuple[str, bool]:
    """Convert PDF bytes into structured markdown text."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = min(len(doc), max_pages) if max_pages > 0 else len(doc)

    if total_pages == 0:
        raise ValueError("PDF file is empty")

    markdown_parts: List[str] = []
    pages_with_text = 0
    used_ocr = False

    try:
        for page_index in range(total_pages):
            page = doc[page_index]
            text_blocks = page.get_text("blocks", sort=True)
            plain_text = page.get_text("text", sort=True)

            if not text_blocks and not plain_text.strip():
                logger.warning(f"Page {page_index + 1} has no text layer")
                if use_ocr_fallback:
                    try:
                        plain_text = _ocr_page(page) if TESSERACT_AVAILABLE else _ocr_page_with_rapidocr(page)
                        if not plain_text.strip():
                            continue
                        used_ocr = True
                    except Exception as exc:
                        logger.error(f"OCR failed on page {page_index + 1}: {exc}")
                        continue
                else:
                    continue

            pages_with_text += 1
            markdown_parts.append(PAGE_MARKER_TEMPLATE.format(page_no=page_index + 1))

            if text_blocks and not used_ocr:
                structured_text = _process_text_blocks(text_blocks)
                markdown_parts.append(structured_text)
                logger.info(
                    f"Page {page_index + 1}/{total_pages}: extracted {len(structured_text)} chars from blocks"
                )
            else:
                cleaned_text = _clean_and_structure_text(plain_text)
                markdown_parts.append(cleaned_text)
                logger.info(
                    f"Page {page_index + 1}/{total_pages}: extracted {len(plain_text)} chars from "
                    f"{'OCR' if used_ocr else 'plain text'}"
                )

            if progress_callback:
                progress_callback(
                    page_index + 1,
                    total_pages,
                    f"正在读取第 {page_index + 1}/{total_pages} 页...",
                )
    finally:
        doc.close()

    if pages_with_text == 0:
        if not use_ocr_fallback:
            raise ValueError("Unable to extract text from PDF")
        raise ValueError("PDF OCR failed")

    markdown_content = "".join(markdown_parts)
    logger.info(
        f"PDF converted to markdown: {len(markdown_content)} chars total from "
        f"{pages_with_text}/{total_pages} pages (OCR: {used_ocr})"
    )
    return markdown_content, used_ocr


def _ocr_page(page) -> str:
    """Extract text from a PDF page using OCR."""
    if not TESSERACT_AVAILABLE:
        raise RuntimeError("Tesseract OCR not available")

    if os.name == "nt":
        tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(tesseract_path):
            pytesseract.pytesseract.tesseract_cmd = tesseract_path

    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
    img_bytes = pix.tobytes("png")
    pil_image = Image.open(BytesIO(img_bytes))
    return pytesseract.image_to_string(pil_image, lang="chi_sim+eng")


def _process_text_blocks(blocks: list) -> str:
    """Process text blocks while preserving rough document structure."""
    lines: List[str] = []
    prev_y = None

    for block in blocks:
        if len(block) < 5:
            continue

        _, y0, _, y1, text = block[:5]
        if not text or not text.strip():
            continue

        text = text.strip()
        if prev_y is not None and y0 - prev_y > 20:
            lines.append("")

        lines.append(_format_question_numbers(text))
        prev_y = y1

    return "\n".join(lines)


def _format_question_numbers(text: str) -> str:
    """Apply light formatting to common question-number prefixes."""
    patterns = [
        (r"^(\d+)\s*[.．、]\s*", r"**\1.** "),
        (r"^([一二三四五六七八九十百千]+)\s*[、.．]\s*", r"**\1、** "),
        (r"^\((\d+)\)\s*", r"**(\1)** "),
        (r"^([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱])\s*", r"**\1** "),
    ]
    for pattern, replacement in patterns:
        if re.match(pattern, text):
            return re.sub(pattern, replacement, text)
    return text


def _clean_and_structure_text(text: str) -> str:
    """Normalize raw text extracted from PDF."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"^\s*第\s*\d+\s*页\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*-\s*\d+\s*-\s*$", "", text, flags=re.MULTILINE)

    formatted_lines: List[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            formatted_lines.append("")
            continue
        formatted_lines.append(_format_question_numbers(line))
    return "\n".join(formatted_lines)


def _guess_question_type(question_text: str) -> str:
    """Best-effort question type detection for local fallback parsing."""
    text = (question_text or "").strip()
    if not text:
        return "other"

    if re.search(r"[A-D][.．、\s]", text) or re.search(r"选择|选出|正确的是|错误的是", text):
        return "choice"

    if "填空" in text or re.search(r"[_＿]{2,}|（\s*）|\(\s*\)", text):
        return "fill_blank"

    if any(keyword in text for keyword in ("解答", "应用题", "证明", "思考", "解决问题")):
        return "problem_solving"

    if re.search(r"[+\-×xX÷/=%]|计算|求[值积和差商]", text):
        return "calculation"

    return "other"


def _extract_page_sections(markdown_text: str) -> List[Tuple[int, str]]:
    """Split markdown into page sections using page markers when available."""
    matches = list(PAGE_MARKER_REGEX.finditer(markdown_text))
    if not matches:
        return [(1, markdown_text)]

    sections: List[Tuple[int, str]] = []
    for index, match in enumerate(matches):
        try:
            page_no = int(match.group(1))
        except (TypeError, ValueError):
            page_no = index + 1

        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown_text)
        content = markdown_text[start:end].strip()
        if content:
            sections.append((page_no, content))

    return sections or [(1, markdown_text)]


def _extract_questions_from_markdown_locally(markdown_text: str) -> List[Dict]:
    """Extract numbered questions without relying on an LLM."""
    page_sections = _extract_page_sections(markdown_text)
    questions: List[Dict] = []
    current_question: Optional[Dict[str, object]] = None

    def flush_current_question() -> None:
        nonlocal current_question
        if not current_question:
            return

        question_data = current_question
        current_question = None
        text = "\n".join(question_data["lines"]).strip()
        if not text:
            return

        questions.append(
            {
                "question_no": question_data["question_no"],
                "question_text": text,
                "page_no": question_data["page_no"],
                "answer": "",
                "solution": "",
                "question_type": _guess_question_type(text),
                "difficulty": "中等",
                "knowledge_point": "",
                "knowledge_category": "其他",
                "is_complete": True,
                "confidence": 0.55,
            }
        )

    for page_no, content in page_sections:
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                if current_question and current_question["lines"] and current_question["lines"][-1] != "":
                    current_question["lines"].append("")
                continue

            line = MARKDOWN_PREFIX_REGEX.sub("", line).strip()
            line = re.sub(r"^\*\*(.+?)\*\*$", r"\1", line).strip()
            line = re.sub(r"^\*\*(\d+\s*(?:[.．、:：)]|\)))\*\*\s*", r"\1 ", line).strip()

            question_match = QUESTION_START_REGEX.match(line)
            if question_match:
                flush_current_question()
                question_no = question_match.group(1)
                rest = (question_match.group(2) or "").strip()
                current_question = {
                    "question_no": question_no,
                    "page_no": page_no,
                    "lines": [f"{question_no}. {rest}".rstrip()],
                }
                continue

            if HEADING_REGEX.match(raw_line.strip()) or DIVIDER_REGEX.match(line):
                continue

            if current_question:
                current_question["lines"].append(line)

        flush_current_question()

    logger.info(f"Local markdown fallback extracted {len(questions)} questions")
    section_questions = _extract_questions_from_markdown_sections(markdown_text)
    if len(section_questions) > len(questions):
        logger.info(
            "Section markdown fallback extracted %s questions, replacing numbered result of %s",
            len(section_questions),
            len(questions),
        )
        return section_questions
    return questions


def _strip_markdown_heading(line: str) -> str:
    line = MARKDOWN_PREFIX_REGEX.sub("", line or "").strip()
    line = re.sub(r"^\*\*(.+?)\*\*$", r"\1", line).strip()
    line = re.sub(r"^\*\*(\d+\s*(?:[.．、:：)]|\)))\*\*\s*", r"\1 ", line).strip()
    return line


def _clean_markdown_question_section(section: str) -> str:
    """Clean one markdown section that likely contains exactly one question."""
    lines: List[str] = []
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue

        if line.startswith(">") and ("注" in line or "说明" in line):
            continue
        stripped = _strip_markdown_heading(line)
        if ANSWER_HEADING_REGEX.match(stripped):
            break
        if ("注：" in stripped or "说明：" in stripped) and "题" in stripped and "分" in stripped:
            continue
        if DIVIDER_REGEX.match(stripped):
            continue
        lines.append(stripped)

    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines).strip()


def _section_title_has_question_signal(text: str) -> bool:
    if not text:
        return False
    signals = (
        "题",
        "选择",
        "填空",
        "解答",
        "计算",
        "应用",
        "如图",
        "求",
        "多少",
        "如果",
        "已知",
        "A.",
        "A．",
        "A、",
    )
    return any(signal in text for signal in signals)


def _extract_questions_from_markdown_sections(markdown_text: str) -> List[Dict]:
    """Extract one question per markdown section split by horizontal dividers."""
    raw_sections = SECTION_DIVIDER_REGEX.split(markdown_text)
    questions: List[Dict] = []
    used_question_nos: set[str] = set()

    for raw_section in raw_sections:
        text = _clean_markdown_question_section(raw_section)
        if not text:
            continue

        lines = [line for line in text.splitlines() if line.strip()]
        if len(lines) == 1 and not _section_title_has_question_signal(lines[0]):
            continue

        compact_text = re.sub(r"\s+", "", text)
        if len(compact_text) < 12:
            continue
        if not _section_title_has_question_signal(text):
            continue

        question_no = str(len(questions) + 1)
        title_match = re.search(r"(?:题目|解答题|选择题|填空题)\s*(\d+)", text)
        if title_match and title_match.group(1) not in used_question_nos:
            question_no = title_match.group(1)
        used_question_nos.add(question_no)

        questions.append(
            {
                "question_no": question_no,
                "question_text": text,
                "page_no": 1,
                "answer": "",
                "solution": "",
                "question_type": _guess_question_type(text),
                "difficulty": "中等",
                "knowledge_point": "",
                "knowledge_category": "其他",
                "is_complete": True,
                "confidence": 0.55,
            }
        )

    logger.info(f"Section markdown fallback extracted {len(questions)} questions")
    return questions


async def _enrich_questions_with_answers(questions: List[Dict], llm_caller) -> List[Dict]:
    """Fill answer and solution for locally parsed questions in batches."""
    if not questions:
        return questions

    if len(questions) <= 6:
        from .deepseek import generate_answer

        semaphore = asyncio.Semaphore(3)

        async def enrich_one(question: Dict) -> None:
            async with semaphore:
                try:
                    result = await generate_answer(
                        question.get("question_text", ""),
                        question.get("question_type", ""),
                        question.get("knowledge_point", ""),
                    )
                except Exception as exc:
                    logger.warning(f"Failed to enrich question {question.get('question_no')}: {exc}")
                    return

            question["answer"] = result.get("answer", question.get("answer", ""))
            question["solution"] = result.get("solution", question.get("solution", ""))

        await asyncio.gather(*(enrich_one(question) for question in questions))
        return questions

    from .deepseek import _fix_latex_json_escapes, _parse_response

    batch_size = 10
    for start in range(0, len(questions), batch_size):
        batch = questions[start:start + batch_size]
        payload = [
            {
                "question_no": q.get("question_no", ""),
                "page_no": q.get("page_no", 1),
                "question_text": q.get("question_text", ""),
                "question_type": q.get("question_type", "other"),
                "knowledge_point": q.get("knowledge_point", ""),
            }
            for q in batch
        ]

        system_prompt = """You are a primary-school math teacher.
For each input question, return strict JSON only and fill:
- answer
- solution
- question_type
- difficulty
- knowledge_point
- knowledge_category

Return:
{
  "questions": [
    {
      "question_no": "1",
      "answer": "answer",
      "solution": "short solution",
      "question_type": "fill_blank|choice|calculation|problem_solving|other",
      "difficulty": "基础|中等|挑战",
      "knowledge_point": "knowledge point",
      "knowledge_category": "几何|计算|数论|方程与应用|逻辑|基础|其他"
    }
  ]
}"""

        user_prompt = (
            "Generate answer and solution for each question below. "
            "Keep explanations concise and return JSON only.\n\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )

        try:
            response = await llm_caller(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                max_tokens=8192,
                timeout=120.0,
                json_output=True,
            )
            parsed = _parse_response(_fix_latex_json_escapes(response))
        except Exception as exc:
            logger.warning(f"Batch answer enrichment failed for questions {start + 1}-{start + len(batch)}: {exc}")
            continue

        parsed_by_no = {str(item.get("question_no", "")).strip(): item for item in parsed if item.get("question_no") is not None}
        for index, question in enumerate(batch):
            item = parsed_by_no.get(str(question.get("question_no", "")).strip())
            if not item and index < len(parsed):
                item = parsed[index]
            if not item:
                continue
            question["answer"] = item.get("answer", question.get("answer", ""))
            question["solution"] = item.get("solution", question.get("solution", ""))
            question["question_type"] = item.get("question_type", question.get("question_type", "other"))
            question["difficulty"] = item.get("difficulty", question.get("difficulty", "中等"))
            question["knowledge_point"] = item.get("knowledge_point", question.get("knowledge_point", ""))
            question["knowledge_category"] = item.get("knowledge_category", question.get("knowledge_category", "其他"))

    return questions


async def _build_local_result(markdown_text: str, llm_caller) -> List[Dict]:
    """Build local parsing result and enrich it with answers when possible."""
    questions = _extract_questions_from_markdown_locally(markdown_text)
    if not questions:
        return questions
    try:
        return await asyncio.wait_for(
            _enrich_questions_with_answers(questions, llm_caller),
            timeout=45.0,
        )
    except Exception as exc:
        logger.warning(f"Local question answer enrichment timed out or failed: {exc}")
        return questions


async def extract_questions_from_markdown(
    markdown_text: str,
    llm_caller,
    pdf_images: Optional[Dict[int, List[bytes]]] = None,
) -> List[Dict]:
    """Extract structured questions from markdown using LLM first, then local fallback."""
    del pdf_images

    page_sections = _extract_page_sections(markdown_text)
    divider_sections = _extract_questions_from_markdown_sections(markdown_text)
    if len(divider_sections) >= 2:
        logger.info(
            f"Using section parser for divider-based markdown ({len(divider_sections)} questions)"
        )
        return divider_sections

    try:
        if len(page_sections) > 4 or len(markdown_text) > 8000:
            logger.info(
                f"Using local parser for large document ({len(markdown_text)} chars, {len(page_sections)} pages)"
            )
            return await _build_local_result(markdown_text, llm_caller)

        if len(page_sections) <= 1 or len(markdown_text) < 3000:
            questions = await _extract_questions_single_batch(markdown_text, llm_caller)
            return questions or await _build_local_result(markdown_text, llm_caller)

        logger.info(
            f"Medium document detected ({len(markdown_text)} chars, {len(page_sections)} pages), processing in batches"
        )
        all_questions: List[Dict] = []

        for index, (page_no, page_content) in enumerate(page_sections, start=1):
            if not page_content.strip():
                continue

            logger.info(
                f"Processing batch {index}/{len(page_sections)} for page {page_no}: {len(page_content)} chars"
            )
            try:
                questions = await _extract_questions_single_batch(page_content, llm_caller)
                for question in questions:
                    if not question.get("page_no"):
                        question["page_no"] = page_no
                all_questions.extend(questions)
            except Exception as exc:
                logger.warning(f"Batch {index} failed: {exc}")

        if all_questions:
            return all_questions

        logger.warning("LLM batch extraction returned no questions, switching to local parser")
    except Exception as exc:
        logger.warning(f"LLM markdown extraction failed, switching to local parser: {exc}")

    return await _build_local_result(markdown_text, llm_caller)


async def _extract_questions_single_batch(markdown_text: str, llm_caller) -> List[Dict]:
    """Extract questions from a single markdown batch via the text model."""
    system_prompt = """You extract primary-school math questions from markdown or PDF text.
Return strict JSON only.

Rules:
1. Detect all numbered questions.
2. Merge sub-questions into one parent question.
3. Keep question text complete.
4. Include page_no when visible in the text; otherwise use 1.
5. Keep answer and solution concise.

Return:
{
  "questions": [
    {
      "question_no": "1",
      "question_text": "full question text",
      "page_no": 1,
      "answer": "answer",
      "solution": "short solution",
      "question_type": "fill_blank|choice|calculation|problem_solving|other",
      "difficulty": "基础|中等|挑战",
      "knowledge_point": "knowledge point",
      "knowledge_category": "几何|计算|数论|方程与应用|逻辑|基础|其他",
      "is_complete": true,
      "confidence": 0.95
    }
  ]
}"""

    user_prompt = f"""Extract all math questions from the following text and return JSON only:

{markdown_text}
"""

    response = ""
    try:
        response = await llm_caller(
            messages=[{"role": "user", "content": user_prompt}],
            system_prompt=system_prompt,
            max_tokens=16384,
            timeout=180.0,
            json_output=True,
        )

        from .deepseek import _fix_latex_json_escapes, _parse_response

        response = _fix_latex_json_escapes(response)
        questions = _parse_response(response)
        logger.info(f"Extracted {len(questions)} questions from single batch")
        return questions
    except Exception as exc:
        logger.error(f"Failed to extract questions from batch: {exc}")
        logger.debug(f"Markdown text length: {len(markdown_text)} chars")
        logger.debug(f"LLM response preview: {response[:1000] if response else 'N/A'}")
        raise


def _attach_images_to_questions(questions: List[Dict], pdf_images: Dict[int, List[bytes]]) -> List[Dict]:
    """Attach extracted PDF images to questions based on page number."""
    from ..config import IMAGE_DIR
    import uuid

    os.makedirs(IMAGE_DIR, exist_ok=True)

    for question in questions:
        if not question.get("has_image"):
            continue

        page_no = int(question.get("page_no", 1)) - 1
        question_images: List[str] = []

        if page_no in pdf_images:
            for image_index, image_bytes in enumerate(pdf_images[page_no], start=1):
                image_name = f"pdf_img_{uuid.uuid4().hex[:8]}_p{page_no + 1}_{image_index}.png"
                image_path = os.path.join(IMAGE_DIR, image_name)
                with open(image_path, "wb") as file_handle:
                    file_handle.write(image_bytes)
                question_images.append(f"/uploads/images/{image_name}")

        if not question_images and page_no + 1 in pdf_images:
            for image_index, image_bytes in enumerate(pdf_images[page_no + 1], start=1):
                image_name = f"pdf_img_{uuid.uuid4().hex[:8]}_p{page_no + 2}_{image_index}.png"
                image_path = os.path.join(IMAGE_DIR, image_name)
                with open(image_path, "wb") as file_handle:
                    file_handle.write(image_bytes)
                question_images.append(f"/uploads/images/{image_name}")

        if question_images:
            question["image_urls"] = question_images

    return questions


def detect_has_images(pdf_bytes: bytes, max_pages: int = 30) -> Dict[int, bool]:
    """Return whether each PDF page contains images."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = min(len(doc), max_pages) if max_pages > 0 else len(doc)

    page_images: Dict[int, bool] = {}
    try:
        for page_num in range(total_pages):
            page = doc[page_num]
            page_images[page_num] = len(page.get_images()) > 0
    finally:
        doc.close()

    return page_images


def extract_images_from_pdf(
    pdf_bytes: bytes,
    max_pages: int = 30,
    min_size: int = 5000,
) -> Dict[int, List[bytes]]:
    """Extract meaningful images from PDF pages."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = min(len(doc), max_pages) if max_pages > 0 else len(doc)

    page_images: Dict[int, List[bytes]] = {}
    try:
        for page_num in range(total_pages):
            page = doc[page_num]
            images = page.get_images()
            if not images:
                continue

            page_images[page_num] = []
            for image_index, image_info in enumerate(images, start=1):
                try:
                    xref = image_info[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    width = base_image.get("width", 0)
                    height = base_image.get("height", 0)

                    if len(image_bytes) < min_size or width < 50 or height < 50:
                        continue

                    page_images[page_num].append(image_bytes)
                    logger.info(
                        f"Extracted image {image_index} from page {page_num + 1}: "
                        f"{len(image_bytes)} bytes, {width}x{height}px"
                    )
                except Exception as exc:
                    logger.warning(f"Failed to extract image {image_index} from page {page_num + 1}: {exc}")
    finally:
        doc.close()

    return page_images
