"""应用配置管理 - 使用环境变量，无硬编码密钥"""
import os
from typing import Optional


class ConfigError(Exception):
    """配置错误异常"""
    pass


def _load_env_file():
    """加载.env文件到环境变量"""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


def _get_required_env(key: str) -> str:
    """获取必需的环境变量，缺失时抛出异常"""
    value = os.getenv(key)
    if not value:
        raise ConfigError(
            f"必需的环境变量 {key} 未设置。"
            f"请在 backend/.env 文件中配置，或参考 backend/.env.example"
        )
    return value


def _get_optional_env(key: str, default: str) -> str:
    """获取可选的环境变量"""
    return os.getenv(key, default)


# 加载.env文件
_load_env_file()


# 数据库配置
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


# JWT配置
class JWTConfig:
    SECRET_KEY: str = _get_optional_env("JWT_SECRET", "question-bank-v4-jwt-secret-key-2026")
    ALGORITHM: str = "HS256"
    EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天


# 文件上传配置
class UploadConfig:
    BASE_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        "uploads"
    )
    IMAGE_DIR: str = os.path.join(BASE_DIR, "images")
    PDF_DIR: str = os.path.join(BASE_DIR, "pdfs")


# AI模型配置
class AIConfig:
    # DeepSeek配置（备选文本模型）
    DEEPSEEK_API_KEY: Optional[str] = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_API_URL: str = _get_optional_env("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions")
    DEEPSEEK_MODEL: str = _get_optional_env("DEEPSEEK_MODEL", "deepseek-chat")

    # Doubao配置（主要文本模型）
    DOUBAO_API_KEY: str = _get_required_env("DOUBAO_API_KEY")
    DOUBAO_API_URL: str = _get_optional_env("DOUBAO_API_URL", "https://api.newcoin.tech/v1/chat/completions")
    DOUBAO_MODEL: str = _get_optional_env("DOUBAO_MODEL", "doubao-seed-1-6-251015")

    # Vision模型配置
    VISION_API_KEY: str = _get_required_env("VISION_API_KEY")
    VISION_API_URL: str = _get_optional_env("VISION_API_URL", "https://api.newcoin.tech/v1/chat/completions")
    VISION_MODEL: str = _get_optional_env("VISION_MODEL", "doubao-seed-1-6-vision-250815")

    # 文本模型提供商选择
    TEXT_LLM_PROVIDER: str = _get_optional_env("TEXT_LLM_PROVIDER", "doubao")

    @classmethod
    def validate(cls):
        """验证AI配置完整性"""
        if cls.TEXT_LLM_PROVIDER == "deepseek" and not cls.DEEPSEEK_API_KEY:
            raise ConfigError("TEXT_LLM_PROVIDER设置为deepseek，但DEEPSEEK_API_KEY未配置")


# CORS配置
class CORSConfig:
    ALLOWED_ORIGINS: list[str] = _get_optional_env(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174"
    ).split(",")


# 验证配置
try:
    AIConfig.validate()
except ConfigError as e:
    print(f"⚠️  配置警告: {e}")


# 向后兼容：导出旧的变量名
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

DOUBAO_API_KEY = AIConfig.DOUBAO_API_KEY
DOUBAO_API_URL = AIConfig.DOUBAO_API_URL
DOUBAO_MODEL = AIConfig.DOUBAO_MODEL

VISION_API_KEY = AIConfig.VISION_API_KEY
VISION_API_URL = AIConfig.VISION_API_URL
VISION_MODEL = AIConfig.VISION_MODEL

TEXT_LLM_PROVIDER = AIConfig.TEXT_LLM_PROVIDER
