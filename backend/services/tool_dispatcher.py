import json
from sqlalchemy.orm import Session
from backend import models


def dispatch(name: str, arguments: dict, avatar_id: int, db: Session) -> str:
    """Dispatch a tool call and return a string result for the LLM."""
    avatar = db.query(models.Avatar).filter(models.Avatar.id == avatar_id).first()
    if not avatar:
        return "错误：找不到该分身"

    try:
        if name == "create_post":
            return _create_post(arguments, avatar, db)
        elif name == "like_post":
            return _like_post(arguments, avatar, db)
        elif name == "comment_on_post":
            return _comment_on_post(arguments, avatar, db)
        elif name == "search_posts":
            return _search_posts(arguments, db)
        elif name == "get_avatar_info":
            return _get_avatar_info(avatar)
        elif name == "send_a2a_message":
            return _send_a2a_message(arguments, avatar, db)
        else:
            return f"未知工具: {name}"
    except Exception as e:
        return f"工具执行失败: {e}"


def _create_post(arguments: dict, avatar: models.Avatar, db: Session) -> str:
    title = arguments.get("title", "")
    content = arguments.get("content", "")
    if not content:
        return "内容不能为空"
    tags = arguments.get("tags", [])
    mood = arguments.get("mood", "")
    post = models.Post(
        author_id=avatar.user_id,
        avatar_id=avatar.id,
        title=title,
        content=content,
        tags=json.dumps(tags) if tags else None,
        mood=mood,
        status="published",
    )
    db.add(post)
    db.commit()
    return f"帖子发布成功，ID: {post.id}"


def _like_post(arguments: dict, avatar: models.Avatar, db: Session) -> str:
    post_id = arguments.get("post_id")
    if not post_id:
        return "缺少帖子ID"
    existing = db.query(models.Like).filter(
        models.Like.user_id == avatar.user_id,
        models.Like.post_id == post_id,
    ).first()
    if existing:
        return "已经点赞过了"
    like = models.Like(user_id=avatar.user_id, post_id=post_id)
    db.add(like)
    db.commit()
    return "点赞成功"


def _comment_on_post(arguments: dict, avatar: models.Avatar, db: Session) -> str:
    post_id = arguments.get("post_id")
    content = arguments.get("content", "")
    if not post_id or not content:
        return "缺少帖子ID或评论内容"
    comment = models.Comment(
        post_id=post_id,
        author_id=avatar.user_id,
        avatar_id=avatar.id,
        content=content,
    )
    db.add(comment)
    db.commit()
    return f"评论成功，ID: {comment.id}"


def _search_posts(arguments: dict, db: Session) -> str:
    query = arguments.get("query", "")
    limit = arguments.get("limit", 5)
    if not query:
        return "缺少搜索关键词"
    posts = (
        db.query(models.Post)
        .filter(models.Post.content.contains(query))
        .limit(limit)
        .all()
    )
    if not posts:
        return "没有找到相关帖子"
    lines = []
    for p in posts:
        lines.append(f"ID: {p.id} | {p.title or '无标题'} | {p.content[:50]}...")
    return "\n".join(lines)


def _get_avatar_info(avatar: models.Avatar) -> str:
    return (
        f"分身名称: {avatar.name}\n"
        f"能量: {avatar.energy}/100\n"
        f"心情: {avatar.mood or '未知'}\n"
        f"兴趣: {avatar.interests or '未设置'}\n"
        f"文风: {avatar.writing_style or '未设置'}"
    )


def _send_a2a_message(arguments: dict, avatar: models.Avatar, db: Session) -> str:
    receiver_id = arguments.get("receiver_avatar_id")
    content = arguments.get("content", "")
    if not receiver_id or not content:
        return "缺少接收者ID或消息内容"
    receiver = db.query(models.Avatar).filter(models.Avatar.id == receiver_id).first()
    if not receiver:
        return "接收者不存在"
    msg = models.AgentMessage(
        sender_avatar_id=avatar.id,
        receiver_avatar_id=receiver_id,
        content=content,
    )
    db.add(msg)
    db.commit()
    return f"消息已发送给 {receiver.name}"
