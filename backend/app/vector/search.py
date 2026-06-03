from __future__ import annotations

import difflib
import re
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core.config import QDRANT_COLLECTION
from ..models import Question
from .client import get_qdrant_client
from .embedding import embed_text


CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    "几何": ("几何", "图形", "面积", "周长", "体积", "表面积", "圆", "三角形", "长方形", "正方形", "阴影"),
    "行程": ("行程", "相遇", "追及", "速度", "路程", "时间", "火车", "钟面行程"),
    "工程": ("工程", "工作效率", "合作", "完工", "牛吃草"),
    "经济": ("经济", "利润", "折扣", "售价", "进价", "成本", "盈利", "亏损"),
    "浓度": ("浓度", "溶液", "盐水", "混合", "稀释", "含盐"),
    "方程与应用": ("方程", "等量关系", "应用题", "年龄", "和差倍", "百分数应用"),
    "计算": ("计算", "简便", "混合运算", "分数运算", "小数", "百分数", "裂项"),
    "数论": ("数论", "整除", "因数", "倍数", "最大公因数", "最小公倍数", "余数", "奇偶"),
    "逻辑推理": ("逻辑", "推理", "排列", "组合", "抽屉", "规律", "最值", "定义新运算"),
    "基础": ("单位换算", "植树", "基础"),
}

POINT_ALIASES: dict[str, tuple[str, ...]] = {
    "平面图形面积": ("面积", "阴影面积", "三角形面积", "正方形面积", "长方形面积", "梯形面积", "圆面积"),
    "平面图形周长": ("周长", "圆的周长"),
    "立体图形体积": ("体积", "圆柱", "圆锥", "长方体", "正方体"),
    "立体图形表面积": ("表面积", "展开图"),
    "行程问题": ("行程", "相遇", "追及", "速度", "路程"),
    "工程问题": ("工程", "工作效率", "合作", "牛吃草"),
    "浓度问题": ("浓度", "溶液", "盐水", "混合", "稀释"),
    "经济问题": ("经济", "利润", "折扣", "售价", "进价"),
    "利润问题": ("利润", "盈利", "亏损", "售价", "进价"),
    "比和比例应用": ("比例", "比", "比例尺"),
    "分数百分数应用": ("分数应用", "百分数应用", "百分比"),
    "方程解法": ("方程", "解方程", "等量关系"),
    "年龄问题": ("年龄",),
    "和差倍问题": ("和差倍", "和倍", "差倍"),
    "简便运算": ("简便", "巧算", "乘法分配律"),
    "分数运算": ("分数", "带分数", "繁分数"),
    "四则混合运算": ("四则", "混合运算"),
    "找规律": ("规律", "数列", "图形规律"),
    "排列组合": ("排列", "组合", "计数"),
    "逻辑推理": ("逻辑", "推理"),
    "定义新运算": ("定义新运算", "新运算"),
}

QUESTION_TYPE_ALIASES: dict[str, tuple[str, ...]] = {
    "choice": ("选择", "选择题", "选项"),
    "fill_blank": ("填空", "填空题", "空格"),
    "calculation": ("计算", "计算题", "脱式"),
    "problem_solving": ("应用", "应用题", "解答", "解决问题"),
}


def _query_qdrant(vector: list[float], limit: int):
    client = get_qdrant_client()
    if hasattr(client, "search"):
        return client.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=vector,
            limit=limit,
            with_payload=True,
        )
    response = client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=vector,
        limit=limit,
        with_payload=True,
    )
    return getattr(response, "points", response)


def _serialize_question(question: Question, score: float = 0.0, source: str = "mysql") -> dict[str, Any]:
    return {
        "question_id": question.question_id,
        "q_id": question.q_id,
        "question_text": question.question_text,
        "answer": question.answer,
        "solution": question.solution,
        "knowledge_point": question.knowledge_point,
        "knowledge_category": question.knowledge_category,
        "question_type": question.question_type,
        "difficulty": question.difficulty,
        "has_image": bool(question.has_image),
        "image_path": question.image_path,
        "score": round(float(score), 4),
        "source": source,
    }


def _tokens(text: str) -> list[str]:
    return [item for item in re.split(r"[\s,，。；;、：:]+", text or "") if len(item) >= 2]


def _contains_any(text: str, aliases: tuple[str, ...]) -> bool:
    return any(alias and alias in text for alias in aliases)


def _infer_query_hints(query_text: str) -> dict[str, set[str]]:
    text = query_text or ""
    categories = {name for name, aliases in CATEGORY_ALIASES.items() if _contains_any(text, aliases)}
    points = {name for name, aliases in POINT_ALIASES.items() if _contains_any(text, aliases)}
    question_types = {
        name for name, aliases in QUESTION_TYPE_ALIASES.items() if _contains_any(text, aliases)
    }
    return {
        "categories": categories,
        "points": points,
        "question_types": question_types,
        "tokens": set(_tokens(text)),
    }


def _metadata_score(question: Question, hints: dict[str, set[str]]) -> float:
    score = 0.0
    category = question.knowledge_category or ""
    point = question.knowledge_point or ""
    qtype = question.question_type or ""
    text = question.question_text or ""

    if point in hints["points"]:
        score += 0.65
    if category in hints["categories"]:
        score += 0.35
    if qtype in hints["question_types"]:
        score += 0.2
    if any(token in point for token in hints["tokens"]):
        score += 0.2
    if any(token in category for token in hints["tokens"]):
        score += 0.12
    if any(token in text for token in hints["tokens"]):
        score += 0.08
    return score


def _apply_alias_boost(question: Question, query_text: str) -> float:
    text = query_text or ""
    point = question.knowledge_point or ""
    category = question.knowledge_category or ""
    score = 0.0
    for name, aliases in POINT_ALIASES.items():
        if point == name and _contains_any(text, aliases):
            score += 0.35
    for name, aliases in CATEGORY_ALIASES.items():
        if category == name and _contains_any(text, aliases):
            score += 0.18
    return score


def _fetch_metadata_candidates(
    db: Session,
    hints: dict[str, set[str]],
    limit: int,
    exclude_ids: set[int] | None = None,
) -> list[Question]:
    filters = []
    if hints["points"]:
        filters.append(Question.knowledge_point.in_(list(hints["points"])))
    if hints["categories"]:
        filters.append(Question.knowledge_category.in_(list(hints["categories"])))
    if hints["question_types"]:
        filters.append(Question.question_type.in_(list(hints["question_types"])))
    for token in list(hints["tokens"])[:8]:
        like = f"%{token}%"
        filters.extend([
            Question.question_text.like(like),
            Question.knowledge_point.like(like),
            Question.knowledge_category.like(like),
        ])
    if not filters:
        return []

    query = db.query(Question).filter(or_(*filters))
    if exclude_ids:
        query = query.filter(~Question.question_id.in_(list(exclude_ids)))
    return query.limit(max(limit, 1)).all()


def _rank_candidates(
    candidates: dict[int, tuple[Question, float, str]],
    hints: dict[str, set[str]],
    query_text: str,
    limit: int,
) -> list[dict[str, Any]]:
    ranked = []
    for question, base_score, source in candidates.values():
        score = base_score + _metadata_score(question, hints) + _apply_alias_boost(question, query_text)
        ranked.append(_serialize_question(question, score=score, source=source))
    return sorted(ranked, key=lambda item: item["score"], reverse=True)[:limit]


def _keyword_fallback(db: Session, query_text: str, limit: int = 10) -> list[dict[str, Any]]:
    hints = _infer_query_hints(query_text)
    rows = _fetch_metadata_candidates(db, hints, limit=limit * 3)
    candidates = {
        row.question_id: (row, 0.25, "mysql_keyword")
        for row in rows
        if row.question_id is not None
    }
    return _rank_candidates(candidates, hints, query_text, limit)


def _same_metadata_fallback(db: Session, question: Question, limit: int = 10) -> list[dict[str, Any]]:
    hints = {
        "categories": {question.knowledge_category} if question.knowledge_category else set(),
        "points": {question.knowledge_point} if question.knowledge_point else set(),
        "question_types": {question.question_type} if question.question_type else set(),
        "tokens": set(),
    }
    rows = _fetch_metadata_candidates(db, hints, limit=limit * 3, exclude_ids={question.question_id})
    candidates = {
        row.question_id: (row, 0.25, "mysql_metadata")
        for row in rows
        if row.question_id is not None
    }
    return _rank_candidates(candidates, hints, question.question_text or "", limit)


async def semantic_search_questions(db: Session, query_text: str, limit: int = 10) -> list[dict[str, Any]]:
    hints = _infer_query_hints(query_text)
    try:
        get_qdrant_client()
        vector = await embed_text(query_text)
        results = _query_qdrant(vector, max(30, min(80, limit * 8)))
        ids = [int(item.payload.get("question_id") or item.id) for item in results]
        questions = db.query(Question).filter(Question.question_id.in_(ids)).all()
        question_map = {question.question_id: question for question in questions}
        candidates: dict[int, tuple[Question, float, str]] = {}
        for hit in results:
            qid = int(hit.payload.get("question_id") or hit.id)
            if qid in question_map:
                candidates[qid] = (question_map[qid], float(hit.score or 0), "qdrant_hybrid")

        for row in _fetch_metadata_candidates(db, hints, limit=limit * 4, exclude_ids=set(candidates)):
            if row.question_id is not None:
                candidates.setdefault(row.question_id, (row, 0.2, "mysql_hybrid"))

        return _rank_candidates(candidates, hints, query_text, limit)
    except Exception:
        return _keyword_fallback(db, query_text, limit)


async def similar_questions(db: Session, question_id: int, limit: int = 10) -> list[dict[str, Any]]:
    question = db.query(Question).filter(Question.question_id == question_id).first()
    if not question:
        return []
    hints = {
        "categories": {question.knowledge_category} if question.knowledge_category else set(),
        "points": {question.knowledge_point} if question.knowledge_point else set(),
        "question_types": {question.question_type} if question.question_type else set(),
        "tokens": set(_tokens(f"{question.knowledge_point or ''} {question.knowledge_category or ''}")),
    }
    try:
        get_qdrant_client()
        vector = await embed_text(question.question_text or "")
        results = _query_qdrant(vector, max(30, min(80, limit * 8)))
        ids = [
            int(item.payload.get("question_id") or item.id)
            for item in results
            if int(item.payload.get("question_id") or item.id) != question_id
        ]
        questions = db.query(Question).filter(Question.question_id.in_(ids)).all()
        question_map = {item.question_id: item for item in questions}
        candidates: dict[int, tuple[Question, float, str]] = {}
        for hit in results:
            qid = int(hit.payload.get("question_id") or hit.id)
            if qid != question_id and qid in question_map:
                candidates[qid] = (question_map[qid], float(hit.score or 0), "qdrant_hybrid")

        for row in _fetch_metadata_candidates(db, hints, limit=limit * 4, exclude_ids={question_id, *candidates}):
            if row.question_id is not None:
                candidates.setdefault(row.question_id, (row, 0.2, "mysql_hybrid"))

        return _rank_candidates(candidates, hints, question.question_text or "", limit)
    except Exception:
        return _same_metadata_fallback(db, question, limit)


async def duplicate_check(db: Session, question_text: str, limit: int = 5) -> list[dict[str, Any]]:
    candidates = await semantic_search_questions(db, question_text, limit=max(limit, 8))
    for item in candidates:
        ratio = difflib.SequenceMatcher(None, question_text, item.get("question_text") or "").ratio()
        item["duplicate_score"] = round(ratio, 4)
    return sorted(
        candidates,
        key=lambda item: max(item.get("score", 0), item.get("duplicate_score", 0)),
        reverse=True,
    )[:limit]
