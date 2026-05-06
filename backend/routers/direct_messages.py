from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.database import get_db
from backend import models, schemas, dependencies

router = APIRouter()


def _enrich_conversation(convo: models.Conversation, current_user: models.User, db: Session):
    """Populate other_user and last_message_preview for a direct conversation."""
    participant = (
        db.query(models.ConversationParticipant)
        .filter(
            models.ConversationParticipant.conversation_id == convo.id,
            models.ConversationParticipant.user_id != current_user.id,
        )
        .first()
    )
    other_user = None
    if participant:
        user = db.query(models.User).filter(models.User.id == participant.user_id).first()
        if user:
            other_user = schemas.UserOut.model_validate(user)

    last_msg = (
        db.query(models.Message)
        .filter(models.Message.conversation_id == convo.id)
        .order_by(models.Message.created_at.desc())
        .first()
    )
    last_preview = last_msg.content[:60] if last_msg else None

    data = schemas.DirectConversationOut.model_validate(convo).model_dump()
    data["other_user"] = other_user.model_dump() if other_user else None
    data["last_message_preview"] = last_preview
    return data


@router.get("/conversations", response_model=list[schemas.DirectConversationOut])
def list_direct_conversations(
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    convo_ids = (
        db.query(models.ConversationParticipant.conversation_id)
        .filter(models.ConversationParticipant.user_id == current_user.id)
        .subquery()
    )
    convos = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.conversation_type == "direct",
            models.Conversation.id.in_(convo_ids),
        )
        .order_by(models.Conversation.updated_at.desc())
        .all()
    )
    return [_enrich_conversation(c, current_user, db) for c in convos]


@router.post("/conversations", response_model=schemas.DirectConversationOut)
def create_direct_conversation(
    data: schemas.DirectMessageCreate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    if data.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot message yourself")

    target = db.query(models.User).filter(models.User.id == data.user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if a direct conversation already exists between these two users
    my_convo_ids = (
        db.query(models.ConversationParticipant.conversation_id)
        .filter(models.ConversationParticipant.user_id == current_user.id)
        .subquery()
    )
    their_convo_ids = (
        db.query(models.ConversationParticipant.conversation_id)
        .filter(models.ConversationParticipant.user_id == data.user_id)
        .subquery()
    )
    existing = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.conversation_type == "direct",
            models.Conversation.id.in_(my_convo_ids),
            models.Conversation.id.in_(their_convo_ids),
        )
        .first()
    )
    if existing:
        return _enrich_conversation(existing, current_user, db)

    # Require following the user to send a message
    follow = db.query(models.Follow).filter(
        models.Follow.follower_id == current_user.id,
        models.Follow.following_id == data.user_id,
    ).first()
    if not follow:
        raise HTTPException(status_code=403, detail="You must follow this user to send a message")

    convo = models.Conversation(
        user_id=current_user.id,
        conversation_type="direct",
        title=None,
    )
    db.add(convo)
    db.commit()
    db.refresh(convo)

    db.add(models.ConversationParticipant(conversation_id=convo.id, user_id=current_user.id))
    db.add(models.ConversationParticipant(conversation_id=convo.id, user_id=data.user_id))
    db.commit()

    return _enrich_conversation(convo, current_user, db)


@router.get("/conversations/{convo_id}/messages", response_model=list[schemas.MessageOut])
def list_direct_messages(
    convo_id: int,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    convo = db.query(models.Conversation).filter(
        models.Conversation.id == convo_id,
        models.Conversation.conversation_type == "direct",
    ).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    participant = db.query(models.ConversationParticipant).filter(
        models.ConversationParticipant.conversation_id == convo_id,
        models.ConversationParticipant.user_id == current_user.id,
    ).first()
    if not participant:
        raise HTTPException(status_code=403, detail="Not a participant")

    messages = (
        db.query(models.Message)
        .filter(models.Message.conversation_id == convo_id)
        .order_by(models.Message.created_at.asc())
        .all()
    )
    return messages


@router.post("/conversations/{convo_id}/messages", response_model=schemas.MessageOut)
def send_direct_message(
    convo_id: int,
    data: schemas.MessageCreate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    convo = db.query(models.Conversation).filter(
        models.Conversation.id == convo_id,
        models.Conversation.conversation_type == "direct",
    ).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    participant = db.query(models.ConversationParticipant).filter(
        models.ConversationParticipant.conversation_id == convo_id,
        models.ConversationParticipant.user_id == current_user.id,
    ).first()
    if not participant:
        raise HTTPException(status_code=403, detail="Not a participant")

    msg = models.Message(
        conversation_id=convo_id,
        sender_id=current_user.id,
        role="user",
        content=data.content,
    )
    db.add(msg)
    # Update conversation updated_at
    convo.updated_at = func.now()
    db.commit()
    db.refresh(msg)
    return msg
