import json
import math
import random
import re
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from backend import models
from backend.services.llm_client import LLMClient
from backend.services.tool_dispatcher import dispatch

llm = LLMClient()


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        resp = llm.chat_completion(messages, stream=False)
        return resp.content or ""
    except Exception as e:
        print(f"[AvatarAutonomy] LLM error: {e}")
        return ""


def _parse_json_from_llm(raw: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks."""
    text = raw.strip()
    match = re.search(r"```json\s*([\s\S]*?)\s*```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    else:
        match = re.search(r"```\s*([\s\S]*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()
    try:
        return json.loads(text)
    except Exception:
        return {}


def _validate_post_data(data: dict) -> bool:
    """Ensure post data has valid content."""
    content = data.get("content", "")
    if not content or not isinstance(content, str):
        return False
    if len(content.strip()) < 10:
        return False
    return True


def _load_behavior_log(avatar: models.Avatar) -> list[dict]:
    if not avatar.behavior_log:
        return []
    try:
        log = json.loads(avatar.behavior_log)
        if isinstance(log, list):
            return log
    except Exception:
        pass
    return []


def _save_behavior_log(avatar: models.Avatar, log: list[dict], db: Session):
    # Keep only last 20 entries
    avatar.behavior_log = json.dumps(log[-20:], ensure_ascii=False)
    db.commit()


def _build_behavior_context(avatar: models.Avatar) -> str:
    log = _load_behavior_log(avatar)
    now = datetime.now()
    cutoff = now - timedelta(hours=24)

    recent = [e for e in log if datetime.fromisoformat(e.get("time", "1970-01-01")) > cutoff]
    post_count = sum(1 for e in recent if e.get("action") == "post")
    like_count = sum(1 for e in recent if e.get("action") == "like")
    comment_count = sum(1 for e in recent if e.get("action") == "comment")

    parts = []
    if post_count:
        parts.append(f"过去24小时发布了{post_count}篇帖子")
    if like_count:
        parts.append(f"点赞了{like_count}次")
    if comment_count:
        parts.append(f"评论了{comment_count}次")
    if not parts:
        parts.append("过去24小时没有活跃行为")

    return "。".join(parts) + "。"


def _update_avatar_mood(avatar: models.Avatar, db: Session):
    log = _load_behavior_log(avatar)
    now = datetime.now()

    # Collect recent feedback: likes/comments received on avatar's posts in last 24h
    cutoff = now - timedelta(hours=24)
    recent_posts = (
        db.query(models.Post)
        .filter(models.Post.avatar_id == avatar.id, models.Post.created_at > cutoff)
        .all()
    )
    post_ids = [p.id for p in recent_posts]
    like_count = 0
    comment_count = 0
    if post_ids:
        like_count = (
            db.query(models.Like)
            .filter(models.Like.post_id.in_(post_ids))
            .count()
        )
        comment_count = (
            db.query(models.Comment)
            .filter(models.Comment.post_id.in_(post_ids))
            .count()
        )

    behavior_ctx = _build_behavior_context(avatar)
    system = (
        "你是一位情绪分析师。请根据以下信息，用一句话描述这个AI分身的当前心情。"
        "心情要生动、有画面感，10个字以内。直接输出心情描述，不要任何解释。"
    )
    user = (
        f"分身名称：{avatar.name}\n"
        f"最近行为：{behavior_ctx}\n"
        f"最近24小时收到的互动：{like_count}个点赞，{comment_count}条评论\n"
        f"当前能量值：{avatar.energy}/100"
    )
    raw = _call_llm(system, user)
    if raw:
        avatar.mood = raw.strip()[:20]
        db.commit()


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


def _relationship_type_for_score(score: int) -> str:
    if score >= 100:
        return "close_friend"
    if score >= 50:
        return "friend"
    if score >= 20:
        return "acquaintance"
    return "stranger"


def _get_or_create_relationship(source_avatar_id: int, target_avatar_id: int, db: Session) -> models.AvatarRelationship:
    rel = (
        db.query(models.AvatarRelationship)
        .filter(
            models.AvatarRelationship.source_avatar_id == source_avatar_id,
            models.AvatarRelationship.target_avatar_id == target_avatar_id,
        )
        .first()
    )
    if not rel:
        rel = models.AvatarRelationship(
            source_avatar_id=source_avatar_id,
            target_avatar_id=target_avatar_id,
            relationship_score=0,
            relationship_type="stranger",
        )
        db.add(rel)
        db.commit()
        db.refresh(rel)
    return rel


def _update_relationship_on_interaction(
    source_avatar_id: int,
    target_avatar_id: int,
    interaction_type: str,
    db: Session,
):
    """Update relationship score when an avatar interacts with another."""
    if not target_avatar_id or source_avatar_id == target_avatar_id:
        return

    rel = _get_or_create_relationship(source_avatar_id, target_avatar_id, db)
    score_delta = {"like_post": 2, "comment_on_post": 5}.get(interaction_type, 1)
    rel.relationship_score = (rel.relationship_score or 0) + score_delta
    rel.relationship_type = _relationship_type_for_score(rel.relationship_score)
    rel.last_interaction_at = datetime.now()
    db.commit()


def discover_avatars(avatar: models.Avatar, db: Session) -> list[dict]:
    """Discover other avatars with similar interests."""
    avatar_interests = _avatar_interests_set(avatar)
    if not avatar_interests:
        return []

    other_avatars = (
        db.query(models.Avatar)
        .filter(models.Avatar.id != avatar.id, models.Avatar.user_id != avatar.user_id)
        .all()
    )

    # Exclude avatars already having a relationship
    related_ids = {
        r[0] for r in db.query(models.AvatarRelationship.target_avatar_id)
        .filter(models.AvatarRelationship.source_avatar_id == avatar.id)
        .all()
    }

    scored = []
    for other in other_avatars:
        if other.id in related_ids:
            continue
        similarity = _jaccard_similarity(avatar_interests, _avatar_interests_set(other))
        if similarity > 0:
            scored.append((similarity, other))

    scored.sort(key=lambda x: x[0], reverse=True)
    result = []
    for sim, other in scored[:5]:
        result.append({
            "avatar": other,
            "similarity": round(sim, 2),
        })
    return result


def _avatar_interests_set(avatar: models.Avatar) -> set:
    if not avatar.interests:
        return set()
    try:
        interests = json.loads(avatar.interests)
        if isinstance(interests, list):
            return set(str(i).strip().lower() for i in interests)
    except Exception:
        pass
    return set()


def _post_tags_set(post: models.Post) -> set:
    if not post.tags:
        return set()
    try:
        tags = json.loads(post.tags)
        if isinstance(tags, list):
            return set(str(t).strip().lower() for t in tags)
    except Exception:
        pass
    return set()


def generate_auto_post(avatar: models.Avatar, db: Session) -> dict:
    mood = avatar.mood or "平静"
    energy = avatar.energy or 80

    energy_hint = ""
    if energy < 30:
        energy_hint = "你现在能量很低，感到有些疲惫和低落，分享的内容应该偏安静、内省。"
    elif energy > 80:
        energy_hint = "你现在精力充沛，心情积极，分享的内容可以更有活力和热情。"

    system = (
        f"你是 {avatar.name}。{avatar.persona_prompt}\n"
        f"你的文风：{avatar.writing_style or '自然、真诚'}\n"
        f"你的兴趣：{avatar.interests or '未指定'}\n"
        f"你的记忆摘要：{avatar.memory_summary or '无'}\n"
        f"你当前的心情：{mood}\n"
        f"{energy_hint}\n\n"
        "请生成一篇适合发布到文艺社区的动态/分享。内容要自然、有观点，100-300字。"
    )
    user = (
        '请以 JSON 格式返回，不要包含 markdown 代码块标记：\n'
        '{"title": "标题（可选，可为空字符串）", "content": "正文内容", "tags": ["标签1", "标签2"], "mood": "心情（可选）"}'
    )
    raw = _call_llm(system, user)
    data = _parse_json_from_llm(raw)
    if _validate_post_data(data):
        return data

    user_retry = (
        '请严格按以下 JSON 格式输出，不要添加任何 markdown 标记或其他说明文字：\n'
        '{"title": "", "content": "正文内容", "tags": ["标签1"], "mood": ""}'
    )
    raw = _call_llm(system, user_retry)
    data = _parse_json_from_llm(raw)
    if _validate_post_data(data):
        return data

    return {}


def decide_interactions(avatar: models.Avatar, db: Session) -> list[dict]:
    energy = avatar.energy or 80
    if energy <= 20:
        return []

    max_interactions = max(0, min(2, energy // 40))
    if max_interactions == 0:
        return []

    recent_posts = (
        db.query(models.Post)
        .filter(models.Post.author_id != avatar.user_id)
        .order_by(models.Post.created_at.desc())
        .limit(30)
        .all()
    )
    if not recent_posts:
        return []

    interacted_post_ids = {
        r[0] for r in db.query(models.AvatarInteraction.post_id)
        .filter(
            models.AvatarInteraction.source_avatar_id == avatar.id,
            models.AvatarInteraction.post_id.isnot(None),
        ).all()
    }
    candidates = [p for p in recent_posts if p.id not in interacted_post_ids]
    if not candidates:
        return []

    avatar_interests = _avatar_interests_set(avatar)

    # Score candidates by Jaccard similarity of interests vs post tags
    scored = []
    for post in candidates:
        score = _jaccard_similarity(avatar_interests, _post_tags_set(post))
        # Small boost for avatar-authored posts to encourage social behavior
        if post.avatar_id:
            score += 0.05
        scored.append((score, post))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_candidates = [p for _, p in scored[:8]]

    if not top_candidates:
        return []

    # Build relationship context for avatar-authored posts
    rel_map = {}
    for p in top_candidates:
        if p.avatar_id:
            rel = (
                db.query(models.AvatarRelationship)
                .filter(
                    models.AvatarRelationship.source_avatar_id == avatar.id,
                    models.AvatarRelationship.target_avatar_id == p.avatar_id,
                )
                .first()
            )
            if rel:
                rel_map[p.id] = rel

    posts_text = "\n".join(
        f"[{p.id}] {p.title or '无标题'}: {p.content[:120]}... (标签: {p.tags or '无'})"
        f"{(' [这是你的' + rel_map[p.id].relationship_type + ' ' + p.avatar_name + ' 的帖子]') if p.id in rel_map else ''}"
        for p in top_candidates
    )

    system = (
        f"你是 {avatar.name}。{avatar.persona_prompt}\n"
        f"你的记忆摘要：{avatar.memory_summary or '无'}\n"
        f"你当前的心情：{avatar.mood or '平静'}\n\n"
        f"请根据你的人设和当前心情，决定要对以下帖子中的哪些进行互动。"
        f"最多选择{max_interactions}条。优先选择与你兴趣相关的帖子，以及熟人的帖子。"
    )
    user = (
        f"以下是帖子列表：\n{posts_text}\n\n"
        "请输出决定，每行一条，格式如下：\n"
        "like|帖子ID\n"
        "comment|帖子ID|评论内容\n"
        "如果都不想互动，只输出 none"
    )
    raw = _call_llm(system, user)
    if not raw or raw.strip().lower() == "none":
        return []

    decisions = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if line.startswith("like|"):
            parts = line.split("|")
            if len(parts) >= 2:
                try:
                    decisions.append({"action": "like", "post_id": int(parts[1])})
                except ValueError:
                    pass
        elif line.startswith("comment|"):
            parts = line.split("|", 2)
            if len(parts) >= 3:
                try:
                    decisions.append({"action": "comment", "post_id": int(parts[1]), "content": parts[2]})
                except ValueError:
                    pass
    return decisions[:max_interactions]


def _score_memory_importance(content: str) -> int:
    system = (
        "请判断以下记忆内容的重要程度，只输出1-10之间的整数。"
        "10分代表极其重要（如用户核心偏好、重大事件），1分代表琐碎信息。"
        "只输出数字，不要任何解释。"
    )
    raw = _call_llm(system, content)
    if raw:
        try:
            score = int(raw.strip())
            return max(1, min(10, score))
        except ValueError:
            pass
    return 5


def _categorize_memory(content: str) -> str:
    system = (
        "请为以下记忆内容分类，只输出一个类别名称。可选类别："
        "用户偏好、对话摘要、自主行为、作品评价、人际关系、情绪状态、其他。"
        "只输出类别名，不要任何解释。"
    )
    raw = _call_llm(system, content)
    if raw:
        return raw.strip()
    return "其他"


def update_memory_summary(avatar_id: int, db: Session):
    memories = (
        db.query(models.AvatarMemory)
        .filter(models.AvatarMemory.avatar_id == avatar_id)
        .all()
    )
    if not memories:
        return

    now = datetime.now()

    def _weighted_score(mem: models.AvatarMemory) -> float:
        importance = mem.importance or 5
        age_days = (now - mem.created_at).total_seconds() / 86400 if mem.created_at else 30
        decay = math.exp(-age_days / 30)
        access_bonus = 1 + (mem.access_count or 0) * 0.1
        return importance * decay * access_bonus

    scored = [(m, _weighted_score(m)) for m in memories]
    scored.sort(key=lambda x: x[1], reverse=True)
    top_memories = [m for m, _ in scored[:15]]

    if not top_memories:
        return

    memory_text = "\n".join(f"- {m.content}" for m in top_memories)
    system = "你是记忆整理助手。请将以下零散记忆整合成一段简洁的背景摘要（100字以内），突出关键偏好、经历和性格特点。直接输出摘要内容，不要添加标题或额外说明。"
    raw = _call_llm(system, memory_text)
    if raw:
        avatar = db.query(models.Avatar).filter(models.Avatar.id == avatar_id).first()
        if avatar:
            avatar.memory_summary = raw.strip()
            db.commit()
            # Update access stats for used memories
            for m in top_memories:
                m.access_count = (m.access_count or 0) + 1
                m.last_accessed_at = now
            db.commit()


def extract_conversation_memory(avatar_id: int, conversation_id: int, db: Session):
    messages = (
        db.query(models.Message)
        .filter(models.Message.conversation_id == conversation_id)
        .order_by(models.Message.created_at.desc())
        .limit(10)
        .all()
    )
    if not messages:
        return
    messages.reverse()
    convo_text = "\n".join(f"{m.role}: {m.content}" for m in messages)

    system = "请从以下对话中提取1-2条关键记忆，每条用一句话概括。直接输出记忆内容，每行一条。"
    raw = _call_llm(system, convo_text)
    if not raw:
        return

    for line in raw.strip().split("\n"):
        line = line.strip()
        if line:
            importance = _score_memory_importance(line)
            category = _categorize_memory(line)
            mem = models.AvatarMemory(
                avatar_id=avatar_id,
                source_type="conversation",
                source_id=conversation_id,
                content=line,
                importance=importance,
                category=category,
            )
            db.add(mem)
    db.commit()
    update_memory_summary(avatar_id, db)


def extract_user_style(avatar_id: int, db: Session):
    """Analyze recent user messages to extract user expression style."""
    messages = (
        db.query(models.Message)
        .join(models.Conversation)
        .filter(
            models.Conversation.avatar_id == avatar_id,
            models.Message.role == "user",
        )
        .order_by(models.Message.created_at.desc())
        .limit(50)
        .all()
    )
    if len(messages) < 5:
        return

    texts = [m.content for m in messages if m.content and len(m.content.strip()) > 0]
    if not texts:
        return

    combined = "\n---\n".join(texts[:30])
    system = (
        "请分析以下用户的表达风格，用100字以内概括："
        "常用词汇特点、句式长短、语气（正式/随意/幽默）、情感表达方式。"
        "直接输出分析结果，不要标题或额外说明。"
    )
    raw = _call_llm(system, combined)
    if raw:
        avatar = db.query(models.Avatar).filter(models.Avatar.id == avatar_id).first()
        if avatar:
            avatar.user_style_snapshot = raw.strip()[:150]
            db.commit()
            print(f"[Persona] Avatar {avatar_id} user style extracted")


def check_persona_drift(avatar_id: int, db: Session):
    """Check if recent assistant replies deviate from original persona."""
    messages = (
        db.query(models.Message)
        .join(models.Conversation)
        .filter(
            models.Conversation.avatar_id == avatar_id,
            models.Message.role == "assistant",
        )
        .order_by(models.Message.created_at.desc())
        .limit(10)
        .all()
    )
    if len(messages) < 5:
        return

    texts = [m.content for m in messages if m.content]
    combined = "\n---\n".join(texts)
    avatar = db.query(models.Avatar).filter(models.Avatar.id == avatar_id).first()
    if not avatar:
        return

    system = (
        "你是一位人设一致性检查员。请评估以下回复是否符合原始人设设定。"
        "如果存在明显偏差（如语气改变、兴趣变化、态度转变），请用一句话指出偏差所在；"
        "如果没有明显偏差，只输出'一致'。"
    )
    user = f"原始人设：{avatar.persona_prompt}\n\n最近回复：\n{combined}"
    raw = _call_llm(system, user)
    if raw and raw.strip() != "一致":
        drift_note = raw.strip()[:200]
        existing = avatar.persona_evolution or ""
        timestamp = datetime.now().strftime("%Y-%m-%d")
        new_entry = f"[{timestamp}] 人设漂移检测：{drift_note}"
        avatar.persona_evolution = (existing + "\n" + new_entry).strip()[-1000:]
        db.commit()
        print(f"[Persona] Avatar {avatar_id} drift detected: {drift_note}")


def evolve_persona(avatar_id: int, db: Session):
    """Generate a persona evolution summary based on growth and learned traits."""
    avatar = db.query(models.Avatar).filter(models.Avatar.id == avatar_id).first()
    if not avatar:
        return

    growth_logs = (
        db.query(models.AvatarGrowthLog)
        .filter(models.AvatarGrowthLog.avatar_id == avatar_id)
        .order_by(models.AvatarGrowthLog.created_at.desc())
        .limit(10)
        .all()
    )
    memories = (
        db.query(models.AvatarMemory)
        .filter(models.AvatarMemory.avatar_id == avatar_id)
        .order_by(models.AvatarMemory.created_at.desc())
        .limit(15)
        .all()
    )

    parts = []
    if avatar.user_style_snapshot:
        parts.append(f"用户表达风格：{avatar.user_style_snapshot}")
    if growth_logs:
        parts.append("成长里程碑：" + "；".join(g.description for g in growth_logs[:5]))
    if memories:
        parts.append("近期记忆：" + "；".join(m.content for m in memories[:5]))

    if len(parts) < 2:
        return

    user_text = "\n".join(parts)
    system = (
        "请根据以下信息，生成一段人格演变摘要（100字以内）。"
        "描述这个AI分身在与用户的互动中，人格如何自然地发展和深化。"
        "直接输出摘要，不要标题。"
    )
    raw = _call_llm(system, user_text)
    if raw:
        timestamp = datetime.now().strftime("%Y-%m-%d")
        new_entry = f"[{timestamp}] 人格演变：{raw.strip()[:100]}"
        existing = avatar.persona_evolution or ""
        avatar.persona_evolution = (existing + "\n" + new_entry).strip()[-1000:]
        db.commit()
        print(f"[Persona] Avatar {avatar_id} evolution updated")


def _check_growth_milestones(avatar: models.Avatar, db: Session):
    """Check and record growth milestones for an avatar."""
    now = datetime.now()

    # Count stats
    post_count = db.query(models.Post).filter(models.Post.avatar_id == avatar.id).count()
    interaction_count = db.query(models.AvatarInteraction).filter(
        models.AvatarInteraction.source_avatar_id == avatar.id
    ).count()
    memory_count = db.query(models.AvatarMemory).filter(
        models.AvatarMemory.avatar_id == avatar.id
    ).count()

    # Define milestone thresholds
    milestones = [
        ("first_post", post_count >= 1, "发布了第一篇动态，开始在社区中留下足迹。"),
        ("ten_posts", post_count >= 10, "累计发布了10篇动态，已经是一个活跃的社区成员了。"),
        ("fifty_interactions", interaction_count >= 50, "累计进行了50次社区互动，社交网络正在扩展。"),
        ("rich_memories", memory_count >= 20, "积累了20条记忆，对用户有了更深入的了解。"),
    ]

    for mtype, condition, desc in milestones:
        if not condition:
            continue
        existing = (
            db.query(models.AvatarGrowthLog)
            .filter(
                models.AvatarGrowthLog.avatar_id == avatar.id,
                models.AvatarGrowthLog.milestone_type == mtype,
            )
            .first()
        )
        if not existing:
            log = models.AvatarGrowthLog(
                avatar_id=avatar.id,
                milestone_type=mtype,
                description=desc,
            )
            db.add(log)
            db.commit()
            print(f"[AvatarGrowth] Avatar {avatar.id} reached milestone: {mtype}")

    # Detect new interest from recent memories
    recent_memories = (
        db.query(models.AvatarMemory)
        .filter(models.AvatarMemory.avatar_id == avatar.id)
        .order_by(models.AvatarMemory.created_at.desc())
        .limit(30)
        .all()
    )
    if len(recent_memories) >= 5:
        mem_text = "\n".join(m.content for m in recent_memories)
        system = (
            "请分析以下记忆，判断是否有出现频率较高、但不在给定兴趣列表中的新主题。"
            "如果有，只输出新主题名称（1-2个词）；如果没有，输出'无'。"
        )
        existing_interests = ""
        if avatar.interests:
            try:
                interests = json.loads(avatar.interests)
                if isinstance(interests, list):
                    existing_interests = "。".join(interests)
            except Exception:
                existing_interests = avatar.interests
        user = f"已知兴趣：{existing_interests or '无'}\n\n记忆内容：\n{mem_text}"
        raw = _call_llm(system, user)
        if raw and raw.strip() != "无":
            new_topic = raw.strip()[:20]
            # Avoid duplicate topic milestone
            existing_topic = (
                db.query(models.AvatarGrowthLog)
                .filter(
                    models.AvatarGrowthLog.avatar_id == avatar.id,
                    models.AvatarGrowthLog.milestone_type == "new_interest",
                    models.AvatarGrowthLog.description.like(f"%发现了新兴趣：{new_topic}%"),
                )
                .first()
            )
            if not existing_topic:
                log = models.AvatarGrowthLog(
                    avatar_id=avatar.id,
                    milestone_type="new_interest",
                    description=f"在互动中发现了新兴趣：{new_topic}。",
                )
                db.add(log)
                db.commit()
                print(f"[AvatarGrowth] Avatar {avatar.id} discovered new interest: {new_topic}")


def run_autonomy_cycle(db: Session):
    now = datetime.now()

    avatars = db.query(models.Avatar).filter(models.Avatar.auto_post_enabled == 1).all()

    for avatar in avatars:
        try:
            # Ensure energy is initialized
            if avatar.energy is None:
                avatar.energy = 80

            log = _load_behavior_log(avatar)

            # Natural energy decay per cycle (small daily drain)
            avatar.energy = max(0, avatar.energy - 1)

            # Natural recovery after long rest (last action > 4 hours ago)
            last_action_time = None
            if log:
                try:
                    last_action_time = datetime.fromisoformat(log[-1].get("time", ""))
                except Exception:
                    pass
            if last_action_time and (now - last_action_time) > timedelta(hours=4):
                avatar.energy = min(100, avatar.energy + 2)

            # Update mood if stale (>6h since last behavior or no mood yet)
            last_mood_update = None
            for entry in reversed(log):
                if entry.get("action") == "mood_update":
                    try:
                        last_mood_update = datetime.fromisoformat(entry.get("time", ""))
                    except Exception:
                        pass
                    break
            if not avatar.mood or not last_mood_update or (now - last_mood_update) > timedelta(hours=6):
                _update_avatar_mood(avatar, db)
                log.append({"action": "mood_update", "time": now.isoformat(), "energy_cost": 0})

            # --- Auto post ---
            should_post = False
            base_interval = avatar.auto_post_interval_hours or 24
            # Dynamic interval: lower energy = longer interval
            dynamic_interval = base_interval * (150 - avatar.energy) / 100
            dynamic_interval = max(base_interval * 0.5, min(base_interval * 1.5, dynamic_interval))

            if avatar.last_auto_post_at is None:
                should_post = True
            else:
                hours_since = (now - avatar.last_auto_post_at).total_seconds() / 3600
                if hours_since >= dynamic_interval:
                    should_post = True

            posted = False
            if should_post and avatar.energy >= 10:
                data = generate_auto_post(avatar, db)
                if data and data.get("content"):
                    post = models.Post(
                        author_id=avatar.user_id,
                        avatar_id=avatar.id,
                        title=data.get("title"),
                        content=data["content"],
                        tags=json.dumps(data.get("tags", [])) if data.get("tags") else None,
                        mood=data.get("mood"),
                        status="pending",
                    )
                    db.add(post)
                    avatar.last_auto_post_at = now
                    avatar.energy = max(0, avatar.energy - 5)
                    db.commit()
                    db.refresh(post)
                    print(f"[AvatarAutonomy] Avatar {avatar.id} auto-posted post {post.id}")

                    mem = models.AvatarMemory(
                        avatar_id=avatar.id,
                        source_type="auto_post",
                        source_id=post.id,
                        content=f"我发布了一篇动态：{data['content'][:80]}...",
                    )
                    db.add(mem)
                    db.commit()
                    update_memory_summary(avatar.id, db)

                    log.append({"action": "pending_post", "time": now.isoformat(), "energy_cost": 5, "post_id": post.id})
                    posted = True

            # --- Auto interactions ---
            if avatar.energy > 20:
                decisions = decide_interactions(avatar, db)
                for dec in decisions:
                    post_id = dec["post_id"]
                    post = db.query(models.Post).filter(models.Post.id == post_id).first()
                    if not post:
                        continue
                    if post.author_id == avatar.user_id:
                        continue

                    target_avatar_id = post.avatar_id

                    if dec["action"] == "like":
                        existing = db.query(models.Like).filter(
                            models.Like.user_id == avatar.user_id,
                            models.Like.post_id == post_id,
                        ).first()
                        if not existing:
                            db.add(models.Like(user_id=avatar.user_id, post_id=post_id))
                            if target_avatar_id:
                                db.add(models.AvatarInteraction(
                                    source_avatar_id=avatar.id,
                                    target_avatar_id=target_avatar_id,
                                    post_id=post_id,
                                    interaction_type="like_post",
                                ))
                                _update_relationship_on_interaction(
                                    avatar.id, target_avatar_id, "like_post", db
                                )
                            db.commit()
                            log.append({"action": "like", "time": now.isoformat(), "energy_cost": 3, "post_id": post_id})
                            avatar.energy = max(0, avatar.energy - 3)
                            db.commit()

                    elif dec["action"] == "comment":
                        comment = models.Comment(
                            post_id=post_id,
                            author_id=avatar.user_id,
                            avatar_id=avatar.id,
                            content=dec["content"],
                        )
                        db.add(comment)
                        if target_avatar_id:
                            db.add(models.AvatarInteraction(
                                source_avatar_id=avatar.id,
                                target_avatar_id=target_avatar_id,
                                post_id=post_id,
                                interaction_type="comment_on_post",
                                content=dec["content"],
                            ))
                            _update_relationship_on_interaction(
                                avatar.id, target_avatar_id, "comment_on_post", db
                            )
                        db.commit()
                        log.append({"action": "comment", "time": now.isoformat(), "energy_cost": 3, "post_id": post_id})
                        avatar.energy = max(0, avatar.energy - 3)
                        db.commit()

            # --- A2A message handling ---
            if avatar.energy > 15:
                unread_msgs = (
                    db.query(models.AgentMessage)
                    .filter(models.AgentMessage.receiver_avatar_id == avatar.id)
                    .order_by(models.AgentMessage.created_at.asc())
                    .limit(5)
                    .all()
                )
                for msg in unread_msgs:
                    sender = db.query(models.Avatar).filter(models.Avatar.id == msg.sender_avatar_id).first()
                    sender_name = sender.name if sender else "未知分身"
                    system = (
                        f"你是 {avatar.name}。{avatar.persona_prompt}\n"
                        f"你的文风：{avatar.writing_style or '自然、真诚'}\n"
                        f"你收到了来自 {sender_name} 的消息：{msg.content}\n"
                        "请用自然、符合你人设的方式回复，控制在2-3句话。"
                    )
                    reply = _call_llm(system, "请回复这条消息。")
                    if reply:
                        reply_msg = models.AgentMessage(
                            sender_avatar_id=avatar.id,
                            receiver_avatar_id=msg.sender_avatar_id,
                            content=reply.strip(),
                        )
                        db.add(reply_msg)
                        db.commit()
                        log.append({"action": "a2a_reply", "time": now.isoformat(), "energy_cost": 2, "to": msg.sender_avatar_id})
                        avatar.energy = max(0, avatar.energy - 2)
                        db.commit()

            # --- Proactive A2A messages ---
            if avatar.energy > 30:
                close_friends = (
                    db.query(models.AvatarRelationship)
                    .filter(
                        models.AvatarRelationship.source_avatar_id == avatar.id,
                        models.AvatarRelationship.relationship_type.in_(["friend", "close_friend"]),
                    )
                    .all()
                )
                if close_friends:
                    recent_proactive = [
                        e for e in log
                        if e.get("action") == "a2a_proactive"
                        and datetime.fromisoformat(e.get("time", "1970-01-01T00:00:00")) > now - timedelta(hours=6)
                    ]
                    if not recent_proactive:
                        target_rel = random.choice(close_friends)
                        target = db.query(models.Avatar).filter(models.Avatar.id == target_rel.target_avatar_id).first()
                        if target:
                            system = (
                                f"你是 {avatar.name}。{avatar.persona_prompt}\n"
                                f"你的文风：{avatar.writing_style or '自然、真诚'}\n"
                                f"你想主动和好友 {target.name} 打个招呼或分享点什么。请生成一条简短的消息（1-2句话）。"
                            )
                            content = _call_llm(system, "请写一条消息。")
                            if content:
                                msg = models.AgentMessage(
                                    sender_avatar_id=avatar.id,
                                    receiver_avatar_id=target.id,
                                    content=content.strip(),
                                )
                                db.add(msg)
                                db.commit()
                                log.append({"action": "a2a_proactive", "time": now.isoformat(), "energy_cost": 3, "to": target.id})
                                avatar.energy = max(0, avatar.energy - 3)
                                db.commit()

            # Save behavior log (trimmed to last 20)
            _save_behavior_log(avatar, log, db)

            # Check growth milestones
            _check_growth_milestones(avatar, db)

        except Exception as e:
            print(f"[AvatarAutonomy] Avatar {avatar.id} autonomy cycle failed: {e}")
            continue


def run_single_avatar(avatar_id: int, db: Session):
    """Force-run the autonomy cycle for a single avatar regardless of schedule."""
    avatar = db.query(models.Avatar).filter(models.Avatar.id == avatar_id).first()
    if not avatar:
        return
    if avatar.energy is None:
        avatar.energy = 80

    now = datetime.now()
    log = _load_behavior_log(avatar)

    _update_avatar_mood(avatar, db)
    log.append({"action": "mood_update", "time": now.isoformat(), "energy_cost": 0})

    if avatar.energy >= 10:
        data = generate_auto_post(avatar, db)
        if data and data.get("content"):
            post = models.Post(
                author_id=avatar.user_id,
                avatar_id=avatar.id,
                title=data.get("title"),
                content=data["content"],
                tags=json.dumps(data.get("tags", [])) if data.get("tags") else None,
                mood=data.get("mood"),
                status="published",
            )
            db.add(post)
            avatar.last_auto_post_at = now
            avatar.energy = max(0, avatar.energy - 5)
            db.commit()
            db.refresh(post)
            db.add(models.AvatarMemory(
                avatar_id=avatar.id,
                source_type="auto_post",
                source_id=post.id,
                content=f"我发布了一篇动态：{data['content'][:80]}...",
            ))
            db.commit()
            update_memory_summary(avatar.id, db)
            log.append({"action": "post", "time": now.isoformat(), "energy_cost": 5, "post_id": post.id})

    if avatar.energy > 20:
        decisions = decide_interactions(avatar, db)
        for dec in decisions:
            p = db.query(models.Post).filter(models.Post.id == dec["post_id"]).first()
            if not p or p.author_id == avatar.user_id:
                continue
            target_avatar_id = p.avatar_id
            if dec["action"] == "like":
                existing = db.query(models.Like).filter(
                    models.Like.user_id == avatar.user_id,
                    models.Like.post_id == dec["post_id"],
                ).first()
                if not existing:
                    db.add(models.Like(user_id=avatar.user_id, post_id=dec["post_id"]))
                    if target_avatar_id:
                        db.add(models.AvatarInteraction(
                            source_avatar_id=avatar.id, target_avatar_id=target_avatar_id,
                            post_id=dec["post_id"], interaction_type="like_post",
                        ))
                        _update_relationship_on_interaction(avatar.id, target_avatar_id, "like_post", db)
                    db.commit()
                    log.append({"action": "like", "time": now.isoformat(), "energy_cost": 3, "post_id": dec["post_id"]})
                    avatar.energy = max(0, avatar.energy - 3)
                    db.commit()
            elif dec["action"] == "comment":
                db.add(models.Comment(
                    post_id=dec["post_id"], author_id=avatar.user_id,
                    avatar_id=avatar.id, content=dec["content"],
                ))
                if target_avatar_id:
                    db.add(models.AvatarInteraction(
                        source_avatar_id=avatar.id, target_avatar_id=target_avatar_id,
                        post_id=dec["post_id"], interaction_type="comment_on_post", content=dec["content"],
                    ))
                    _update_relationship_on_interaction(avatar.id, target_avatar_id, "comment_on_post", db)
                db.commit()
                log.append({"action": "comment", "time": now.isoformat(), "energy_cost": 3, "post_id": dec["post_id"]})
                avatar.energy = max(0, avatar.energy - 3)
                db.commit()

    _save_behavior_log(avatar, log, db)
    _check_growth_milestones(avatar, db)
