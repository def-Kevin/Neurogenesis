import threading
from datetime import datetime
from backend.database import SessionLocal
from backend import models
from backend.services.llm_client import LLMClient
from backend.services.tool_registry import TOOLS
from backend.services.tool_dispatcher import dispatch

llm = LLMClient()


def run_subagent_task(subagent_id: int):
    """Run a sub-agent task synchronously in a background thread."""
    db = SessionLocal()
    try:
        sub = db.query(models.AvatarSubAgent).filter(models.AvatarSubAgent.id == subagent_id).first()
        if not sub:
            return

        parent = db.query(models.Avatar).filter(models.Avatar.id == sub.parent_avatar_id).first()
        if not parent:
            sub.status = "failed"
            sub.result = "Parent avatar not found"
            db.commit()
            return

        system = (
            f"你是 {parent.name} 的子分身，任务名称：{sub.name}\n"
            f"父分身人设：{parent.persona_prompt}\n"
            f"你的任务：{sub.task}\n"
            "你可以使用社区工具来完成任务。"
            "请直接输出任务结果，不要添加额外说明。"
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"开始执行任务：{sub.task}"},
        ]

        resp = llm.chat_completion(messages, tools=TOOLS, stream=False)

        # Handle tool calls if any
        if resp.tool_calls:
            messages.append({
                "role": "assistant",
                "content": resp.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in resp.tool_calls
                ],
            })
            for tc in resp.tool_calls:
                name = tc.function.name
                try:
                    arguments = __import__("json").loads(tc.function.arguments)
                except Exception:
                    arguments = {}
                result = dispatch(name, arguments, parent.id, db)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": result,
                })
            final_resp = llm.chat_completion(messages, tools=TOOLS, stream=False)
            result_text = final_resp.content or ""
        else:
            result_text = resp.content or ""

        sub.result = result_text.strip()
        sub.status = "completed"
        sub.completed_at = datetime.now()
        db.commit()
        print(f"[SubAgent] Sub-agent {subagent_id} completed: {sub.name}")
    except Exception as e:
        print(f"[SubAgent] Sub-agent {subagent_id} failed: {e}")
        sub = db.query(models.AvatarSubAgent).filter(models.AvatarSubAgent.id == subagent_id).first()
        if sub:
            sub.status = "failed"
            sub.result = str(e)
            db.commit()
    finally:
        db.close()


def run_subagent_task_async(subagent_id: int):
    """Launch a sub-agent task in a background thread."""
    t = threading.Thread(target=run_subagent_task, args=(subagent_id,), daemon=True)
    t.start()
