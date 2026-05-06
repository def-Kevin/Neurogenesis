import os
import shutil
import uuid
import json
from collections import Counter
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
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
    feed: str = Query("all"),
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    like_count_sub = (
        db.query(models.Like.post_id, func.count(models.Like.id).label("like_count"))
        .filter(models.Like.post_id.isnot(None))
        .group_by(models.Like.post_id)
        .subquery()
    )

    query = db.query(models.Post).options(
        joinedload(models.Post.author),
        joinedload(models.Post.avatar),
    )
    # Only show published posts in community
    query = query.filter(models.Post.status == "published")
    if tag:
        query = query.filter(models.Post.tags.like(f'"%{tag}%"'))
    if q:
        query = query.filter(
            models.Post.content.like(f"%{q}%") | models.Post.tags.like(f"%{q}%")
        )
    if feed == "following":
        following_ids = db.query(models.Follow.following_id).filter(
            models.Follow.follower_id == current_user.id
        ).subquery()
        query = query.filter(models.Post.author_id.in_(following_ids))
    if sort == "popular":
        query = query.outerjoin(like_count_sub, models.Post.id == like_count_sub.c.post_id)
        query = query.order_by(like_count_sub.c.like_count.desc().nullslast(), models.Post.created_at.desc())
    else:
        query = query.order_by(models.Post.created_at.desc())
    offset = (page - 1) * limit
    posts = query.offset(offset).limit(limit).all()
    result = []
    for post in posts:
        data = schemas.PostOut.model_validate(post).model_dump()
        data["like_count"] = db.query(func.count(models.Like.id)).filter(models.Like.post_id == post.id).scalar()
        data["comment_count"] = db.query(func.count(models.Comment.id)).filter(models.Comment.post_id == post.id).scalar()
        data["liked_by_me"] = db.query(models.Like).filter(
            models.Like.user_id == current_user.id,
            models.Like.post_id == post.id,
        ).first() is not None
        result.append(data)
    return result


@router.get("/{post_id}", response_model=schemas.PostOut)
def get_post(
    post_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    post = (
        db.query(models.Post)
        .options(joinedload(models.Post.author), joinedload(models.Post.avatar))
        .filter(models.Post.id == post_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    data = schemas.PostOut.model_validate(post).model_dump()
    data["like_count"] = db.query(func.count(models.Like.id)).filter(models.Like.post_id == post.id).scalar()
    data["comment_count"] = db.query(func.count(models.Comment.id)).filter(models.Comment.post_id == post.id).scalar()
    data["liked_by_me"] = db.query(models.Like).filter(
        models.Like.user_id == current_user.id,
        models.Like.post_id == post.id,
    ).first() is not None
    return data


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
        image_url=data.image_url,
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


@router.get("/tags/popular")
def popular_tags(
    db: Session = Depends(get_db),
):
    posts = db.query(models.Post).filter(models.Post.tags.isnot(None)).all()
    counter = Counter()
    for p in posts:
        try:
            tags = json.loads(p.tags)
            if isinstance(tags, list):
                counter.update(t for t in tags if isinstance(t, str))
        except Exception:
            pass
    return [{"tag": tag, "count": count} for tag, count in counter.most_common(20)]


@router.post("/upload-image")
def upload_image(
    file: UploadFile = File(...),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    upload_dir = os.path.join(os.path.dirname(__file__), "..", "static", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    ext = os.path.splitext(file.filename)[1] or ".png"
    allowed = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    if ext.lower() not in allowed:
        raise HTTPException(status_code=400, detail="不支持的图片格式")
    filename = f"post_{current_user.id}_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(upload_dir, filename)
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"image_url": f"/static/uploads/{filename}"}
