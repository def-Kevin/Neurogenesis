from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from backend.database import get_db
from backend import models, schemas, dependencies

router = APIRouter()


@router.get("", response_model=list[schemas.PostOut])
def list_posts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    tag: Optional[str] = None,
    q: Optional[str] = None,
    sort: str = Query("newest"),
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(models.Post)
    if tag:
        query = query.filter(models.Post.tags.like(f"%{tag}%"))
    if q:
        query = query.filter(
            models.Post.content.like(f"%{q}%") | models.Post.tags.like(f"%{q}%")
        )
    if sort == "newest":
        query = query.order_by(models.Post.created_at.desc())
    else:
        query = query.order_by(models.Post.created_at.desc())
    offset = (page - 1) * limit
    return query.offset(offset).limit(limit).all()


@router.get("/{post_id}", response_model=schemas.PostOut)
def get_post(
    post_id: int,
    db: Session = Depends(get_db),
):
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.post("", response_model=schemas.PostOut)
def create_post(
    data: schemas.PostCreate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    if data.avatar_id:
        avatar = db.query(models.Avatar).filter(
            models.Avatar.id == data.avatar_id,
            models.Avatar.user_id == current_user.id,
        ).first()
        if not avatar:
            raise HTTPException(status_code=403, detail="Avatar not found")
    post = models.Post(
        author_id=current_user.id,
        avatar_id=data.avatar_id,
        title=data.title,
        content=data.content,
        tags=json.dumps(data.tags) if data.tags else None,
        mood=data.mood,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@router.delete("/{post_id}")
def delete_post(
    post_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post or post.author_id != current_user.id:
        raise HTTPException(status_code=404, detail="Post not found")
    db.delete(post)
    db.commit()
    return {"success": True}


@router.post("/{post_id}/like")
def like_post(
    post_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    existing = db.query(models.Like).filter(
        models.Like.user_id == current_user.id,
        models.Like.post_id == post_id,
    ).first()
    if existing:
        db.delete(existing)
        db.commit()
        liked = False
    else:
        db.add(models.Like(user_id=current_user.id, post_id=post_id))
        db.commit()
        liked = True
    count = db.query(func.count(models.Like.id)).filter(models.Like.post_id == post_id).scalar()
    return {"liked": liked, "like_count": count}


import json
