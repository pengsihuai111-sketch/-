from __future__ import annotations

from typing import Iterable, List

from sqlalchemy.orm import Session

from ..core.config import QDRANT_COLLECTION
from ..models import Question
from .client import ensure_question_collection, get_qdrant_client
from .embedding import embed_texts


def question_to_vector_text(question: Question) -> str:
    """Build a retrieval document that emphasizes math metadata before the raw stem."""
    parts = [
        f"知识点：{question.knowledge_point or ''}",
        f"知识类别：{question.knowledge_category or ''}",
        f"题型：{question.question_type or ''}",
        f"难度：{question.difficulty or ''}",
        f"题干：{question.question_text or ''}",
        f"答案：{question.answer or ''}",
        f"解析：{question.solution or ''}",
        f"年级：{question.grade_level or ''}",
    ]
    return "\n".join(parts)


def question_payload(question: Question) -> dict:
    return {
        "question_id": question.question_id,
        "q_id": question.q_id,
        "knowledge_point": question.knowledge_point,
        "knowledge_category": question.knowledge_category,
        "question_type": question.question_type,
        "difficulty": question.difficulty,
        "grade_level": question.grade_level,
        "has_image": bool(question.has_image),
        "source_exam": question.source_exam,
        "question_text": (question.question_text or "")[:500],
    }


async def upsert_questions(questions: Iterable[Question]) -> int:
    items = [question for question in questions if question and question.question_id]
    if not items:
        return 0
    vectors = await embed_texts([question_to_vector_text(question) for question in items])
    if not vectors:
        return 0
    ensure_question_collection(len(vectors[0]))
    client = get_qdrant_client()
    from qdrant_client.models import PointStruct

    client.upsert(
        collection_name=QDRANT_COLLECTION,
        points=[
            PointStruct(
                id=int(question.question_id),
                vector=vector,
                payload=question_payload(question),
            )
            for question, vector in zip(items, vectors)
        ],
    )
    return len(items)


async def upsert_question(question: Question) -> int:
    return await upsert_questions([question])


def delete_question_vector(question_id: int) -> None:
    from qdrant_client.models import PointIdsList

    client = get_qdrant_client()
    client.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=PointIdsList(points=[int(question_id)]),
    )


async def sync_all_questions(db: Session, limit: int | None = None, offset: int = 0) -> dict:
    query = db.query(Question).order_by(Question.question_id.asc()).offset(max(0, offset))
    if limit:
        query = query.limit(max(1, min(5000, limit)))
    questions: List[Question] = query.all()
    count = 0
    batch_size = 24
    for start in range(0, len(questions), batch_size):
        count += await upsert_questions(questions[start:start + batch_size])
    return {"synced": count, "offset": offset, "limit": limit}
