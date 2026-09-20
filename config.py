import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    yandex_api_key: str
    yandex_folder_id: str
    yandex_model: str
    webhook_base_url: str
    webhook_secret: str
    cron_secret: str
    port: int
    database_path: str
    admin_ids: tuple[int, ...]


def parse_ids(value: str) -> tuple[int, ...]:
    result = []

    for item in value.split(","):
        item = item.strip()

        if item:
            result.append(int(item))

    return tuple(result)


def load_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    yandex_api_key = os.getenv("YANDEX_API_KEY", "").strip()
    yandex_folder_id = os.getenv("YANDEX_FOLDER_ID", "").strip()
    webhook_base_url = os.getenv(
        "WEBHOOK_BASE_URL",
        "http://localhost:10000",
    ).strip().rstrip("/")
    webhook_secret = os.getenv("WEBHOOK_SECRET", "").strip()
    cron_secret = os.getenv("CRON_SECRET", "").strip()
    admin_ids_raw = os.getenv("ADMIN_IDS", "").strip()

    if not bot_token:
        raise ValueError("Не задан BOT_TOKEN.")

    if not yandex_api_key:
        raise ValueError("Не задан YANDEX_API_KEY.")

    if not yandex_folder_id:
        raise ValueError("Не задан YANDEX_FOLDER_ID.")

    if not webhook_secret:
        raise ValueError("Не задан WEBHOOK_SECRET.")

    if not cron_secret:
        raise ValueError("Не задан CRON_SECRET.")

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", webhook_secret):
        raise ValueError(
            "WEBHOOK_SECRET содержит недопустимые символы."
        )

    if not admin_ids_raw:
        raise ValueError(
            "Не задан ADMIN_IDS. Укажите Telegram ID администратора."
        )

    return Settings(
        bot_token=bot_token,
        yandex_api_key=yandex_api_key,
        yandex_folder_id=yandex_folder_id,
        yandex_model=os.getenv(
            "YANDEX_GPT_MODEL",
            "yandexgpt-lite",
        ).strip(),
        webhook_base_url=webhook_base_url,
        webhook_secret=webhook_secret,
        cron_secret=cron_secret,
        port=int(os.getenv("PORT") or "10000"),
        database_path=os.getenv(
            "DATABASE_PATH",
            "content_bot.db",
        ).strip(),
        admin_ids=parse_ids(admin_ids_raw),
    )


settings = load_settings()