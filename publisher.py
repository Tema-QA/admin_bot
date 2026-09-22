from aiogram.types import Message

from moderation import format_post


async def publish_post_message(
    bot,
    chat_id: str | int,
    post: dict,
) -> Message:
    formatted = format_post(post)
    image_file_id = str(post.get("image_file_id") or "").strip()

    if not image_file_id:
        return await bot.send_message(
            chat_id=chat_id,
            text=formatted,
            parse_mode="Markdown",
        )

    if len(formatted) <= 1024:
        return await bot.send_photo(
            chat_id=chat_id,
            photo=image_file_id,
            caption=formatted,
            parse_mode="Markdown",
        )

    title = str(post.get("title", "")).strip()
    short_caption = f"**{title}**" if title else "📌"

    photo_message = await bot.send_photo(
        chat_id=chat_id,
        photo=image_file_id,
        caption=short_caption,
        parse_mode="Markdown",
    )

    await bot.send_message(
        chat_id=chat_id,
        text=formatted,
        parse_mode="Markdown",
    )

    return photo_message
