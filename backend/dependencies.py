from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend import models


def get_current_user(request: Request, db: Session = Depends(get_db)):
    session_token = request.cookies.get("session_id")
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = db.query(models.Session).filter(models.Session.session_token == session_token).first()
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    user = db.query(models.User).filter(models.User.id == session.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
