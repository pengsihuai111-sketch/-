from __future__ import annotations

import hashlib
from typing import Iterable, List

import httpx

from ..core.config import EMBEDDING_API_KEY, EMBEDDING_API_URL, EMBEDDING_DIM, EMBEDDING_MODEL
from .client import VectorUnavailable

_remote_embedding_disabled = False


def _normalize(vec: list[float]) -> list[float]:
    norm = sum(item * item for item in vec) ** 0.5
    if not norm:
        return vec
    return [item / norm for item in vec]


def local_hash_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Deterministic local embedding fallback.

    This is weaker than a real embedding model, but it still enables Qdrant
    vector retrieval when the paid embedding API is unavailable.
    """
    vector = [0.0] * dim
    normalized = (text or "").replace("\n", " ").strip()
    tokens = [item for item in normalized.split(" ") if item]
    compact = "".join(tokens) or normalized
    # Chinese math question text often has no spaces, so add char n-grams.
    for n in (2, 3, 4):
        tokens.extend(compact[i:i + n] for i in range(max(0, len(compact) - n + 1)))
    if not tokens:
        tokens = [text[:64] or "empty"]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    return _normalize(vector)


async def embed_texts(texts: Iterable[str]) -> List[list[float]]:
    global _remote_embedding_disabled
    items = [text or "" for text in texts]
    if not items:
        return []
    if not EMBEDDING_API_KEY or _remote_embedding_disabled:
        return [local_hash_embedding(text) for text in items]

    payload = {
        "model": EMBEDDING_MODEL,
        "input": items,
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=8.0)) as client:
        resp = await client.post(
            EMBEDDING_API_URL,
            headers={
                "Authorization": f"Bearer {EMBEDDING_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if resp.status_code != 200:
        _remote_embedding_disabled = True
        return [local_hash_embedding(text) for text in items]
    data = resp.json().get("data") or []
    vectors = [item.get("embedding") for item in sorted(data, key=lambda row: row.get("index", 0))]
    if len(vectors) != len(items) or any(not isinstance(vec, list) for vec in vectors):
        _remote_embedding_disabled = True
        return [local_hash_embedding(text) for text in items]
    return [_normalize([float(value) for value in vec]) for vec in vectors]


async def embed_text(text: str) -> list[float]:
    return (await embed_texts([text]))[0]
