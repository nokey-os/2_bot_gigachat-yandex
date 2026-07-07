"""
Основной модуль бота — обработчики команд и сообщений.

Содержит:
  - Обработчики команд /start, /gigachat, /yandex
  - Обработчик inline-кнопок выбора провайдера
  - Обработчик текстовых сообщений (вызов AI и отправка ответа)
  - Словарь _user_providers для хранения выбора каждого пользователя
"""
import asyncio
import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import AppConfig
from gigachat_ai import GigaChatClient
from yandex_ai import YandexAIClient

logger = logging.getLogger(__name__)

# Telegram не может отправить одно сообщение длиннее 4096 символов
TELEGRAM_MESSAGE_LIMIT = 4096

# Router — основной механизм aiogram для регистрации обработчиков
router = Router()

# Глобальные экземпляры клиентов AI-провайдеров (инициализируются в setup())
_giga_client: GigaChatClient | None = None
_yandex_client: YandexAIClient | None = None

# Хранилище выбора провайдера для каждого пользователя
# key: user_id (int), value: "gigachat" | "yandex"
_user_providers: dict[int, str] = {}

# Список доступных провайдеров (заполняется в setup())
AVAILABLE_PROVIDERS: list[str] = []


# ═══════════════════════════════════════════════
#  Инициализация
# ═══════════════════════════════════════════════
def setup(config: AppConfig):
    """Создаёт клиенты для настроенных AI-провайдеров.

    Вызывается из main.py один раз при старте бота.
    """
    global _giga_client, _yandex_client, AVAILABLE_PROVIDERS

    if config.gigachat:
        _giga_client = GigaChatClient(config.gigachat)
        AVAILABLE_PROVIDERS.append("gigachat")

    if config.yandex:
        _yandex_client = YandexAIClient(config.yandex)
        AVAILABLE_PROVIDERS.append("yandex")


# ═══════════════════════════════════════════════
#  Клавиатура выбора провайдера
# ═══════════════════════════════════════════════
def _provider_keyboard(current: str | None = None) -> InlineKeyboardMarkup:
    """Формирует inline-клавиатуру с кнопками доступных провайдеров.

    Текущий выбранный провайдер помечается галочкой (✓).
    """
    builder = InlineKeyboardBuilder()
    for name in AVAILABLE_PROVIDERS:
        label = "GigaChat" if name == "gigachat" else "YandexGPT"
        if name == current:
            label += " ✓"
        builder.button(text=label, callback_data=f"provider:{name}")
    builder.adjust(1)  # по одной кнопке в столбце
    return builder.as_markup()


# ═══════════════════════════════════════════════
#  Утилиты
# ═══════════════════════════════════════════════
def _split_message(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Разбивает длинный текст на части для отправки по частям."""
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    while text:
        parts.append(text[:limit])
        text = text[limit:]
    return parts


# ═══════════════════════════════════════════════
#  Команда /start
# ═══════════════════════════════════════════════
@router.message(CommandStart())
async def cmd_start(message: Message):
    """Приветственное сообщение + клавиатура выбора провайдера."""
    user_id = message.from_user.id
    current = _user_providers.get(
        user_id,
        AVAILABLE_PROVIDERS[0] if AVAILABLE_PROVIDERS else None,
    )

    text = (
        "Привет! Я объединённый AI-бот. Я могу отвечать через:\n"
        "• GigaChat (Сбер)\n"
        "• YandexGPT (Яндекс)\n\n"
        "Выберите провайдера снизу или используйте команды:\n"
        "/gigachat — переключиться на GigaChat\n"
        "/yandex — переключиться на YandexGPT\n\n"
        f"Текущий провайдер: {'GigaChat' if current == 'gigachat' else 'YandexGPT'}"
    )
    await message.answer(text, reply_markup=_provider_keyboard(current))


# ═══════════════════════════════════════════════
#  Команда /gigachat — переключить на GigaChat
# ═══════════════════════════════════════════════
@router.message(Command("gigachat"))
async def cmd_gigachat(message: Message):
    if "gigachat" not in AVAILABLE_PROVIDERS:
        await message.answer("GigaChat не настроен (нет AUTHORIZATION_KEY в .env)")
        return
    _user_providers[message.from_user.id] = "gigachat"
    await message.answer(
        "Переключено на GigaChat ✓",
        reply_markup=_provider_keyboard("gigachat"),
    )


# ═══════════════════════════════════════════════
#  Команда /yandex — переключить на YandexGPT
# ═══════════════════════════════════════════════
@router.message(Command("yandex"))
async def cmd_yandex(message: Message):
    if "yandex" not in AVAILABLE_PROVIDERS:
        await message.answer("YandexGPT не настроен (нет YC_API_KEY/YC_FOLDER_ID в .env)")
        return
    _user_providers[message.from_user.id] = "yandex"
    await message.answer(
        "Переключено на YandexGPT ✓",
        reply_markup=_provider_keyboard("yandex"),
    )


# ═══════════════════════════════════════════════
#  Обработчик нажатий на inline-кнопки провайдера
# ═══════════════════════════════════════════════
@router.callback_query(lambda c: c.data and c.data.startswith("provider:"))
async def callback_provider(callback: CallbackQuery):
    """Обрабатывает нажатие на кнопку выбора провайдера в клавиатуре."""
    provider = callback.data.split(":", 1)[1]  # "gigachat" или "yandex"
    if provider not in AVAILABLE_PROVIDERS:
        await callback.answer("Этот провайдер недоступен", show_alert=True)
        return

    # Сохраняем выбор пользователя
    user_id = callback.from_user.id
    _user_providers[user_id] = provider
    await callback.answer(f"Выбран {'GigaChat' if provider == 'gigachat' else 'YandexGPT'}")

    # Обновляем клавиатуру — ставим галочку на выбранном провайдере
    await callback.message.edit_reply_markup(
        reply_markup=_provider_keyboard(provider)
    )


# ═══════════════════════════════════════════════
#  Обработчик текстовых сообщений (основная логика)
# ═══════════════════════════════════════════════
@router.message()
async def handle_message(message: Message):
    """Принимает текст от пользователя, отправляет выбранному AI и возвращает ответ."""
    if not message.text:
        return

    if not AVAILABLE_PROVIDERS:
        await message.answer("Нет доступных AI-провайдеров. Проверьте .env")
        return

    # Определяем, какой провайдер выбран для этого пользователя
    user_id = message.from_user.id
    provider = _user_providers.get(user_id, AVAILABLE_PROVIDERS[0])
    try:
        logger.info(
            "user_id=%s, provider=%s, text='%s'",
            user_id,
            provider,
            (message.text or "")[:80],
        )
    except Exception:
        pass  # Лог — не критично

    # Сначала отправляем временное сообщение "Думаю..."
    sent = await message.answer("Думаю...")

    try:
        # Вызываем нужного провайдера
        if provider == "gigachat":
            if not _giga_client:
                await sent.edit_text("GigaChat не настроен")
                return
            reply = await _giga_client.ask(message.text)
        else:
            if not _yandex_client:
                await sent.edit_text("YandexGPT не настроен")
                return
            reply = await _yandex_client.ask(message.text)

        try:
            logger.info("user_id=%s, ответ получен (%d символов)", user_id, len(reply))
        except Exception:
            pass

        # Разбиваем длинный ответ на части и отправляем
        parts = _split_message(reply)
        await sent.edit_text(parts[0])
        for part in parts[1:]:
            await message.answer(part)

        # После ответа показываем клавиатуру выбора провайдера
        await message.answer(
            "Выберите провайдера для следующего вопроса:",
            reply_markup=_provider_keyboard(provider),
        )

    except asyncio.TimeoutError:
        logger.warning("user_id=%s, таймаут AI", user_id)
        await sent.edit_text("Превышено время ожидания ответа AI. Попробуйте ещё раз.")
        await message.answer(
            "Выберите провайдера:",
            reply_markup=_provider_keyboard(_user_providers.get(user_id, AVAILABLE_PROVIDERS[0])),
        )
    except Exception as e:
        logger.exception("user_id=%s, ошибка: %s", user_id, e)
        await sent.edit_text(f"Ошибка: {e}")
        await message.answer(
            "Выберите провайдера:",
            reply_markup=_provider_keyboard(_user_providers.get(user_id, AVAILABLE_PROVIDERS[0])),
        )
