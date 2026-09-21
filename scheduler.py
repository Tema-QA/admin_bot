from datetime import datetime, timezone

from moderation import format_post


async def publish_due_posts(
    database,
    bot,
) -> list[int]:
    now_iso = datetime.now(timezone.utc).replace(
        tzinfo=None
    ).isoformat()

    due_posts = database.get_due_posts(now_iso)
    published_ids = []

    for post in due_posts:
        settings = database.get_settings(post["admin_id"])
        target_chat_id = settings.get("target_chat_id")

        if not target_chat_id:
            database.set_status(
                post["id"],
                "error",
            )
            continue

        try:
            sent_message = await bot.send_message(
                chat_id=target_chat_id,
                text=format_post(post),
                parse_mode="Markdown",
            )

            database.set_status(
                post["id"],
                "published",
                published_message_id=sent_message.message_id,
            )

            published_ids.append(post["id"])

        except Exception:
            database.set_status(
                post["id"],
                "error",
            )

    return published_ids