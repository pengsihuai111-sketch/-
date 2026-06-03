"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from typing import Optional


class ConfigError(Exception):
    """Configuration error."""


def _load_env_file() -> None:
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        ".env",
    )
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def _get_optional_env(key: str, default: str) -> str:
    return os.getenv(key, default)


_load_env_file()


class DatabaseConfig:
    HOST: str = _get_optional_env("DB_HOST", "localhost")
    PORT: int = int(_get_optional_env("DB_PORT", "3306"))
    USER: str = _get_optional_env("DB_USER", "root")
    PASSWORD: str = _get_optional_env("DB_PASSWORD", "123456")
    DATABASE: str = _get_optional_env("DB_NAME", "question_bank_v4")

    @classmethod
    def get_url(cls) -> str:
        return f"mysql+pymysql://{cls.USER}:{cls.PASSWORD}@{cls.HOST}:{cls.PORT}/{cls.DATABASE}?charset=utf8mb4"


DATABASE_URL = DatabaseConfig.get_url()


class JWTConfig:
    SECRET_KEY: str = _get_optional_env("JWT_SECRET", "question-bank-v4-jwt-secret-key-2026")
    ALGORITHM: str = "HS256"
    EXPIRE_MINUTES: int = 60 * 24 * 7


class UploadConfig:
    BASE_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        "uploads",
    )
    IMAGE_DIR: str = os.path.join(BASE_DIR, "images")
    PDF_DIR: str = os.path.join(BASE_DIR, "pdfs")


class AIConfig:
    DEEPSEEK_API_KEY: Optional[str] = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_API_URL: str = _get_optional_env("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions")
    DEEPSEEK_MODEL: str = _get_optional_env("DEEPSEEK_MODEL", "deepseek-chat")
    ANSWER_LLM_MODEL: str = _get_optional_env("ANSWER_LLM_MODEL", DEEPSEEK_MODEL)

    ZHIPU_API_KEY: Optional[str] = os.getenv("ZHIPU_API_KEY")
    ZHIPU_API_URL: str = _get_optional_env("ZHIPU_API_URL", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
    ZHIPU_MODEL: str = _get_optional_env("ZHIPU_MODEL", "glm-4-flash")

    VISION_API_KEY: Optional[str] = os.getenv("VISION_API_KEY")
    VISION_API_URL: str = _get_optional_env("VISION_API_URL", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
    VISION_MODEL: str = _get_optional_env("VISION_MODEL", "glm-4v-flash")

    TEXT_LLM_PROVIDER: str = _get_optional_env("TEXT_LLM_PROVIDER", "zhipu")
    EMBEDDING_API_KEY: Optional[str] = os.getenv("EMBEDDING_API_KEY") or os.getenv("ZHIPU_API_KEY")
    EMBEDDING_API_URL: str = _get_optional_env("EMBEDDING_API_URL", "https://open.bigmodel.cn/api/paas/v4/embeddings")
    EMBEDDING_MODEL: str = _get_optional_env("EMBEDDING_MODEL", "embedding-3")

    @classmethod
    def validate(cls) -> None:
        if cls.TEXT_LLM_PROVIDER == "deepseek" and not cls.DEEPSEEK_API_KEY:
            raise ConfigError("TEXT_LLM_PROVIDER is deepseek but DEEPSEEK_API_KEY is not configured")
        if cls.TEXT_LLM_PROVIDER == "zhipu" and not cls.ZHIPU_API_KEY:
            raise ConfigError("TEXT_LLM_PROVIDER is zhipu but ZHIPU_API_KEY is not configured")


class VectorConfig:
    QDRANT_URL: str = _get_optional_env("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: Optional[str] = os.getenv("QDRANT_API_KEY")
    QDRANT_COLLECTION: str = _get_optional_env("QDRANT_COLLECTION", "math_questions")
    QDRANT_TIMEOUT: float = float(_get_optional_env("QDRANT_TIMEOUT", "3.0"))
    EMBEDDING_DIM: int = int(_get_optional_env("EMBEDDING_DIM", "2048"))
    QDRANT_LOCAL_PATH: str = _get_optional_env(
        "QDRANT_LOCAL_PATH",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "storage", "qdrant"),
    )


class CORSConfig:
    ALLOWED_ORIGINS: list[str] = _get_optional_env(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174",
    ).split(",")


try:
    AIConfig.validate()
except ConfigError as e:
    print(f"配置警告: {e}")


DATABASE_CONFIG = {
    "host": DatabaseConfig.HOST,
    "port": DatabaseConfig.PORT,
    "user": DatabaseConfig.USER,
    "password": DatabaseConfig.PASSWORD,
    "database": DatabaseConfig.DATABASE,
}

JWT_SECRET_KEY = JWTConfig.SECRET_KEY
JWT_ALGORITHM = JWTConfig.ALGORITHM
JWT_EXPIRE_MINUTES = JWTConfig.EXPIRE_MINUTES

UPLOAD_DIR = UploadConfig.BASE_DIR
IMAGE_DIR = UploadConfig.IMAGE_DIR
PDF_DIR = UploadConfig.PDF_DIR

DEEPSEEK_API_KEY = AIConfig.DEEPSEEK_API_KEY or ""
DEEPSEEK_API_URL = AIConfig.DEEPSEEK_API_URL
DEEPSEEK_MODEL = AIConfig.DEEPSEEK_MODEL
ANSWER_LLM_MODEL = AIConfig.ANSWER_LLM_MODEL

ZHIPU_API_KEY = AIConfig.ZHIPU_API_KEY or ""
ZHIPU_API_URL = AIConfig.ZHIPU_API_URL
ZHIPU_MODEL = AIConfig.ZHIPU_MODEL

# Backward-compatible Doubao names now point to the configured Zhipu model.
DOUBAO_API_KEY = AIConfig.ZHIPU_API_KEY or ""
DOUBAO_API_URL = AIConfig.ZHIPU_API_URL
DOUBAO_MODEL = AIConfig.ZHIPU_MODEL

VISION_API_KEY = AIConfig.VISION_API_KEY or ""
VISION_API_URL = AIConfig.VISION_API_URL
VISION_MODEL = AIConfig.VISION_MODEL

TEXT_LLM_PROVIDER = AIConfig.TEXT_LLM_PROVIDER

EMBEDDING_API_KEY = AIConfig.EMBEDDING_API_KEY or ""
EMBEDDING_API_URL = AIConfig.EMBEDDING_API_URL
EMBEDDING_MODEL = AIConfig.EMBEDDING_MODEL

QDRANT_URL = VectorConfig.QDRANT_URL
QDRANT_API_KEY = VectorConfig.QDRANT_API_KEY or ""
QDRANT_COLLECTION = VectorConfig.QDRANT_COLLECTION
QDRANT_TIMEOUT = VectorConfig.QDRANT_TIMEOUT
EMBEDDING_DIM = VectorConfig.EMBEDDING_DIM
QDRANT_LOCAL_PATH = VectorConfig.QDRANT_LOCAL_PATH
