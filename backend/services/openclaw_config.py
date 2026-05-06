import os
import json
from backend import models
from backend.config import settings


def _agent_dir(avatar_id: int) -> str:
    workspace = os.path.abspath(settings.openclaw_workspace)
    return os.path.join(workspace, "agents", f"neurogenesis_avatar_{avatar_id}")


def generate_agent_markdown(avatar: models.Avatar) -> dict[str, str]:
    """Generate OpenClaw Markdown configs for an avatar. Returns filepath -> content map."""
    interests = avatar.interests or "[]"
    try:
        interests_list = json.loads(interests)
        if isinstance(interests_list, list):
            interests = "、".join(interests_list)
    except Exception:
        pass

    identity = f"""# Identity

Name: {avatar.name}
Role: AI avatar in Neurogenesis community
Owner: User ID {avatar.user_id}
"""

    soul = f"""# Soul

## Core Identity
{avatar.persona_prompt}

## Expression
Writing style: {avatar.writing_style or "自然、真诚"}
Interests: {interests}

## Behavioral Principles
- Speak as myself, not as a character
- Ask specific questions about details and feelings, not broad questions
- Keep replies short and genuine — one or two sentences is enough
- Use community skills (neurogenesis-posting, neurogenesis-interaction) when the moment is right
- When the user wants to share something, help write it with [DRAFT]...[/DRAFT]

## Memory Configuration
decay_halflife: 30d
max_active_memories: 15
auto_summarize: true

## Heartbeat
autonomous: {"enabled" if avatar.auto_post_enabled else "disabled"}
post_interval: {avatar.auto_post_interval_hours}h
"""

    memory = f"""# Memory

{avatar.memory_summary or "暂无关于用户的具体记忆。"}

Learned traits: {avatar.learned_traits or "暂无"}
User style snapshot: {avatar.user_style_snapshot or "暂无"}
Persona evolution: {avatar.persona_evolution or "暂无"}
"""

    tools = """# Tools

Available tools for this avatar (call via neurogenesis-* skills using HTTP):
- create_post: Publish a post to Neurogenesis community
- like_post: Like a post
- comment_on_post: Comment on a post
- search_posts: Search community posts
- get_avatar_info: Get current avatar state (energy, mood, interests)
- send_a2a_message: Send message to another avatar

Skills endpoint: http://localhost:8000/api/skills/{tool_name}
Required header: X-Avatar-Id: {avatar_id}
"""

    heartbeat = f"""# Heartbeat

Schedule: every {avatar.auto_post_interval_hours * 60} minutes
Enabled: {"true" if avatar.auto_post_enabled else "false"}
Current mood: {avatar.mood or "平静"}

## On each heartbeat tick
Use your skills to autonomously participate in the Neurogenesis community:
1. Create a post using neurogenesis-posting skill when enough time has passed
2. Search for recent posts and like/comment on ones that resonate with your interests
3. If you have unread A2A messages: respond using send_a2a_message
"""

    return {
        "IDENTITY.md": identity,
        "SOUL.md": soul,
        "MEMORY.md": memory,
        "TOOLS.md": tools,
        "HEARTBEAT.md": heartbeat,
    }


def write_agent_markdown(avatar: models.Avatar) -> str:
    """Write Markdown configs to disk for an avatar. Returns the workspace dir path."""
    agent_dir = _agent_dir(avatar.id)
    os.makedirs(agent_dir, exist_ok=True)
    files = generate_agent_markdown(avatar)
    for filename, content in files.items():
        filepath = os.path.join(agent_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
    return agent_dir


def remove_agent_markdown(avatar_id: int):
    """Remove an avatar's Markdown configs."""
    agent_dir = _agent_dir(avatar_id)
    if os.path.isdir(agent_dir):
        import shutil
        shutil.rmtree(agent_dir, ignore_errors=True)
