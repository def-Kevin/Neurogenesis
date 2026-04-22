from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from backend.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    nickname = Column(String)
    avatar_url = Column(String)
    password_hash = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_token = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Avatar(Base):
    __tablename__ = "avatars"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    persona_prompt = Column(Text, nullable=False)
    interests = Column(Text)  # JSON array string
    writing_style = Column(Text)
    auto_post_enabled = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    avatar_id = Column(Integer, ForeignKey("avatars.id"), nullable=True)
    title = Column(String)
    content = Column(Text, nullable=False)
    content_type = Column(String, default="share")
    tags = Column(Text)  # JSON array string
    mood = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    avatar_id = Column(Integer, ForeignKey("avatars.id"), nullable=True)
    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Like(Base):
    __tablename__ = "likes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=True)
    comment_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("user_id", "post_id", "comment_id", name="uix_like"),)


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    avatar_id = Column(Integer, ForeignKey("avatars.id"), nullable=True)
    title = Column(String)
    status = Column(String, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    tool_calls = Column(Text)
    tool_result = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ConversationDraft(Base):
    __tablename__ = "conversation_drafts"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    draft_content = Column(Text, nullable=False)
    is_published = Column(Integer, default=0)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Recommendation(Base):
    __tablename__ = "recommendations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)
    work_type = Column(String, nullable=False)
    work_title = Column(String, nullable=False)
    work_creator = Column(String)
    reason = Column(Text)
    user_feedback = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AvatarInteraction(Base):
    __tablename__ = "avatar_interactions"
    id = Column(Integer, primary_key=True, index=True)
    source_avatar_id = Column(Integer, ForeignKey("avatars.id"), nullable=False)
    target_avatar_id = Column(Integer, ForeignKey("avatars.id"), nullable=False)
    interaction_type = Column(String, nullable=False)
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
