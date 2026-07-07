"""
Модуль для работы с YandexGPT через Yandex Cloud API.

Используется официальный OpenAI-совместимый клиент (AsyncOpenAI),
поскольку YandexGPT поддерживает тот же протокол.
"""
import asyncio

from openai import AsyncOpenAI

from config import YandexAIConfig

# Базовый URL Yandex Cloud AI API
YC_BASE_URL = "https://ai.api.cloud.yandex.net/v1"


class YandexAIClient:
    """Асинхронный клиент для YandexGPT (Yandex Cloud)."""

    def __init__(self, config: YandexAIConfig):
        self.config = config
        self._client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=YC_BASE_URL,
        )

    async def ask(self, user_message: str) -> str:
        """Отправляет сообщение в YandexGPT, возвращает ответ (макс. 60 сек)."""
        response = await asyncio.wait_for(
            self._client.responses.create(
                model=self.config.model_uri,
                input=user_message,
                instructions=self.config.system_prompt,
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_output_tokens,
            ),
            timeout=60.0,
        )
        return response.output[0].content[0].text

    async def close(self):
        """Закрывает HTTP-сессию клиента (не блокирует больше 10 сек)."""
        try:
            await asyncio.wait_for(self._client.close(), timeout=10.0)
        except (asyncio.TimeoutError, Exception):
            pass
