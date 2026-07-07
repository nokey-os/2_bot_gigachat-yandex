"""
Точка входа в приложение.

Задачи:
  1. Загрузить .env и конфигурацию (config.py)
  2. Настроить прокси / DNS для доступа к Telegram
  3. Создать экземпляры Bot и Dispatcher (aiogram)
  4. Инициализировать клиентов AI-провайдеров (bot.setup)
  5. Запустить polling (прослушивание входящих сообщений)
"""
import asyncio
import io
import logging
import os
import sys

# Принудительно включаем UTF-8 для консоли (иначе эмодзи и unicode в логах валят бота)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import socket

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

from config import AppConfig
from bot import router, setup


# ═══════════════════════════════════════════════
#  DNS-патч (если api.telegram.org не резолвится)
# ═══════════════════════════════════════════════
def _patch_dns(hostname: str, ip: str):
    """Подменяет DNS-резолвинг: вместо hostname использует указанный IP.

    Нужно, когда DNS-провайдер блокирует api.telegram.org.
    """
    original = socket.getaddrinfo

    def patched(host, port, family=0, type=0, proto=0, flags=0):
        if host == hostname:
            host = ip
        return original(host, port, family, type, proto, flags)

    socket.getaddrinfo = patched


# ═══════════════════════════════════════════════
#  Сессия aiogram с поддержкой прокси
# ═══════════════════════════════════════════════
def _create_aiohttp_session(proxy_url: str | None):
    """
    Создаёт HTTP-сессию для aiogram.

    Если указан прокси (socks5://...), сессия будет ходить через него.
    aiohttp-socks в aiogram поддерживается из коробки через параметр proxy.
    """
    from aiogram.client.session.aiohttp import AiohttpSession

    if proxy_url:
        # aiohttp-socks не понимает socks5h, заменяем на socks5
        normalized = proxy_url.replace("socks5h://", "socks5://")
        # Увеличиваем таймаут, т.к. через Tor/Tor-like прокси соединение может быть медленным
        return AiohttpSession(proxy=normalized, timeout=120.0)
    return AiohttpSession(timeout=120.0)


# ═══════════════════════════════════════════════
#  Главная функция
# ═══════════════════════════════════════════════
async def main():
    """Основная логика запуска бота."""
    # Загружаем .env и настраиваем логирование
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger = logging.getLogger(__name__)

    # Читаем всю конфигурацию из .env
    config = AppConfig.from_env()

    # Применяем DNS-патч, если указан прямой IP
    if config.telegram_api_ip:
        _patch_dns("api.telegram.org", config.telegram_api_ip)
        logger.info("DNS для api.telegram.org подменён на %s", config.telegram_api_ip)

    # Логируем прокси (если есть)
    if config.telegram_proxy:
        logger.info("Прокси для Telegram: %s", config.telegram_proxy)

    # Создаём сессию (с прокси или без) и экземпляр бота
    session = _create_aiohttp_session(config.telegram_proxy)
    bot = Bot(token=config.telegram_bot_token, session=session)
    dp = Dispatcher()

    # Инициализируем клиентов AI-провайдеров
    setup(config)

    # Подключаем обработчики из bot.py
    dp.include_router(router)

    # Собираем список доступных провайдеров для лога
    providers = []
    if config.gigachat:
        providers.append("GigaChat")
    if config.yandex:
        providers.append("YandexGPT")

    try:
        logger.info("Бот запущен. Доступные провайдеры: %s", ", ".join(providers))
        # Запускаем бесконечный цикл получения сообщений от Telegram
        await dp.start_polling(bot)
    finally:
        # При остановке корректно закрываем все соединения
        if config.gigachat:
            from bot import _giga_client
            if _giga_client:
                await _giga_client.close()
        if config.yandex:
            from bot import _yandex_client
            if _yandex_client:
                await _yandex_client.close()
        await bot.session.close()


# ═══════════════════════════════════════════════
#  Точка входа
# ═══════════════════════════════════════════════
if __name__ == "__main__":
    asyncio.run(main())
