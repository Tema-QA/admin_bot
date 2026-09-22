import json
import sqlite3
from datetime import datetime
from typing import Any


class Database:
    def __init__(self, path: str):
        self.path = path
        self.initialize()

    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self):
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    admin_id INTEGER PRIMARY KEY,
                    channel_theme TEXT NOT NULL DEFAULT '',
                    audience TEXT NOT NULL DEFAULT '',
                    style TEXT NOT NULL DEFAULT '',
                    frequency TEXT NOT NULL DEFAULT '',
                    publish_time TEXT NOT NULL DEFAULT '',
                    images_enabled INTEGER NOT NULL DEFAULT 0,
                    forbidden_topics TEXT NOT NULL DEFAULT '',
                    rubrics TEXT NOT NULL DEFAULT '',
                    target_chat_id TEXT NOT NULL DEFAULT '',
                    target_chat_title TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    text TEXT NOT NULL DEFAULT '',
                    hashtags TEXT NOT NULL DEFAULT '[]',
                    disclaimer TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'draft',
                    scheduled_at TEXT,
                    published_message_id INTEGER,
                    image_file_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

            self._ensure_post_columns(connection)

    def _ensure_post_columns(self, connection):
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(posts)"
            ).fetchall()
        }

        if "image_file_id" not in columns:
            connection.execute(
                """
                ALTER TABLE posts
                ADD COLUMN image_file_id TEXT NOT NULL DEFAULT ''
                """
            )

    def ensure_admin(self, admin_id: int):
        now = datetime.utcnow().isoformat()

        with self.connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO settings (admin_id)
                VALUES (?)
                """,
                (admin_id,),
            )

            connection.execute(
                """
                UPDATE settings
                SET
                    channel_theme = channel_theme,
                    audience = audience,
                    style = style,
                    frequency = frequency,
                    publish_time = publish_time,
                    images_enabled = images_enabled,
                    forbidden_topics = forbidden_topics,
                    rubrics = rubrics,
                    target_chat_id = target_chat_id,
                    target_chat_title = target_chat_title
                WHERE admin_id = ?
                """,
                (admin_id,),
            )

    def get_settings(self, admin_id: int) -> dict[str, Any]:
        self.ensure_admin(admin_id)

        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM settings
                WHERE admin_id = ?
                """,
                (admin_id,),
            ).fetchone()

        return dict(row)

    def update_setting(
        self,
        admin_id: int,
        field: str,
        value: Any,
    ):
        allowed_fields = {
            "channel_theme",
            "audience",
            "style",
            "frequency",
            "publish_time",
            "images_enabled",
            "forbidden_topics",
            "rubrics",
            "target_chat_id",
            "target_chat_title",
        }

        if field not in allowed_fields:
            raise ValueError(f"Недопустимое поле настроек: {field}")

        self.ensure_admin(admin_id)

        with self.connect() as connection:
            connection.execute(
                f"""
                UPDATE settings
                SET {field} = ?
                WHERE admin_id = ?
                """,
                (value, admin_id),
            )

    def create_post(
        self,
        admin_id: int,
        title: str,
        text: str,
        hashtags: list[str],
        disclaimer: str,
    ) -> int:
        now = datetime.utcnow().isoformat()

        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO posts (
                    admin_id,
                    title,
                    text,
                    hashtags,
                    disclaimer,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'draft', ?, ?)
                """,
                (
                    admin_id,
                    title,
                    text,
                    json.dumps(hashtags, ensure_ascii=False),
                    disclaimer,
                    now,
                    now,
                ),
            )

            return int(cursor.lastrowid)

    def get_post(self, post_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM posts
                WHERE id = ?
                """,
                (post_id,),
            ).fetchone()

        return dict(row) if row else None

    def update_post_text(
        self,
        post_id: int,
        text: str,
    ):
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE posts
                SET
                    text = ?,
                    image_file_id = '',
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    text,
                    datetime.utcnow().isoformat(),
                    post_id,
                ),
            )

    def set_post_image(
        self,
        post_id: int,
        image_file_id: str,
    ):
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE posts
                SET
                    image_file_id = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    image_file_id,
                    datetime.utcnow().isoformat(),
                    post_id,
                ),
            )

    def clear_post_image(self, post_id: int):
        self.set_post_image(post_id, "")

    def update_post(
        self,
        post_id: int,
        title: str,
        text: str,
        hashtags: list[str],
        disclaimer: str,
    ):
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE posts
                SET
                    title = ?,
                    text = ?,
                    hashtags = ?,
                    disclaimer = ?,
                    image_file_id = '',
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    title,
                    text,
                    json.dumps(hashtags, ensure_ascii=False),
                    disclaimer,
                    datetime.utcnow().isoformat(),
                    post_id,
                ),
            )

    def set_status(
        self,
        post_id: int,
        status: str,
        scheduled_at: str | None = None,
        published_message_id: int | None = None,
    ):
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE posts
                SET
                    status = ?,
                    scheduled_at = ?,
                    published_message_id = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    scheduled_at,
                    published_message_id,
                    datetime.utcnow().isoformat(),
                    post_id,
                ),
            )

    def get_due_posts(self, now_iso: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM posts
                WHERE status = 'scheduled'
                  AND scheduled_at IS NOT NULL
                  AND scheduled_at <= ?
                ORDER BY scheduled_at
                LIMIT 20
                """,
                (now_iso,),
            ).fetchall()

        return [dict(row) for row in rows]

    def get_recent_posts(
        self,
        admin_id: int,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM posts
                WHERE admin_id = ?
                  AND status = 'published'
                ORDER BY published_message_id DESC
                LIMIT ?
                """,
                (admin_id, limit),
            ).fetchall()

        return [dict(row) for row in rows]