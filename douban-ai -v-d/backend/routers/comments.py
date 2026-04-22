from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend import models, schemas, dependencies

router = APIRouter()


@router.get("/posts/{post_id}/comments", response_model=list[schemas.CommentOut])
def list_comments(
    post_id: int,
    db: Session = Depends(get_db),
):
    comments = (
        db.query(models.Comment)
        .filter(models.Comment.post_id == post_id)
        .order_by(models.Comment.created_at.asc())
        .all()
    )
    return comments


@router.post("/posts/{post_id}/comments", response_model=schemas.CommentOut)
def create_comment(
    post_id: int,
    data: schemas.CommentCreate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if data.avatar_id:
        avatar = db.query(models.Avatar).filter(
            models.Avatar.id == data.avatar_id,
            models.Avatar.user_id == current_user.id,
        ).first()
        if not avatar:
            raise HTTPException(status_code=403, detail="Avatar not found")
    comment = models.Comment(
        post_id=post_id,
        author_id=current_user.id,
        avatar_id=data.avatar_id,
        parent_id=data.parent_id,
        content=data.content,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment
