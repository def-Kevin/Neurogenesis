from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from backend.config import settings
from backend.database import engine, Base, SessionLocal
from backend.routers import auth, conversations, posts, comments, avatars, recommendations, follows, skills, direct_messages
from backend.scheduler import start_scheduler, shutdown_scheduler
from backend.services import openclaw_cli
from backend.services.openclaw_gateway import gateway_client
from backend import models

_openclaw_process = None


def _run_migrations():
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    avatar_cols = [c["name"] for c in inspector.get_columns("avatars")] if "avatars" in existing_tables else []
    post_cols = [c["name"] for c in inspector.get_columns("posts")] if "posts" in existing_tables else []
    draft_cols = [c["name"] for c in inspector.get_columns("conversation_drafts")] if "conversation_drafts" in existing_tables else []
    memory_cols = [c["name"] for c in inspector.get_columns("avatar_memories")] if "avatar_memories" in existing_tables else []
    with engine.begin() as conn:
        if "avatars" in existing_tables:
            if "auto_post_interval_hours" not in avatar_cols:
                conn.execute(text("ALTER TABLE avatars ADD COLUMN auto_post_interval_hours INTEGER DEFAULT 24"))
            if "last_auto_post_at" not in avatar_cols:
                conn.execute(text("ALTER TABLE avatars ADD COLUMN last_auto_post_at DATETIME"))
            if "memory_summary" not in avatar_cols:
                conn.execute(text("ALTER TABLE avatars ADD COLUMN memory_summary TEXT"))
            if "energy" not in avatar_cols:
                conn.execute(text("ALTER TABLE avatars ADD COLUMN energy INTEGER DEFAULT 80"))
            if "mood" not in avatar_cols:
                conn.execute(text("ALTER TABLE avatars ADD COLUMN mood TEXT"))
            if "behavior_log" not in avatar_cols:
                conn.execute(text("ALTER TABLE avatars ADD COLUMN behavior_log TEXT"))
            if "learned_traits" not in avatar_cols:
                conn.execute(text("ALTER TABLE avatars ADD COLUMN learned_traits TEXT"))
            if "user_style_snapshot" not in avatar_cols:
                conn.execute(text("ALTER TABLE avatars ADD COLUMN user_style_snapshot TEXT"))
            if "persona_evolution" not in avatar_cols:
                conn.execute(text("ALTER TABLE avatars ADD COLUMN persona_evolution TEXT"))
        if "posts" in existing_tables:
            if "image_url" not in post_cols:
                conn.execute(text("ALTER TABLE posts ADD COLUMN image_url TEXT"))
            if "status" not in post_cols:
                conn.execute(text("ALTER TABLE posts ADD COLUMN status TEXT DEFAULT 'published'"))
        if "conversation_drafts" in existing_tables:
            if "title" not in draft_cols:
                conn.execute(text("ALTER TABLE conversation_drafts ADD COLUMN title TEXT"))
            if "tags" not in draft_cols:
                conn.execute(text("ALTER TABLE conversation_drafts ADD COLUMN tags TEXT"))
            if "mood" not in draft_cols:
                conn.execute(text("ALTER TABLE conversation_drafts ADD COLUMN mood TEXT"))
        if "avatar_memories" in existing_tables:
            if "importance" not in memory_cols:
                conn.execute(text("ALTER TABLE avatar_memories ADD COLUMN importance INTEGER DEFAULT 5"))
            if "category" not in memory_cols:
                conn.execute(text("ALTER TABLE avatar_memories ADD COLUMN category TEXT"))
            if "access_count" not in memory_cols:
                conn.execute(text("ALTER TABLE avatar_memories ADD COLUMN access_count INTEGER DEFAULT 0"))
            if "last_accessed_at" not in memory_cols:
                conn.execute(text("ALTER TABLE avatar_memories ADD COLUMN last_accessed_at DATETIME"))
        convo_cols = [c["name"] for c in inspector.get_columns("conversations")] if "conversations" in existing_tables else []
        if "conversations" in existing_tables:
            if "openclaw_session_key" not in convo_cols:
                conn.execute(text("ALTER TABLE conversations ADD COLUMN openclaw_session_key TEXT"))
            if "conversation_type" not in convo_cols:
                conn.execute(text("ALTER TABLE conversations ADD COLUMN conversation_type TEXT DEFAULT 'ai'"))
        msg_cols = [c["name"] for c in inspector.get_columns("messages")] if "messages" in existing_tables else []
        if "messages" in existing_tables and "sender_id" not in msg_cols:
            conn.execute(text("ALTER TABLE messages ADD COLUMN sender_id INTEGER"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    _run_migrations()
    Base.metadata.create_all(bind=engine)
    global _openclaw_process
    _openclaw_process = openclaw_cli.gateway_start()
    start_scheduler()
    if settings.openclaw_enabled:
        import asyncio
        await asyncio.sleep(2)
        await gateway_client.connect()
    yield
    shutdown_scheduler()
    openclaw_cli.gateway_stop(_openclaw_process)


app = FastAPI(title="Neurogenesis", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
app.include_router(posts.router, prefix="/api/posts", tags=["posts"])
app.include_router(comments.router, prefix="/api/comments", tags=["comments"])
app.include_router(avatars.router, prefix="/api/avatars", tags=["avatars"])
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["recommendations"])
app.include_router(follows.router, prefix="/api/follows", tags=["follows"])
app.include_router(direct_messages.router, prefix="/api/direct-messages", tags=["direct-messages"])
app.include_router(skills.router)

app.mount("/static", StaticFiles(directory="backend/static"), name="static")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "Neurogenesis api"}


@app.post("/api/feishu/card-action")
def feishu_card_action(payload: dict, db: Session = Depends(get_db)):
    import sys
    print(f"[card-action] payload={payload}", flush=True, file=sys.stderr)
    if "challenge" in payload:
        return {"challenge": payload["challenge"]}

    action_value = payload.get("action", {}).get("value", {})
    open_id = payload.get("open_id", "")
    action_type = action_value.get("action")
    draft_id_str = action_value.get("draft_id")

    if not draft_id_str:
        return {}

    draft = db.query(models.ConversationDraft).filter(
        models.ConversationDraft.id == int(draft_id_str)
    ).first()
    if not draft:
        return {"toast": {"type": "error", "content": "草稿不存在"}}

    if action_type == "publish_draft":
        if draft.is_published:
            return {"toast": {"type": "info", "content": "该草稿已发布过了"}}
        convo = db.query(models.Conversation).filter(
            models.Conversation.id == draft.conversation_id
        ).first()
        post = models.Post(
            author_id=convo.user_id,
            avatar_id=convo.avatar_id,
            content=draft.draft_content,
            content_type="share",
            status="published",
        )
        db.add(post)
        db.flush()
        draft.is_published = 1
        draft.post_id = post.id
        db.commit()
        return {
            "toast": {"type": "success", "content": "已发布到社区！"},
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {"title": {"tag": "plain_text", "content": "✅ 已发布到社区"}, "template": "green"},
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": draft.draft_content}}
                ],
            },
        }

    elif action_type == "discard_draft":
        draft.is_published = 1  # mark consumed so it won't show again
        db.commit()
        return {
            "toast": {"type": "info", "content": "草稿已放弃"},
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {"title": {"tag": "plain_text", "content": "🗑️ 草稿已放弃"}, "template": "grey"},
                "elements": [],
            },
        }

    return {}
