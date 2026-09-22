import asyncio
import base64
import json
import random
import re

import aiohttp


YANDEX_ART_PROMPT_MAX_LEN = 500

INFOGRAPHIC_STYLE_BASE = (
    "Flat health infographic, portrait, white bg, rounded cards, "
    "icons, Russian text, checklist, #здоровье_просто, no photo."
)

STYLE_VARIANTS = (
    "Blue-cyan, water drops.",
    "Mint-green, leaves.",
    "Soft green, sun icon.",
)


def _shorten(text: str, limit: int) -> str:
    value = " ".join(str(text).split())

    if len(value) <= limit:
        return value

    if limit <= 1:
        return value[:limit]

    return value[: limit - 1].rstrip() + "…"


def _fit_art_prompt(prompt: str, max_len: int = YANDEX_ART_PROMPT_MAX_LEN) -> str:
    compact = " ".join(prompt.split())

    if len(compact) <= max_len:
        return compact

    return compact[: max_len - 1].rstrip() + "…"


def normalize_brief_for_art(brief: dict) -> dict:
    items = brief.get("items", [])

    if not isinstance(items, list):
        items = []

    normalized_items = []

    for item in items[:3]:
        text = _shorten(str(item).strip(), 28)

        if text:
            normalized_items.append(text)

    return {
        "title": _shorten(brief.get("title", ""), 42),
        "subtitle": _shorten(brief.get("subtitle", ""), 32),
        "items": normalized_items,
        "footer": "#здоровье_просто",
    }


class YandexArtGenerator:
    def __init__(
        self,
        api_key: str,
        folder_id: str,
        model: str = "yandex-art/latest",
    ):
        self.api_key = api_key
        self.folder_id = folder_id
        self.model = model
        self.generate_url = (
            "https://llm.api.cloud.yandex.net/"
            "foundationModels/v1/imageGenerationAsync"
        )
        self.operations_url = (
            "https://llm.api.cloud.yandex.net/operations"
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Api-Key {self.api_key}",
            "x-folder-id": self.folder_id,
            "Content-Type": "application/json",
        }

    async def generate_image(
        self,
        prompt: str,
        seed: int | None = None,
        width_ratio: str = "3",
        height_ratio: str = "4",
    ) -> bytes:
        if seed is None:
            seed = random.randint(1, 2_000_000_000)

        prompt = _fit_art_prompt(prompt)

        payload = {
            "modelUri": f"art://{self.folder_id}/{self.model}",
            "generationOptions": {
                "seed": seed,
                "aspectRatio": {
                    "widthRatio": width_ratio,
                    "heightRatio": height_ratio,
                },
            },
            "messages": [
                {
                    "weight": "1",
                    "text": prompt,
                }
            ],
        }

        timeout = aiohttp.ClientTimeout(total=180)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                self.generate_url,
                headers=self._headers(),
                json=payload,
            ) as response:
                response_text = await response.text()

                if response.status >= 400:
                    raise RuntimeError(
                        f"YandexART {response.status}: "
                        f"{response_text[:1000]}"
                    )

                operation = json.loads(response_text)

            operation_id = operation.get("id")

            if not operation_id:
                raise RuntimeError(
                    "YandexART не вернул id операции."
                )

            for _ in range(60):
                await asyncio.sleep(3)

                async with session.get(
                    f"{self.operations_url}/{operation_id}",
                    headers=self._headers(),
                ) as response:
                    response_text = await response.text()

                    if response.status >= 400:
                        raise RuntimeError(
                            f"YandexART operation {response.status}: "
                            f"{response_text[:500]}"
                        )

                    status_data = json.loads(response_text)

                if status_data.get("done"):
                    error = status_data.get("error")

                    if error:
                        raise RuntimeError(
                            f"YandexART: {error}"
                        )

                    image_b64 = (
                        status_data.get("response", {}).get("image")
                    )

                    if not image_b64:
                        raise RuntimeError(
                            "YandexART не вернул изображение."
                        )

                    return base64.b64decode(image_b64)

            raise TimeoutError(
                "YandexART: превышено время ожидания генерации."
            )

    async def generate_variants(
        self,
        prompts: list[str],
        seeds: list[int] | None = None,
    ) -> list[bytes]:
        if seeds is None:
            seeds = [
                random.randint(1, 2_000_000_000)
                for _ in prompts
            ]

        tasks = [
            self.generate_image(prompt, seed=seed)
            for prompt, seed in zip(prompts, seeds)
        ]

        return await asyncio.gather(*tasks)


def build_art_prompts(brief: dict) -> list[str]:
    normalized = normalize_brief_for_art(brief)
    title = normalized["title"]
    subtitle = normalized["subtitle"]
    items = normalized["items"]
    footer = normalized["footer"]

    items_text = "; ".join(items) if items else "краткий список советов"

    prompts = []

    for variant in STYLE_VARIANTS:
        prompt = (
            f"{INFOGRAPHIC_STYLE_BASE} {variant} "
            f"Title: {title}. Subtitle: {subtitle}. "
            f"Points: {items_text}. Footer: {footer}."
        )
        prompts.append(_fit_art_prompt(prompt))

    return prompts


async def build_infographic_brief(
    gpt_generator,
    post: dict,
) -> dict:
    title = str(post.get("title", "")).strip()
    text = str(post.get("text", "")).strip()
    hashtags = post.get("hashtags", [])

    if isinstance(hashtags, str):
        try:
            hashtags = json.loads(hashtags)
        except json.JSONDecodeError:
            hashtags = []

    hashtag_text = " ".join(
        str(tag).strip() for tag in hashtags if str(tag).strip()
    )

    prompt = f"""
По тексту поста подготовь ТЗ на инфографику для генератора картинок.
Лимит текста на изображении жёсткий: заголовок до 40 символов, подзаголовок до 30,
ровно 3 пункта, каждый до 25 символов, без длинных слов.

Заголовок поста: {title}
Текст поста:
{text}

Верни только JSON:
{{
  "title": "до 40 символов",
  "subtitle": "до 30 символов",
  "items": ["пункт 1", "пункт 2", "пункт 3"],
  "footer": "{hashtag_text or '#здоровье_просто'}"
}}
"""

    headers = {
        "Authorization": f"Api-Key {gpt_generator.api_key}",
        "x-folder-id": gpt_generator.folder_id,
        "Content-Type": "application/json",
    }

    payload = {
        "modelUri": (
            f"gpt://{gpt_generator.folder_id}/"
            f"{gpt_generator.model}"
        ),
        "completionOptions": {
            "stream": False,
            "temperature": 0.4,
            "maxTokens": 800,
        },
        "messages": [
            {
                "role": "system",
                "text": (
                    "Ты дизайнер инфографики для медицинского "
                    "Telegram-канала. Отвечай только JSON."
                ),
            },
            {
                "role": "user",
                "text": prompt,
            },
        ],
    }

    timeout = aiohttp.ClientTimeout(total=60)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            gpt_generator.url,
            headers=headers,
            json=payload,
        ) as response:
            response_text = await response.text()

            if response.status >= 400:
                raise RuntimeError(
                    f"YandexGPT brief {response.status}: "
                    f"{response_text[:800]}"
                )

            data = json.loads(response_text)

    alternatives = data.get("result", {}).get("alternatives", [])

    if not alternatives:
        raise RuntimeError(
            "Не удалось подготовить ТЗ для инфографики."
        )

    content = alternatives[0].get("message", {}).get("text", "")
    content = content.strip()

    if content.startswith("```"):
        content = re.sub(
            r"^```(?:json)?\s*",
            "",
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(r"\s*```$", "", content).strip()

    start = content.find("{")
    end = content.rfind("}")

    if start == -1 or end == -1:
        raise ValueError(
            f"ТЗ инфографики не в JSON: {content[:300]}"
        )

    brief = json.loads(content[start : end + 1])

    if not brief.get("title"):
        brief["title"] = title

    if not brief.get("items"):
        brief["items"] = [
            line.strip(" ☐•-\t")
            for line in text.splitlines()
            if line.strip()
        ][:3]

    return normalize_brief_for_art(brief)
