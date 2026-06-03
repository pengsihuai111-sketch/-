from typing import Any, Dict


def safe_tool_args(args: Dict[str, Any] | None) -> Dict[str, Any]:
    """Drop fields that tools must never trust from LLM/user payloads."""
    cleaned = dict(args or {})
    cleaned.pop("user_id", None)
    cleaned.pop("sql", None)
    cleaned.pop("raw_sql", None)
    return cleaned

