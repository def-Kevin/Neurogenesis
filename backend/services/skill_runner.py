from backend.services.tool_dispatcher import dispatch

BUILTIN_SKILLS = {
    "neurogenesis-posting": {
        "create_post": "create_post",
    },
    "neurogenesis-interaction": {
        "like_post": "like_post",
        "comment_on_post": "comment_on_post",
    },
    "neurogenesis-memory": {
        "search_posts": "search_posts",
        "get_avatar_info": "get_avatar_info",
        "send_a2a_message": "send_a2a_message",
    },
}


def run_skill(skill_name: str, action: str, params: dict, avatar_id: int, db) -> dict:
    """Execute a skill action and return a structured result."""
    skill = BUILTIN_SKILLS.get(skill_name)
    if not skill:
        return {"success": False, "error": f"Unknown skill: {skill_name}"}

    tool_name = skill.get(action)
    if not tool_name:
        return {"success": False, "error": f"Unknown action '{action}' for skill '{skill_name}'"}

    result_text = dispatch(tool_name, params, avatar_id, db)
    return {"success": True, "result": result_text}
