"""
Модуль для работы с GigaChat (Сбер).

Библиотека gigachat — синхронная, поэтому все вызовы обёрнуты в
asyncio.to_thread / run_in_executor, чтобы не блокировать главный цикл aiogram.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from config import GigaChatConfig

# Пул потоков для синхронных вызовов GigaChat (не больше 4 одновременных)
_thread_pool = ThreadPoolExecutor(max_workers=4)


class GigaChatClient:
    """Асинхронная обёртка над синхронным GigaChat-клиентом."""

    def __init__(self, config: GigaChatConfig):
        self.config = config
        # Создаём синхронный клиент GigaChat
        self._client = GigaChat(
            credentials=config.credentials,
            base_url=config.base_url,
            verify_ssl_certs=config.verify_ssl_certs,
            timeout=config.timeout,
        )

    async def ask(self, user_message: str) -> str:
        """
        Отправляет сообщение пользователя в GigaChat и возвращает ответ модели.

        Выполняется в отдельном потоке (run_in_executor), чтобы не блокировать
        асинхронный цикл обработки сообщений Telegram.
        """
        # Формируем запрос: системный промпт + сообщение пользователя
        chat = Chat(
            messages=[
                Messages(role=MessagesRole.SYSTEM, content=self.config.system_prompt),
                Messages(role=MessagesRole.USER, content=user_message),
            ]
        )
        # Запускаем синхронный self._client.chat() в потоке из пула
        # и ждём результат не дольше 60 секунд
        loop = asyncio.get_running_loop()
        response = await asyncio.wait_for(
            loop.run_in_executor(_thread_pool, self._client.chat, chat),
            timeout=60.0,
        )

        # Извлекаем текст ответа
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("GigaChat вернул пустой ответ")
        return content

    async def close(self):
        """Закрывает соединение с GigaChat (тоже синхронное, оборачиваем в поток)."""
        try:
            await asyncio.wait_for(
                asyncio.get_running_loop().run_in_executor(_thread_pool, self._client.close),
                timeout=10.0,
            )
        except (asyncio.TimeoutError, Exception):
            pass  # Игнорируем ошибки при закрытии
