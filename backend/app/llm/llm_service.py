"""
LLM provider abstraction. The RAG pipeline calls `LLMService.generate()`
and never depends on a specific provider - `LLM_PROVIDER` in
configuration decides whether that's a local Ollama model, OpenAI, or
any other OpenAI-compatible endpoint.
"""
from abc import ABC, abstractmethod

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import Settings, get_settings
from app.core.exceptions import ConfigurationError, LLMError
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMService(ABC):
    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError


class OllamaLLMService(LLMService):
    def __init__(self, settings: Settings):
        self.base_url = settings.LLM_BASE_URL.rstrip("/")
        self.model = settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self.timeout = settings.LLM_TIMEOUT_SECONDS

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("message", {}).get("content", "").strip()
        except httpx.HTTPError as exc:
            raise LLMError(f"Ollama request failed: {exc}") from exc


class OpenAICompatibleLLMService(LLMService):
    def __init__(self, settings: Settings, base_url: str | None = None):
        if not settings.LLM_API_KEY and settings.LLM_PROVIDER == "openai":
            raise ConfigurationError("LLM_API_KEY is required when LLM_PROVIDER=openai")

        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY or "not-required",
            base_url=base_url or (None if settings.LLM_PROVIDER == "openai" else settings.LLM_BASE_URL),
        )
        self.model = settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"LLM request failed: {exc}") from exc


def get_llm_service() -> LLMService:
    settings = get_settings()
    if settings.LLM_PROVIDER == "ollama":
        return OllamaLLMService(settings)
    return OpenAICompatibleLLMService(settings)
