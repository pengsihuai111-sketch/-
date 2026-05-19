from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import Request
from fastapi.responses import JSONResponse
import traceback
import logging
from .api import auth, questions, wrong_questions, practice, payment
from .database import engine, Base
from .models import *  # noqa: ensure models registered
from .config import UPLOAD_DIR

logger = logging.getLogger(__name__)

app = FastAPI(title="小升初数学题库管理系统 v4.0", version="4.0.0")

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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务（上传的图片）
import os
os.makedirs(UPLOAD_DIR, exist_ok=True)
if os.path.exists(UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# 注册路由
app.include_router(auth.router)
app.include_router(questions.router)
app.include_router(wrong_questions.router)
app.include_router(practice.router)
app.include_router(payment.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "4.0.0"}
