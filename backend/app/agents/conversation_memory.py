from __future__ import annotations

import re
from typing import Any


_NAME_PATTERNS = [
    re.compile(r"(?:我叫|我的名字叫|我名字叫|我名叫)\s*([\u4e00-\u9fa5A-Za-z0-9_\-]{1,16})"),
    re.compile(r"^我是\s*([\u4e00-\u9fa5A-Za-z0-9_\-]{1,16})$"),
]

_BAD_NAME_WORDS = {
    "谁",
    "什么",
    "学生",
    "家长",
    "老师",
    "小学生",
    "六年级",
    "助手",
}


def _clean_name(value: str) -> str:
    name = re.split(r"[，,。.!！?？\s]", value or "", maxsplit=1)[0].strip()
    return name[:16]


def extract_user_name(text: str) -> str:
    """Extract a simple self-introduced user name from Chinese chat text."""
    raw = (text or "").strip()
    if not raw:
        return ""
    for pattern in _NAME_PATTERNS:
        match = pattern.search(raw)
        if not match:
            continue
        name = _clean_name(match.group(1))
        if name and name not in _BAD_NAME_WORDS and not any(word in name for word in _BAD_NAME_WORDS):
            return name
    return ""


def is_name_query(text: str) -> bool:
    compact = re.sub(r"\s+", "", text or "")
    return any(
        phrase in compact
        for phrase in (
            "我叫什么",
            "我的名字是什么",
            "我名字是什么",
            "你记得我叫什么",
            "你知道我叫什么",
            "我是谁",
        )
    )


def remembered_user_name(history: list[dict[str, Any]]) -> str:
    """Find the latest user name mentioned in recent session history."""
    for item in reversed(history or []):
        if item.get("role") != "user":
            continue
        name = extract_user_name(str(item.get("content") or ""))
        if name:
            return name
    return ""


def build_memory_reply(message: str, history: list[dict[str, Any]], args: dict[str, Any] | None = None) -> str:
    args = args or {}
    introduced_name = args.get("remembered_name") or extract_user_name(message)
    if introduced_name:
        return f"我记住啦，你叫{introduced_name}。以后这段对话里我会按这个名字称呼你。"

    if is_name_query(message):
        name = remembered_user_name(history)
        if name:
            return f"你叫{name}，我记得的。"
        return "我现在还没有记到你的名字。你可以直接说“我叫某某”，我就会在这段对话里记住。"

    return ""
