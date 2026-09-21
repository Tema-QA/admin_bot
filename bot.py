import asyncio
import random
from datetime import datetime, timedelta, timezone

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message
from aiogram.webhook.aiohttp_server import (
    SimpleRequestHandler,
    setup_application,
)

from ai_generator import YandexGPTGenerator
from config import settings
from database import Database
from keyboards import (
    cancel_keyboard,
    chat_type_keyboard,
    main_keyboard,
    post_actions_keyboard,
    settings_keyboard,
)
from moderation import format_post, validate_post
from scheduler import publish_due_posts


bot = Bot(token=settings.bot_token)
dp = Dispatcher(storage=MemoryStorage())
database = Database(settings.database_path)

generator = YandexGPTGenerator(
    api_key=settings.yandex_api_key,
    folder_id=settings.yandex_folder_id,
    model=settings.yandex_model,
)

SAMARA_TZ = timezone(timedelta(hours=4))

EXAMPLE_TOPICS = (
    "Как восстановить режим сна после отпуска",
    "Какие анализы действительно нужны для профилактики",
    "Как распознать признаки обезвоживания летом",
    "Что помогает снизить количество соли в рационе",
    "Почему важна регулярная физическая активность",
    "Как подготовиться к приёму врача и ничего не забыть",
    "Зачем измерять артериальное давление дома",
    "Как поддерживать здоровье глаз при работе за экраном",
    "Что учитывать при выборе полезного перекуса",
    "Как стресс влияет на сон и самочувствие",
    "Почему нельзя игнорировать длительную усталость",
    "Как безопасно возвращаться к тренировкам после перерыва",
)
last_example_topics: tuple[str, ...] = ()


class Form(StatesGroup):
    waiting_topic = State()
    waiting_edit_text = State()
    waiting_schedule = State()
    waiting_setting_value = State()
    waiting_chat_id = State()


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


def get_example_topics() -> tuple[str, ...]:
    global last_example_topics

    available_topics = list(EXAMPLE_TOPICS)
    example_topics = tuple(random.sample(available_topics, 3))

    while example_topics == last_example_topics:
        example_topics = tuple(random.sample(available_topics, 3))

    last_example_topics = example_topics
    return example_topics


def parse_schedule(value: str) -> str:
    value = value.strip()

    datetime.strptime(
        value,
        "%Y-%m-%d %H:%M",
    )

    return value


@dp.message(CommandStart())
async def start_command(
    message: Message,
    state: FSMContext,
):
    user_id = message.from_user.id

    if not is_admin(user_id):
        await message.answer(
            "🚫 У вас нет доступа к управлению этим ботом."
        )
        return

    database.ensure_admin(user_id)
    await state.clear()

    await message.answer(
        "👋 **Контент-менеджер запущен!**\n\n"
        "Я помогу создать пост, показать его на проверку, "
        "опубликовать сразу или поставить в очередь.",
        reply_markup=main_keyboard(),
        parse_mode="Markdown",
    )


@dp.message(F.text == "📝 Создать пост")
async def create_post_start(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    await state.set_state(Form.waiting_topic)

    example_topics = get_example_topics()

    await message.answer(
        "📝 Напишите тему поста.\n\n"
        "Например:\n"
        f"• {example_topics[0]}\n"
        f"• {example_topics[1]}\n"
        f"• {example_topics[2]}\n\n"
        "Если хотите, чтобы тему выбрала нейросеть, отправьте:\n"
        "`автоматически`",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown",
    )


@dp.message(Form.waiting_topic)
async def generate_post(
    message: Message,
    state: FSMContext,
):
    admin_id = message.from_user.id
    topic = message.text.strip()

    await message.answer(
        "⏳ Анализирую тему и создаю черновик…"
    )

    channel_settings = database.get_settings(admin_id)
    recent_posts = database.get_recent_posts(
        admin_id,
        limit=100,
    )

    try:
        result = await generator.generate(
            settings=channel_settings,
            recent_posts=recent_posts,
            requested_topic=topic,
        )

        is_valid, moderation_message = validate_post(
            result,
            channel_settings,
        )

        if not is_valid:
            await message.answer(
                "⚠️ Черновик не прошёл автоматическую проверку:\n\n"
                f"{moderation_message}\n\n"
                "Попробуйте другую тему.",
            )
            await state.clear()
            return

        post_id = database.create_post(
            admin_id=admin_id,
            title=result["title"],
            text=result["text"],
            hashtags=result["hashtags"],
            disclaimer=result["disclaimer"],
        )

        await state.clear()

        await message.answer(
            f"📝 **Черновик поста №{post_id}**\n\n"
            f"{format_post(result)}\n\n"
            "Выберите действие:",
            reply_markup=post_actions_keyboard(post_id),
            parse_mode="Markdown",
        )

    except Exception as error:
        await state.clear()

        await message.answer(
            "❌ Не удалось сгенерировать пост.\n\n"
            f"Техническая причина: `{str(error)[:500]}`",
            parse_mode="Markdown",
        )


@dp.message(F.text == "⚙️ Настройки канала")
async def settings_start(message: Message):
    if not is_admin(message.from_user.id):
        return

    current = database.get_settings(message.from_user.id)

    await message.answer(
        "⚙️ **Настройки канала**\n\n"
        f"📌 Тематика: `{current.get('channel_theme') or 'не задана'}`\n"
        f"🧑‍⚕️ Аудитория: `{current.get('audience') or 'не задана'}`\n"
        f"📝 Стиль: `{current.get('style') or 'не задан'}`\n"
        f"📅 Время: `{current.get('publish_time') or 'не задано'}`\n"
        f"📌 Рубрики: `{current.get('rubrics') or 'не заданы'}`\n"
        f"🚫 Запрещённые темы: "
        f"`{current.get('forbidden_topics') or 'не заданы'}`",
        reply_markup=settings_keyboard(),
        parse_mode="Markdown",
    )


@dp.callback_query(F.data.startswith("settings:"))
async def settings_action(
    callback: CallbackQuery,
    state: FSMContext,
):
    action = callback.data.split(":", 1)[1]
    admin_id = callback.from_user.id

    if action == "back":
        await callback.message.edit_text(
            "⚙️ Настройки закрыты."
        )
        await callback.answer()
        return

    field_map = {
        "audience": (
            "audience",
            "🧑‍⚕️ Опишите целевую аудиторию.",
        ),
        "style": (
            "style",
            "📝 Опишите стиль публикаций.",
        ),
        "rubrics": (
            "rubrics",
            "📌 Укажите рубрики через запятую.",
        ),
        "forbidden": (
            "forbidden_topics",
            "🚫 Укажите запрещённые темы через запятую.",
        ),
        "schedule": (
            "publish_time",
            "📅 Введите время в формате `HH:MM`.",
        ),
    }

    if action not in field_map:
        await callback.answer()
        return

    field, prompt = field_map[action]

    await state.update_data(setting_field=field)
    await state.set_state(Form.waiting_setting_value)

    await callback.message.edit_text(
        prompt,
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown",
    )

    await callback.answer()


@dp.message(Form.waiting_setting_value)
async def save_setting(
    message: Message,
    state: FSMContext,
):
    data = await state.get_data()
    field = data.get("setting_field")
    value = message.text.strip()

    if not value:
        await message.answer("⚠️ Значение не может быть пустым.")
        return

    if field == "publish_time":
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError:
            await message.answer(
                "⚠️ Используйте формат `HH:MM`, например `09:30`.",
                parse_mode="Markdown",
            )
            return

    database.update_setting(
        message.from_user.id,
        field,
        value,
    )

    await state.clear()

    await message.answer(
        "✅ Настройка сохранена.",
        reply_markup=main_keyboard(),
    )


@dp.message(F.text == "📣 Выбрать чат")
async def choose_chat(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    await state.set_state(Form.waiting_chat_id)

    await message.answer(
        "📣 Отправьте сюда числовой chat_id канала.\n\n"
        "Бот должен быть администратором канала "
        "с правом публикации сообщений.\n\n"
        "Пример:\n"
        "`-1001234567890`",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown",
    )


@dp.message(Form.waiting_chat_id)
async def save_chat_id(
    message: Message,
    state: FSMContext,
):
    value = message.text.strip()

    if not value.startswith("-100"):
        await message.answer(
            "⚠️ Для Telegram-канала chat_id обычно начинается с `-100`.",
            parse_mode="Markdown",
        )
        return

    try:
        chat = await bot.get_chat(int(value))
    except Exception as error:
        await message.answer(
            "❌ Бот не смог получить доступ к этому чату.\n\n"
            "Проверьте, что бот добавлен администратором канала.\n"
            f"`{str(error)[:300]}`",
            parse_mode="Markdown",
        )
        return

    database.update_setting(
        message.from_user.id,
        "target_chat_id",
        value,
    )

    database.update_setting(
        message.from_user.id,
        "target_chat_title",
        chat.title or value,
    )

    await state.clear()

    await message.answer(
        f"✅ Чат выбран: **{chat.title or value}**",
        reply_markup=main_keyboard(),
        parse_mode="Markdown",
    )


@dp.callback_query(F.data.startswith("post:publish:"))
async def publish_now(callback: CallbackQuery):
    post_id = int(callback.data.rsplit(":", 1)[1])
    post = database.get_post(post_id)

    if not post or post["admin_id"] != callback.from_user.id:
        await callback.answer(
            "Пост не найден.",
            show_alert=True,
        )
        return

    channel_settings = database.get_settings(callback.from_user.id)
    target_chat_id = channel_settings.get("target_chat_id")

    if not target_chat_id:
        await callback.answer(
            "Сначала выберите канал.",
            show_alert=True,
        )
        return

    formatted_post = format_post(post)

    try:
        sent_message = await bot.send_message(
            chat_id=target_chat_id,
            text=formatted_post,
            parse_mode="Markdown",
        )

        database.set_status(
            post_id,
            "published",
            published_message_id=sent_message.message_id,
        )

        await callback.message.edit_text(
            "✅ Пост опубликован в канале."
        )
        await callback.answer("Опубликовано.")

    except Exception as error:
        await callback.answer(
            f"Ошибка публикации: {str(error)[:200]}",
            show_alert=True,
        )


@dp.callback_query(F.data.startswith("post:edit:"))
async def edit_post_start(
    callback: CallbackQuery,
    state: FSMContext,
):
    post_id = int(callback.data.rsplit(":", 1)[1])
    post = database.get_post(post_id)

    if not post or post["admin_id"] != callback.from_user.id:
        await callback.answer("Пост не найден.", show_alert=True)
        return

    await state.update_data(edit_post_id=post_id)
    await state.set_state(Form.waiting_edit_text)

    await callback.message.edit_text(
        "✏️ Отправьте новый текст поста одним сообщением.\n\n"
        "Заголовок и хэштеги останутся прежними.",
        reply_markup=cancel_keyboard(),
    )

    await callback.answer()


@dp.message(Form.waiting_edit_text)
async def edit_post_save(
    message: Message,
    state: FSMContext,
):
    data = await state.get_data()
    post_id = data.get("edit_post_id")

    database.update_post_text(
        post_id,
        message.text.strip(),
    )

    await state.clear()

    post = database.get_post(post_id)

    await message.answer(
        f"✏️ **Обновлённый черновик №{post_id}**\n\n"
        f"{format_post(post)}",
        reply_markup=post_actions_keyboard(post_id),
        parse_mode="Markdown",
    )


@dp.callback_query(F.data.startswith("post:regenerate:"))
async def regenerate_post(
    callback: CallbackQuery,
):
    post_id = int(callback.data.rsplit(":", 1)[1])
    post = database.get_post(post_id)

    if not post or post["admin_id"] != callback.from_user.id:
        await callback.answer("Пост не найден.", show_alert=True)
        return

    await callback.answer("Генерирую новый вариант…")

    settings_data = database.get_settings(callback.from_user.id)
    recent_posts = database.get_recent_posts(
        callback.from_user.id,
        limit=100,
    )

    try:
        result = await generator.generate(
            settings_data,
            recent_posts,
            requested_topic=post["title"],
        )

        is_valid, reason = validate_post(
            result,
            settings_data,
        )

        if not is_valid:
            await callback.message.answer(
                f"⚠️ Новый вариант не прошёл проверку: {reason}"
            )
            return

        database.update_post(
            post_id,
            result["title"],
            result["text"],
            result["hashtags"],
            result["disclaimer"],
        )

        await callback.message.edit_text(
            f"🔄 **Новый вариант поста №{post_id}**\n\n"
            f"{format_post(result)}",
            reply_markup=post_actions_keyboard(post_id),
            parse_mode="Markdown",
        )

    except Exception as error:
        await callback.message.answer(
            f"❌ Ошибка генерации: `{str(error)[:500]}`",
            parse_mode="Markdown",
        )


@dp.callback_query(F.data.startswith("post:schedule:"))
async def schedule_post_start(
    callback: CallbackQuery,
    state: FSMContext,
):
    post_id = int(callback.data.rsplit(":", 1)[1])
    post = database.get_post(post_id)

    if not post or post["admin_id"] != callback.from_user.id:
        await callback.answer("Пост не найден.", show_alert=True)
        return

    await state.update_data(schedule_post_id=post_id)
    await state.set_state(Form.waiting_schedule)

    await callback.message.edit_text(
        "⏰ Введите дату и время публикации по UTC:\n\n"
        "`2026-09-21 08:30`\n\n"
        "Для вашего часового пояса UTC+4 это будет 12:30.",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown",
    )

    await callback.answer()


@dp.message(Form.waiting_schedule)
async def schedule_post_save(
    message: Message,
    state: FSMContext,
):
    data = await state.get_data()
    post_id = data.get("schedule_post_id")
    value = message.text.strip()

    try:
        scheduled = datetime.strptime(
            value,
            "%Y-%m-%d %H:%M",
        )
    except ValueError:
        await message.answer(
            "⚠️ Неверный формат.\n"
            "Используйте: `2026-09-21 08:30`",
            parse_mode="Markdown",
        )
        return

    scheduled_utc = scheduled.replace(
        tzinfo=SAMARA_TZ,
    ).astimezone(timezone.utc).replace(tzinfo=None)

    database.set_status(
        post_id,
        "scheduled",
        scheduled_at=scheduled_utc.isoformat(),
    )

    await state.clear()

    await message.answer(
        f"⏰ Пост запланирован на местное время (UTC+4): `{value}`.\n\n"
        "Внешний cron проверит очередь и опубликует его.",
        reply_markup=main_keyboard(),
        parse_mode="Markdown",
    )


@dp.callback_query(F.data.startswith("post:reject:"))
async def reject_post(callback: CallbackQuery):
    post_id = int(callback.data.rsplit(":", 1)[1])
    post = database.get_post(post_id)

    if not post or post["admin_id"] != callback.from_user.id:
        await callback.answer("Пост не найден.", show_alert=True)
        return

    database.set_status(post_id, "rejected")

    await callback.message.edit_text(
        "❌ Черновик отклонён и удалён из очереди."
    )
    await callback.answer("Отклонено.")


@dp.callback_query(F.data == "cancel")
async def cancel_action(
    callback: CallbackQuery,
    state: FSMContext,
):
    await state.clear()

    await callback.message.edit_text(
        "❌ Действие отменено."
    )

    await callback.answer("Отменено.")


async def health_handler(request: web.Request):
    return web.Response(
        text="OK",
        status=200,
        content_type="text/plain",
    )


async def cron_publish_handler(request: web.Request):
    authorization = request.headers.get("Authorization", "")
    expected = f"Bearer {settings.cron_secret}"

    if authorization != expected:
        return web.json_response(
            {"ok": False, "error": "unauthorized"},
            status=401,
        )

    published_ids = await publish_due_posts(
        database,
        bot,
    )

    return web.json_response(
        {
            "ok": True,
            "published_post_ids": published_ids,
        }
    )


async def on_startup():
    await bot.set_webhook(
        url=f"{settings.webhook_base_url}/telegram/webhook",
        secret_token=settings.webhook_secret,
        allowed_updates=dp.resolve_used_update_types(),
        drop_pending_updates=False,
    )


async def on_shutdown():
    await bot.session.close()


def create_app() -> web.Application:
    app = web.Application()

    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/cron/publish", cron_publish_handler)
    app.router.add_post("/cron/publish", cron_publish_handler)

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=settings.webhook_secret,
    )

    webhook_handler.register(
        app,
        path="/telegram/webhook",
    )

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    setup_application(
        app,
        dp,
        bot=bot,
    )

    return app


if __name__ == "__main__":
    application = create_app()

    web.run_app(
        application,
        host="0.0.0.0",
        port=settings.port,
    )