"""
向后兼容的认证模块 - 已弃用
请使用 app.core.security 代替

此文件保留用于向后兼容，所有功能已迁移到 app.core.security
"""
import warnings

warnings.warn(
    "app.utils.auth 已弃用，请使用 app.core.security 代替",
    DeprecationWarning,
    stacklevel=2
)

# 从新模块导入所有功能
from ..core.security import (
    security,
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    get_current_user_id,
    get_current_username,
)

__all__ = [
    "security",
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "get_current_user_id",
    "get_current_username",
]
