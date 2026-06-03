from __future__ import annotations

import atexit
from functools import lru_cache
from typing import Any

from ..core.config import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    QDRANT_API_KEY,
    QDRANT_COLLECTION,
    QDRANT_LOCAL_PATH,
    QDRANT_TIMEOUT,
    QDRANT_URL,
)


class VectorUnavailable(RuntimeError):
    """Raised when Qdrant or vector dependencies are unavailable."""


@lru_cache(maxsize=1)
def get_qdrant_client() -> Any:
    try:
        from qdrant_client import QdrantClient
    except Exception as exc:
        raise VectorUnavailable("qdrant-client is not installed") from exc

    remote_error = None
    try:
        client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY or None,
            timeout=QDRANT_TIMEOUT,
            check_compatibility=False,
        )
        # Force a light request so we can fallback when the service is not running.
        client.get_collections()
        client._codex_vector_mode = "remote"
        return client
    except Exception as exc:
        remote_error = exc

    try:
        client = QdrantClient(path=QDRANT_LOCAL_PATH, check_compatibility=False)
        client._codex_vector_mode = "local"
        client._codex_remote_error = str(remote_error)
        return client
    except Exception as exc:
        raise VectorUnavailable(f"cannot create qdrant client: {exc}") from exc


def _extract_vector_size(collection_info: Any) -> int | None:
    """Return the collection vector size for unnamed or single-vector Qdrant configs."""
    try:
        vectors = collection_info.config.params.vectors
    except Exception:
        return None

    size = getattr(vectors, "size", None)
    if isinstance(size, int):
        return size

    if isinstance(vectors, dict):
        first_vector = next(iter(vectors.values()), None)
        size = getattr(first_vector, "size", None)
        return size if isinstance(size, int) else None

    return None


def ensure_question_collection(vector_size: int = EMBEDDING_DIM) -> None:
    try:
        from qdrant_client.models import Distance, VectorParams
    except Exception as exc:
        raise VectorUnavailable("qdrant-client models are unavailable") from exc

    client = get_qdrant_client()
    collections = client.get_collections().collections
    exists = any(item.name == QDRANT_COLLECTION for item in collections)
    if exists:
        info = client.get_collection(QDRANT_COLLECTION)
        existing_size = _extract_vector_size(info)
        if existing_size == vector_size:
            return
        if existing_size is not None and existing_size != vector_size:
            client.delete_collection(collection_name=QDRANT_COLLECTION)
        else:
            return
    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def _collection_details(client: Any) -> dict[str, Any]:
    try:
        info = client.get_collection(QDRANT_COLLECTION)
    except Exception:
        return {}
    return {
        "vector_size": _extract_vector_size(info),
        "points_count": getattr(info, "points_count", None),
        "vectors_count": getattr(info, "vectors_count", None),
    }


def recreate_question_collection(vector_size: int = EMBEDDING_DIM) -> None:
    try:
        from qdrant_client.models import Distance, VectorParams
    except Exception as exc:
        raise VectorUnavailable("qdrant-client models are unavailable") from exc

    client = get_qdrant_client()
    collections = client.get_collections().collections
    exists = any(item.name == QDRANT_COLLECTION for item in collections)
    if exists:
        client.delete_collection(collection_name=QDRANT_COLLECTION)
    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def clear_qdrant_client_cache() -> None:
    try:
        if get_qdrant_client.cache_info().currsize == 0:
            return
        client = get_qdrant_client()
        close = getattr(client, "close", None)
        if callable(close):
            close()
    except Exception:
        pass
    finally:
        get_qdrant_client.cache_clear()


atexit.register(clear_qdrant_client_cache)


def vector_status() -> dict[str, Any]:
    try:
        client = get_qdrant_client()
        collections = client.get_collections().collections
        collection_names = [item.name for item in collections]
        collection_exists = QDRANT_COLLECTION in collection_names
        details = _collection_details(client) if collection_exists else {}
        return {
            "available": True,
            "collection": QDRANT_COLLECTION,
            "collection_exists": collection_exists,
            "embedding_model": EMBEDDING_MODEL,
            "url": QDRANT_URL,
            "mode": getattr(client, "_codex_vector_mode", "remote"),
            "local_path": QDRANT_LOCAL_PATH if getattr(client, "_codex_vector_mode", "remote") == "local" else "",
            "remote_error": getattr(client, "_codex_remote_error", ""),
            **details,
        }
    except Exception as exc:
        return {
            "available": False,
            "collection": QDRANT_COLLECTION,
            "collection_exists": False,
            "embedding_model": EMBEDDING_MODEL,
            "url": QDRANT_URL,
            "error": str(exc),
        }
