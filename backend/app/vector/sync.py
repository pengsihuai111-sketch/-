from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Question, VectorSyncAction, VectorSyncJob, VectorSyncStatus
from .indexer import delete_question_vector, upsert_question


def enqueue_question_sync(db: Session, question_id: int, action: str = VectorSyncAction.upsert.value) -> VectorSyncJob:
    job = VectorSyncJob(
        entity_type="question",
        entity_id=question_id,
        action=action,
        status=VectorSyncStatus.pending.value,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


async def process_pending_jobs(db: Session, limit: int = 50) -> dict:
    rows = (
        db.query(VectorSyncJob)
        .filter(VectorSyncJob.status == VectorSyncStatus.pending.value)
        .order_by(VectorSyncJob.created_at.asc())
        .limit(max(1, min(200, limit)))
        .all()
    )
    success = 0
    failed = 0
    for job in rows:
        job.status = VectorSyncStatus.processing.value
        db.commit()
        try:
            if job.action == VectorSyncAction.delete.value:
                delete_question_vector(job.entity_id)
            else:
                question = db.query(Question).filter(Question.question_id == job.entity_id).first()
                if question:
                    await upsert_question(question)
            job.status = VectorSyncStatus.success.value
            job.error_message = None
            success += 1
        except Exception as exc:
            job.status = VectorSyncStatus.failed.value
            job.error_message = str(exc)[:1000]
            failed += 1
        db.commit()
    return {"processed": len(rows), "success": success, "failed": failed}
