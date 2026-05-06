from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from backend.database import get_db
from backend import models, schemas, dependencies
from sqlalchemy import func

router = APIRouter()


@router.get("/posts/{post_id}/comments", response_model=list[schemas.CommentOut])
def list_comments(
    post_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    comments = (
        db.query(models.Comment)
        .options(joinedload(models.Comment.author), joinedload(models.Comment.avatar))
        .filter(models.Comment.post_id == post_id)
        .order_by(models.Comment.created_at.asc())
        .all()
    )
    result = []
    for c in comments:
        data = schemas.CommentOut.model_validate(c).model_dump()
        data["like_count"] = db.query(func.count(models.Like.id)).filter(models.Like.comment_id == c.id).scalar()
        data["liked_by_me"] = db.query(models.Like).filter(
            models.Like.user_id == current_user.id,
            models.Like.comment_id == c.id,
        ).first() is not None
        result.append(data)
    return result


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

    # Update avatar relationship if both source and target are avatars
    if data.avatar_id and post.avatar_id:
        from backend.services.avatar_autonomy import _update_relationship_on_interaction
        _update_relationship_on_interaction(
            data.avatar_id, post.avatar_id, "comment_on_post", db
        )

    return comment


@router.post("/comments/{comment_id}/like")
def like_comment(
    comment_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    existing = db.query(models.Like).filter(
        models.Like.user_id == current_user.id,
        models.Like.comment_id == comment_id,
    ).first()
    if existing:
        db.delete(existing)
        db.commit()
        liked = False
    else:
        db.add(models.Like(user_id=current_user.id, comment_id=comment_id))
        db.commit()
        liked = True
    count = db.query(func.count(models.Like.id)).filter(models.Like.comment_id == comment_id).scalar()
    return {"liked": liked, "like_count": count}
