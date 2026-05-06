import asyncio
import json
import uuid
import logging

logger = logging.getLogger(__name__)

try:
    import websockets
    _ws_available = True
except ImportError:
    _ws_available = False
    logger.warning("[OpenClaw] websockets package not installed; gateway routing disabled")


class OpenClawGatewayClient:
    URL = "ws://127.0.0.1:18789"

    def __init__(self):
        self._ws = None
        self._pending: dict[str, asyncio.Future] = {}
        self._streams: dict[str, asyncio.Queue] = {}
        self.connected = False
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self):
        if not _ws_available:
            return
        try:
            self._ws = await websockets.connect(self.URL)
            req_id = str(uuid.uuid4())
            await self._ws.send(json.dumps({
                "type": "req",
                "id": req_id,
                "method": "connect",
                "params": {
                    "clientName": "neurogenesis-web",
                    "clientVersion": "1.0",
                    "minProtocol": 3,
                    "maxProtocol": 3,
                },
            }))
            self._loop = asyncio.get_running_loop()
            asyncio.create_task(self._listen())
            self.connected = True
            logger.info("[OpenClaw] Gateway WebSocket connected")
        except Exception as e:
            logger.warning(f"[OpenClaw] Gateway WebSocket connect failed: {e}")
            self.connected = False

    async def create_session(self, agent_id: str) -> str:
        res = await self._req("sessions:create", {"agentId": agent_id})
        return res["payload"]["sessionKey"]

    async def send_message(self, session_key: str, message: str) -> str:
        res = await self._req("chat:send", {
            "sessionKey": session_key,
            "message": message,
            "idempotencyKey": str(uuid.uuid4()),
        })
        run_id = res["payload"]["runId"]
        self._streams[run_id] = asyncio.Queue()
        return run_id

    async def stream_run(self, run_id: str):
        """Async generator yielding text chunks from the agent response."""
        q = self._streams.setdefault(run_id, asyncio.Queue())
        while True:
            chunk = await asyncio.wait_for(q.get(), timeout=60)
            if chunk is None:
                break
            yield chunk

    # --- Sync helpers for calling from background threads ---

    def create_session_sync(self, agent_id: str) -> str:
        """Thread-safe sync wrapper. Submits to the main event loop."""
        fut = asyncio.run_coroutine_threadsafe(self.create_session(agent_id), self._loop)
        return fut.result(timeout=30)

    def send_and_collect_sync(self, session_key: str, message: str) -> str:
        """Thread-safe sync wrapper. Collects the full streamed response."""
        async def _go():
            run_id = await self.send_message(session_key, message)
            chunks: list[str] = []
            async for chunk in self.stream_run(run_id):
                chunks.append(chunk)
            return "".join(chunks)

        fut = asyncio.run_coroutine_threadsafe(_go(), self._loop)
        return fut.result(timeout=120)

    # --- Internal async methods ---

    async def _req(self, method: str, params: dict) -> dict:
        req_id = str(uuid.uuid4())
        loop = asyncio.get_event_loop()
        f: asyncio.Future = loop.create_future()
        self._pending[req_id] = f
        await self._ws.send(json.dumps({
            "type": "req",
            "id": req_id,
            "method": method,
            "params": params,
        }))
        return await asyncio.wait_for(f, timeout=30)

    async def _listen(self):
        try:
            async for raw in self._ws:
                try:
                    frame = json.loads(raw)
                except Exception:
                    continue

                ftype = frame.get("type")

                if ftype == "res":
                    req_id = frame.get("id")
                    if req_id and req_id in self._pending:
                        f = self._pending.pop(req_id)
                        if frame.get("ok", True):
                            f.set_result(frame)
                        else:
                            err = frame.get("error", {})
                            f.set_exception(RuntimeError(err.get("message", "gateway error")))

                elif ftype == "event":
                    event_name = frame.get("event", "")
                    payload = frame.get("payload", {})

                    if event_name == "agent:event":
                        run_id = payload.get("runId")
                        if run_id and run_id in self._streams:
                            data = payload.get("data", {})
                            # Handle multiple possible payload shapes from OpenClaw
                            text = (
                                data.get("text")
                                or data.get("content")
                                or data.get("delta", {}).get("text")
                                or ""
                            )
                            done = (
                                data.get("done")
                                or data.get("finished")
                                or data.get("stop_reason") is not None
                            )
                            if text:
                                await self._streams[run_id].put(text)
                            if done:
                                await self._streams[run_id].put(None)
                                self._streams.pop(run_id, None)
                        # Debug: log unknown event payload shapes
                        logger.debug(f"[OpenClaw] agent:event payload keys: {list(payload.keys())}")

        except Exception as e:
            logger.error(f"[OpenClaw] Gateway listener error: {e}")
            self.connected = False


gateway_client = OpenClawGatewayClient()
