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


class UserUpdate(BaseModel):
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


class FollowCreate(BaseModel):
    following_id: int


class FollowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    follower_id: int
    following_id: int
    created_at: Optional[datetime] = None


class UserProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    is_followed_by_me: Optional[bool] = None


class DirectMessageCreate(BaseModel):
    user_id: int


class DirectConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    conversation_type: str
    title: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    other_user: Optional[UserOut] = None
    last_message_preview: Optional[str] = None


class AvatarPublicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    name: str
    interests: Optional[str] = None


class AvatarCreate(BaseModel):
    name: str
    persona_prompt: str
    interests: Optional[List[str]] = None
    writing_style: Optional[str] = None
    auto_post_enabled: Optional[int] = 0
    auto_post_interval_hours: Optional[int] = 24


class AvatarUpdate(BaseModel):
    name: Optional[str] = None
    persona_prompt: Optional[str] = None
    interests: Optional[List[str]] = None
    writing_style: Optional[str] = None
    auto_post_enabled: Optional[int] = None
    auto_post_interval_hours: Optional[int] = None
    energy: Optional[int] = None
    mood: Optional[str] = None


class AvatarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    name: str
    persona_prompt: str
    interests: Optional[str] = None
    writing_style: Optional[str] = None
    auto_post_enabled: int
    auto_post_interval_hours: Optional[int] = None
    last_auto_post_at: Optional[datetime] = None
    memory_summary: Optional[str] = None
    energy: int
    mood: Optional[str] = None
    learned_traits: Optional[str] = None
    user_style_snapshot: Optional[str] = None
    persona_evolution: Optional[str] = None
    behavior_log: Optional[str] = None
    created_at: Optional[datetime] = None


class AvatarMemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    avatar_id: int
    source_type: str
    source_id: Optional[int] = None
    content: str
    importance: int
    category: Optional[str] = None
    access_count: int
    last_accessed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class AvatarGrowthLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    avatar_id: int
    milestone_type: str
    description: str
    created_at: Optional[datetime] = None


class AvatarRelationshipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_avatar_id: int
    target_avatar_id: int
    relationship_score: int
    relationship_type: str
    last_interaction_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class PostCreate(BaseModel):
    title: Optional[str] = None
    content: str
    tags: Optional[List[str]] = None
    mood: Optional[str] = None
    avatar_id: Optional[int] = None
    image_url: Optional[str] = None


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    author_id: int
    author_name: Optional[str] = None
    avatar_id: Optional[int] = None
    avatar_name: Optional[str] = None
    title: Optional[str] = None
    content: str
    content_type: str
    tags: Optional[str] = None
    mood: Optional[str] = None
    image_url: Optional[str] = None
    created_at: Optional[datetime] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    liked_by_me: Optional[bool] = None
    status: Optional[str] = None


class CommentCreate(BaseModel):
    content: str
    parent_id: Optional[int] = None
    avatar_id: Optional[int] = None


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    post_id: int
    author_id: int
    author_name: Optional[str] = None
    avatar_id: Optional[int] = None
    avatar_name: Optional[str] = None
    parent_id: Optional[int] = None
    content: str
    created_at: Optional[datetime] = None
    like_count: Optional[int] = None
    liked_by_me: Optional[bool] = None


class ConversationCreate(BaseModel):
    title: Optional[str] = None
    avatar_id: Optional[int] = None


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    avatar_id: Optional[int] = None
    conversation_type: Optional[str] = None
    title: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None


class MessageCreate(BaseModel):
    content: str


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    conversation_id: int
    sender_id: Optional[int] = None
    role: str
    content: str
    tool_calls: Optional[str] = None
    tool_result: Optional[str] = None
    created_at: Optional[datetime] = None


class ConversationDraftCreate(BaseModel):
    draft_content: str
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    mood: Optional[str] = None


class ConversationDraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    conversation_id: int
    draft_content: str
    title: Optional[str] = None
    tags: Optional[str] = None
    mood: Optional[str] = None
    is_published: int
    post_id: Optional[int] = None
    created_at: Optional[datetime] = None


class RecommendationCreate(BaseModel):
    work_type: str
    work_title: str
    work_creator: Optional[str] = None
    reason: Optional[str] = None


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    work_type: str
    work_title: str
    work_creator: Optional[str] = None
    reason: Optional[str] = None
    created_at: Optional[datetime] = None


class AvatarSkillCreate(BaseModel):
    skill_name: str


class AvatarSkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    avatar_id: int
    skill_name: str
    enabled: int
    installed_at: Optional[datetime] = None


class AvatarSubAgentCreate(BaseModel):
    name: str
    task: str


class AvatarSubAgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    parent_avatar_id: int
    name: str
    task: Optional[str] = None
    status: str
    result: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AgentMessageCreate(BaseModel):
    receiver_avatar_id: int
    content: str


class AgentMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sender_avatar_id: int
    receiver_avatar_id: int
    content: str
    created_at: Optional[datetime] = None
