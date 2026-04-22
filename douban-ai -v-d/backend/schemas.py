from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class UserCreate(BaseModel):
    username: str
    password: str
    nickname: Optional[str] = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None


class AvatarCreate(BaseModel):
    name: str
    persona_prompt: str
    interests: Optional[List[str]] = None
    writing_style: Optional[str] = None


class AvatarUpdate(BaseModel):
    name: Optional[str] = None
    persona_prompt: Optional[str] = None
    interests: Optional[List[str]] = None
    writing_style: Optional[str] = None


class AvatarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    name: str
    persona_prompt: str
    interests: Optional[str] = None
    writing_style: Optional[str] = None
    auto_post_enabled: int
    created_at: Optional[datetime] = None


class PostCreate(BaseModel):
    title: Optional[str] = None
    content: str
    tags: Optional[List[str]] = None
    mood: Optional[str] = None
    avatar_id: Optional[int] = None


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    author_id: int
    avatar_id: Optional[int] = None
    title: Optional[str] = None
    content: str
    content_type: str
    tags: Optional[str] = None
    mood: Optional[str] = None
    created_at: Optional[datetime] = None


class CommentCreate(BaseModel):
    content: str
    parent_id: Optional[int] = None
    avatar_id: Optional[int] = None


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    post_id: int
    author_id: int
    avatar_id: Optional[int] = None
    parent_id: Optional[int] = None
    content: str
    created_at: Optional[datetime] = None


class ConversationCreate(BaseModel):
    title: Optional[str] = None
    avatar_id: Optional[int] = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    avatar_id: Optional[int] = None
    title: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None


class MessageCreate(BaseModel):
    content: str


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    conversation_id: int
    role: str
    content: str
    tool_calls: Optional[str] = None
    tool_result: Optional[str] = None
    created_at: Optional[datetime] = None


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    work_type: str
    work_title: str
    work_creator: Optional[str] = None
    reason: Optional[str] = None
    created_at: Optional[datetime] = None
