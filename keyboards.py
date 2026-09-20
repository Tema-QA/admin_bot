from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📝 Создать пост"),
            ],
            [
                KeyboardButton(text="⚙️ Настройки канала"),
            ],
            [
                KeyboardButton(text="📣 Выбрать чат"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие…",
    )


def post_actions_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Опубликовать",
                    callback_data=f"post:publish:{post_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Изменить",
                    callback_data=f"post:edit:{post_id}",
                ),
                InlineKeyboardButton(
                    text="🔄 Перегенерировать",
                    callback_data=f"post:regenerate:{post_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⏰ Запланировать",
                    callback_data=f"post:schedule:{post_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"post:reject:{post_id}",
                )
            ],
        ]
    )


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🧑‍⚕️ Целевая аудитория",
                    callback_data="settings:audience",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📝 Стиль текста",
                    callback_data="settings:style",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📅 Расписание",
                    callback_data="settings:schedule",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📌 Рубрики",
                    callback_data="settings:rubrics",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Запрещённые темы",
                    callback_data="settings:forbidden",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="settings:back",
                )
            ],
        ]
    )


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data="cancel",
                )
            ]
        ]
    )


def chat_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📣 Использовать текущий чат",
                    callback_data="chat:current",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data="cancel",
                )
            ],
        ]
    )