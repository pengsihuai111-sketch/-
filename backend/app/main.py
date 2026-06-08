from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import Request
from fastapi.responses import JSONResponse
import traceback
import logging
from sqlalchemy import inspect, text
from .api import assistant, auth, questions, wrong_questions, practice, practice_ai, payment
from .database import engine, Base
from .models import *  # noqa: ensure models registered
from .models import AgentInvocationLog, AssistantMessage, AssistantSession, VectorSyncJob
from .core.config import UploadConfig, CORSConfig

logger = logging.getLogger(__name__)

app = FastAPI(title="小升初数学题库管理系统 v4.0", version="4.0.0")

# 开发环境自动创建 AI 助手所需表；已有业务表仍由原迁移流程管理。
Base.metadata.create_all(bind=engine, tables=[
    AssistantSession.__table__,
    AssistantMessage.__table__,
    AgentInvocationLog.__table__,
    VectorSyncJob.__table__,
])


def _ensure_ai_assistant_columns() -> None:
    """Keep AI assistant helper columns compatible with older deployments."""
    try:
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("assistant_sessions")}
        statements = []
        if "context_json" not in columns:
            statements.append(
                "ALTER TABLE assistant_sessions ADD COLUMN context_json MEDIUMTEXT NULL"
                if engine.dialect.name == "mysql"
                else "ALTER TABLE assistant_sessions ADD COLUMN context_json TEXT"
            )
        if "session_type" not in columns:
            statements.append("ALTER TABLE assistant_sessions ADD COLUMN session_type VARCHAR(50) DEFAULT 'chat'")
        if "summary" not in columns:
            statements.append("ALTER TABLE assistant_sessions ADD COLUMN summary VARCHAR(200) NULL")
        if not statements:
            return
        with engine.begin() as conn:
            for ddl in statements:
                conn.execute(text(ddl))
    except Exception as exc:
        logger.warning("AI助手会话上下文字段检查失败: %s", exc)


_ensure_ai_assistant_columns()

# 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    print(f"========== 全局异常 ==========")
    print(f"路径: {request.url}")
    print(f"方法: {request.method}")
    print(f"异常: {exc}")
    print(f"堆栈: {traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"服务器内部错误: {str(exc)}"}
    )

# CORS - 从环境变量读取允许的源
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORSConfig.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务（上传的图片）
import os
os.makedirs(UploadConfig.BASE_DIR, exist_ok=True)
if os.path.exists(UploadConfig.BASE_DIR):
    app.mount("/uploads", StaticFiles(directory=UploadConfig.BASE_DIR), name="uploads")

# 注册路由
app.include_router(auth.router)
app.include_router(questions.router)
app.include_router(wrong_questions.router)
app.include_router(practice.router)
app.include_router(practice_ai.router)
app.include_router(assistant.router)
app.include_router(payment.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "4.0.0"}
