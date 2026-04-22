from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.database import engine, Base
from backend.routers import auth, conversations, posts, comments, avatars, recommendations

Base.metadata.create_all(bind=engine)

app = FastAPI(title="douban-ai", version="1.0.0")

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

app.mount("/static", StaticFiles(directory="backend/static"), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "douban-ai api"}
