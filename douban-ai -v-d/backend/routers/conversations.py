from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.database import get_db
from backend import models, schemas, dependencies
from backend.services.agent_engine import agent_engine
import json

router = APIRouter()


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
    # add system greeting
    if data.avatar_id:
        greeting = "嗨，我是你的AI分身。想聊点什么？"
    else:
        greeting = "嗨，我是小dou。最近有看什么好书、电影，或者听到什么打动你的音乐吗？"
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

    # Collect all chunks before streaming to avoid DB session issues in generator
    chunks = []
    try:
        for chunk in agent_engine.process_turn_stream(conversation_id, current_user, db, avatar=avatar):
            chunks.append(chunk)
    except RuntimeError as e:
        chunks = [f"[配置错误：{e}]"]
    except Exception:
        chunks = ["抱歉，我暂时有点懵，稍后再试好吗？"]

    full_content = "".join(chunks)
    assistant_msg = models.Message(
        conversation_id=conversation_id,
        role="assistant",
        content=full_content,
    )
    db.add(assistant_msg)
    db.commit()

    def event_generator():
        for chunk in chunks:
            yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    from fastapi.responses import StreamingResponse
    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
        content_type="share",
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    draft.is_published = 1
    draft.post_id = post.id
    db.commit()
    return {"post_id": post.id}
