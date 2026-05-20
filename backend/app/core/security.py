"""安全工具模块 - 密码哈希和JWT令牌管理"""
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .config import JWTConfig

security = HTTPBearer()


def hash_password(password: str) -> str:
    """使用bcrypt哈希密码"""
    # bcrypt限制密码长度为72字节
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]

    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed: str) -> bool:
    """
    验证密码，支持新旧两种格式：
    - 新格式：bcrypt哈希（以$2b$开头）
    - 旧格式：SHA-256+salt（格式：salt$hash）
    """
    # 检查是否是bcrypt格式
    if hashed.startswith("$2b$") or hashed.startswith("$2a$") or hashed.startswith("$2y$"):
        # 新格式：使用bcrypt验证
        try:
            password_bytes = plain_password.encode('utf-8')
            if len(password_bytes) > 72:
                password_bytes = password_bytes[:72]
            return bcrypt.checkpw(password_bytes, hashed.encode('utf-8'))
        except (ValueError, AttributeError):
            return False

    # 旧格式：使用SHA-256验证（向后兼容）
    try:
        if "$" in hashed:
            salt, h = hashed.split("$", 1)
            computed_hash = hashlib.sha256((salt + plain_password).encode()).hexdigest()
            return computed_hash == h
        return False
    except (ValueError, AttributeError):
        return False


def needs_rehash(hashed: str) -> bool:
    """检查密码是否需要重新哈希（从旧格式升级到bcrypt）"""
    # 如果不是bcrypt格式，需要重新哈希
    return not (hashed.startswith("$2b$") or hashed.startswith("$2a$") or hashed.startswith("$2y$"))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建JWT访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=JWTConfig.EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWTConfig.SECRET_KEY, algorithm=JWTConfig.ALGORITHM)


def decode_access_token(token: str) -> dict:
    """解码JWT令牌"""
    try:
        return jwt.decode(token, JWTConfig.SECRET_KEY, algorithms=[JWTConfig.ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的登录令牌"
        )


def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    """从JWT令牌获取当前用户ID"""
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的登录令牌"
        )
    return int(user_id)


def get_current_username(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """从JWT令牌获取当前用户名"""
    payload = decode_access_token(credentials.credentials)
    username = payload.get("username")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的登录令牌"
        )
    return username
