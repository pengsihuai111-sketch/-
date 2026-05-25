"""
向后兼容的配置文件 - 已弃用
请使用 app.core.config 代替

此文件保留用于向后兼容，所有配置已迁移到 app.core.config
"""
import warnings

warnings.warn(
    "app.config 已弃用，请使用 app.core.config 代替",
    DeprecationWarning,
    stacklevel=2
)

# 从新配置模块导入所有配置
from app.core.config import (
    DATABASE_CONFIG,
    DATABASE_URL,
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    JWT_EXPIRE_MINUTES,
    UPLOAD_DIR,
    IMAGE_DIR,
    PDF_DIR,
    DEEPSEEK_API_KEY,
    DEEPSEEK_API_URL,
    DEEPSEEK_MODEL,
    ZHIPU_API_KEY,
    ZHIPU_API_URL,
    ZHIPU_MODEL,
    DOUBAO_API_KEY,
    DOUBAO_API_URL,
    DOUBAO_MODEL,
    VISION_API_KEY,
    VISION_API_URL,
    VISION_MODEL,
    TEXT_LLM_PROVIDER,
)

__all__ = [
    "DATABASE_CONFIG",
    "DATABASE_URL",
    "JWT_SECRET_KEY",
    "JWT_ALGORITHM",
    "JWT_EXPIRE_MINUTES",
    "UPLOAD_DIR",
    "IMAGE_DIR",
    "PDF_DIR",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_API_URL",
    "DEEPSEEK_MODEL",
    "ZHIPU_API_KEY",
    "ZHIPU_API_URL",
    "ZHIPU_MODEL",
    "DOUBAO_API_KEY",
    "DOUBAO_API_URL",
    "DOUBAO_MODEL",
    "VISION_API_KEY",
    "VISION_API_URL",
    "VISION_MODEL",
    "TEXT_LLM_PROVIDER",
]
