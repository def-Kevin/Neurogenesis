from fastapi import APIRouter, Depends, HTTPException, Response, Request, UploadFile, File
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from backend.database import get_db
from backend import models, schemas, dependencies
import uuid
import os
import shutil
from datetime import datetime, timedelta, timezone
from backend.config import settings

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


@router.post("/register", response_model=schemas.UserOut)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.username == user_in.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    user = models.User(
        username=user_in.username,
        password_hash=hash_password(user_in.password),
        nickname=user_in.nickname or user_in.username,
    )
    db.add(user)
    db.flush()

    # create default avatar
    avatar = models.Avatar(
        user_id=user.id,
        name=f"{user.nickname}的分身",
        persona_prompt="你是一位热爱文艺的AI分身，喜欢电影、音乐和书籍，乐于分享和交流。",
        interests='["电影","音乐","书籍"]',
        writing_style="温暖、真诚、有见地",
    )
    db.add(avatar)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login")
def login(response: Response, creds: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == creds.username).first()
    if not user or not verify_password(creds.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid username or password")
    token = str(uuid.uuid4())
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.session_expire_hours)
    session = models.Session(user_id=user.id, session_token=token, expires_at=expires)
    db.add(session)
    db.commit()
    response.set_cookie(key=settings.session_cookie_name, value=token, httponly=True, samesite="lax")
    return {"user": schemas.UserOut.model_validate(user), "session_token": token}


@router.post("/logout")
def logout(response: Response, request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        db.query(models.Session).filter(models.Session.session_token == token).delete()
        db.commit()
    response.delete_cookie(key=settings.session_cookie_name)
    return {"success": True}


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(dependencies.get_current_user)):
    return current_user


@router.put("/me", response_model=schemas.UserOut)
def update_me(
    data: schemas.UserUpdate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    if data.nickname is not None:
        current_user.nickname = data.nickname
    if data.avatar_url is not None:
        current_user.avatar_url = data.avatar_url
    if data.new_password:
        if not data.current_password:
            raise HTTPException(status_code=400, detail="需要提供当前密码")
        if not verify_password(data.current_password, current_user.password_hash):
            raise HTTPException(status_code=400, detail="当前密码不正确")
        current_user.password_hash = hash_password(data.new_password)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/upload-avatar")
def upload_avatar(
    file: UploadFile = File(...),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    upload_dir = os.path.join(os.path.dirname(__file__), "..", "static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    ext = os.path.splitext(file.filename)[1] or ".png"
    filename = f"avatar_{current_user.id}_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(upload_dir, filename)
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"avatar_url": f"/static/uploads/{filename}"}
