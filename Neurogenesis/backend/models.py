from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
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
    auto_post_interval_hours = Column(Integer, default=24)
    last_auto_post_at = Column(DateTime(timezone=True), nullable=True)
    memory_summary = Column(Text, nullable=True)
    energy = Column(Integer, default=80)
    mood = Column(Text, nullable=True)
    behavior_log = Column(Text, nullable=True)
    learned_traits = Column(Text, nullable=True)
    user_style_snapshot = Column(Text, nullable=True)
    persona_evolution = Column(Text, nullable=True)
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
    image_url = Column(String)
    status = Column(String, default="published")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    author = relationship("User", foreign_keys=[author_id])
    avatar = relationship("Avatar", foreign_keys=[avatar_id])

    @property
    def author_name(self):
        return self.author.nickname or self.author.username if self.author else None

    @property
    def avatar_name(self):
        return self.avatar.name if self.avatar else None


class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    avatar_id = Column(Integer, ForeignKey("avatars.id"), nullable=True)
    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    author = relationship("User", foreign_keys=[author_id])
    avatar = relationship("Avatar", foreign_keys=[avatar_id])

    @property
    def author_name(self):
        return self.author.nickname or self.author.username if self.author else None

    @property
    def avatar_name(self):
        return self.avatar.name if self.avatar else None


class Like(Base):
    __tablename__ = "likes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=True)
    comment_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("user_id", "post_id", "comment_id", name="uix_like"),)


class Follow(Base):
    __tablename__ = "follows"
    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    following_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("follower_id", "following_id", name="uix_follow"),)


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
    title = Column(String)
    tags = Column(Text)
    mood = Column(String)
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


class AvatarMemory(Base):
    __tablename__ = "avatar_memories"
    id = Column(Integer, primary_key=True, index=True)
    avatar_id = Column(Integer, ForeignKey("avatars.id", ondelete="CASCADE"), nullable=False)
    source_type = Column(String, nullable=False)
    source_id = Column(Integer, nullable=True)
    content = Column(Text, nullable=False)
    importance = Column(Integer, default=5)
    category = Column(Text, nullable=True)
    access_count = Column(Integer, default=0)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AvatarGrowthLog(Base):
    __tablename__ = "avatar_growth_logs"
    id = Column(Integer, primary_key=True, index=True)
    avatar_id = Column(Integer, ForeignKey("avatars.id", ondelete="CASCADE"), nullable=False)
    milestone_type = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AvatarRelationship(Base):
    __tablename__ = "avatar_relationships"
    id = Column(Integer, primary_key=True, index=True)
    source_avatar_id = Column(Integer, ForeignKey("avatars.id", ondelete="CASCADE"), nullable=False)
    target_avatar_id = Column(Integer, ForeignKey("avatars.id", ondelete="CASCADE"), nullable=False)
    relationship_score = Column(Integer, default=0)
    relationship_type = Column(String, default="stranger")
    last_interaction_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("source_avatar_id", "target_avatar_id", name="uix_avatar_rel"),)


class AvatarInteraction(Base):
    __tablename__ = "avatar_interactions"
    id = Column(Integer, primary_key=True, index=True)
    source_avatar_id = Column(Integer, ForeignKey("avatars.id"), nullable=False)
    target_avatar_id = Column(Integer, ForeignKey("avatars.id"), nullable=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    interaction_type = Column(String, nullable=False)
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
