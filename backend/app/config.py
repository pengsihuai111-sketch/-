import os

# Load .env file if present
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_env_path):
    with open(_env_path, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

DATABASE_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "123456"),
    "database": os.getenv("DB_NAME", "question_bank_v4"),
}

DATABASE_URL = f"mysql+pymysql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}?charset=utf8mb4"

JWT_SECRET_KEY = os.getenv("JWT_SECRET", "question-bank-v4-jwt-secret-key-2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
IMAGE_DIR = os.path.join(UPLOAD_DIR, "images")
PDF_DIR = os.path.join(UPLOAD_DIR, "pdfs")

# DeepSeek — 备选文本模型（当 TEXT_LLM_PROVIDER=deepseek 时使用）
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# Unified OpenAI-compatible text endpoint. In this workspace the .env maps these
# fields to Zhipu GLM models, so the code path stays simple while the model stays single-source.
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "")
DOUBAO_API_URL = os.getenv("DOUBAO_API_URL", "https://api.newcoin.tech/v1/chat/completions")
DOUBAO_MODEL = os.getenv("DOUBAO_MODEL", "doubao-seed-1-6-251015")

# 文本模型选择: 当前默认走统一配置字段；本地 .env 已配置为智谱 GLM。
TEXT_LLM_PROVIDER = os.getenv("TEXT_LLM_PROVIDER", "doubao")

# Vision/OCR API config — 本地 .env 已配置为智谱视觉模型。
VISION_API_KEY = os.getenv("VISION_API_KEY", "")
VISION_API_URL = os.getenv("VISION_API_URL", "https://api.newcoin.tech/v1/chat/completions")
VISION_MODEL = os.getenv("VISION_MODEL", "doubao-seed-1-6-vision-250815")
