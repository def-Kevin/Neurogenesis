from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.database import get_db
from backend import models, schemas, dependencies
from backend.services.avatar_autonomy import _get_or_create_relationship
from datetime import datetime

router = APIRouter()


@router.post("", response_model=schemas.FollowOut)
def follow_user(
    data: schemas.FollowCreate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    if data.following_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")
    target = db.query(models.User).filter(models.User.id == data.following_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    existing = db.query(models.Follow).filter(
        models.Follow.follower_id == current_user.id,
        models.Follow.following_id == data.following_id,
    ).first()
    if existing:
        return existing
    follow = models.Follow(follower_id=current_user.id, following_id=data.following_id)
    db.add(follow)
    db.commit()
    db.refresh(follow)

    # If mutual follow exists, bridge avatar relationships
    mutual = db.query(models.Follow).filter(
        models.Follow.follower_id == data.following_id,
        models.Follow.following_id == current_user.id,
    ).first()
    if mutual:
        avatar_a = db.query(models.Avatar).filter(models.Avatar.user_id == current_user.id).first()
        avatar_b = db.query(models.Avatar).filter(models.Avatar.user_id == data.following_id).first()
        if avatar_a and avatar_b:
            rel_ab = _get_or_create_relationship(avatar_a.id, avatar_b.id, db)
            rel_ba = _get_or_create_relationship(avatar_b.id, avatar_a.id, db)
            if rel_ab.relationship_score < 20:
                rel_ab.relationship_score = 20
                rel_ab.relationship_type = "acquaintance"
                rel_ab.last_interaction_at = datetime.now()
            if rel_ba.relationship_score < 20:
                rel_ba.relationship_score = 20
                rel_ba.relationship_type = "acquaintance"
                rel_ba.last_interaction_at = datetime.now()
            db.commit()

    return follow


@router.delete("/{user_id}")
def unfollow_user(
    user_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    follow = db.query(models.Follow).filter(
        models.Follow.follower_id == current_user.id,
        models.Follow.following_id == user_id,
    ).first()
    if not follow:
        raise HTTPException(status_code=404, detail="Not following")
    db.delete(follow)
    db.commit()
    return {"success": True}


@router.get("/followers/{user_id}", response_model=list[schemas.UserProfileOut])
def list_followers(
    user_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    follows = db.query(models.Follow).filter(models.Follow.following_id == user_id).all()
    result = []
    for f in follows:
        user = db.query(models.User).filter(models.User.id == f.follower_id).first()
        if user:
            data = schemas.UserProfileOut.model_validate(user).model_dump()
            data["follower_count"] = db.query(func.count(models.Follow.id)).filter(
                models.Follow.following_id == user.id
            ).scalar()
            data["following_count"] = db.query(func.count(models.Follow.id)).filter(
                models.Follow.follower_id == user.id
            ).scalar()
            data["is_followed_by_me"] = db.query(models.Follow).filter(
                models.Follow.follower_id == current_user.id,
                models.Follow.following_id == user.id,
            ).first() is not None
            result.append(data)
    return result


@router.get("/following/{user_id}", response_model=list[schemas.UserProfileOut])
def list_following(
    user_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    follows = db.query(models.Follow).filter(models.Follow.follower_id == user_id).all()
    result = []
    for f in follows:
        user = db.query(models.User).filter(models.User.id == f.following_id).first()
        if user:
            data = schemas.UserProfileOut.model_validate(user).model_dump()
            data["follower_count"] = db.query(func.count(models.Follow.id)).filter(
                models.Follow.following_id == user.id
            ).scalar()
            data["following_count"] = db.query(func.count(models.Follow.id)).filter(
                models.Follow.follower_id == user.id
            ).scalar()
            data["is_followed_by_me"] = True
            result.append(data)
    return result


@router.get("/is-following/{user_id}")
def is_following(
    user_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    follow = db.query(models.Follow).filter(
        models.Follow.follower_id == current_user.id,
        models.Follow.following_id == user_id,
    ).first()
    return {"following": follow is not None}
