import json
import time

import httpx

from backend.config import settings

_token_cache: dict = {}

FEISHU_BASE = "https://open.feishu.cn/open-apis"


def get_tenant_access_token() -> str:
    now = time.time()
    if _token_cache.get("expire_at", 0) > now + 60:
        return _token_cache["token"]
    resp = httpx.post(
        f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": settings.feishu_app_id, "app_secret": settings.feishu_app_secret},
        timeout=10,
    )
    data = resp.json()
    _token_cache["token"] = data["tenant_access_token"]
    _token_cache["expire_at"] = now + data.get("expire", 7200)
    return _token_cache["token"]


def send_text(open_id: str, text: str) -> None:
    token = get_tenant_access_token()
    httpx.post(
        f"{FEISHU_BASE}/im/v1/messages",
        params={"receive_id_type": "open_id"},
        headers={"Authorization": f"Bearer {token}"},
        json={"receive_id": open_id, "msg_type": "text", "content": json.dumps({"text": text})},
        timeout=10,
    )


def send_draft_card(open_id: str, draft_content: str, draft_id: int, prefix: str = "") -> None:
    token = get_tenant_access_token()
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "✍️ 草稿已生成"},
            "template": "blue",
        },
        "elements": [
            *(
                [{"tag": "div", "text": {"tag": "lark_md", "content": prefix}}]
                if prefix else []
            ),
            {"tag": "div", "text": {"tag": "lark_md", "content": draft_content}},
            {"tag": "hr"},
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "发布到社区"},
                        "type": "primary",
                        "value": {"action": "publish_draft", "draft_id": str(draft_id)},
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "放弃"},
                        "type": "danger",
                        "value": {"action": "discard_draft", "draft_id": str(draft_id)},
                    },
                ],
            },
        ],
    }
    httpx.post(
        f"{FEISHU_BASE}/im/v1/messages",
        params={"receive_id_type": "open_id"},
        headers={"Authorization": f"Bearer {token}"},
        json={"receive_id": open_id, "msg_type": "interactive", "content": json.dumps(card)},
        timeout=10,
    )
