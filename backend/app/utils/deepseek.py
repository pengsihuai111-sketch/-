"""
Question recognition, answer generation, and deduplication.

All text and vision tasks use the configured LLM provider (Zhipu AI / GLM)
via OpenAI-compatible API format. The single model handles both
text-only tasks (answer generation, matching) and multimodal tasks
(image recognition with text prompts).

Recognition uses a two-stage approach for better accuracy:
1. Detection stage: Identify all questions and their boundaries
2. Recognition stage: Extract content and solve each question
"""
import json
import base64
import re
import logging
import io
import asyncio
import difflib
import math
import httpx
from typing import List, Tuple
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

from ..config import (
    DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL,
    ZHIPU_API_KEY, ZHIPU_API_URL, ZHIPU_MODEL,
    VISION_API_KEY, VISION_API_URL, VISION_MODEL,
    TEXT_LLM_PROVIDER,
)
from .image_enhancement import analyze_image_quality, enhance_image, should_enhance
from .recognition_config import (
    RecognitionStrategy, select_strategy,
    MIN_CONFIDENCE_THRESHOLD, MAX_PARALLEL_RECOGNITIONS,
)
from .knowledge_classifier import normalize_question_metadata, normalize_questions_metadata


def _make_async_client(timeout: float = 120.0) -> httpx.AsyncClient:
    """Create an httpx client with connection pooling and reasonable timeouts."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=15.0),
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
    )

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)
_rapid_ocr_engine = None

def _get_text_llm_config() -> dict:
    """Get text LLM config based on TEXT_LLM_PROVIDER."""
    provider = TEXT_LLM_PROVIDER.lower()
    if provider == "zhipu":
        return {
            "api_key": ZHIPU_API_KEY,
            "api_url": ZHIPU_API_URL,
            "model": ZHIPU_MODEL,
        }
    # default: deepseek
    return {
        "api_key": DEEPSEEK_API_KEY,
        "api_url": DEEPSEEK_API_URL,
        "model": DEEPSEEK_MODEL,
    }


async def _call_text_llm(
    messages: list,
    system_prompt: str = "",
    max_tokens: int = 4096,
    timeout: float = 180.0,
    json_output: bool = False,
) -> str:
    """Unified text LLM caller — supports DeepSeek and Zhipu AI."""
    config = _get_text_llm_config()
    api_key = config["api_key"]
    if not api_key:
        raise ValueError(f"{TEXT_LLM_PROVIDER} API key 未配置")

    payload = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            *messages,
        ],
    }
    # Zhipu glm models don't support max_tokens; others do
    if not config["model"].startswith("glm-"):
        payload["max_tokens"] = max_tokens
    elif json_output:
        payload["response_format"] = {"type": "json_object"}

    async with _make_async_client(timeout) as client:
        resp = await client.post(
            config["api_url"],
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if resp.status_code != 200:
        raise RuntimeError(
            f"LLM API error (status {resp.status_code}): {resp.text[:500]}"
        )

    result = resp.json()
    content = (
        result.get("choices", [{}])[0].get("message", {}).get("content", "")
    )
    return content


async def call_text_llm(
    messages: list,
    system_prompt: str = "",
    max_tokens: int = 4096,
    timeout: float = 180.0,
    json_output: bool = False,
) -> str:
    """Public wrapper for text LLM calls.

    This is a public interface for calling the text LLM, used by other modules
    like pdf_to_markdown for question extraction.
    """
    return await _call_text_llm(messages, system_prompt, max_tokens, timeout, json_output)


async def _call_multimodal_llm(
    image_bytes: bytes,
    text_prompt: str = "",
    system_prompt: str = None,
    max_tokens: int = 4096,
    timeout: float = 120.0,
    json_output: bool = False,
) -> str:
    """Call LLM with image input using OpenAI-compatible format.

    Uses the VISION model config (Zhipu AI vision model - GLM-4V).
    NOTE: GLM vision API does NOT support 'system' role messages,
    so system_prompt is merged into the user message text.
    """
    api_key = VISION_API_KEY
    model = VISION_MODEL
    api_url = VISION_API_URL
    if not api_key:
        raise ValueError("API key 未配置")

    image_bytes = preprocess_image(image_bytes)
    base64_image = encode_image(image_bytes)

    # Merge system prompt into user text — vision APIs typically don't support system role
    user_text = text_prompt
    if system_prompt:
        if user_text:
            user_text = f"{system_prompt}\n\n{user_text}"
        else:
            user_text = system_prompt

    # Build content parts - text first, then image (better for some models)
    content_parts = []
    if user_text:
        content_parts.append({"type": "text", "text": user_text})

    content_parts.append({
        "type": "image_url",
        "image_url": {
            "url": f"data:image/jpeg;base64,{base64_image}",
        },
    })

    messages = [{"role": "user", "content": content_parts}]

    # Zhipu glm models don't support max_tokens; others do
    payload = {
        "model": model,
        "messages": messages,
    }
    if not model.startswith("glm-"):
        payload["max_tokens"] = max_tokens
    elif json_output:
        payload["response_format"] = {"type": "json_object"}

    async with _make_async_client(timeout) as client:
        try:
            logger.info(f"Calling vision API: {api_url}, model: {model}")
            resp = await client.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except Exception as e:
            logger.error(f"Vision API request failed: {e}")
            raise RuntimeError(f"API 请求失败: {str(e)}")

    if resp.status_code != 200:
        error_text = resp.text[:500]
        logger.error(f"Vision API error {resp.status_code}: {error_text}")
        raise RuntimeError(
            f"LLM API error (status {resp.status_code}): {error_text}"
        )

    result = resp.json()
    content = (
        result.get("choices", [{}])[0].get("message", {}).get("content", "")
    )

    if not content:
        logger.warning("Vision API returned empty content")
    else:
        logger.info(f"Vision API response length: {len(content)} chars")

    return content


async def call_vision_llm(
    image_data: str,
    prompt: str = "",
    system_prompt: str = None,
    max_tokens: int = 4096,
    timeout: float = 120.0,
    json_output: bool = False,
) -> str:
    """Backward-compatible wrapper for vision calls that receive base64 image data."""
    image_bytes = base64.b64decode(image_data)
    return await _call_multimodal_llm(
        image_bytes=image_bytes,
        text_prompt=prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        timeout=timeout,
        json_output=json_output,
    )


# Maximum image dimensions for processing
MAX_IMAGE_DIMENSION = 2400  # increased for better detail preservation
JPEG_QUALITY = 95  # high quality for better recognition

# Stage 1: Detect questions and their boundaries
DETECTION_SYSTEM_PROMPT = """你是小学数学试卷分析助手。分析这张试卷图片，检测所有题目的位置和边界。

任务：
1. 识别图片中所有题目的题号（如：1. 2. 3. 或 一、二、三、）
2. 估算每道题的大致区域（上下左右边界）
3. 判断题目类型（填空、选择、计算、应用题等）
4. 检测是否有配图、表格、图形
5. 评估题目完整性（是否被截断、遮挡）

注意：
- 只检测印刷体题目，忽略手写内容和批改痕迹
- 题号必须准确，不能遗漏
- 边界估算要包含题目的所有内容（题干+配图）
- 多个子问题（(1)(2)或①②）算作一道大题

输出纯 JSON：
{
  "total_questions": 3,
  "page_layout": "single_column|double_column|mixed",
  "has_handwriting": false,
  "has_correction_marks": false,
  "questions": [
    {
      "question_no": "1",
      "estimated_bbox": [x1, y1, x2, y2],
      "question_type_hint": "calculation",
      "has_diagram": false,
      "has_sub_questions": false,
      "is_complete": true,
      "confidence": 0.95
    }
  ]
}"""

# Stage 2: Recognize individual question content
RECOGNITION_SYSTEM_PROMPT = """你是小学数学题目识别助手。从完整的试卷图片中精确提取指定题号的题目内容并解答。

任务：
1. 在图片中找到指定题号的题目（如：1. 2. 3. 或 一、二、三、）
2. 提取该题目的完整文字内容（题号+题干+所有子问题）
3. 如果有配图、表格、图形，详细描述其内容
4. 给出完整的答案和详细的解题步骤
5. 判断题型、知识点、难度

重要提示：
- 图片中可能包含多道题，但你只需要提取指定题号的那一道
- 必须提取该题的完整内容，不能遗漏任何部分
- 题目可能跨越多行，要完整提取到题目结束（下一题开始或页面结束）
- 多个子问题（(1)(2)或①②）都属于同一道大题，要全部提取

要求：
- 题目文字必须完整准确，不能遗漏任何条件
- 公式用 LaTeX 格式：\\frac{1}{2}、\\sqrt{3}、x^2
- 多子问题的答案用分号分隔："(1)答案1; (2)答案2"
- 解析要详细到小学生能看懂每一步，包含计算过程
- 答案必须包含单位（如：米、千克、元）
- 如果题目依赖配图，必须设置 has_image=true 并描述图形
- 如果找不到指定题号，设置 is_complete=false 并说明原因

输出纯 JSON：
{
  "question_no": "题号",
  "question_text": "完整题目内容（从题号开始到题目结束）",
  "answer": "答案（含单位）",
  "solution": "分步解析",
  "question_type": "fill_blank|choice|calculation|problem_solving|other",
  "difficulty": "基础|中等|挑战",
  "knowledge_point": "具体知识点",
  "knowledge_category": "行程|工程|经济|浓度|几何|计算|数论|方程与应用|逻辑推理|统计|基础|其他",
  "has_image": false,
  "diagram_description": "",
  "is_complete": true,
  "confidence": 0.95
}"""


def preprocess_image(image_bytes: bytes) -> bytes:
    """Resize and compress image if needed, preserving quality for recognition."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        orig_size = len(image_bytes)
        orig_w, orig_h = img.size

        max_dim = max(orig_w, orig_h)
        min_dim = min(orig_w, orig_h)

        # Quality check: warn if image is too small
        if max_dim < 800 or min_dim < 600:
            logger.warning(
                f"Image resolution is low ({orig_w}x{orig_h}). "
                f"Recognition quality may be affected. Consider using higher resolution images."
            )

        # NEVER downscale small images - just fix color mode
        if max_dim < 800:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=False)
                return buf.getvalue()
            return image_bytes

        # Only process if image is too large
        if max_dim <= MAX_IMAGE_DIMENSION and orig_size <= 3 * 1024 * 1024:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=False)
                return buf.getvalue()
            return image_bytes

        # Resize if too large
        if max_dim > MAX_IMAGE_DIMENSION:
            ratio = MAX_IMAGE_DIMENSION / max_dim
            new_w = int(orig_w * ratio)
            new_h = int(orig_h * ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            logger.info(f"Resized image from {orig_w}x{orig_h} to {new_w}x{new_h}")

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=False)
        processed = buf.getvalue()

        logger.info(
            f"Image preprocessed: {orig_w}x{orig_h} {orig_size/1024:.0f}KB -> "
            f"{img.width}x{img.height} {len(processed)/1024:.0f}KB"
        )
        return processed
    except Exception as e:
        logger.warning(f"Image preprocessing failed, using original: {e}")
        return image_bytes


def get_image_info(image_bytes: bytes) -> dict:
    """Return image dimensions and estimated content completeness."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        w, h = img.size
        # Heuristic: very short images likely contain incomplete content
        too_short = h < 400
        too_narrow = w < 400
        return {
            "width": w,
            "height": h,
            "likely_partial": too_short or too_narrow,
            "warning": "图片尺寸较小，可能未截取完整题目，建议重新全屏截图" if (too_short or too_narrow) else None,
        }
    except Exception:
        return {"width": 0, "height": 0, "likely_partial": False, "warning": None}


def _get_rapid_ocr_engine():
    """Lazily initialize local OCR engine for offline fallback."""
    global _rapid_ocr_engine
    if _rapid_ocr_engine is None:
        _rapid_ocr_engine = RapidOCR()
    return _rapid_ocr_engine


def _extract_text_with_local_ocr(image_bytes: bytes) -> str:
    """Extract text from an image using local OCR, without remote API calls."""
    engine = _get_rapid_ocr_engine()
    result, _ = engine(image_bytes)
    if not result:
        return ""
    lines = []
    for item in result:
        if len(item) < 2:
            continue
        text = item[1].strip()
        if text:
            lines.append(text)
    return "\n".join(lines).strip()


def _looks_like_remote_auth_failure(questions: List[dict]) -> bool:
    """Whether all recognized questions are placeholder failures from invalid API auth."""
    if not questions:
        return False
    texts = [str(q.get("question_text", "")).strip() for q in questions]
    valid_texts = [t for t in texts if t]
    if not valid_texts:
        return False
    return all(("识别失败" in t and "Invalid token" in t) for t in valid_texts)


def _build_local_ocr_question(text: str) -> dict:
    """Wrap local OCR text into the standard question payload shape."""
    return normalize_question_metadata({
        "question_no": "1",
        "question_text": text,
        "answer": "",
        "solution": "",
        "question_type": "other",
        "difficulty": "中等",
        "knowledge_point": "",
        "knowledge_category": "其他",
        "has_image": False,
        "is_complete": len(text) >= 20,
        "confidence": 0.55,
        "quality_issues": ["已切换到本地OCR兜底，未生成答案和解析"],
    })


def encode_image(image_bytes: bytes) -> str:
    """Encode image bytes to base64."""
    import base64
    return base64.b64encode(image_bytes).decode("utf-8")


def _slice_image(image_bytes: bytes, max_slices: int = 3) -> List[bytes]:
    """Slice a tall image into overlapping horizontal strips.

    NOTE: With glm-4v-plus, slicing is disabled entirely — the model handles
    full-page images well. This avoids the overhead of multiple parallel API
    calls per image and eliminates slice-boundary deduplication issues.
    """
    return [image_bytes]


def _fix_latex_json_escapes(text: str) -> str:
    """Fix LaTeX backslashes that conflict with JSON escape sequences.

    The AI often returns LaTeX math (\\triangle, \\frac, \\underbrace, etc.)
    inside JSON strings. Some of these break json.loads():
    - \\u is a JSON Unicode escape prefix, so \\underbrace, \\underline fail
    - \\b, \\f, \\n, \\r, \\t get silently converted to control chars
    """
    # Normalize a few common OCR-misread LaTeX commands before escaping.
    text = re.sub(r'\\+1rac', r'\\\\frac', text)

    # Crucial: \\u not followed by 4 hex digits is LaTeX, not a JSON Unicode escape
    text = re.sub(r'\\u(?![\da-fA-F]{4})', r'\\\\u', text)
    # \\b \\f \\n \\r \\t followed by a letter = LaTeX command, not JSON escape
    text = re.sub(r'\\([bfnrt])(?=[a-zA-Z])', r'\\\\\\1', text)
    # Any other unsupported JSON backslash escape is likely OCR/LaTeX noise
    text = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)
    return text


def _extract_json_objects(s: str) -> list:
    """Extract complete JSON objects using brace counting.
    Only returns objects that have the required 'question_text' field."""
    objects = []
    i = 0
    while i < len(s):
        obj_start = s.find('{', i)
        if obj_start == -1:
            break

        # Check if this looks like a question object (has "question_text" nearby)
        preview = s[obj_start:obj_start+100]
        if '"question_text"' not in preview:
            i = obj_start + 1
            continue

        # Find the matching closing brace using counting
        brace_count = 0
        j = obj_start
        in_string = False
        escape = False
        while j < len(s):
            ch = s[j]
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = not in_string
            elif not in_string:
                if ch == '{':
                    brace_count += 1
                elif ch == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        obj_str = s[obj_start:j + 1]
                        try:
                            obj = json.loads(obj_str)
                            if obj.get("question_text", "").strip():
                                objects.append(obj)
                        except json.JSONDecodeError:
                            try:
                                obj_str = obj_str.encode('utf-8', errors='replace').decode('utf-8')
                                obj = json.loads(obj_str)
                                if obj.get("question_text", "").strip():
                                    objects.append(obj)
                            except json.JSONDecodeError:
                                pass
                        break
            j += 1
        i = j + 1 if j < len(s) else obj_start + 1
    return objects


def _parse_response(text: str) -> List[dict]:
    """Parse JSON from AI response, handling markdown code blocks and encoding issues."""
    text = text.strip()

    # Strip any BOM or invisible control characters (except newlines and tabs)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)

    # Fix LaTeX backslashes that conflict with JSON escape sequences
    text = _fix_latex_json_escapes(text)

    # Find the first JSON object/array start
    json_start = text.find('{')
    arr_start = text.find('[')
    if json_start == -1 and arr_start == -1:
        logger.error(f"No JSON content found in response. First 500 chars: {text[:500]}")
        raise ValueError(f"No JSON content found in response")
    if arr_start >= 0 and (json_start == -1 or arr_start < json_start):
        start = arr_start
    else:
        start = json_start
    if start > 0:
        logger.debug(f"Stripped {start} chars before JSON start")
        text = text[start:]

    # Try direct JSON parse first
    try:
        data = json.loads(text)
        logger.debug("Direct JSON parse succeeded")
    except json.JSONDecodeError as e:
        logger.warning(f"Direct JSON parse failed: {e}. Trying recovery...")

        # Try extracting from markdown code block
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            json_text = match.group(1).strip()
            logger.debug(f"Found JSON in markdown block, length: {len(json_text)}")
            try:
                data = json.loads(json_text)
                logger.debug("Markdown block JSON parse succeeded")
            except json.JSONDecodeError as e2:
                logger.warning(f"Markdown block JSON parse failed: {e2}. Trying object extraction...")
                # Try extracting complete objects
                recovered = _extract_json_objects(json_text)
                if recovered:
                    logger.info(f"Recovered {len(recovered)} question objects from markdown block")
                    return recovered
                logger.error(f"All parse attempts failed. JSON text: {json_text[:500]}")
                raise ValueError(f"无法解析 AI 响应的 JSON 格式: {str(e2)}")
        else:
            # No markdown block, try extracting objects directly
            recovered = _extract_json_objects(text)
            if recovered:
                logger.info(f"Recovered {len(recovered)} question objects from raw text")
                return recovered
            logger.error(f"All parse attempts failed. Raw text: {text[:500]}")
            raise ValueError(f"无法解析 AI 响应的 JSON 格式: {str(e)}")

    # Extract questions from parsed data
    if isinstance(data, dict):
        questions = data.get("questions", [data] if data.get("question_text") else [])
    elif isinstance(data, list):
        questions = data
    else:
        logger.error(f"Unexpected data type: {type(data)}")
        raise ValueError(f"AI 返回的数据格式异常")

    if isinstance(questions, dict):
        questions = [questions]

    logger.info(f"Successfully parsed {len(questions)} questions")
    return questions


def _fill_defaults(questions: List[dict]) -> List[dict]:
    """Fill default values for missing fields and validate question quality."""
    normalize_questions_metadata(questions)
    for i, q in enumerate(questions):
        q.setdefault("answer", "")
        q.setdefault("solution", "")
        q.setdefault("has_image", False)
        q.setdefault("difficulty", "中等")
        q.setdefault("question_type", "other")
        q.setdefault("is_complete", True)
        q.setdefault("confidence", 0.8)

        # Quality validation
        quality_issues = []

        # Check question text
        question_text = q.get("question_text", "").strip()
        if not question_text:
            quality_issues.append("题目文字为空")
            q["is_complete"] = False
        elif len(question_text) < 5:
            quality_issues.append("题目文字过短")
            q["confidence"] = min(q.get("confidence", 0.8), 0.5)

        # Check answer
        if not q.get("answer"):
            quality_issues.append("缺少答案")
        else:
            answer = q["answer"].strip()
            # Check if answer looks reasonable
            if len(answer) < 1:
                quality_issues.append("答案为空")
            elif answer in ["无法确定", "需要配合原图", "[推测]", "未知"]:
                quality_issues.append("答案不确定")
                q["confidence"] = min(q.get("confidence", 0.8), 0.6)

        # Check solution
        if not q.get("solution"):
            quality_issues.append("缺少解析")
        elif len(q["solution"].strip()) < 10:
            quality_issues.append("解析过于简短")
            q["confidence"] = min(q.get("confidence", 0.8), 0.7)

        normalize_question_metadata(q)
        # Check knowledge point
        if not q.get("knowledge_point"):
            quality_issues.append("缺少知识点")

        # Store quality issues
        if quality_issues:
            q["quality_issues"] = quality_issues
            logger.warning(
                f"Question {i+1} quality issues: {', '.join(quality_issues)}. "
                f"Text: {question_text[:60]}..."
            )

        # Log missing critical fields
        if not q.get("answer"):
            logger.warning(
                f"Question {i+1} missing answer: {question_text[:80]}..."
            )
        if not q.get("solution"):
            logger.warning(
                f"Question {i+1} missing solution: {question_text[:80]}..."
            )

    return questions


async def _fill_missing_answers(questions: List[dict]) -> List[dict]:
    """Post-recognition: auto-generate answers/solutions for questions missing them."""
    filled_count = 0
    for i, q in enumerate(questions):
        if q.get("answer") and q.get("solution"):
            continue  # already complete

        # Skip filling if question is known to be incomplete (missing content)
        if not q.get("is_complete", True) or len(q.get("question_text", "").strip()) < 10:
            logger.info(f"Skipping answer generation for question {i+1}: incomplete or too short")
            continue

        try:
            logger.info(f"Generating answer for question {i+1}: {q.get('question_text', '')[:60]}...")
            result = await generate_answer(
                q.get("question_text", ""),
                q.get("question_type", ""),
                q.get("knowledge_point", ""),
            )
            if not q.get("answer") and result.get("answer"):
                q["answer"] = result["answer"]
                filled_count += 1
            if not q.get("solution") and result.get("solution"):
                q["solution"] = result["solution"]
                filled_count += 1
        except Exception as e:
            logger.warning(f"Answer generation failed for question {i+1}: {e}")

    if filled_count > 0:
        logger.info(f"Auto-filled {filled_count} missing answer/solution fields")
    return questions


async def _detect_questions(image_bytes: bytes, filename: str) -> dict:
    """Stage 1: Detect questions and their boundaries in the image.

    Returns dict with:
    - total_questions: int
    - page_layout: str
    - has_handwriting: bool
    - has_correction_marks: bool
    - questions: list of detected question regions with bbox and metadata
    """
    info = get_image_info(image_bytes)
    w, h = info["width"], info["height"]

    try:
        content_text = await _call_multimodal_llm(
            image_bytes=image_bytes,
            text_prompt=f"分析这张试卷图片（{w}×{h}像素），检测所有题目的位置和边界。",
            system_prompt=DETECTION_SYSTEM_PROMPT,
            max_tokens=2048,
            timeout=60.0,
            json_output=True,
        )
        logger.info(f"Detection API response length: {len(content_text)}")

        if not content_text:
            raise ValueError("Detection API returned empty response")

        # Parse detection result
        text = content_text.strip()
        text = _fix_latex_json_escapes(text)
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1).strip()

        detection = json.loads(text)
        logger.info(f"Detected {detection.get('total_questions', 0)} questions")
        return detection

    except Exception as e:
        logger.error(f"Question detection failed: {e}")
        # Return fallback: assume single question covering full image
        return {
            "total_questions": 1,
            "page_layout": "unknown",
            "has_handwriting": False,
            "has_correction_marks": False,
            "questions": [{
                "question_no": "1",
                "estimated_bbox": [0, 0, w, h],
                "question_type_hint": "other",
                "has_diagram": False,
                "has_sub_questions": False,
                "is_complete": True,
                "confidence": 0.5
            }]
        }


async def _recognize_single_question(
    image_bytes: bytes,
    question_no: str,
    bbox: list = None,
    type_hint: str = "",
    use_full_image: bool = True,
) -> dict:
    """Stage 2: Recognize a single question's content.

    Args:
        image_bytes: Full image bytes
        question_no: Question number to recognize
        bbox: Estimated bounding box (for reference only if use_full_image=True)
        type_hint: Question type hint
        use_full_image: If True, use full image with question number hint instead of cropping
                       (recommended for PDFs to avoid incomplete questions)

    Returns dict with question_text, answer, solution, etc.
    """
    # For PDFs and structured documents, use full image with question number hint
    # instead of cropping, to avoid cutting off question content
    if use_full_image:
        logger.info(f"Recognizing question {question_no} from full image (no crop)")
        prompt_text = (
            f"请从这张图片中提取题号为 {question_no} 的题目。"
            f"只提取这一道题的完整内容，包括题干、所有子问题、配图描述。"
            f"题型提示：{type_hint or '未知'}"
        )
    else:
        # Crop to bbox if provided and use_full_image=False
        if bbox and len(bbox) == 4:
            from ..utils.image_processing import crop_bbox
            try:
                image_bytes = crop_bbox(image_bytes, tuple(bbox))
                logger.info(f"Cropped question {question_no} to bbox {bbox}")
            except Exception as e:
                logger.warning(f"Failed to crop bbox for question {question_no}: {e}")

        prompt_text = f"提取这道题的完整内容并解答。题号：{question_no}，题型提示：{type_hint or '未知'}"

    try:
        content_text = await _call_multimodal_llm(
            image_bytes=image_bytes,
            text_prompt=prompt_text,
            system_prompt=RECOGNITION_SYSTEM_PROMPT,
            max_tokens=4096,
            timeout=90.0,
            json_output=True,
        )
        logger.info(f"Recognition API response for Q{question_no}: {len(content_text)} chars")

        if not content_text:
            raise ValueError(f"Recognition API returned empty for question {question_no}")

        # Parse recognition result
        text = content_text.strip()
        text = _fix_latex_json_escapes(text)
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1).strip()

        question = json.loads(text)

        # Ensure question_no is set
        if not question.get("question_no"):
            question["question_no"] = question_no

        return question

    except Exception as e:
        logger.error(f"Recognition failed for question {question_no}: {e}")
        return {
            "question_no": question_no,
            "question_text": f"[识别失败: {str(e)[:100]}]",
            "answer": "",
            "solution": "",
            "question_type": "other",
            "difficulty": "中等",
            "knowledge_point": "",
            "knowledge_category": "其他",
            "has_image": False,
            "is_complete": False,
            "confidence": 0.0
        }


async def _call_vision_api_two_stage(image_bytes: bytes, filename: str) -> List[dict]:
    """Two-stage recognition: detect questions first, then recognize each one.

    Stage 1: Detect all questions and their boundaries
    Stage 2: Recognize each question individually using FULL IMAGE (no crop)

    This approach improves accuracy by:
    - Ensuring no questions are missed
    - Providing full context for each question (avoids cutting off content)
    - Allowing parallel recognition of multiple questions

    Note: For PDFs, we use full image with question number hints instead of
    cropping to avoid incomplete questions due to inaccurate bbox estimation.
    """
    # Stage 1: Detect questions
    detection = await _detect_questions(image_bytes, filename)
    detected_questions = detection.get("questions", [])

    if not detected_questions:
        logger.warning("No questions detected, falling back to full-image recognition")
        return await _call_vision_api_fallback(image_bytes, filename)

    logger.info(f"Stage 1 complete: detected {len(detected_questions)} questions")

    # Determine if we should use full image (recommended for PDFs)
    # PDF pages and structured documents should use full image to avoid cropping issues
    use_full_image = True  # Always use full image for better accuracy
    if use_full_image:
        logger.info("Using full image for all questions (no cropping)")

    # Stage 2: Recognize each question
    tasks = []
    for q_meta in detected_questions:
        task = _recognize_single_question(
            image_bytes=image_bytes,
            question_no=q_meta.get("question_no", ""),
            bbox=q_meta.get("estimated_bbox"),
            type_hint=q_meta.get("question_type_hint", ""),
            use_full_image=use_full_image,
        )
        tasks.append(task)

    # Run recognitions in parallel (limited concurrency)
    questions = []
    for i in range(0, len(tasks), 3):  # Process 3 at a time
        batch = tasks[i:i+3]
        batch_results = await asyncio.gather(*batch, return_exceptions=True)
        for result in batch_results:
            if isinstance(result, Exception):
                logger.error(f"Recognition task failed: {result}")
            elif isinstance(result, dict):
                questions.append(result)

    logger.info(f"Stage 2 complete: recognized {len(questions)} questions")
    return _fill_defaults(questions)


async def _call_vision_api_fallback(image_bytes: bytes, filename: str) -> List[dict]:
    """Fallback: single-stage recognition of full image (original approach).

    Used when detection fails or for simple single-question images.
    """
    info = get_image_info(image_bytes)
    w, h = info["width"], info["height"]

    # Build a combined prompt for full-page recognition
    full_page_prompt = """你是小学数学识别解题助手。提取图片中全部题目并完整解答。

核心规则：
1. 图片有几道题提取几道，数题号，不能少！
2. 多子问（(1)(2)或①②）合并为一道
3. 忽略手写和批改，只提取印刷体
4. 公式用 LaTeX：\\frac{1}{2}、\\sqrt{3}
5. 必须给出每道题的完整答案和分步解析，含单位
6. 多子问答法: "(1)答案; (2)答案"
7. 有图形时 has_image=true
8. 题目不完整时 is_complete=false

输出纯 JSON：
{"questions":[{
  "question_text":"完整题目内容",
  "answer":"答案（含单位）",
  "solution":"分步解析",
  "question_type":"fill_blank|choice|calculation|problem_solving|other",
  "difficulty":"基础|中等|挑战",
  "knowledge_point":"具体知识点名称",
  "knowledge_category":"行程|工程|经济|浓度|几何|计算|数论|方程与应用|逻辑推理|统计|基础|其他",
  "has_image":false,
  "is_complete":true
}]}"""

    for attempt in range(2):
        try:
            content_text = await _call_multimodal_llm(
                image_bytes=image_bytes,
                text_prompt=f"识别这张图片中的所有数学题目（{w}×{h}像素）",
                system_prompt=full_page_prompt,
                max_tokens=4096,
                timeout=120.0,
                json_output=True,
            )
            logger.info(f"Fallback API response length: {len(content_text)}")
            if not content_text:
                if attempt == 0:
                    logger.warning("Fallback API returned empty, retrying...")
                    continue
                raise ValueError("AI returned empty response")
            questions = _parse_response(content_text)
            logger.info(f"Parsed {len(questions)} questions from fallback API")
            return _fill_defaults(questions)
        except (ValueError, RuntimeError) as e:
            if attempt == 0:
                logger.warning(f"Fallback attempt {attempt + 1} failed: {e}. Retrying...")
                continue
            raise
        except Exception as e:
            if attempt == 0:
                logger.warning(f"Fallback unexpected error: {e}. Retrying...")
                continue
            raise


async def _call_deepseek_text(text: str) -> List[dict]:
    """Send extracted text to text LLM for structuring into question format.

    Uses the configured text LLM provider (DeepSeek or Zhipu AI).
    """
    system_prompt = VISION_SYSTEM_PROMPT.replace(
        "Analyze the image and extract all questions.",
        "Given OCR-extracted text from a math exam paper, identify and structure each question."
    )

    content_text = await _call_text_llm(
        messages=[
            {
                "role": "user",
                "content": f"以下是从数学试卷图片中提取的文字，请从中提取并结构化每道题目：\n\n{text}",
            },
        ],
        system_prompt=system_prompt,
        max_tokens=4096,
        timeout=180.0,
        json_output=True,
    )

    logger.info(f"Text LLM response text length: {len(content_text)}")

    if not content_text:
        raise ValueError("AI returned empty response")

    questions = _parse_response(content_text)
    logger.info(f"Parsed {len(questions)} questions from text LLM response")
    return _fill_defaults(questions)


async def recognize_questions(
    image_bytes: bytes,
    filename: str = "",
    strategy: RecognitionStrategy = RecognitionStrategy.AUTO,
    auto_enhance: bool = True
) -> dict:
    """Recognize questions from an image using configurable strategy.

    Args:
        image_bytes: Image data
        filename: Original filename (used for strategy selection)
        strategy: Recognition strategy (AUTO, TWO_STAGE, or SINGLE_STAGE)
        auto_enhance: Whether to automatically enhance image quality

    Returns:
        Dict containing:
        - questions: List of recognized questions with answers and solutions
        - quality_info: Image quality analysis results
        - warnings: List of quality warnings
        - enhanced: Whether image was enhanced

    Strategy selection:
    - AUTO: Automatically choose based on image characteristics
    - TWO_STAGE: Detect questions first, then recognize each (better accuracy)
    - SINGLE_STAGE: Direct full-image recognition (faster)
    """
    # Analyze image quality
    quality_info = analyze_image_quality(image_bytes)
    warnings = quality_info.get("warnings", [])
    enhanced = False

    # Auto-enhance if needed
    if auto_enhance and should_enhance(quality_info):
        logger.info(f"Image quality issues detected: {warnings}")
        logger.info("Applying automatic image enhancement")
        try:
            image_bytes = enhance_image(image_bytes, quality_info)
            enhanced = True
        except Exception as e:
            logger.error(f"Image enhancement failed: {e}")
            # Continue with original image

    questions = None

    # Auto-select strategy if needed
    if strategy == RecognitionStrategy.AUTO:
        info = get_image_info(image_bytes)
        strategy = select_strategy(info["width"], info["height"], filename)
        logger.info(f"Auto-selected strategy: {strategy}")

    # Try recognition based on selected strategy
    try:
        if strategy == RecognitionStrategy.TWO_STAGE:
            logger.info(f"Using two-stage recognition for {filename}")
            questions = await _call_vision_api_two_stage(image_bytes, filename)
        else:
            logger.info(f"Using single-stage recognition for {filename}")
            questions = await _call_vision_api_fallback(image_bytes, filename)
    except Exception as e:
        logger.warning(f"Primary recognition failed: {e}. Trying fallback...")

    # Fallback to alternative strategy if primary failed
    if questions is None or len(questions) == 0:
        try:
            if strategy == RecognitionStrategy.TWO_STAGE:
                logger.info("Two-stage failed, trying single-stage fallback")
                questions = await _call_vision_api_fallback(image_bytes, filename)
            else:
                logger.info("Single-stage failed, trying two-stage fallback")
                questions = await _call_vision_api_two_stage(image_bytes, filename)
        except Exception as e:
            logger.error(f"Fallback recognition also failed: {e}")
            # Last resort: try OCR + text LLM
            try:
                import pytesseract
                try:
                    pytesseract.get_tesseract_version()
                except Exception:
                    raise RuntimeError(
                        "所有识别方法均失败。请检查 API 配置或安装 Tesseract OCR。"
                    )

                image_bytes = preprocess_image(image_bytes)
                pil_image = Image.open(io.BytesIO(image_bytes))
                ocr_text = pytesseract.image_to_string(pil_image, lang="chi_sim+eng")

                if not ocr_text.strip():
                    raise ValueError("OCR 未能从图片中识别出文字内容")

                logger.info(f"OCR extracted {len(ocr_text)} chars")
                questions = await _call_deepseek_text(ocr_text)

            except ImportError:
                raise RuntimeError("所有识别方法均失败，且未安装 OCR 组件")
            except Exception as ocr_error:
                logger.error(f"OCR fallback error: {ocr_error}", exc_info=True)
                raise RuntimeError(f"识别失败: {str(ocr_error)}")

    # Post-processing: auto-generate answers/solutions for questions missing them
    if _looks_like_remote_auth_failure(questions or []):
        logger.warning("Remote vision/text API token appears invalid, switching to local OCR fallback")
        try:
            local_ocr_text = _extract_text_with_local_ocr(image_bytes)
            if local_ocr_text:
                questions = [_build_local_ocr_question(local_ocr_text)]
                warnings = list(warnings) + ["远端识别服务鉴权失败，已自动切换到本地OCR模式"]
            else:
                warnings = list(warnings) + ["远端识别服务鉴权失败，且本地OCR未提取到文本"]
        except Exception as local_ocr_error:
            logger.error(f"Local OCR fallback failed: {local_ocr_error}", exc_info=True)
            warnings = list(warnings) + [f"远端识别服务鉴权失败，本地OCR兜底也失败: {local_ocr_error}"]

    if questions:
        using_local_ocr_fallback = any(
            "本地OCR兜底" in issue
            for q in questions
            for issue in q.get("quality_issues", [])
        )
        missing_count = sum(1 for q in questions if not q.get("answer") or not q.get("solution"))
        if missing_count > 0 and not using_local_ocr_fallback:
            logger.info(f"{missing_count}/{len(questions)} questions missing answer/solution, auto-generating...")
            questions = await _fill_missing_answers(questions)

    # Return result with quality info
    return {
        "questions": questions or [],
        "quality_info": quality_info,
        "warnings": warnings,
        "enhanced": enhanced
    }


# ===== Advanced / Corrected-Paper Prompts =====

CORRECTED_PAPER_SYSTEM_PROMPT = """你是一个小学数学试卷识别助手。请分析这张试卷图片。

任务：
1. 判断图片中是否包含多道题。
2. 判断图片中是否有红色批改痕迹、学生手写内容、圈画、对勾、叉号、分数、老师批注。
3. 找出每道题的题号和大致区域。
4. 区分印刷体原题、学生手写解答和老师批改痕迹。
5. 不要把红色批改、手写演算、对勾、叉号、圈画、分数计入题目正文。
6. 只输出 JSON，不要输出解释性文字。

JSON 格式：
{
  "image_type": "normal_question | corrected_paper | unknown",
  "has_multiple_questions": true,
  "has_correction_marks": true,
  "has_student_handwriting": true,
  "need_question_segmentation": true,
  "questions": [
    {
      "question_no": "1",
      "bbox": [x1, y1, x2, y2],
      "visible_text_summary": "",
      "confidence": 0.0
    }
  ]
}"""

SINGLE_QUESTION_PROMPT = """你是一个小学数学错题识别助手。请从图片中提取"原始印刷题目"。

要求：
1. 只提取试卷上的印刷体题干。
2. 忽略学生手写答案、红色批改、圈画、对勾、叉号、分数、老师批注。
3. 如果某些文字被遮挡，请标记为 unclear，不要编造。
4. 保留数学符号、分数、单位、图形描述。
5. 判断题型、知识点、难度。
6. 输出 JSON，不要输出解释性文字。

JSON 格式：
{
  "question_no": "",
  "question_text": "",
  "question_type": "fill_blank | choice | calculation | problem_solving",
  "knowledge_points": [],
  "difficulty": "基础 | 中等 | 挑战",
  "keywords": [],
  "has_diagram": false,
  "diagram_description": "",
  "is_complete": true,
  "unclear_parts": [],
  "confidence": 0.0
}"""


async def analyze_page_structure(image_bytes: bytes, filename: str = "") -> dict:
    """Analyze a page image to detect questions, correction marks, and layout.

    Uses the multimodal LLM (Zhipu AI GLM-4V) to return structured info about the page.
    Returns parsed dict with image_type, questions list, etc.
    """
    try:
        content_text = await _call_multimodal_llm(
            image_bytes=image_bytes,
            text_prompt="请分析这张试卷图片，按规范输出 JSON。",
            system_prompt=CORRECTED_PAPER_SYSTEM_PROMPT,
            max_tokens=4096,
            timeout=120.0,
            json_output=True,
        )
    except Exception as e:
        logger.error(f"Page analysis API error: {e}")
        return {"image_type": "unknown", "has_multiple_questions": False,
                "has_correction_marks": False, "questions": []}

    if not content_text:
        return {"image_type": "unknown", "has_multiple_questions": False,
                "has_correction_marks": False, "questions": []}

    try:
        text = content_text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1)
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse page analysis JSON: {content_text[:200]}")
        return {"image_type": "unknown", "has_multiple_questions": False,
                "has_correction_marks": False, "questions": []}


async def recognize_single_question(image_bytes: bytes, question_no: str = "") -> dict:
    """Recognize a single question from a cropped image region.

    Uses the multimodal LLM (Zhipu AI GLM-4V) with a prompt tailored for corrected papers.
    Returns dict with question_text, question_type, etc.
    """
    try:
        content_text = await _call_multimodal_llm(
            image_bytes=image_bytes,
            text_prompt=f"请提取这张图片中的数学题目。题号：{question_no}",
            system_prompt=SINGLE_QUESTION_PROMPT,
            max_tokens=4096,
            timeout=120.0,
            json_output=True,
        )
    except Exception as e:
        logger.error(f"Single question API error: {e}")
        return {"question_text": "", "question_type": "other",
                "knowledge_points": [], "confidence": 0.0}

    if not content_text:
        return {"question_text": "", "question_type": "other",
                "knowledge_points": [], "confidence": 0.0}

    try:
        text = content_text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1)
        parsed = json.loads(text)
        return parsed
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse single question JSON: {content_text[:200]}")
        return {"question_text": content_text[:500], "question_type": "other",
                "knowledge_points": [], "confidence": 0.0}


async def match_question_candidates(recognized_text: str, keywords: list,
                                    candidates: list) -> dict:
    """Use text LLM to determine the best match among candidate questions.

    candidates: list of dicts with question_id, question_text, knowledge_point, difficulty
    Returns dict with matched_question_id, similarity, reason, need_manual_confirm
    """
    if not candidates:
        return {"matched_question_id": None, "similarity": 0.0,
                "reason": "无候选题", "need_manual_confirm": True}

    prompt = f"""下面是从图片中识别出的错题文本，以及题库中检索出的候选题。
请判断哪一道题最可能是原题。

要求：
1. 优先比较题干中的关键数字、人物、单位、条件关系。
2. 不要只看知识点相同。
3. 如果没有可靠匹配，返回 null。
4. 输出 JSON，不要输出解释性文字。

识别文本: {recognized_text}

关键词: {json.dumps(keywords, ensure_ascii=False)}

候选题:
{json.dumps(candidates, ensure_ascii=False, indent=2)}

输出 JSON:
{{
  "matched_question_id": null,
  "similarity": 0.0,
  "reason": "",
  "need_manual_confirm": true
}}"""

    try:
        content = await _call_text_llm(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="你是一个数学题库匹配助手。输出严格的 JSON，不要 markdown 包裹。",
            max_tokens=1024,
            timeout=30.0,
            json_output=True,
        )

        import re
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        if match:
            content = match.group(1)
        return json.loads(content)
    except Exception as e:
        logger.error(f"Match candidates error: {e}")
        return {"matched_question_id": None, "similarity": 0.0,
                "reason": f"匹配异常: {str(e)}", "need_manual_confirm": True}


async def generate_answer(question_text: str, question_type: str = "", knowledge_point: str = "") -> dict:
    """用配置的文本 LLM 自动生成题目答案和解析。"""
    prompt = (
        "你是一位资深小学数学老师。请认真审题，为下面这道题生成准确答案和解析。\n\n"
        f"题目：{question_text}\n"
        f"题型：{question_type or '未知'}\n"
        f"知识点：{knowledge_point or '未知'}\n\n"
        "要求：\n"
        "1. 答案要准确，必要时包含单位。\n"
        "2. 如果题目有多个小问，请在 answer 中逐项作答。\n"
        "3. 如果题目依赖配图或表格，仍要基于文字部分尽量推导，并在 answer 中说明需要结合原图。\n"
        "4. solution 用中文分步说明，适合小学学生理解。\n"
        "5. 不要直接输出“无法解答”。只有题干完全缺少关键条件时，才写“条件不足”，并说明缺失条件。\n"
        "6. 严格输出 JSON，不要输出 markdown 代码块。\n\n"
        "JSON 格式：\n"
        '{\n'
        '  "answer": "最终答案",\n'
        '  "solution": "分步解析"\n'
        '}'
    )

    for attempt in range(2):
        try:
            content = await _call_text_llm(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="你是一位资深小学数学老师。只输出严格 JSON，不要输出 markdown 代码块。",
                max_tokens=4096,
                timeout=90.0,
                json_output=True,
            )

            if not content:
                continue

            content = content.strip()
            if content.startswith("```"):
                match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
                if match:
                    content = match.group(1).strip()

            try:
                parsed = json.loads(_fix_latex_json_escapes(content))
            except json.JSONDecodeError:
                match = re.search(r"\{[\s\S]*\}", content)
                if not match:
                    logger.warning(f"Failed to parse text LLM answer JSON: {content[:200]}")
                    continue
                parsed = json.loads(_fix_latex_json_escapes(match.group(0)))

            answer = str(parsed.get("answer", "") or "").strip()
            solution = str(parsed.get("solution", "") or "").strip()
            if answer or solution:
                return {"answer": answer, "solution": solution}
        except Exception as e:
            logger.warning(f"Text LLM answer generation attempt {attempt + 1} failed: {e}")

    return {"answer": "", "solution": ""}
