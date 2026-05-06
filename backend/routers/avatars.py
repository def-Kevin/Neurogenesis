from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
import os
import threading
from sqlalchemy.orm import Session
from backend.database import get_db
from backend import models, schemas, dependencies
from backend.services import openclaw_config, openclaw_cli
from backend.services.channel_bridge import handle_feishu_message, handle_wechat_message
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from pydantic import BaseModel
import json

router = APIRouter()


class SkillToggle(BaseModel):
    enabled: int



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


@router.get("/public/{avatar_id}", response_model=schemas.AvatarPublicOut)
def get_public_avatar(
    avatar_id: int,
    db: Session = Depends(get_db),
):
    avatar = db.query(models.Avatar).filter(models.Avatar.id == avatar_id).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")
    return avatar


@router.post("", response_model=schemas.AvatarOut)
def create_avatar(
    data: schemas.AvatarCreate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.query(models.Avatar).filter(models.Avatar.user_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="每位用户只能拥有一个分身")
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
    # Pre-populate default OpenClaw skills
    for skill_name in ["neurogenesis-posting", "neurogenesis-interaction", "neurogenesis-memory"]:
        db.add(models.AvatarSkill(avatar_id=avatar.id, skill_name=skill_name))
    db.commit()
    try:
        workspace_dir = openclaw_config.write_agent_markdown(avatar)
        openclaw_cli.agent_add(avatar.id, workspace_dir)
    except Exception as e:
        print(f"[OpenClaw] create avatar sync failed: {e}")
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
    try:
        openclaw_config.write_agent_markdown(avatar)
        openclaw_cli.agent_sync(avatar.id)
    except Exception as e:
        print(f"[OpenClaw] update avatar sync failed: {e}")
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
    try:
        openclaw_config.remove_agent_markdown(avatar_id)
        openclaw_cli.agent_delete(avatar_id)
    except Exception as e:
        print(f"[OpenClaw] delete avatar sync failed: {e}")
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


# --- Skills ---

@router.get("/{avatar_id}/skills", response_model=list[schemas.AvatarSkillOut])
def list_skills(
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
    return db.query(models.AvatarSkill).filter(models.AvatarSkill.avatar_id == avatar_id).all()


@router.post("/{avatar_id}/skills", response_model=schemas.AvatarSkillOut)
def install_skill(
    avatar_id: int,
    data: schemas.AvatarSkillCreate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    avatar = db.query(models.Avatar).filter(
        models.Avatar.id == avatar_id,
        models.Avatar.user_id == current_user.id,
    ).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")
    skill = models.AvatarSkill(avatar_id=avatar_id, skill_name=data.skill_name)
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


@router.put("/{avatar_id}/skills/{skill_id}")
def toggle_skill(
    avatar_id: int,
    skill_id: int,
    data: SkillToggle,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    avatar = db.query(models.Avatar).filter(
        models.Avatar.id == avatar_id,
        models.Avatar.user_id == current_user.id,
    ).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")
    skill = db.query(models.AvatarSkill).filter(
        models.AvatarSkill.id == skill_id,
        models.AvatarSkill.avatar_id == avatar_id,
    ).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    skill.enabled = data.enabled
    db.commit()
    db.refresh(skill)
    return skill


@router.delete("/{avatar_id}/skills/{skill_id}")
def uninstall_skill(
    avatar_id: int,
    skill_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    avatar = db.query(models.Avatar).filter(
        models.Avatar.id == avatar_id,
        models.Avatar.user_id == current_user.id,
    ).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")
    skill = db.query(models.AvatarSkill).filter(
        models.AvatarSkill.id == skill_id,
        models.AvatarSkill.avatar_id == avatar_id,
    ).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    db.delete(skill)
    db.commit()
    return {"success": True}


# --- Sub-agents ---

@router.get("/{avatar_id}/subagents", response_model=list[schemas.AvatarSubAgentOut])
def list_subagents(
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
    return db.query(models.AvatarSubAgent).filter(models.AvatarSubAgent.parent_avatar_id == avatar_id).all()


@router.post("/{avatar_id}/subagents", response_model=schemas.AvatarSubAgentOut)
def spawn_subagent(
    avatar_id: int,
    data: schemas.AvatarSubAgentCreate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    avatar = db.query(models.Avatar).filter(
        models.Avatar.id == avatar_id,
        models.Avatar.user_id == current_user.id,
    ).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")
    sub = models.AvatarSubAgent(
        parent_avatar_id=avatar_id,
        name=data.name,
        task=data.task,
        status="running",
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    from backend.services.subagent_runner import run_subagent_task_async
    run_subagent_task_async(sub.id)
    return sub


@router.get("/{avatar_id}/subagents/{sub_id}", response_model=schemas.AvatarSubAgentOut)
def get_subagent(
    avatar_id: int,
    sub_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    avatar = db.query(models.Avatar).filter(
        models.Avatar.id == avatar_id,
        models.Avatar.user_id == current_user.id,
    ).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")
    sub = db.query(models.AvatarSubAgent).filter(
        models.AvatarSubAgent.id == sub_id,
        models.AvatarSubAgent.parent_avatar_id == avatar_id,
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Sub-agent not found")
    return sub


@router.delete("/{avatar_id}/subagents/{sub_id}")
def delete_subagent(
    avatar_id: int,
    sub_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    avatar = db.query(models.Avatar).filter(
        models.Avatar.id == avatar_id,
        models.Avatar.user_id == current_user.id,
    ).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")
    sub = db.query(models.AvatarSubAgent).filter(
        models.AvatarSubAgent.id == sub_id,
        models.AvatarSubAgent.parent_avatar_id == avatar_id,
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Sub-agent not found")
    db.delete(sub)
    db.commit()
    return {"success": True}


# --- A2A Messages ---

@router.get("/{avatar_id}/messages", response_model=list[schemas.AgentMessageOut])
def list_agent_messages(
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
        db.query(models.AgentMessage)
        .filter(
            (models.AgentMessage.sender_avatar_id == avatar_id)
            | (models.AgentMessage.receiver_avatar_id == avatar_id)
        )
        .order_by(models.AgentMessage.created_at.desc())
        .limit(50)
        .all()
    )


@router.post("/{avatar_id}/messages", response_model=schemas.AgentMessageOut)
def send_agent_message(
    avatar_id: int,
    data: schemas.AgentMessageCreate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    avatar = db.query(models.Avatar).filter(
        models.Avatar.id == avatar_id,
        models.Avatar.user_id == current_user.id,
    ).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")
    receiver = db.query(models.Avatar).filter(models.Avatar.id == data.receiver_avatar_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver avatar not found")
    msg = models.AgentMessage(
        sender_avatar_id=avatar_id,
        receiver_avatar_id=data.receiver_avatar_id,
        content=data.content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


# --- Manual Trigger ---

@router.post("/{avatar_id}/trigger-autonomy")
def trigger_autonomy(
    avatar_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger the autonomy cycle for a single avatar (demo/testing)."""
    avatar = db.query(models.Avatar).filter(
        models.Avatar.id == avatar_id,
        models.Avatar.user_id == current_user.id,
    ).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")
    import threading
    from backend.services.avatar_autonomy import run_single_avatar
    from backend.database import SessionLocal
    def _run():
        _db = SessionLocal()
        try:
            run_single_avatar(avatar_id, _db)
        finally:
            _db.close()
    threading.Thread(target=_run, daemon=True).start()
    return {"success": True, "message": "自主行为已触发"}


@router.get("/{avatar_id}/openclaw-config")
def get_openclaw_config(
    avatar_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    """Return generated OpenClaw markdown config files for an avatar."""
    avatar = db.query(models.Avatar).filter(
        models.Avatar.id == avatar_id,
        models.Avatar.user_id == current_user.id,
    ).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")
    from backend.services.openclaw_config import generate_agent_markdown, write_agent_markdown, _agent_dir
    agent_dir = _agent_dir(avatar_id)
    # Prefer on-disk files (may have been edited); fall back to generated
    generated = generate_agent_markdown(avatar)
    files = {}
    for filename, content in generated.items():
        disk_path = os.path.join(agent_dir, filename)
        if os.path.exists(disk_path):
            with open(disk_path, encoding="utf-8") as f:
                files[filename] = f.read()
        else:
            files[filename] = content
    return {"files": files}


@router.put("/{avatar_id}/openclaw-config/{filename}")
def save_openclaw_config(
    avatar_id: int,
    filename: str,
    body: dict,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    """Save an edited OpenClaw config file to disk."""
    allowed = {"SOUL.md", "MEMORY.md", "HEARTBEAT.md", "TOOLS.md", "IDENTITY.md"}
    if filename not in allowed:
        raise HTTPException(status_code=400, detail="Invalid filename")
    avatar = db.query(models.Avatar).filter(
        models.Avatar.id == avatar_id,
        models.Avatar.user_id == current_user.id,
    ).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")
    from backend.services.openclaw_config import _agent_dir
    agent_dir = _agent_dir(avatar_id)
    os.makedirs(agent_dir, exist_ok=True)
    filepath = os.path.join(agent_dir, filename)
    content = body.get("content", "")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return {"ok": True}


# --- Channel Webhooks ---

@router.post("/{avatar_id}/webhooks/feishu")
def feishu_webhook(
    avatar_id: str,
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Receive Feishu Event API webhook."""
    # URL verification handshake
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    event = payload.get("event", {})
    sender = event.get("sender", {})
    open_id = sender.get("sender_id", {}).get("open_id", "")
    message = event.get("message", {})
    if message.get("message_type") != "text" or not open_id:
        return {}

    try:
        content = json.loads(message.get("content", "{}")).get("text", "").strip()
    except Exception:
        return {}
    if not content:
        return {}

    # Look up avatar by numeric ID or by name
    avatar = None
    if avatar_id.isdigit():
        avatar = db.query(models.Avatar).filter(models.Avatar.id == int(avatar_id)).first()
    if not avatar:
        avatar = db.query(models.Avatar).filter(models.Avatar.name == avatar_id).first()
    if not avatar:
        return {}

    def _run():
        try:
            handle_feishu_message(avatar.id, open_id, content)
        except Exception as e:
            import traceback
            traceback.print_exc()
    threading.Thread(target=_run, daemon=True).start()
    return {}


@router.post("/{avatar_id}/webhooks/wechat")
def wechat_webhook(
    avatar_id: int,
    payload: dict,
    db: Session = Depends(get_db),
):
    """Receive WeChat bot message webhook."""
    avatar = db.query(models.Avatar).filter(models.Avatar.id == avatar_id).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")
    openid = payload.get("openid", "unknown")
    content = payload.get("content", "")
    reply = handle_wechat_message(avatar_id, openid, content)
    return {"reply": reply}
