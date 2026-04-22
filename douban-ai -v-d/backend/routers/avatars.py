from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend import models, schemas, dependencies
import json

router = APIRouter()


@router.get("", response_model=list[schemas.AvatarOut])
def list_avatars(
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(models.Avatar).filter(models.Avatar.user_id == current_user.id).all()


@router.get("/{avatar_id}", response_model=schemas.AvatarOut)
def get_avatar(
    avatar_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    avatar = db.query(models.Avatar).filter(
        models.Avatar.id == avatar_id,
        models.Avatar.user_id == current_user.id,
    ).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")
    return avatar


@router.post("", response_model=schemas.AvatarOut)
def create_avatar(
    data: schemas.AvatarCreate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    avatar = models.Avatar(
        user_id=current_user.id,
        name=data.name,
        persona_prompt=data.persona_prompt,
        interests=json.dumps(data.interests) if data.interests else None,
        writing_style=data.writing_style,
    )
    db.add(avatar)
    db.commit()
    db.refresh(avatar)
    return avatar


@router.put("/{avatar_id}", response_model=schemas.AvatarOut)
def update_avatar(
    avatar_id: int,
    data: schemas.AvatarUpdate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    avatar = db.query(models.Avatar).filter(
        models.Avatar.id == avatar_id,
        models.Avatar.user_id == current_user.id,
    ).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")
    if data.name is not None:
        avatar.name = data.name
    if data.persona_prompt is not None:
        avatar.persona_prompt = data.persona_prompt
    if data.interests is not None:
        avatar.interests = json.dumps(data.interests)
    if data.writing_style is not None:
        avatar.writing_style = data.writing_style
    db.commit()
    db.refresh(avatar)
    return avatar


@router.delete("/{avatar_id}")
def delete_avatar(
    avatar_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    avatar = db.query(models.Avatar).filter(
        models.Avatar.id == avatar_id,
        models.Avatar.user_id == current_user.id,
    ).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")
    db.delete(avatar)
    db.commit()
    return {"success": True}


@router.get("/explore/list", response_model=list[schemas.AvatarOut])
def explore_avatars(
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.Avatar)
        .filter(models.Avatar.user_id != current_user.id)
        .limit(20)
        .all()
    )
