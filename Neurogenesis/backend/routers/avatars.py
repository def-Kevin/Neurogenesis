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
        auto_post_enabled=data.auto_post_enabled or 0,
        auto_post_interval_hours=data.auto_post_interval_hours or 24,
        energy=data.energy if data.energy is not None else 80,
        mood=data.mood,
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
    if data.auto_post_enabled is not None:
        avatar.auto_post_enabled = data.auto_post_enabled
    if data.auto_post_interval_hours is not None:
        avatar.auto_post_interval_hours = data.auto_post_interval_hours
    if data.energy is not None:
        avatar.energy = max(0, min(100, data.energy))
    if data.mood is not None:
        avatar.mood = data.mood
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
    recommend: bool = False,
    avatar_id: int = None,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    if recommend and avatar_id:
        from backend.services.avatar_autonomy import discover_avatars
        avatar = db.query(models.Avatar).filter(
            models.Avatar.id == avatar_id,
            models.Avatar.user_id == current_user.id,
        ).first()
        if avatar:
            results = discover_avatars(avatar, db)
            return [r["avatar"] for r in results]
    return (
        db.query(models.Avatar)
        .filter(models.Avatar.user_id != current_user.id)
        .limit(20)
        .all()
    )


@router.get("/{avatar_id}/relationships", response_model=list[schemas.AvatarRelationshipOut])
def list_relationships(
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
    return (
        db.query(models.AvatarRelationship)
        .filter(models.AvatarRelationship.source_avatar_id == avatar_id)
        .order_by(models.AvatarRelationship.relationship_score.desc())
        .all()
    )


@router.get("/{avatar_id}/memories", response_model=list[schemas.AvatarMemoryOut])
def list_memories(
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
    return (
        db.query(models.AvatarMemory)
        .filter(models.AvatarMemory.avatar_id == avatar_id)
        .order_by(models.AvatarMemory.created_at.desc())
        .all()
    )


@router.get("/{avatar_id}/growth", response_model=list[schemas.AvatarGrowthLogOut])
def list_growth(
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
    return (
        db.query(models.AvatarGrowthLog)
        .filter(models.AvatarGrowthLog.avatar_id == avatar_id)
        .order_by(models.AvatarGrowthLog.created_at.desc())
        .all()
    )


@router.delete("/{avatar_id}/memories/{memory_id}")
def delete_memory(
    avatar_id: int,
    memory_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    avatar = db.query(models.Avatar).filter(
        models.Avatar.id == avatar_id,
        models.Avatar.user_id == current_user.id,
    ).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")
    mem = db.query(models.AvatarMemory).filter(
        models.AvatarMemory.id == memory_id,
        models.AvatarMemory.avatar_id == avatar_id,
    ).first()
    if not mem:
        raise HTTPException(status_code=404, detail="Memory not found")
    db.delete(mem)
    db.commit()
    return {"success": True}


@router.get("/{avatar_id}/pending-posts", response_model=list[schemas.PostOut])
def list_pending_posts(
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
    posts = (
        db.query(models.Post)
        .options(joinedload(models.Post.author), joinedload(models.Post.avatar))
        .filter(models.Post.avatar_id == avatar_id, models.Post.status == "pending")
        .order_by(models.Post.created_at.desc())
        .all()
    )
    result = []
    for post in posts:
        data = schemas.PostOut.model_validate(post).model_dump()
        data["like_count"] = db.query(func.count(models.Like.id)).filter(models.Like.post_id == post.id).scalar()
        data["liked_by_me"] = db.query(models.Like).filter(
            models.Like.user_id == current_user.id,
            models.Like.post_id == post.id,
        ).first() is not None
        result.append(data)
    return result


@router.post("/posts/{post_id}/publish")
def publish_pending_post(
    post_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post or post.author_id != current_user.id:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status != "pending":
        raise HTTPException(status_code=400, detail="Post is not pending")
    post.status = "published"
    db.commit()
    return {"success": True}


@router.delete("/posts/{post_id}")
def delete_avatar_post(
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
