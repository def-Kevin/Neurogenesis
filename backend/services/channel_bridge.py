"""
Channel bridge for Feishu (Lark) and WeChat integration.

Feishu messages are received via the real Feishu Event API and replies are
sent back through the Feishu message API (not the webhook response body).

Avatar conversations are routed through OpenClaw Gateway when available,
falling back to agent_engine when the gateway is not connected.
"""

import re

from backend.database import SessionLocal
from backend import models
from backend.services.agent_engine import agent_engine
from backend.services.feishu import send_text, send_draft_card
from backend.services.openclaw_gateway import gateway_client

DRAFT_RE = re.compile(r'\[DRAFT\]([\s\S]*?)\[/DRAFT\]', re.IGNORECASE)


def handle_feishu_message(avatar_id: int, open_id: str, content: str) -> None:
    """Process an incoming Feishu message and send the reply via Feishu API."""
    db = SessionLocal()
    try:
        avatar = db.query(models.Avatar).filter(models.Avatar.id == avatar_id).first()
        if not avatar:
            return
        user = db.query(models.User).filter(models.User.id == avatar.user_id).first()
        if not user:
            return

        # Find or create a per-user-per-avatar Feishu conversation
        convo = db.query(models.Conversation).filter(
            models.Conversation.avatar_id == avatar_id,
            models.Conversation.title.like(f"Feishu:{open_id}%"),
        ).first()
        if not convo:
            convo = models.Conversation(
                user_id=avatar.user_id,
                avatar_id=avatar_id,
                title=f"Feishu:{open_id}",
            )
            db.add(convo)
            db.commit()
            db.refresh(convo)

        db.add(models.Message(conversation_id=convo.id, role="user", content=content))
        db.commit()

        # Route through OpenClaw Gateway when available
        if gateway_client.connected and gateway_client._loop is not None:
            try:
                session_key = convo.openclaw_session_key
                if not session_key:
                    agent_id = f"neurogenesis_avatar_{avatar_id}"
                    session_key = gateway_client.create_session_sync(agent_id)
                    convo.openclaw_session_key = session_key
                    db.commit()
                reply = gateway_client.send_and_collect_sync(session_key, content)
            except Exception as e:
                import traceback
                traceback.print_exc()
                # Fallback to agent_engine on gateway error
                reply = agent_engine.process_turn(convo.id, user, db, avatar=avatar)
        else:
            reply = agent_engine.process_turn(convo.id, user, db, avatar=avatar)

        db.add(models.Message(conversation_id=convo.id, role="assistant", content=reply))
        db.commit()

        match = DRAFT_RE.search(reply)
        if match:
            draft_content = match.group(1).strip()
            clean_reply = DRAFT_RE.sub("", reply).strip()
            draft = models.ConversationDraft(
                conversation_id=convo.id, draft_content=draft_content
            )
            db.add(draft)
            db.commit()
            send_draft_card(open_id, draft_content, draft.id, clean_reply)
        else:
            send_text(open_id, reply)
    finally:
        db.close()


def handle_wechat_message(avatar_id: int, openid: str, content: str) -> str:
    """Handle an incoming WeChat message and return the avatar's reply."""
    db = SessionLocal()
    try:
        avatar = db.query(models.Avatar).filter(models.Avatar.id == avatar_id).first()
        if not avatar:
            return "Avatar not found"
        convo = (
            db.query(models.Conversation)
            .filter(
                models.Conversation.avatar_id == avatar_id,
                models.Conversation.title.like(f"WeChat:{openid}%"),
            )
            .first()
        )
        if not convo:
            convo = models.Conversation(
                user_id=avatar.user_id,
                avatar_id=avatar_id,
                title=f"WeChat:{openid}",
            )
            db.add(convo)
            db.commit()
            db.refresh(convo)

        db.add(models.Message(conversation_id=convo.id, role="user", content=content))
        db.commit()

        user = db.query(models.User).filter(models.User.id == avatar.user_id).first()
        if not user:
            return "User not found"

        reply = agent_engine.process_turn(convo.id, user, db, avatar=avatar)

        db.add(models.Message(conversation_id=convo.id, role="assistant", content=reply))
        db.commit()
        return reply
    finally:
        db.close()
