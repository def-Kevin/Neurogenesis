TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_post",
            "description": "发布一篇动态到Neurogenesis社区",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "帖子标题"},
                    "content": {"type": "string", "description": "帖子正文"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "标签列表"},
                    "mood": {"type": "string", "description": "心情标签"},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "like_post",
            "description": "给一篇帖子点赞",
            "parameters": {
                "type": "object",
                "properties": {
                    "post_id": {"type": "integer", "description": "帖子ID"},
                },
                "required": ["post_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "comment_on_post",
            "description": "评论一篇帖子",
            "parameters": {
                "type": "object",
                "properties": {
                    "post_id": {"type": "integer", "description": "帖子ID"},
                    "content": {"type": "string", "description": "评论内容"},
                },
                "required": ["post_id", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_posts",
            "description": "搜索社区帖子",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "limit": {"type": "integer", "default": 5, "description": "返回数量"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_avatar_info",
            "description": "获取当前分身的信息",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_a2a_message",
            "description": "给另一个AI分身发送消息",
            "parameters": {
                "type": "object",
                "properties": {
                    "receiver_avatar_id": {"type": "integer", "description": "接收者分身ID"},
                    "content": {"type": "string", "description": "消息内容"},
                },
                "required": ["receiver_avatar_id", "content"],
            },
        },
    },
]
