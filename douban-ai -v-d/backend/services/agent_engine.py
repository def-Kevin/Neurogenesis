import json
from sqlalchemy.orm import Session
from backend import models
from backend.services.llm_client import LLMClient
from backend.config import settings

SYSTEM_PROMPT_TEMPLATE = """你是 douban-ai 的文艺助手"小dou"。你的职责是：
1. 通过自然、温暖的对话，引导用户分享最近的文艺体验（电影、书籍、音乐、展览等）。
2. 帮助用户将碎片化的感受整理成结构化的分享文案。
3. 根据用户的喜好，推荐相关的文艺作品。
4. 当用户同意时，生成分享草稿并用 [DRAFT]...[/DRAFT] 包裹。
5. 推荐作品时用 [REC]作品类型|作品名|创作者|推荐理由[/REC] 格式。
6. 推荐分身时用 [AVATAR]分身ID|推荐理由[/AVATAR] 格式。

人格特质：
- 像一位懂文艺、有品味的朋友，不机械，不冗长。
- 善于提问，但不过度追问。每次回复控制在 3-5 句话以内，除非用户在整理长文。
- 使用中文，偶尔可以引用诗句或歌词。

工作流程：
1. 开场：如果对话为空，主动问候并问一个轻松的文艺相关问题。
2. 挖掘：根据用户回答，追问细节（如"哪一幕最打动你？"）。
3. 整理：当信息足够时，生成分享草稿，询问用户是否满意。
4. 推荐：根据话题，推荐 1-2 部相关作品。
5. 发布：用户确认后，提示已准备好发布。

当前用户信息：{user_info}
"""


class AgentEngine:
    def __init__(self):
        self.llm = LLMClient()

    def _build_system_prompt(self, user: models.User, db: Session) -> str:
        user_info = f"昵称：{user.nickname or user.username}"
        avatar = db.query(models.Avatar).filter(models.Avatar.user_id == user.id).first()
        if avatar and avatar.interests:
            user_info += f"，兴趣：{avatar.interests}"
        return SYSTEM_PROMPT_TEMPLATE.format(user_info=user_info)

    def _load_history(self, conversation_id: int, db: Session) -> list[dict]:
        messages = (
            db.query(models.Message)
            .filter(models.Message.conversation_id == conversation_id)
            .order_by(models.Message.created_at.asc())
            .all()
        )
        return [{"role": m.role, "content": m.content} for m in messages]

    def process_turn(self, conversation_id: int, user: models.User, db: Session, avatar: models.Avatar = None) -> str:
        system_prompt = self._build_system_prompt(user, db) if not avatar else avatar.persona_prompt
        history = self._load_history(conversation_id, db)
        messages = [{"role": "system", "content": system_prompt}] + history
        resp = self.llm.chat_completion(messages, stream=False)
        return resp.content or ""

    def process_turn_stream(self, conversation_id: int, user: models.User, db: Session, avatar: models.Avatar = None):
        system_prompt = self._build_system_prompt(user, db) if not avatar else avatar.persona_prompt
        history = self._load_history(conversation_id, db)
        messages = [{"role": "system", "content": system_prompt}] + history
        yield from self.llm.chat_completion(messages, stream=True)


agent_engine = AgentEngine()
