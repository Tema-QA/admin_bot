import json
import re

import aiohttp


class YandexGPTGenerator:
    def __init__(
        self,
        api_key: str,
        folder_id: str,
        model: str,
    ):
        self.api_key = api_key
        self.folder_id = folder_id
        self.model = model
        self.url = (
            "https://llm.api.cloud.yandex.net/"
            "foundationModels/v1/completion"
        )

    def build_prompt(
        self,
        settings: dict,
        recent_posts: list[dict],
        requested_topic: str,
    ) -> str:
        recent_titles = []

        for post in recent_posts:
            recent_titles.append(post.get("title", ""))

        recent_titles_text = "\n".join(
            f"- {title}" for title in recent_titles if title
        )

        forbidden_topics = settings.get(
            "forbidden_topics",
            "",
        )

        rubrics = settings.get("rubrics", "")

        return f"""
Ты — редактор Telegram-канала о здоровье.

Создай один пост на русском языке.

Настройки канала:
- Тематика: {settings.get("channel_theme", "здоровье")}
- Целевая аудитория: {settings.get("audience", "")}
- Стиль: {settings.get("style", "простой и понятный")}
- Рубрики: {rubrics}
- Запрещённые темы: {forbidden_topics}
- Тема от администратора: {requested_topic}

Посты, опубликованные недавно:
{recent_titles_text}

Не повторяй темы и формулировки последних 100 постов.
Если тема администратора задана, используй её как основу.
Если тема пустая, выбери полезную тему в рамках тематики канала.

Требования:
- писать на русском языке;
- простой и понятный стиль;
- длина основного текста 800–1500 символов;
- структурировать текст на 3–5 коротких блоков, разделённых пустой строкой;
- использовать текстовые элементы инфографики: эмодзи-метки, короткие заголовки блоков и списки;
- добавить практический чек-лист из 3–6 пунктов с квадратными маркерами: ☐ пункт;
- не превращать пост в сплошную стену текста;
- не использовать кликбейт;
- не обещать лечение;
- не ставить диагнозы;
- не рекомендовать отменять назначенные врачом препараты;
- отделять научные факты от личных советов;
- добавить короткий призыв к обсуждению;
- добавить 3–5 релевантных хэштегов;
- не использовать запрещённые темы;
- не выдавать медицинскую рекомендацию как замену врачу.
- Не добавляй в поля title или text медицинскую оговорку;
- поле disclaimer оставь пустым: стандартная оговорка добавляется ботом один раз.

Верни только JSON:
{{
  "title": "...",
  "text": "...",
  "hashtags": ["...", "..."],
  "disclaimer": "..."
}}
"""

    async def generate(
        self,
        settings: dict,
        recent_posts: list[dict],
        requested_topic: str,
    ) -> dict:
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "x-folder-id": self.folder_id,
            "Content-Type": "application/json",
        }

        payload = {
            "modelUri": f"gpt://{self.folder_id}/{self.model}",
            "completionOptions": {
                "stream": False,
                "temperature": 0.7,
                "maxTokens": 2400,
            },
            "messages": [
                {
                    "role": "system",
                    "text": (
                        "Ты профессиональный редактор "
                        "медицинского Telegram-канала."
                    ),
                },
                {
                    "role": "user",
                    "text": self.build_prompt(
                        settings,
                        recent_posts,
                        requested_topic,
                    ),
                },
            ],
        }

        timeout = aiohttp.ClientTimeout(total=90)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                self.url,
                headers=headers,
                json=payload,
            ) as response:
                response_text = await response.text()

                if response.status >= 400:
                    raise RuntimeError(
                        f"YandexGPT {response.status}: "
                        f"{response_text[:1000]}"
                    )

                data = json.loads(response_text)

        alternatives = data.get("result", {}).get("alternatives", [])

        if not alternatives:
            raise RuntimeError("YandexGPT не вернул ответ.")

        content = alternatives[0].get("message", {}).get("text", "")
        content = content.strip()

        if content.startswith("```"):
            content = re.sub(
                r"^```(?:json)?\s*",
                "",
                content,
                flags=re.IGNORECASE,
            )
            content = re.sub(
                r"\s*```$",
                "",
                content,
            ).strip()

        start = content.find("{")
        end = content.rfind("}")

        if start == -1 or end == -1:
            raise ValueError(
                f"YandexGPT вернул не JSON: {content[:500]}"
            )

        result = json.loads(content[start : end + 1])

        title = str(result.get("title", "")).strip()
        text = str(result.get("text", "")).strip()
        disclaimer = str(result.get("disclaimer", "")).strip()
        hashtags = result.get("hashtags", [])

        if not isinstance(hashtags, list):
            hashtags = []

        hashtags = [
            str(tag).strip()
            for tag in hashtags
            if str(tag).strip()
        ]

        if not title or not text:
            raise ValueError(
                "YandexGPT вернул пустой заголовок или текст."
            )

        return {
            "title": title,
            "text": text,
            "hashtags": hashtags[:5],
            "disclaimer": disclaimer,
        }