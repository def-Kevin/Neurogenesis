from openai import OpenAI
from typing import Iterator, Optional
from backend.config import settings


class LLMClient:
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.llm_api_key or "dummy-key",
            base_url=settings.llm_base_url,
        )
        self.model = settings.llm_model

    def chat_completion(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        stream: bool = False,
    ):
        if not settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY not configured")
        kwargs = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if stream:
            return self._stream_response(**kwargs)
        resp = self.client.chat.completions.create(**kwargs)
        return resp.choices[0].message

    def _stream_response(self, **kwargs):
        for chunk in self.client.chat.completions.create(**kwargs):
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
