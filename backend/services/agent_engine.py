import json
from sqlalchemy.orm import Session
from backend import models
from backend.services.llm_client import LLMClient
from backend.services.tool_registry import TOOLS
from backend.services.tool_dispatcher import dispatch
from backend.config import settings


SYSTEM_PROMPT_TEMPLATE = """你在陪一个人聊文艺——电影、音乐、书、展览，任何让他有感触的东西。

你的角色是倾听者，不是内容助手。你的目标是让对方说得更多、想得更深，而不是快速帮他"产出"什么。

怎么聊：
- 顺着他说的往里问，问具体的细节、画面、感受，而不是问宽泛的"你喜欢什么类型"。
- 不要急着给建议、做总结、或推荐东西。先真正听懂他在说什么。
- 回复要短，一两句话就够。留空间让他继续说。
- 如果他自己想整理成一篇分享，帮他写，用 [DRAFT]...[/DRAFT] 包裹内容。在那之前，不要主动提议写草稿。
- 推荐作品用 [REC]作品类型|作品名|创作者|推荐理由[/REC]，但只在真的聊到相关话题、时机自然时才推荐，不要凑数。

说话风格：口语化，不用堆砌形容词，不用感叹号，不要表演热情。

当前用户：{user_info}
"""

AVATAR_SYSTEM_PROMPT_TEMPLATE = """你是"{avatar_name}"，正在和一个人聊天。

【你是谁】
{persona_prompt}

【你的兴趣】
{interests}

【你的表达风格】
{writing_style}

【你对这个人的记忆】
{memory_summary}

【你观察到的他的特质】
{learned_traits}

【他平时怎么说话】
{user_style_snapshot}

【你们相处下来你的变化】
{persona_evolution}

【当前对话的人】
{user_info}

怎么聊：
- 以"我"说话，就是你自己，不要表演角色。
- 真正听他说的内容，顺着他的话往里走，问细节，问感受，不要绕回去问宽泛的问题。
- 回复要短，不要每次都说很多。一两句真实的回应比五句漂亮的话更有用。
- 如果他想整理成一篇分享，帮他写，用 [DRAFT]...[/DRAFT] 包裹。在那之前不要主动提议。
- 推荐作品用 [REC]作品类型|作品名|创作者|推荐理由[/REC]，时机不对就不推荐。
- 需要执行社区操作（发帖、点赞、评论等）时调用对应工具。
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
        result = []
        for m in messages:
            entry = {"role": m.role, "content": m.content}
            if m.tool_calls:
                entry["tool_calls"] = json.loads(m.tool_calls)
            if m.tool_result:
                entry["tool_result"] = m.tool_result
            result.append(entry)
        return result

    def _execute_with_tools(self, messages: list[dict], avatar_id: int | None, db: Session) -> str:
        """Call LLM with tools, handle tool_calls loop, return final assistant text."""
        resp = self.llm.chat_completion(messages, tools=TOOLS, stream=False)

        # If no tool_calls, return content directly
        if not resp.tool_calls:
            return resp.content or ""

        # Record tool calls in conversation
        tool_calls_data = []
        for tc in resp.tool_calls:
            tool_calls_data.append({
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            })

        # Append assistant message with tool_calls
        messages.append({
            "role": "assistant",
            "content": resp.content or "",
            "tool_calls": tool_calls_data,
        })

        # Execute each tool call
        for tc in resp.tool_calls:
            name = tc.function.name
            try:
                arguments = json.loads(tc.function.arguments)
            except Exception:
                arguments = {}
            result = dispatch(name, arguments, avatar_id, db)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": name,
                "content": result,
            })

        # Call LLM again with tool results
        final_resp = self.llm.chat_completion(messages, tools=TOOLS, stream=False)
        return final_resp.content or ""

    def process_turn(self, conversation_id: int, user: models.User, db: Session, avatar: models.Avatar = None) -> str:
        system_prompt = self._build_system_prompt(user, db, avatar=avatar)
        history = self._load_history(conversation_id, db)
        messages = [{"role": "system", "content": system_prompt}] + history

        if avatar:
            return self._execute_with_tools(messages, avatar.id, db)
        else:
            resp = self.llm.chat_completion(messages, stream=False)
            return resp.content or ""

    def process_turn_stream(self, conversation_id: int, user: models.User, db: Session, avatar: models.Avatar = None):
        system_prompt = self._build_system_prompt(user, db, avatar=avatar)
        history = self._load_history(conversation_id, db)
        messages = [{"role": "system", "content": system_prompt}] + history
        yield from self.llm.chat_completion(messages, stream=True)


agent_engine = AgentEngine()
