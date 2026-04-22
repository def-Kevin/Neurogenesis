from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.database import engine, Base
from backend.routers import auth, conversations, posts, comments, avatars, recommendations, follows
from backend.scheduler import start_scheduler, shutdown_scheduler


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    _run_migrations()
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    yield
    shutdown_scheduler()


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

app.mount("/static", StaticFiles(directory="backend/static"), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "Neurogenesis api"}
