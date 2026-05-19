"""
v3.0 JSON -> v4.0 MySQL data migration script
Usage: python migrate_v3_to_v4.py
"""
import json
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.database import SessionLocal, engine
from app.models import Base, Question


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def migrate():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    base_dir = os.path.join(os.path.dirname(__file__), "..", "..", "math_bank_v3")
    if not os.path.exists(base_dir):
        print("[ERROR] v3 directory not found:", base_dir)
        return

    master_path = os.path.join(base_dir, "index", "master_index.json")
    if not os.path.exists(master_path):
        print("[ERROR] master_index.json not found:", master_path)
        return

    master = load_json(master_path)
    print(f"[INFO] Master index: {len(master['questions'])} questions")

    # Load all shards
    shards_dir = os.path.join(base_dir, "questions")
    shard_data = {}
    for fname in os.listdir(shards_dir):
        if fname.endswith(".json"):
            shard_name = fname.replace(".json", "")
            shard_data[shard_name] = load_json(os.path.join(shards_dir, fname))

    count = 0
    seen_ids = set()
    for q_meta in master["questions"]:
        q_id = q_meta["q_id"]

        # Skip duplicate q_ids in source data
        if q_id in seen_ids:
            print(f"  [WARN] Skipping duplicate q_id: {q_id}")
            continue
        seen_ids.add(q_id)

        shard_name = q_meta.get("shard", "")

        # Find full content from shard
        full_content = None
        if shard_name in shard_data:
            for q in shard_data[shard_name].get("questions", []):
                if q["q_id"] == q_id:
                    full_content = q
                    break

        existing = db.query(Question).filter(Question.q_id == q_id).first()
        if existing:
            continue

        question = Question(
            q_id=q_id,
            knowledge_point=q_meta.get("knowledge_point", ""),
            knowledge_category=shard_name or None,
            question_type=_parse_qtype(q_meta.get("question_type")),
            difficulty=_parse_difficulty(q_meta.get("difficulty")),
            question_text=full_content.get("question_text", "") if full_content else "",
            answer=full_content.get("answer", "") if full_content else "",
            solution=full_content.get("solution", "") if full_content else "",
            has_image=bool(q_meta.get("has_image")),
            image_path=q_meta.get("image_path"),
            source_school=q_meta.get("source_school_full"),
            source_exam=q_meta.get("source_exam"),
            source_number=q_meta.get("source_number"),
            exam_year=q_meta.get("exam_year", "2025"),
            is_key_point=bool(q_meta.get("is_key_point")),
            is_difficult=bool(q_meta.get("is_difficult")),
            is_high_freq=bool(q_meta.get("is_high_freq")),
            verification_status=_parse_verify(q_meta.get("answer_status")),
            global_usage_count=q_meta.get("usage_count", 0),
        )
        db.add(question)
        count += 1

    db.commit()
    db.close()
    print(f"[INFO] Migration complete! {count} questions imported")


def _parse_qtype(t):
    mapping = {
        "fill_blank": "fill_blank",
        "choice": "choice",
        "problem_solving": "problem_solving",
        "calculation": "calculation",
    }
    return mapping.get(t)


def _parse_difficulty(d):
    mapping = {
        "基础": "基础",
        "中等": "中等",
        "挑战": "挑战",
    }
    return mapping.get(d, "中等")


def _parse_verify(s):
    mapping = {
        "verified": "verified",
        "ai_generated": "ai_generated",
        "needs_review": "needs_review",
        "pending": "pending",
    }
    return mapping.get(s, "pending")


if __name__ == "__main__":
    migrate()
