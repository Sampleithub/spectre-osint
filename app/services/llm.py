from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from app.config import config


class LLMService:
    def __init__(self):
        self._client: AsyncOpenAI | None = None
        self._model: str | None = None

    def _ensure_client(self):
        if self._client is not None:
            return

        if config.llm_provider == "ollama":
            self._client = AsyncOpenAI(
                base_url=config.ollama_base_url,
                api_key="ollama",
            )
            self._model = config.ollama_model
        else:
            kwargs: dict[str, Any] = {"api_key": config.openai_api_key}
            if config.openai_base_url:
                kwargs["base_url"] = config.openai_base_url
            self._client = AsyncOpenAI(**kwargs)
            self._model = config.openai_model

    @property
    def client(self) -> AsyncOpenAI:
        self._ensure_client()
        return self._client

    @property
    def model(self) -> str:
        self._ensure_client()
        return self._model or ""

    async def chat(
        self,
        messages: list[dict[str, str]],
        response_format: type | None = None,
    ) -> str:
        self._ensure_client()
        kwargs = {
            "model": self._model,
            "messages": messages,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format

        response = await self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""


llm = LLMService()
