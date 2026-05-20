from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from ..database import get_db
from ..models import User, MemberType, UserStatus
from ..schemas import UserRegister, UserLogin, LoginResponse, UserProfile
from ..core.security import hash_password, verify_password, create_access_token, get_current_user_id, needs_rehash

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register")
def register(req: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    if req.email:
        email_exist = db.query(User).filter(User.email == req.email).first()
        if email_exist:
            raise HTTPException(status_code=400, detail="邮箱已被注册")

    # 将空字符串转为 None，避免 UNIQUE KEY 冲突
    email = req.email if req.email else None
    phone = req.phone if req.phone else None

    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        email=email,
        phone=phone,
        real_name=req.real_name,
        grade_level=req.grade_level,
        member_type=MemberType.free,
        status=UserStatus.active,
        register_date=datetime.now(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"user_id": user.user_id, "username": user.username})
    return LoginResponse(
        access_token=token, user=UserProfile.model_validate(user)
    )


@router.post("/login")
def login(req: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if user.status == UserStatus.suspended:
        raise HTTPException(status_code=403, detail="账号已被停用")

    # 自动升级旧密码格式到bcrypt
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(req.password)

    user.last_login = datetime.now()
    db.commit()

    token = create_access_token({"user_id": user.user_id, "username": user.username})
    return LoginResponse(
        access_token=token, user=UserProfile.model_validate(user)
    )


@router.get("/profile")
def get_profile(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserProfile.model_validate(user)
