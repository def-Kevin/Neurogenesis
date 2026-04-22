from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.database import get_db
from backend import models, schemas, dependencies
from backend.services.agent_engine import agent_engine
from backend.services.avatar_autonomy import extract_conversation_memory
from backend.database import SessionLocal
from datetime import datetime
import json
import threading

router = APIRouter()

# Track recent memory extractions to avoid duplicate background jobs
_memory_extraction_tracker = {}
_memory_lock = threading.Lock()
_MEMORY_EXTRACTION_COOLDOWN_SECONDS = 300  # 5 minutes


def _extract_memory_bg(avatar_id: int, conversation_id: int):
    now = datetime.now().timestamp()
    with _memory_lock:
        last_extracted = _memory_extraction_tracker.get(conversation_id, 0)
        if now - last_extracted < _MEMORY_EXTRACTION_COOLDOWN_SECONDS:
            return
        _memory_extraction_tracker[conversation_id] = now

    db = SessionLocal()
    try:
        extract_conversation_memory(avatar_id, conversation_id, db)
    finally:
        db.close()


def _extract_user_style_bg(avatar_id: int):
    db = SessionLocal()
    try:
        extract_user_style(avatar_id, db)
    finally:
        db.close()


@router.get("", response_model=list[schemas.ConversationOut])
def list_conversations(
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    convos = (
        db.query(models.Conversation)
        .filter(models.Conversation.user_id == current_user.id)
        .order_by(models.Conversation.updated_at.desc())
        .all()
    )
    return convos


@router.post("", response_model=schemas.ConversationOut)
def create_conversation(
    data: schemas.ConversationCreate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    if data.avatar_id:
        avatar = db.query(models.Avatar).filter(
            models.Avatar.id == data.avatar_id,
        ).first()
        title = data.title or (avatar.name + "的对话" if avatar else "新对话")
    else:
        title = data.title or "新对话"
    convo = models.Conversation(user_id=current_user.id, avatar_id=data.avatar_id, title=title)
    db.add(convo)
    db.commit()
    db.refresh(convo)
    # add personalized system greeting
    hour = datetime.now().hour
    if 5 <= hour < 12:
        time_greeting = "早上好"
    elif 12 <= hour < 18:
        time_greeting = "下午好"
    else:
        time_greeting = "晚上好"

    nickname = current_user.nickname or current_user.username

    if data.avatar_id and avatar:
        persona_short = avatar.persona_prompt.split("。")[0] if avatar.persona_prompt else "你的AI分身"
        greeting = f"{nickname}，{time_greeting}。我是{avatar.name}，{persona_short}。想聊点什么？"
    else:
        greeting = f"{nickname}，{time_greeting}！我是小N。最近有看什么好书、电影，或者听到什么打动你的音乐吗？"
    msg = models.Message(
        conversation_id=convo.id,
        role="assistant",
        content=greeting,
    )
    db.add(msg)
    db.commit()
    return convo


@router.get("/{conversation_id}/messages", response_model=list[schemas.MessageOut])
def list_messages(
    conversation_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    convo = db.query(models.Conversation).filter(models.Conversation.id == conversation_id).first()
    if not convo or convo.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = (
        db.query(models.Message)
        .filter(models.Message.conversation_id == conversation_id)
        .order_by(models.Message.created_at.asc())
        .all()
    )
    return messages


@router.post("/{conversation_id}/messages", response_model=schemas.MessageOut)
def send_message_json(
    conversation_id: int,
    data: schemas.MessageCreate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    convo = db.query(models.Conversation).filter(models.Conversation.id == conversation_id).first()
    if not convo or convo.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    user_msg = models.Message(
        conversation_id=conversation_id,
        role="user",
        content=data.content,
    )
    db.add(user_msg)
    db.commit()
    avatar = None
    if convo.avatar_id:
        avatar = db.query(models.Avatar).filter(models.Avatar.id == convo.avatar_id).first()
    try:
        reply = agent_engine.process_turn(conversation_id, current_user, db, avatar=avatar)
    except RuntimeError as e:
        reply = f"[配置错误：{e}]"
    except Exception as e:
        reply = "抱歉，我暂时有点懵，稍后再试好吗？"
    assistant_msg = models.Message(
        conversation_id=conversation_id,
        role="assistant",
        content=reply,
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    if convo.avatar_id:
        threading.Thread(
            target=_extract_memory_bg,
            args=(convo.avatar_id, conversation_id),
            daemon=True,
        ).start()
        # Count user messages in this conversation, trigger style extraction every 10
        user_msg_count = (
            db.query(models.Message)
            .filter(
                models.Message.conversation_id == conversation_id,
                models.Message.role == "user",
            )
            .count()
        )
        if user_msg_count > 0 and user_msg_count % 10 == 0:
            threading.Thread(
                target=_extract_user_style_bg,
                args=(convo.avatar_id,),
                daemon=True,
            ).start()

    return assistant_msg


@router.post("/{conversation_id}/messages/stream")
def send_message_stream(
    conversation_id: int,
    data: schemas.MessageCreate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    convo = db.query(models.Conversation).filter(models.Conversation.id == conversation_id).first()
    if not convo or convo.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    user_msg = models.Message(
        conversation_id=conversation_id,
        role="user",
        content=data.content,
    )
    db.add(user_msg)
    db.commit()

    avatar = None
    if convo.avatar_id:
        avatar = db.query(models.Avatar).filter(models.Avatar.id == convo.avatar_id).first()

    # Capture IDs before the original session closes; the User/Avatar objects
    # themselves may become detached inside the generator.
    _user_id = current_user.id
    _avatar_id = convo.avatar_id

    def event_generator():
        full_content = ""
        error_occurred = False
        try:
            # Use a fresh session inside the generator because the original session
            # may be closed by FastAPI before the generator finishes iterating.
            from backend.database import SessionLocal
            gen_db = SessionLocal()
            try:
                user = gen_db.query(models.User).filter(models.User.id == _user_id).first()
                avatar_obj = None
                if _avatar_id:
                    avatar_obj = gen_db.query(models.Avatar).filter(models.Avatar.id == _avatar_id).first()
                for chunk in agent_engine.process_turn_stream(conversation_id, user, gen_db, avatar=avatar_obj):
                    full_content += chunk
                    yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
            finally:
                gen_db.close()
        except RuntimeError as e:
            error_occurred = True
            full_content = f"[配置错误：{e}]"
            yield f"data: {json.dumps({'chunk': full_content}, ensure_ascii=False)}\n\n"
        except Exception as e:
            import traceback
            print(f"[ChatStream] ERROR: {e}")
            traceback.print_exc()
            error_occurred = True
            full_content = "抱歉，我暂时有点懵，稍后再试好吗？"
            yield f"data: {json.dumps({'chunk': full_content}, ensure_ascii=False)}\n\n"
        finally:
            # Persist assistant message in a fresh session to avoid cross-generator DB issues
            from backend.database import SessionLocal
            persist_db = SessionLocal()
            try:
                assistant_msg = models.Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=full_content,
                )
                persist_db.add(assistant_msg)
                persist_db.commit()
            except Exception as e:
                print(f"[Stream] Failed to persist assistant message: {e}")
            finally:
                persist_db.close()

            if convo.avatar_id:
                threading.Thread(
                    target=_extract_memory_bg,
                    args=(convo.avatar_id, conversation_id),
                    daemon=True,
                ).start()
                # Need to count user messages in a fresh session
                count_db = SessionLocal()
                try:
                    user_msg_count = (
                        count_db.query(models.Message)
                        .filter(
                            models.Message.conversation_id == conversation_id,
                            models.Message.role == "user",
                        )
                        .count()
                    )
                    if user_msg_count > 0 and user_msg_count % 10 == 0:
                        threading.Thread(
                            target=_extract_user_style_bg,
                            args=(convo.avatar_id,),
                            daemon=True,
                        ).start()
                finally:
                    count_db.close()

            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    from fastapi.responses import StreamingResponse
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.put("/{conversation_id}", response_model=schemas.ConversationOut)
def update_conversation(
    conversation_id: int,
    data: schemas.ConversationUpdate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    convo = db.query(models.Conversation).filter(models.Conversation.id == conversation_id).first()
    if not convo or convo.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if data.title is not None:
        convo.title = data.title
    if data.status is not None:
        convo.status = data.status
    db.commit()
    db.refresh(convo)
    return convo


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    convo = db.query(models.Conversation).filter(models.Conversation.id == conversation_id).first()
    if not convo or convo.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.query(models.Message).filter(models.Message.conversation_id == conversation_id).delete()
    db.delete(convo)
    db.commit()
    return {"ok": True}


@router.post("/{conversation_id}/drafts", response_model=schemas.ConversationDraftOut)
def create_draft(
    conversation_id: int,
    data: schemas.ConversationDraftCreate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    convo = db.query(models.Conversation).filter(models.Conversation.id == conversation_id).first()
    if not convo or convo.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    draft = models.ConversationDraft(
        conversation_id=conversation_id,
        draft_content=data.draft_content,
        title=data.title,
        tags=json.dumps(data.tags) if data.tags else None,
        mood=data.mood,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


@router.put("/{conversation_id}/drafts/{draft_id}", response_model=schemas.ConversationDraftOut)
def update_draft(
    conversation_id: int,
    draft_id: int,
    data: schemas.ConversationDraftCreate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    convo = db.query(models.Conversation).filter(models.Conversation.id == conversation_id).first()
    if not convo or convo.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    draft = db.query(models.ConversationDraft).filter(
        models.ConversationDraft.id == draft_id,
        models.ConversationDraft.conversation_id == conversation_id,
    ).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    draft.draft_content = data.draft_content
    if data.title is not None:
        draft.title = data.title
    if data.tags is not None:
        draft.tags = json.dumps(data.tags)
    if data.mood is not None:
        draft.mood = data.mood
    db.commit()
    db.refresh(draft)
    return draft


@router.post("/{conversation_id}/recommendations", response_model=schemas.RecommendationOut)
def create_recommendation(
    conversation_id: int,
    data: schemas.RecommendationCreate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    convo = db.query(models.Conversation).filter(models.Conversation.id == conversation_id).first()
    if not convo or convo.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    rec = models.Recommendation(
        user_id=current_user.id,
        conversation_id=conversation_id,
        work_type=data.work_type,
        work_title=data.work_title,
        work_creator=data.work_creator,
        reason=data.reason,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.post("/{conversation_id}/publish")
def publish_draft(
    conversation_id: int,
    draft_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    convo = db.query(models.Conversation).filter(models.Conversation.id == conversation_id).first()
    if not convo or convo.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    draft = db.query(models.ConversationDraft).filter(
        models.ConversationDraft.id == draft_id,
        models.ConversationDraft.conversation_id == conversation_id,
    ).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    post = models.Post(
        author_id=current_user.id,
        content=draft.draft_content,
        title=draft.title,
        tags=draft.tags,
        mood=draft.mood,
        content_type="share",
        status="published",
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    draft.is_published = 1
    draft.post_id = post.id
    db.commit()
    return {"post_id": post.id}
