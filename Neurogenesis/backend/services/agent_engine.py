import json
from sqlalchemy.orm import Session
from backend import models
from backend.services.llm_client import LLMClient
from backend.config import settings

import json

SYSTEM_PROMPT_TEMPLATE = """你是 神经发生 (Neurogenesis) 的文艺助手"小N"。你的职责是：
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

AVATAR_SYSTEM_PROMPT_TEMPLATE = """你是用户的AI分身，你的名字是"{avatar_name}"。

【你的人设】
{persona_prompt}

【你的兴趣】
{interests}

【你的文风】
{writing_style}

【关于用户的记忆】
{memory_summary}

【已学习的用户特质】
{learned_traits}

【用户表达风格参考】
{user_style_snapshot}

【人格演变记录】
{persona_evolution}

【当前对话用户】
{user_info}

【行为准则】
1. 以第一人称"我"进行对话，保持人设的核心一致性。
2. 结合你的兴趣、记忆和已学习的特质，给出有个性、有温度的回应。
3. 当用户提到你们之前的共同记忆时，自然地引用和回应。
4. 可以适当模仿用户的表达风格，但不要完全复制，保持自己的个性。
5. 帮助用户整理文艺体验，生成分享草稿时用 [DRAFT]...[/DRAFT] 包裹。
6. 推荐作品时用 [REC]作品类型|作品名|创作者|推荐理由[/REC] 格式。
7. 每次回复控制在 3-5 句话以内，除非用户在整理长文。
8. 使用中文，风格要符合你的文风设定。你的人设核心是稳定的，但可以自然地吸收与用户的共同经历。
"""


class AgentEngine:
    MAX_HISTORY_MESSAGES = 20

    def __init__(self):
        self.llm = LLMClient()

    def _build_system_prompt(self, user: models.User, db: Session, avatar: models.Avatar = None) -> str:
        user_info = f"昵称：{user.nickname or user.username}"
        default_avatar = db.query(models.Avatar).filter(models.Avatar.user_id == user.id).first()
        if default_avatar and default_avatar.interests:
            user_info += f"，兴趣：{default_avatar.interests}"

        if avatar:
            interests = avatar.interests or "未指定"
            try:
                interests_list = json.loads(interests)
                if isinstance(interests_list, list):
                    interests = "、".join(interests_list)
            except Exception:
                pass

            learned_traits = avatar.learned_traits or "暂无"
            user_style = avatar.user_style_snapshot or "暂无"
            evolution = avatar.persona_evolution or "暂无"

            return AVATAR_SYSTEM_PROMPT_TEMPLATE.format(
                avatar_name=avatar.name,
                persona_prompt=avatar.persona_prompt,
                interests=interests,
                writing_style=avatar.writing_style or "自然、真诚",
                memory_summary=avatar.memory_summary or "暂无关于用户的具体记忆。",
                learned_traits=learned_traits,
                user_style_snapshot=user_style,
                persona_evolution=evolution,
                user_info=user_info,
            )

        return SYSTEM_PROMPT_TEMPLATE.format(user_info=user_info)

    def _load_history(self, conversation_id: int, db: Session) -> list[dict]:
        messages = (
            db.query(models.Message)
            .filter(models.Message.conversation_id == conversation_id)
            .order_by(models.Message.created_at.desc())
            .limit(self.MAX_HISTORY_MESSAGES)
            .all()
        )
        messages.reverse()
        return [{"role": m.role, "content": m.content} for m in messages]

    def process_turn(self, conversation_id: int, user: models.User, db: Session, avatar: models.Avatar = None) -> str:
        system_prompt = self._build_system_prompt(user, db, avatar=avatar)
        history = self._load_history(conversation_id, db)
        messages = [{"role": "system", "content": system_prompt}] + history
        resp = self.llm.chat_completion(messages, stream=False)
        return resp.content or ""

    def process_turn_stream(self, conversation_id: int, user: models.User, db: Session, avatar: models.Avatar = None):
        system_prompt = self._build_system_prompt(user, db, avatar=avatar)
        history = self._load_history(conversation_id, db)
        messages = [{"role": "system", "content": system_prompt}] + history
        yield from self.llm.chat_completion(messages, stream=True)


agent_engine = AgentEngine()
