import os
from dataclasses import dataclass


# ═══════════════════════════════════════════════
#  Конфигурация GigaChat (Сбер)
# ═══════════════════════════════════════════════
@dataclass
class GigaChatConfig:
    """Настройки для подключения к GigaChat API."""
    credentials: str          # AUTHORIZATION_KEY — ключ доступа к GigaChat
    base_url: str = "https://gigachat.devices.sberbank.ru/api/v1"  # адрес API
    verify_ssl_certs: bool = False  # проверять SSL-сертификаты
    timeout: float = 120.0          # таймаут запроса (сек)
    system_prompt: str = "Ты вежливый и профессиональный личный помощник, работающий в Telegram."

    @classmethod
    def from_env(cls) -> "GigaChatConfig":
        """Считывает настройки GigaChat из переменных окружения (.env)."""
        credentials = os.getenv("AUTHORIZATION_KEY", "")
        if not credentials:
            raise ValueError("AUTHORIZATION_KEY не задан в .env")
        return cls(
            credentials=credentials,
            base_url=os.getenv("GIGACHAT_BASE_URL", cls.base_url),
            verify_ssl_certs=os.getenv("GIGACHAT_VERIFY_SSL_CERTS", "false").lower() == "true",
            timeout=float(os.getenv("GIGACHAT_TIMEOUT", "120")),
            system_prompt=os.getenv("GIGACHAT_SYSTEM_PROMPT") or cls.system_prompt,
        )


# ═══════════════════════════════════════════════
#  Конфигурация YandexGPT (Яндекс)
# ═══════════════════════════════════════════════
@dataclass
class YandexAIConfig:
    """Настройки для подключения к YandexGPT через Yandex Cloud."""
    api_key: str            # YC_API_KEY — IAM-токен или API-ключ Яндекс Облака
    folder_id: str          # YC_FOLDER_ID — ID каталога в Яндекс Облаке
    model_name: str = "yandexgpt-lite"  # имя модели (yandexgpt-lite / yandexgpt)
    system_prompt: str | None = None    # системный промпт (необязательный)
    temperature: float = 0.6            # "креативность" ответов (0..1)
    max_output_tokens: int = 1500       # макс. токенов в ответе

    @classmethod
    def from_env(cls) -> "YandexAIConfig":
        """Считывает настройки YandexGPT из переменных окружения (.env)."""
        api_key = os.getenv("YC_API_KEY", "")
        folder_id = os.getenv("YC_FOLDER_ID", "")
        model_name = os.getenv("YC_MODEL_NAME", "yandexgpt-lite")
        # Сначала проверяем YANDEX_SYSTEM_PROMPT, затем старый ключ SYSTEM_PROMPT
        system_prompt = os.getenv("YANDEX_SYSTEM_PROMPT") or os.getenv("SYSTEM_PROMPT") or None

        if not api_key:
            raise ValueError("YC_API_KEY не задан в .env")
        if not folder_id:
            raise ValueError("YC_FOLDER_ID не задан в .env")

        return cls(
            api_key=api_key,
            folder_id=folder_id,
            model_name=model_name,
            system_prompt=system_prompt,
        )

    @property
    def model_uri(self) -> str:
        """Формирует URI модели в формате: gpt://<folder_id>/<model_name>"""
        return f"gpt://{self.folder_id}/{self.model_name}"


# ═══════════════════════════════════════════════
#  Общая конфигурация приложения
# ═══════════════════════════════════════════════
@dataclass
class AppConfig:
    """Главная конфигурация: Telegram + все AI-провайдеры."""
    telegram_bot_token: str          # токен бота от @BotFather
    telegram_api_ip: str | None = None  # прямой IP api.telegram.org (если DNS заблокирован)
    telegram_proxy: str | None = None   # прокси для Telegram (socks5/http)

    gigachat: GigaChatConfig | None = None  # настройки GigaChat (None = не настроен)
    yandex: YandexAIConfig | None = None    # настройки YandexGPT (None = не настроен)

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Собирает полную конфигурацию из .env.

        Провайдеры загружаются независимо — если для одного не хватает ключей,
        он пропускается (gigachat/yandex остаётся None). Ошибка будет только
        если не настроен ни один провайдер.
        """
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN не задан в .env")

        # Пытаемся загрузить каждого провайдера по отдельности
        gigachat = None
        yandex = None

        try:
            gigachat = GigaChatConfig.from_env()
        except ValueError:
            pass  # GigaChat не настроен — пропускаем

        try:
            yandex = YandexAIConfig.from_env()
        except ValueError:
            pass  # YandexGPT не настроен — пропускаем

        if not gigachat and not yandex:
            raise ValueError(
                "Не заданы ключи ни для одного AI-провайдера. "
                "Укажите AUTHORIZATION_KEY (GigaChat) и/или YC_API_KEY+YC_FOLDER_ID (Yandex)."
            )

        return cls(
            telegram_bot_token=token,
            telegram_api_ip=os.getenv("TELEGRAM_API_IP"),
            telegram_proxy=os.getenv("TELEGRAM_PROXY"),
            gigachat=gigachat,
            yandex=yandex,
        )
