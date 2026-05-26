import json
import random
import re
from collections import Counter
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import (
    PracticeSheet,
    PracticeType,
    Question,
    SheetQuestion,
    SheetType,
    User,
    UserKnowledgeMastery,
    UserPracticeHistory,
    UserWrongQuestion,
)
from ..schemas import (
    AIParsedRequirement,
    AIPracticeAdjustResponse,
    AIPracticeConfirmRequest,
    AIPracticeConfirmResponse,
    AIPracticePreviewRequest,
    AIPracticePreviewResponse,
    AIPracticeSuggestion,
    AIPracticeVariant,
    AISelectedQuestion,
    PracticeSheetOut,
    QuestionOut,
)
from .deepseek import call_text_llm


ALLOWED_TYPES = {"calculation", "fill_blank", "choice", "problem_solving"}
ALLOWED_DIFFICULTIES = {"基础", "中等", "挑战"}
ALLOWED_SHEET_TYPES = {"daily", "wrong_redo", "special_topic", "exam"}
TYPE_ALIASES = {
    "计算": "calculation",
    "计算题": "calculation",
    "填空": "fill_blank",
    "填空题": "fill_blank",
    "选择": "choice",
    "选择题": "choice",
    "应用": "problem_solving",
    "应用题": "problem_solving",
    "解决问题": "problem_solving",
}
TYPE_LABELS = {
    "calculation": "计算题",
    "fill_blank": "填空题",
    "choice": "选择题",
    "problem_solving": "应用题",
}
DIFFICULTY_WEIGHT = {"基础": 0, "中等": 1, "挑战": 2}
REPLACE_MODES = {"balanced", "easier", "harder", "same_type", "same_knowledge", "wrong_focused"}


def _extract_json_object(text: str) -> Dict[str, Any]:
    if not text:
        raise ValueError("AI response is empty")
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("AI response is not valid JSON")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("AI JSON response must be an object")
    return data


def _clean_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _dedupe_list(values: Optional[List[str]]) -> List[str]:
    result: List[str] = []
    seen = set()
    for item in values or []:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _normalize_question_types(values: Optional[List[str]]) -> List[str]:
    return [item for item in _dedupe_list(values) if item in ALLOWED_TYPES]


def _normalize_difficulties(values: Optional[List[str]]) -> List[str]:
    return [item for item in _dedupe_list(values) if item in ALLOWED_DIFFICULTIES]


def _normalize_type_counts(values: Optional[Dict[str, Any]]) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for key, raw_value in (values or {}).items():
        mapped_key = TYPE_ALIASES.get(key, key)
        if mapped_key not in ALLOWED_TYPES:
            continue
        try:
            count = int(raw_value)
        except (TypeError, ValueError):
            continue
        if count > 0:
            result[mapped_key] = min(count, 20)
    return result


def _estimate_time(questions: List[Question]) -> int:
    time_map = {"基础": 2, "中等": 3, "挑战": 5}
    type_map = {"fill_blank": 2, "choice": 2, "problem_solving": 8, "calculation": 3}
    total = 0
    for q in questions:
        total += max(type_map.get(q.question_type, 3), time_map.get(q.difficulty, 3))
    return min(total, 60)


def _get_knowledge_catalog(db: Session) -> Dict[str, List[str]]:
    rows = db.query(Question.knowledge_point, Question.knowledge_category).distinct().all()
    catalog: Dict[str, List[str]] = {}
    for kp, cat in rows:
        if not kp:
            continue
        category = cat or "其他"
        catalog.setdefault(category, [])
        if kp not in catalog[category]:
            catalog[category].append(kp)
    for category in catalog:
        catalog[category].sort()
    return catalog


def _get_user_learning_snapshot(user_id: int, db: Session) -> Dict[str, Any]:
    weak_rows = (
        db.query(UserKnowledgeMastery)
        .filter(UserKnowledgeMastery.user_id == user_id)
        .order_by(UserKnowledgeMastery.is_weak_point.desc(), UserKnowledgeMastery.mastery_rate.asc())
        .limit(16)
        .all()
    )
    weak_points = [row.knowledge_point for row in weak_rows if row.knowledge_point]

    wrong_rows = (
        db.query(UserWrongQuestion.question_id)
        .filter(UserWrongQuestion.user_id == user_id, UserWrongQuestion.mastered == False)
        .all()
    )
    wrong_ids = {row[0] for row in wrong_rows if row[0]}

    recent_rows = (
        db.query(UserPracticeHistory.question_id)
        .filter(
            UserPracticeHistory.user_id == user_id,
            UserPracticeHistory.practice_date >= date.today() - timedelta(days=5),
        )
        .all()
    )
    recent_ids = {row[0] for row in recent_rows if row[0]}

    return {
        "weak_points": weak_points,
        "wrong_ids": wrong_ids,
        "recent_ids": recent_ids,
    }


def _extract_sheet_count(text: str) -> int:
    patterns = [
        r"(\d+)\s*(?:份|张|套)(?:练习|试卷|卷子|练习单)",
        r"出\s*(\d+)\s*(?:份|张|套)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return max(1, min(5, int(match.group(1))))
    cn_map = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5}
    for key, value in cn_map.items():
        if f"{key}份" in text or f"{key}张" in text or f"{key}套" in text:
            return value
    return 1


def _extract_type_counts(text: str) -> Dict[str, int]:
    result: Dict[str, int] = {}
    aliases = [
        ("calculation", ["计算题", "计算"]),
        ("fill_blank", ["填空题", "填空"]),
        ("choice", ["选择题", "选择"]),
        ("problem_solving", ["应用题", "应用", "解决问题"]),
    ]
    for target, names in aliases:
        for name in names:
            patterns = [
                rf"(\d+)\s*(?:道|个|题)?{re.escape(name)}",
                rf"{re.escape(name)}(?:保证|不少于|至少|控制在|安排|各)?\s*(\d+)\s*(?:道|个|题)",
                rf"每套.*?{re.escape(name)}.*?(\d+)\s*(?:道|个|题)",
                rf"每张.*?{re.escape(name)}.*?(\d+)\s*(?:道|个|题)",
            ]
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    result[target] = int(match.group(1))
                    break
            if target in result:
                break
    return result


def _extract_target_count(text: str) -> Optional[int]:
    patterns = [
        r"每(?:套|张|份|卷)(?:试卷|练习单)?\s*(\d+)\s*题",
        r"每(?:套|张|份|卷).*?(\d+)\s*题",
        r"(\d+)\s*题(?:每套|每张|每份|每卷)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return max(4, min(24, int(match.group(1))))

    generic_match = re.search(r"(\d+)\s*题", text)
    if generic_match:
        return max(4, min(24, int(generic_match.group(1))))
    return None


def _extract_target_minutes(text: str) -> Optional[int]:
    patterns = [
        r"每(?:套|张|份|卷).*?(\d+)\s*分钟",
        r"控制在\s*(\d+)\s*分钟",
        r"(\d+)\s*分钟",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return max(10, min(120, int(match.group(1))))
    return None


def _build_requirement_fallback(prompt: str, user_grade: str, catalog: Dict[str, List[str]]) -> Dict[str, Any]:
    text = prompt or ""
    all_points = [kp for points in catalog.values() for kp in points]
    categories = list(catalog.keys())

    target_count = 8
    target_minutes = 30
    explicit_target_count = _extract_target_count(text)
    if explicit_target_count:
        target_count = explicit_target_count
    explicit_target_minutes = _extract_target_minutes(text)
    if explicit_target_minutes:
        target_minutes = explicit_target_minutes

    difficulties = [value for value in ["基础", "中等", "挑战"] if value in text]
    if not difficulties:
        difficulties = ["基础", "中等"]

    question_types = []
    if "计算" in text:
        question_types.append("calculation")
    if "填空" in text:
        question_types.append("fill_blank")
    if "选择" in text:
        question_types.append("choice")
    if "应用" in text or "解决问题" in text:
        question_types.append("problem_solving")

    exclude_question_types = []
    if "不要选择" in text or "不要选择题" in text:
        exclude_question_types.append("choice")
    if "不要应用" in text or "不要应用题" in text:
        exclude_question_types.append("problem_solving")

    selected_categories = [cat for cat in categories if cat and cat in text]
    selected_points = [kp for kp in all_points if kp and kp in text]
    must_include_wrong = any(token in text for token in ["错题", "查漏补缺", "弱点", "最近", "近一周", "近7天", "近30天"])
    type_counts = _extract_type_counts(text)

    return {
        "sheet_name": "AI练习单",
        "sheet_type": "wrong_redo" if must_include_wrong else "special_topic",
        "sheet_count": _extract_sheet_count(text),
        "target_count": target_count,
        "target_minutes": target_minutes,
        "knowledge_categories": selected_categories,
        "knowledge_points": selected_points,
        "question_types": question_types,
        "question_type_counts": type_counts,
        "exclude_question_types": exclude_question_types,
        "difficulties": difficulties,
        "difficulty_progression": True,
        "must_include_wrong_questions": must_include_wrong,
        "avoid_recent_questions": True,
        "strategy_hint": "wrong_focused" if must_include_wrong else "topic_balanced",
        "reasoning_summary": "系统会先理解题量、题型和知识点要求，再从题库里筛出更匹配的候选题。",
        "learning_advice": f"建议先覆盖 {user_grade or '当前年级'} 的核心题型，再搭配少量提升题，整体更适合持续练习。",
    }


def _merge_structured_requirement_input(req: AIPracticePreviewRequest) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for key in [
        "sheet_name",
        "sheet_type",
        "sheet_count",
        "target_count",
        "target_minutes",
        "knowledge_categories",
        "knowledge_points",
        "question_types",
        "question_type_counts",
        "exclude_question_types",
        "difficulties",
        "difficulty_progression",
        "must_include_wrong_questions",
        "avoid_recent_questions",
    ]:
        value = getattr(req, key, None)
        if value not in (None, "", [], {}):
            merged[key] = value
    return merged


async def _parse_ai_requirement(req: AIPracticePreviewRequest, user_id: int, db: Session) -> Dict[str, Any]:
    prompt = req.prompt or ""
    user = db.query(User).filter(User.user_id == user_id).first()
    grade_level = user.grade_level if user else ""
    catalog = _get_knowledge_catalog(db)
    snapshot = _get_user_learning_snapshot(user_id, db)
    fallback = _build_requirement_fallback(prompt, grade_level, catalog)
    structured_input = _merge_structured_requirement_input(req)

    if not prompt.strip() and not any(structured_input.values()):
        raise HTTPException(status_code=400, detail="请至少填写练习需求描述或选择一项条件")

    use_llm_parse = bool(prompt.strip())
    if prompt.strip():
        structured_signal_count = sum(
            1
            for value in structured_input.values()
            if value not in (None, "", [], {}, False)
        )
        if structured_signal_count >= 5 and len(prompt.strip()) <= 40:
            use_llm_parse = False

    prompt_text = (
        "你是小学数学练习单规划助手。请把用户需求解析成结构化配置。\n"
        "要求：\n"
        "1. 只使用提供的知识点和知识类别。\n"
        "2. sheet_type 只能是 daily、wrong_redo、special_topic、exam 之一。\n"
        "3. question_types / question_type_counts 只能使用 calculation、fill_blank、choice、problem_solving。\n"
        "4. difficulties 只能是 基础、中等、挑战。\n"
        "5. 如果用户提到多份、几张、几套练习单，要写入 sheet_count。\n"
        "6. 如果用户提到每套固定题型数量，比如 4 个计算题，要写入 question_type_counts。\n"
        "7. 只返回严格 JSON，不要 markdown。\n\n"
        f"用户年级：{grade_level or '六年级'}\n"
        f"用户薄弱知识点：{json.dumps(snapshot['weak_points'], ensure_ascii=False)}\n"
        f"表单条件：\n{json.dumps(structured_input, ensure_ascii=False)}\n"
        f"可用知识目录：\n{json.dumps(catalog, ensure_ascii=False)}\n\n"
        f"用户需求：{prompt}\n\n"
        "输出格式：\n"
        "{\n"
        '  "sheet_name": "",\n'
        '  "sheet_type": "special_topic",\n'
        '  "sheet_count": 1,\n'
        '  "target_count": 8,\n'
        '  "target_minutes": 30,\n'
        '  "knowledge_categories": [],\n'
        '  "knowledge_points": [],\n'
        '  "question_types": [],\n'
        '  "question_type_counts": {},\n'
        '  "exclude_question_types": [],\n'
        '  "difficulties": [],\n'
        '  "difficulty_progression": true,\n'
        '  "must_include_wrong_questions": false,\n'
        '  "avoid_recent_questions": true,\n'
        '  "strategy_hint": "",\n'
        '  "reasoning_summary": "",\n'
        '  "learning_advice": ""\n'
        "}"
    )

    parsed: Dict[str, Any] = {}
    if use_llm_parse:
        try:
            content = await call_text_llm(
            messages=[{"role": "user", "content": prompt_text}],
            system_prompt="你是练习单需求解析助手。只返回严格 JSON。",
            max_tokens=900,
            timeout=12.0,
        )
            parsed = _extract_json_object(content)
        except Exception:
            parsed = {}

    merged = fallback.copy()
    merged.update(structured_input)
    merged.update({k: v for k, v in parsed.items() if v not in (None, "")})
    merged["sheet_name"] = _clean_str(merged.get("sheet_name")) or fallback["sheet_name"]
    merged["sheet_type"] = _clean_str(merged.get("sheet_type")) or fallback["sheet_type"]
    if merged["sheet_type"] not in ALLOWED_SHEET_TYPES:
        merged["sheet_type"] = fallback["sheet_type"]

    try:
        merged["sheet_count"] = max(1, min(5, int(merged.get("sheet_count") or fallback["sheet_count"])))
    except (TypeError, ValueError):
        merged["sheet_count"] = fallback["sheet_count"]

    try:
        merged["target_count"] = max(4, min(24, int(merged.get("target_count") or fallback["target_count"])))
    except (TypeError, ValueError):
        merged["target_count"] = fallback["target_count"]

    try:
        merged["target_minutes"] = max(10, min(120, int(merged.get("target_minutes") or fallback["target_minutes"])))
    except (TypeError, ValueError):
        merged["target_minutes"] = fallback["target_minutes"]

    merged["knowledge_categories"] = [item for item in _dedupe_list(merged.get("knowledge_categories")) if item in catalog]
    all_points = {kp for points in catalog.values() for kp in points}
    merged["knowledge_points"] = [item for item in _dedupe_list(merged.get("knowledge_points")) if item in all_points]
    merged["question_types"] = _normalize_question_types(merged.get("question_types"))
    merged["question_type_counts"] = _normalize_type_counts(merged.get("question_type_counts"))
    merged["exclude_question_types"] = _normalize_question_types(merged.get("exclude_question_types"))
    merged["difficulties"] = _normalize_difficulties(merged.get("difficulties")) or fallback["difficulties"]
    merged["difficulty_progression"] = bool(merged.get("difficulty_progression", True))
    merged["must_include_wrong_questions"] = bool(merged.get("must_include_wrong_questions", fallback["must_include_wrong_questions"]))
    merged["avoid_recent_questions"] = bool(merged.get("avoid_recent_questions", True))
    merged["strategy_hint"] = _clean_str(merged.get("strategy_hint")) or fallback["strategy_hint"]
    merged["reasoning_summary"] = _clean_str(merged.get("reasoning_summary")) or fallback["reasoning_summary"]
    merged["learning_advice"] = _clean_str(merged.get("learning_advice")) or fallback["learning_advice"]

    explicit_sheet_count = _extract_sheet_count(prompt)
    explicit_target_count = _extract_target_count(prompt)
    explicit_target_minutes = _extract_target_minutes(prompt)
    explicit_type_counts = _extract_type_counts(prompt)
    explicit_wrong = any(token in prompt for token in ["错题", "查漏补缺", "弱点", "最近", "近一周", "近7天", "近30天"])

    if explicit_sheet_count:
        merged["sheet_count"] = explicit_sheet_count
    if explicit_target_count:
        merged["target_count"] = explicit_target_count
    if explicit_target_minutes:
        merged["target_minutes"] = explicit_target_minutes
    if explicit_type_counts:
        merged["question_type_counts"] = explicit_type_counts
        if not merged["question_types"]:
            merged["question_types"] = list(explicit_type_counts.keys())
    if explicit_wrong:
        merged["must_include_wrong_questions"] = True
        if merged["sheet_type"] == "special_topic":
            merged["sheet_type"] = "wrong_redo"

    if merged["question_type_counts"] and not merged["question_types"]:
        merged["question_types"] = list(merged["question_type_counts"].keys())
    return merged


def _candidate_base_query(
    db: Session,
    parsed: Dict[str, Any],
    grade_level: str,
    ignore_difficulty: bool = False,
    ignore_types: bool = False,
    use_categories_only: bool = False,
):
    query = db.query(Question)
    if grade_level:
        query = query.filter(Question.grade_level == grade_level)

    knowledge_points = parsed.get("knowledge_points") or []
    knowledge_categories = parsed.get("knowledge_categories") or []
    if knowledge_points and not use_categories_only:
        query = query.filter(Question.knowledge_point.in_(knowledge_points))
    elif knowledge_categories:
        query = query.filter(Question.knowledge_category.in_(knowledge_categories))

    if parsed.get("difficulties") and not ignore_difficulty:
        query = query.filter(Question.difficulty.in_(parsed["difficulties"]))
    if parsed.get("question_types") and not ignore_types:
        query = query.filter(Question.question_type.in_(parsed["question_types"]))
    if parsed.get("exclude_question_types"):
        query = query.filter(Question.question_type.notin_(parsed["exclude_question_types"]))
    return query


def _build_candidate_questions(parsed: Dict[str, Any], user_id: int, db: Session) -> Tuple[List[Question], Dict[int, float], Dict[str, Any]]:
    user = db.query(User).filter(User.user_id == user_id).first()
    grade_level = user.grade_level if user else ""
    snapshot = _get_user_learning_snapshot(user_id, db)
    target_count = int(parsed.get("target_count") or 8)
    required_pool = max(target_count * 5, 30)

    candidate_sets: List[List[Question]] = []
    query_modes = [
        {"ignore_difficulty": False, "ignore_types": False, "use_categories_only": False},
        {"ignore_difficulty": True, "ignore_types": False, "use_categories_only": False},
        {"ignore_difficulty": True, "ignore_types": True, "use_categories_only": False},
        {"ignore_difficulty": True, "ignore_types": True, "use_categories_only": True},
    ]
    for mode in query_modes:
        rows = _candidate_base_query(db, parsed, grade_level, **mode).limit(160).all()
        candidate_sets.append(rows)
        if len(rows) >= required_pool:
            break

    merged: Dict[int, Question] = {}
    for rows in candidate_sets:
        for row in rows:
            merged[row.question_id] = row

    candidates = list(merged.values())
    if not candidates:
        raise HTTPException(status_code=400, detail="题库中暂时没有符合该需求的题目")

    requested_points = set(parsed.get("knowledge_points") or [])
    requested_categories = set(parsed.get("knowledge_categories") or [])
    requested_types = set(parsed.get("question_types") or [])
    requested_difficulties = set(parsed.get("difficulties") or [])
    weak_points = set(snapshot["weak_points"])
    wrong_ids = set(snapshot["wrong_ids"])
    recent_ids = set(snapshot["recent_ids"])
    must_include_wrong = bool(parsed.get("must_include_wrong_questions"))
    avoid_recent = bool(parsed.get("avoid_recent_questions", True))

    score_map: Dict[int, float] = {}
    for q in candidates:
        score = 0.0
        if requested_points and q.knowledge_point in requested_points:
            score += 42
        if requested_categories and q.knowledge_category in requested_categories:
            score += 18
        if requested_types and q.question_type in requested_types:
            score += 15
        if requested_difficulties and q.difficulty in requested_difficulties:
            score += 10
        if q.knowledge_point in weak_points:
            score += 10
        if q.question_id in wrong_ids:
            score += 24 if must_include_wrong else 6
        if avoid_recent and q.question_id in recent_ids:
            score -= 16
        if q.is_high_freq:
            score += 2
        if q.is_classic:
            score += 2
        if q.has_image and q.knowledge_category == "几何":
            score += 3
        score -= (q.global_usage_count or 0) * 0.05
        score_map[q.question_id] = score

    candidates.sort(key=lambda q: (score_map.get(q.question_id, 0), random.random()), reverse=True)
    return candidates[: max(required_pool, 60)], score_map, snapshot


def _question_reason(question: Question, parsed: Dict[str, Any], snapshot: Dict[str, Any], mode: str = "selected") -> str:
    reasons: List[str] = []
    if question.knowledge_point in set(parsed.get("knowledge_points") or []):
        reasons.append("命中指定知识点")
    elif question.knowledge_category in set(parsed.get("knowledge_categories") or []):
        reasons.append("属于目标专题")
    if question.question_type in set(parsed.get("question_types") or []):
        reasons.append(f"题型匹配{TYPE_LABELS.get(question.question_type, '当前要求')}")
    if question.difficulty in set(parsed.get("difficulties") or []):
        reasons.append(f"难度位于{question.difficulty}范围")
    if question.question_id in snapshot["wrong_ids"]:
        reasons.append("和近期错题有关")
    if question.knowledge_point in snapshot["weak_points"]:
        reasons.append("覆盖当前薄弱点")
    if mode == "replace":
        reasons.insert(0, "用来替换同类型位置")
    if mode == "supplement":
        reasons.insert(0, "用于补足当前练习单题量")
    return "，".join(reasons[:3]) or "综合匹配当前练习目标"


def _distribute_counts(total: int, keys: List[str]) -> Dict[str, int]:
    if total <= 0 or not keys:
        return {}
    base = total // len(keys)
    remainder = total % len(keys)
    result: Dict[str, int] = {}
    for index, key in enumerate(keys):
        result[key] = base + (1 if index < remainder else 0)
    return result


def _build_target_type_counts(parsed: Dict[str, Any], candidates: List[Question], target_count: int) -> Dict[str, int]:
    explicit = dict(parsed.get("question_type_counts") or {})
    explicit_total = sum(max(0, int(count)) for count in explicit.values())
    if explicit_total >= target_count:
        trimmed: Dict[str, int] = {}
        remaining = target_count
        for question_type, count in sorted(explicit.items(), key=lambda item: (-int(item[1]), item[0])):
            if remaining <= 0:
                break
            keep = min(max(0, int(count)), remaining)
            if keep > 0:
                trimmed[question_type] = keep
                remaining -= keep
        return trimmed

    available_type_set = {q.question_type for q in candidates if q.question_type}
    requested_types = [item for item in parsed.get("question_types") or [] if item in available_type_set]
    available_types = requested_types or [item for item in ALLOWED_TYPES if item in available_type_set]

    result = {key: max(0, int(value)) for key, value in explicit.items() if key in available_type_set}
    remaining = max(0, target_count - sum(result.values()))
    filler_types = [item for item in available_types if item not in result] or available_types
    for key, value in _distribute_counts(remaining, filler_types).items():
        result[key] = result.get(key, 0) + value
    return {key: value for key, value in result.items() if value > 0}


def _build_target_difficulty_counts(parsed: Dict[str, Any], candidates: List[Question], target_count: int) -> Dict[str, int]:
    available = [item for item in ["鍩虹", "涓瓑", "鎸戞垬"] if any(q.difficulty == item for q in candidates)]
    requested = [item for item in parsed.get("difficulties") or [] if item in available]
    difficulty_keys = requested or available or ["涓瓑"]
    return _distribute_counts(target_count, difficulty_keys)


def _build_slot_plan(parsed: Dict[str, Any], candidates: List[Question]) -> List[Dict[str, Optional[str]]]:
    target_count = int(parsed.get("target_count") or 8)
    type_counts = _build_target_type_counts(parsed, candidates, target_count)
    difficulty_counts = _build_target_difficulty_counts(parsed, candidates, target_count)

    type_slots: List[Optional[str]] = []
    for question_type, count in type_counts.items():
        type_slots.extend([question_type] * count)
    if len(type_slots) < target_count:
        type_slots.extend([None] * (target_count - len(type_slots)))
    type_slots = type_slots[:target_count]

    difficulty_slots: List[Optional[str]] = []
    for difficulty in ["鍩虹", "涓瓑", "鎸戞垬"]:
        difficulty_slots.extend([difficulty] * difficulty_counts.get(difficulty, 0))
    if len(difficulty_slots) < target_count:
        difficulty_slots.extend(["涓瓑"] * (target_count - len(difficulty_slots)))
    difficulty_slots = difficulty_slots[:target_count]
    if not parsed.get("difficulty_progression"):
        random.shuffle(difficulty_slots)

    slots: List[Dict[str, Optional[str]]] = []
    for index in range(target_count):
        slots.append({
            "required_type": type_slots[index] if index < len(type_slots) else None,
            "desired_difficulty": difficulty_slots[index] if index < len(difficulty_slots) else None,
        })
    return slots


def _pick_best(
    pool: List[Question],
    selected: List[Question],
    score_map: Dict[int, float],
    variant_penalty: Counter,
    required_type: Optional[str] = None,
    desired_difficulty: Optional[str] = None,
    target_question: Optional[Question] = None,
    blocked_ids: Optional[set] = None,
) -> Optional[Question]:
    selected_ids = {q.question_id for q in selected}
    blocked_ids = blocked_ids or set()
    selected_types = Counter(q.question_type for q in selected)
    selected_points = Counter(q.knowledge_point for q in selected if q.knowledge_point)

    best_question = None
    best_score = None
    for question in pool:
        if question.question_id in selected_ids:
            continue
        if question.question_id in blocked_ids:
            continue
        score = score_map.get(question.question_id, 0.0)
        score -= variant_penalty.get(question.question_id, 0) * 8
        score -= selected_points.get(question.knowledge_point, 0) * 5
        score -= selected_types.get(question.question_type, 0) * 2
        if required_type:
            score += 20 if question.question_type == required_type else -12
        if desired_difficulty:
            if question.difficulty == desired_difficulty:
                score += 10
            elif question.difficulty and desired_difficulty:
                score -= abs(DIFFICULTY_WEIGHT.get(question.difficulty, 1) - DIFFICULTY_WEIGHT.get(desired_difficulty, 1)) * 3
        if target_question:
            if question.question_type == target_question.question_type:
                score += 14
            if question.knowledge_point == target_question.knowledge_point:
                score += 12
            if question.knowledge_category == target_question.knowledge_category:
                score += 7
            if question.difficulty == target_question.difficulty:
                score += 6
            elif question.difficulty and target_question.difficulty:
                score -= abs(DIFFICULTY_WEIGHT.get(question.difficulty, 1) - DIFFICULTY_WEIGHT.get(target_question.difficulty, 1)) * 2
        score += random.random()
        if best_score is None or score > best_score:
            best_score = score
            best_question = question
    return best_question


def _evaluate_variant(
    selected: List[Question],
    parsed: Dict[str, Any],
    snapshot: Dict[str, Any],
    score_map: Dict[int, float],
) -> float:
    if not selected:
        return -10**9

    score = sum(score_map.get(question.question_id, 0.0) for question in selected)
    target_count = int(parsed.get("target_count") or 8)
    target_minutes = int(parsed.get("target_minutes") or 30)
    target_type_counts = _build_target_type_counts(parsed, selected, target_count)
    target_difficulty_counts = _build_target_difficulty_counts(parsed, selected, target_count)

    selected_type_counts = Counter(question.question_type for question in selected if question.question_type)
    selected_difficulty_counts = Counter(question.difficulty for question in selected if question.difficulty)
    point_counts = Counter(question.knowledge_point for question in selected if question.knowledge_point)
    category_counts = Counter(question.knowledge_category for question in selected if question.knowledge_category)

    for question_type, expected in target_type_counts.items():
        actual = selected_type_counts.get(question_type, 0)
        score -= abs(expected - actual) * 14
        if actual >= expected:
            score += 4

    requested_types = set(parsed.get("question_types") or [])
    for question_type in requested_types:
        if selected_type_counts.get(question_type, 0) > 0:
            score += 3
        else:
            score -= 12

    for difficulty, expected in target_difficulty_counts.items():
        actual = selected_difficulty_counts.get(difficulty, 0)
        score -= abs(expected - actual) * 8

    requested_points = set(parsed.get("knowledge_points") or [])
    requested_categories = set(parsed.get("knowledge_categories") or [])
    if requested_points:
        covered_points = len({q.knowledge_point for q in selected if q.knowledge_point in requested_points})
        score += covered_points * 12
        score -= max(0, len(requested_points) - covered_points) * 8
    elif requested_categories:
        covered_categories = len({q.knowledge_category for q in selected if q.knowledge_category in requested_categories})
        score += covered_categories * 8

    weak_points = set(snapshot.get("weak_points") or [])
    wrong_ids = set(snapshot.get("wrong_ids") or [])
    weak_hit_count = sum(1 for q in selected if q.knowledge_point in weak_points)
    wrong_hit_count = sum(1 for q in selected if q.question_id in wrong_ids)
    score += weak_hit_count * 4
    score += wrong_hit_count * (8 if parsed.get("must_include_wrong_questions") else 3)
    if parsed.get("must_include_wrong_questions") and wrong_hit_count == 0:
        score -= 35

    duplicate_point_penalty = sum(max(0, count - 1) for count in point_counts.values())
    duplicate_category_penalty = sum(max(0, count - 2) for count in category_counts.values())
    score -= duplicate_point_penalty * 6
    score -= duplicate_category_penalty * 2

    estimated_time = _estimate_time(selected)
    score -= abs(estimated_time - target_minutes) * 0.8
    if abs(estimated_time - target_minutes) <= 5:
        score += 6

    if parsed.get("difficulty_progression"):
        progression_penalty = 0
        weights = [DIFFICULTY_WEIGHT.get(question.difficulty, 1) for question in selected]
        for previous, current in zip(weights, weights[1:]):
            if current < previous:
                progression_penalty += previous - current
        score -= progression_penalty * 4

    if len(selected) < target_count:
        score -= (target_count - len(selected)) * 30

    return score


def _build_variant_summaries(selected: List[Question], parsed: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, str]:
    type_counts = Counter(question.question_type for question in selected if question.question_type)
    difficulty_counts = Counter(question.difficulty for question in selected if question.difficulty)
    knowledge_points = [question.knowledge_point for question in selected if question.knowledge_point]
    unique_points = len(set(knowledge_points))
    wrong_hit_count = sum(1 for question in selected if question.question_id in set(snapshot.get("wrong_ids") or []))

    type_summary = "、".join(
        f"{TYPE_LABELS.get(question_type, question_type)} {count} 题"
        for question_type, count in sorted(type_counts.items(), key=lambda item: item[0])
    ) or "题型均衡搭配"
    difficulty_summary = "、".join(
        f"{difficulty} {count} 题"
        for difficulty, count in sorted(difficulty_counts.items(), key=lambda item: DIFFICULTY_WEIGHT.get(item[0], 1))
    ) or "难度自动平衡"

    composition_summary = f"题型结构：{type_summary}；难度分布：{difficulty_summary}。"
    coverage_summary = f"共覆盖 {unique_points} 个知识点，预计 { _estimate_time(selected) } 分钟完成。"
    if wrong_hit_count:
        coverage_summary += f" 其中包含 {wrong_hit_count} 题与你的错题/薄弱点直接相关。"

    review_summary = "整体按先易后难排列，重复知识点已尽量压低。"
    if parsed.get("must_include_wrong_questions") and not wrong_hit_count:
        review_summary = "当前题库中符合条件的错题较少，本套以相近知识点题目补足。"

    return {
        "composition_summary": composition_summary,
        "coverage_summary": coverage_summary,
        "review_summary": review_summary,
    }


def _build_preview_explanations(parsed: Dict[str, Any], variants: List[Dict[str, Any]], snapshot: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    if parsed.get("question_type_counts"):
        lines.append("优先满足你明确填写的题型数量，再补足整套题量。")
    elif parsed.get("question_types"):
        lines.append("先按指定题型筛出候选题，再在每种题型里做平衡。")
    if parsed.get("knowledge_points"):
        lines.append("选题会优先覆盖你点名的知识点，避免整套题只集中在一个小点上。")
    elif parsed.get("knowledge_categories"):
        lines.append("本次按知识类别先粗筛，再在类别内部做难度和题型协调。")
    if parsed.get("difficulty_progression"):
        lines.append("默认按先易后难安排，减少一开始就过难的情况。")
    if parsed.get("must_include_wrong_questions"):
        lines.append("会优先命中你的错题和薄弱点，不足部分再补相近题。")
    if len(variants) > 1:
        lines.append("多套草稿之间会尽量减少重复题，保证每套都有自己的训练价值。")
    return lines[:4]


def _should_use_ai_candidate_rerank(parsed: Dict[str, Any], candidates: List[Question]) -> bool:
    if len(candidates) < 10:
        return False
    if int(parsed.get("sheet_count") or 1) > 1:
        return True
    if bool(parsed.get("must_include_wrong_questions")):
        return True
    if len(parsed.get("knowledge_points") or []) >= 2:
        return True
    if len(parsed.get("question_type_counts") or {}) >= 2:
        return True
    if len(parsed.get("question_types") or []) >= 2 and len(parsed.get("difficulties") or []) >= 2:
        return True
    return False


def _should_use_ai_variant_review(parsed: Dict[str, Any], variants: List[Dict[str, Any]]) -> bool:
    if not variants:
        return False
    if int(parsed.get("sheet_count") or 1) > 1:
        return True
    if int(parsed.get("target_count") or 8) >= 12:
        return True
    if bool(parsed.get("must_include_wrong_questions")) and len(parsed.get("knowledge_points") or []) >= 1:
        return True
    return False


async def _apply_ai_candidate_rerank(
    parsed: Dict[str, Any],
    candidates: List[Question],
    score_map: Dict[int, float],
    snapshot: Dict[str, Any],
) -> Tuple[Dict[int, float], Dict[str, str]]:
    top_candidates = candidates[: min(len(candidates), 12)]
    if len(top_candidates) < 6:
        return score_map, {}

    payload = []
    wrong_ids = set(snapshot.get("wrong_ids") or [])
    weak_points = set(snapshot.get("weak_points") or [])
    for question in top_candidates:
        payload.append({
            "question_id": question.question_id,
            "knowledge_point": question.knowledge_point,
            "knowledge_category": question.knowledge_category,
            "question_type": question.question_type,
            "difficulty": question.difficulty,
            "is_wrong_related": question.question_id in wrong_ids,
            "is_weak_point": question.knowledge_point in weak_points,
            "text_preview": (question.question_text or "")[:80],
        })

    prompt = (
        "你是小学数学组卷复核助手。请基于用户需求，从候选题中挑出更值得优先入选的题。\n"
        "只返回 JSON，不要 Markdown。\n"
        "输出格式：\n"
        "{\n"
        '  "preferred_ids": [1,2,3],\n'
        '  "selection_reason": "",\n'
        '  "coverage_summary": "",\n'
        '  "review_summary": ""\n'
        "}\n\n"
        f"用户需求：{json.dumps(parsed, ensure_ascii=False)}\n"
        f"候选题：{json.dumps(payload, ensure_ascii=False)}\n"
    )

    try:
        content = await call_text_llm(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="你只输出严格 JSON，帮助复核候选题优先级。",
            max_tokens=700,
            timeout=8.0,
        )
        rerank = _extract_json_object(content)
    except Exception:
        return score_map, {}

    adjusted = dict(score_map)
    preferred_ids = rerank.get("preferred_ids") or []
    boost = len(preferred_ids) * 2
    for question_id in preferred_ids:
        try:
            qid = int(question_id)
        except (TypeError, ValueError):
            continue
        if qid in adjusted:
            adjusted[qid] += max(boost, 4)
            boost -= 1

    insights = {
        "selection_reason": _clean_str(rerank.get("selection_reason")),
        "coverage_summary": _clean_str(rerank.get("coverage_summary")),
        "review_summary": _clean_str(rerank.get("review_summary")),
    }
    return adjusted, insights


async def _apply_ai_variant_review(
    parsed: Dict[str, Any],
    variants: List[Dict[str, Any]],
) -> Dict[str, Dict[str, str]]:
    if not variants:
        return {}

    payload = []
    for item in variants[:5]:
        payload.append({
            "variant_id": item["variant_id"],
            "estimated_time": item["estimated_time"],
            "questions": [
                {
                    "question_id": question.question_id,
                    "knowledge_point": question.knowledge_point,
                    "question_type": question.question_type,
                    "difficulty": question.difficulty,
                }
                for question in item["selected_questions"]
            ],
        })

    prompt = (
        "你是小学数学练习单复核助手。请根据用户需求，对每一套草稿给出一句结构说明、覆盖说明和复核意见。\n"
        "只返回 JSON，不要 Markdown。\n"
        "输出格式：\n"
        "{\n"
        '  "variants": [\n'
        '    {"variant_id": "variant-1", "composition_summary": "", "coverage_summary": "", "review_summary": ""}\n'
        "  ]\n"
        "}\n\n"
        f"用户需求：{json.dumps(parsed, ensure_ascii=False)}\n"
        f"草稿：{json.dumps(payload, ensure_ascii=False)}\n"
    )
    try:
        content = await call_text_llm(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="你只输出严格 JSON，用于练习单草稿复核。",
            max_tokens=900,
            timeout=10.0,
        )
        review = _extract_json_object(content)
    except Exception:
        return {}

    result: Dict[str, Dict[str, str]] = {}
    for item in review.get("variants") or []:
        variant_id = _clean_str(item.get("variant_id"))
        if not variant_id:
            continue
        result[variant_id] = {
            "composition_summary": _clean_str(item.get("composition_summary")),
            "coverage_summary": _clean_str(item.get("coverage_summary")),
            "review_summary": _clean_str(item.get("review_summary")),
        }
    return result


def _build_one_variant(
    parsed: Dict[str, Any],
    candidates: List[Question],
    score_map: Dict[int, float],
    snapshot: Dict[str, Any],
    variant_penalty: Counter,
) -> List[Question]:
    slot_plan = _build_slot_plan(parsed, candidates)
    selected: List[Question] = []
    for slot in slot_plan:
        required_type = slot.get("required_type")
        desired_difficulty = slot.get("desired_difficulty")
        picked = _pick_best(
            candidates,
            selected,
            score_map,
            variant_penalty,
            required_type=required_type,
            desired_difficulty=desired_difficulty,
        )
        if not picked and required_type:
            picked = _pick_best(
                candidates,
                selected,
                score_map,
                variant_penalty,
                required_type=required_type,
            )
        if not picked and desired_difficulty:
            picked = _pick_best(
                candidates,
                selected,
                score_map,
                variant_penalty,
                desired_difficulty=desired_difficulty,
            )
        if not picked:
            picked = _pick_best(candidates, selected, score_map, variant_penalty)
        if not picked:
            break
        selected.append(picked)

    if parsed.get("difficulty_progression"):
        selected.sort(key=lambda q: (DIFFICULTY_WEIGHT.get(q.difficulty, 1), TYPE_LABELS.get(q.question_type or "", "")))
    return selected


def _build_variants(parsed: Dict[str, Any], candidates: List[Question], score_map: Dict[int, float], snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    sheet_count = max(1, min(5, int(parsed.get("sheet_count") or 1)))
    variants: List[Dict[str, Any]] = []
    penalty = Counter()
    used_signatures = set()
    attempt_count = max(sheet_count * 4, 5)
    for index in range(sheet_count):
        best_selected: List[Question] = []
        best_score: Optional[float] = None
        for _ in range(attempt_count):
            selected = _build_one_variant(parsed, candidates, score_map, snapshot, penalty)
            if not selected:
                continue
            signature = tuple(question.question_id for question in selected)
            current_score = _evaluate_variant(selected, parsed, snapshot, score_map)
            if signature in used_signatures:
                current_score -= 20
            if best_score is None or current_score > best_score:
                best_selected = selected
                best_score = current_score
        if not best_selected:
            continue
        used_signatures.add(tuple(question.question_id for question in best_selected))
        for question in best_selected:
            penalty[question.question_id] += 1
        variants.append({
            "variant_id": f"variant-{index + 1}",
            "sheet_name": parsed.get("sheet_name") or "AI练习单",
            "selected_questions": best_selected,
            "estimated_time": _estimate_time(best_selected),
        })
    return variants


def _serialize_selected_question(question: Question, reason: str) -> AISelectedQuestion:
    return AISelectedQuestion(
        question_id=question.question_id,
        q_id=question.q_id,
        knowledge_point=question.knowledge_point,
        knowledge_category=question.knowledge_category,
        question_type=question.question_type,
        difficulty=question.difficulty,
        question_text=question.question_text,
        has_image=bool(question.has_image),
        image_path=question.image_path,
        selected_reason=reason,
    )


def _serialize_variant(item: Dict[str, Any], parsed: Dict[str, Any], snapshot: Dict[str, Any], ai_review_map: Optional[Dict[str, Dict[str, str]]] = None) -> AIPracticeVariant:
    questions = item["selected_questions"]
    fallback_summary = _build_variant_summaries(questions, parsed, snapshot)
    ai_review = (ai_review_map or {}).get(item["variant_id"], {})
    return AIPracticeVariant(
        variant_id=item["variant_id"],
        sheet_name=item["sheet_name"],
        estimated_time=item["estimated_time"],
        composition_summary=ai_review.get("composition_summary") or fallback_summary["composition_summary"],
        coverage_summary=ai_review.get("coverage_summary") or fallback_summary["coverage_summary"],
        review_summary=ai_review.get("review_summary") or fallback_summary["review_summary"],
        selected_questions=[
            _serialize_selected_question(question, _question_reason(question, parsed, snapshot))
            for question in questions
        ],
    )


async def build_ai_preview(req: AIPracticePreviewRequest, user_id: int, db: Session) -> AIPracticePreviewResponse:
    parsed = await _parse_ai_requirement(req, user_id, db)
    candidates, score_map, snapshot = _build_candidate_questions(parsed, user_id, db)
    rerank_insights: Dict[str, str] = {}
    if _should_use_ai_candidate_rerank(parsed, candidates):
        score_map, rerank_insights = await _apply_ai_candidate_rerank(parsed, candidates, score_map, snapshot)
    candidates.sort(key=lambda q: (score_map.get(q.question_id, 0), random.random()), reverse=True)
    variants = _build_variants(parsed, candidates, score_map, snapshot)
    if not variants:
        raise HTTPException(status_code=400, detail="这次没有选出合适的题目，请换一种描述再试")

    ai_review_map: Dict[str, Dict[str, str]] = {}
    if _should_use_ai_variant_review(parsed, variants):
        ai_review_map = await _apply_ai_variant_review(parsed, variants)
    parsed_requirement = AIParsedRequirement(**parsed)
    variant_models = [_serialize_variant(item, parsed, snapshot, ai_review_map) for item in variants]
    first_variant = variant_models[0]
    summary = parsed.get("reasoning_summary") or "已按你的要求优先匹配题型、知识点和难度。"
    if parsed.get("sheet_count", 1) > 1:
        summary += f" 这次先给你准备了 {parsed['sheet_count']} 套可直接生成的草稿。"

    return AIPracticePreviewResponse(
        parsed_requirement=parsed_requirement,
        suggestion=AIPracticeSuggestion(
            summary=summary,
            selection_reason=rerank_insights.get("selection_reason") or "优先满足明确题型数量，再补足知识点覆盖和难度梯度。",
            ordering_reason="默认按难度由浅入深排序，减少一上来就过难的情况。",
            coverage_summary=rerank_insights.get("coverage_summary") or "候选题先经过程序粗筛，再做多套差异化组合，尽量减少套与套之间的重复。",
            explanation_lines=_build_preview_explanations(parsed, variants, snapshot),
            review_summary=rerank_insights.get("review_summary") or "",
        ),
        variants=variant_models,
        selected_questions=first_variant.selected_questions,
        candidate_count=len(candidates),
        estimated_time=first_variant.estimated_time,
        total_variants=len(variant_models),
    )

def _persist_sheet(
    selected: List[Question],
    user_id: int,
    db: Session,
    sheet_name: str,
    sheet_type: str,
) -> PracticeSheetOut:
    safe_sheet_type = sheet_type if sheet_type in ALLOWED_SHEET_TYPES else "special_topic"
    sheet = PracticeSheet(
        user_id=user_id,
        sheet_name=sheet_name,
        sheet_type=SheetType(safe_sheet_type),
        total_questions=len(selected),
        estimated_time=_estimate_time(selected),
    )
    db.add(sheet)
    db.flush()

    practice_type = safe_sheet_type if safe_sheet_type in {item.value for item in PracticeType} else PracticeType.special_topic.value
    for index, question in enumerate(selected):
        db.add(SheetQuestion(sheet_id=sheet.sheet_id, question_id=question.question_id, question_order=index + 1))
        db.add(UserPracticeHistory(
            user_id=user_id,
            question_id=question.question_id,
            practice_date=date.today(),
            practice_type=practice_type,
            sheet_id=sheet.sheet_id,
        ))

    db.commit()
    db.refresh(sheet)
    return PracticeSheetOut(
        sheet_id=sheet.sheet_id,
        sheet_name=sheet.sheet_name,
        sheet_type=sheet.sheet_type,
        total_questions=sheet.total_questions,
        estimated_time=sheet.estimated_time,
        generated_date=sheet.generated_date,
        questions=[QuestionOut.model_validate(q) for q in selected],
    )


def confirm_ai_sheets(req: AIPracticeConfirmRequest, user_id: int, db: Session) -> AIPracticeConfirmResponse:
    variant_payloads = list(req.variants or [])
    if not variant_payloads and req.question_ids:
        variant_payloads = [{
            "variant_id": "variant-1",
            "sheet_name": req.sheet_name,
            "question_ids": req.question_ids,
        }]

    if not variant_payloads:
        raise HTTPException(status_code=400, detail="请至少确认一套练习单")

    created: List[PracticeSheetOut] = []
    base_name = _clean_str(req.sheet_name) or "AI练习单"

    for index, item in enumerate(variant_payloads, start=1):
        question_ids = item.question_ids if hasattr(item, "question_ids") else item.get("question_ids", [])
        if not question_ids:
            continue
        selected = db.query(Question).filter(Question.question_id.in_(question_ids)).all()
        if not selected:
            continue
        id_order = {qid: order for order, qid in enumerate(question_ids)}
        selected.sort(key=lambda q: id_order.get(q.question_id, 9999))
        item_name = _clean_str(item.sheet_name if hasattr(item, "sheet_name") else item.get("sheet_name")) or base_name
        if len(variant_payloads) > 1 and item_name == base_name:
            item_name = f"{item_name} {index}"
        created.append(_persist_sheet(selected, user_id, db, item_name, req.sheet_type))

    if not created:
        raise HTTPException(status_code=400, detail="没有可生成的练习单")

    return AIPracticeConfirmResponse(created_count=len(created), sheets=created)


def _select_adjust_question(
    parsed_requirement: AIParsedRequirement,
    current_question_ids: List[int],
    user_id: int,
    db: Session,
    replace_question_id: Optional[int] = None,
) -> Tuple[Question, Dict[str, Any], List[Question]]:
    parsed = parsed_requirement.model_dump()
    candidates, score_map, snapshot = _build_candidate_questions(parsed, user_id, db)
    current_selected = db.query(Question).filter(Question.question_id.in_(current_question_ids)).all()
    current_map = {q.question_id: q for q in current_selected}
    target_question = current_map.get(replace_question_id) if replace_question_id else None

    selected_without_target = [q for q in current_selected if q.question_id != replace_question_id]
    penalty = Counter({qid: 1 for qid in current_question_ids for qid in [qid]})
    blocked_ids = {replace_question_id} if replace_question_id else set()
    replacement = _pick_best(
        candidates,
        selected_without_target,
        score_map,
        penalty,
        target_question=target_question,
        blocked_ids=blocked_ids,
    )
    if not replacement:
        raise HTTPException(status_code=400, detail="暂时没有更合适的替换题")
    return replacement, snapshot, selected_without_target + [replacement]


def replace_ai_question(req, user_id: int, db: Session) -> AIPracticeAdjustResponse:
    replacement, snapshot, final_questions = _select_adjust_question(
        req.parsed_requirement,
        req.current_question_ids,
        user_id,
        db,
        replace_question_id=req.replace_question_id,
    )
    return AIPracticeAdjustResponse(
        question=_serialize_selected_question(replacement, _question_reason(replacement, req.parsed_requirement.model_dump(), snapshot, mode="replace")),
        estimated_time=_estimate_time(final_questions),
    )


def supplement_ai_question(req, user_id: int, db: Session) -> AIPracticeAdjustResponse:
    replacement, snapshot, final_questions = _select_adjust_question(
        req.parsed_requirement,
        req.current_question_ids,
        user_id,
        db,
        replace_question_id=None,
    )
    return AIPracticeAdjustResponse(
        question=_serialize_selected_question(replacement, _question_reason(replacement, req.parsed_requirement.model_dump(), snapshot, mode="supplement")),
        estimated_time=_estimate_time(final_questions),
    )


def _apply_replace_mode_bias(
    score_map: Dict[int, float],
    candidates: List[Question],
    snapshot: Dict[str, Any],
    mode: str,
    target_question: Optional[Question],
) -> Dict[int, float]:
    adjusted = dict(score_map)
    safe_mode = mode if mode in REPLACE_MODES else "balanced"
    wrong_ids = set(snapshot.get("wrong_ids") or [])

    for question in candidates:
        if safe_mode == "same_type" and target_question:
            adjusted[question.question_id] += 12 if question.question_type == target_question.question_type else -8
        elif safe_mode == "same_knowledge" and target_question:
            if question.knowledge_point == target_question.knowledge_point:
                adjusted[question.question_id] += 14
            elif question.knowledge_category == target_question.knowledge_category:
                adjusted[question.question_id] += 6
        elif safe_mode == "easier" and target_question:
            adjusted[question.question_id] += (
                DIFFICULTY_WEIGHT.get(target_question.difficulty, 1) - DIFFICULTY_WEIGHT.get(question.difficulty, 1)
            ) * 5
        elif safe_mode == "harder" and target_question:
            adjusted[question.question_id] += (
                DIFFICULTY_WEIGHT.get(question.difficulty, 1) - DIFFICULTY_WEIGHT.get(target_question.difficulty, 1)
            ) * 5
        elif safe_mode == "wrong_focused":
            adjusted[question.question_id] += 10 if question.question_id in wrong_ids else 0
    return adjusted


def _select_adjust_question(
    parsed_requirement: AIParsedRequirement,
    current_question_ids: List[int],
    user_id: int,
    db: Session,
    replace_question_id: Optional[int] = None,
    replace_mode: str = "balanced",
) -> Tuple[Question, Dict[str, Any], List[Question], str]:
    parsed = parsed_requirement.model_dump()
    candidates, score_map, snapshot = _build_candidate_questions(parsed, user_id, db)
    current_selected = db.query(Question).filter(Question.question_id.in_(current_question_ids)).all()
    current_map = {q.question_id: q for q in current_selected}
    target_question = current_map.get(replace_question_id) if replace_question_id else None
    adjusted_score_map = _apply_replace_mode_bias(score_map, candidates, snapshot, replace_mode, target_question)

    selected_without_target = [q for q in current_selected if q.question_id != replace_question_id]
    penalty = Counter({qid: 1 for qid in current_question_ids for qid in [qid]})
    blocked_ids = {replace_question_id} if replace_question_id else set()
    replacement = _pick_best(
        candidates,
        selected_without_target,
        adjusted_score_map,
        penalty,
        target_question=target_question,
        blocked_ids=blocked_ids,
    )
    if not replacement:
        raise HTTPException(status_code=400, detail="暂时没有更合适的替换题")

    review_hint = {
        "balanced": "已按综合匹配为你更换题目。",
        "easier": "已尽量换成更容易上手的同类题。",
        "harder": "已尽量换成更有挑战性的同类题。",
        "same_type": "已优先换成同题型题目。",
        "same_knowledge": "已优先换成同知识点或同类别题目。",
        "wrong_focused": "已优先换成更贴近错题和薄弱点的题目。",
    }.get(replace_mode, "已按综合匹配为你更换题目。")

    return replacement, snapshot, selected_without_target + [replacement], review_hint


def replace_ai_question(req, user_id: int, db: Session) -> AIPracticeAdjustResponse:
    replacement, snapshot, final_questions, review_hint = _select_adjust_question(
        req.parsed_requirement,
        req.current_question_ids,
        user_id,
        db,
        replace_question_id=req.replace_question_id,
        replace_mode=getattr(req, "replace_mode", "balanced"),
    )
    return AIPracticeAdjustResponse(
        question=_serialize_selected_question(replacement, _question_reason(replacement, req.parsed_requirement.model_dump(), snapshot, mode="replace")),
        estimated_time=_estimate_time(final_questions),
        review_hint=review_hint,
    )


def supplement_ai_question(req, user_id: int, db: Session) -> AIPracticeAdjustResponse:
    replacement, snapshot, final_questions, review_hint = _select_adjust_question(
        req.parsed_requirement,
        req.current_question_ids,
        user_id,
        db,
        replace_question_id=None,
        replace_mode="balanced",
    )
    return AIPracticeAdjustResponse(
        question=_serialize_selected_question(replacement, _question_reason(replacement, req.parsed_requirement.model_dump(), snapshot, mode="supplement")),
        estimated_time=_estimate_time(final_questions),
        review_hint=review_hint,
    )
