import json
import re


def validate_post(post: dict, settings: dict) -> tuple[bool, str]:
    text = str(post.get("text", "")).strip()
    title = str(post.get("title", "")).strip()

    if not title:
        return False, "Не указан заголовок."

    if not text:
        return False, "Пост пустой."

    if len(text) < 300:
        return False, "Текст короче 300 символов."

    if len(text) > 5000:
        return False, "Текст слишком длинный."

    forbidden_raw = settings.get("forbidden_topics", "")
    forbidden_topics = [
        item.strip().lower()
        for item in forbidden_raw.split(",")
        if item.strip()
    ]

    combined = f"{title}\n{text}".lower()

    for topic in forbidden_topics:
        if topic in combined:
            return False, f"Обнаружена запрещённая тема: {topic}"

    risky_phrases = [
        "гарантированно вылечит",
        "заменяет врача",
        "отмените препарат",
        "не обращайтесь к врачу",
        "точно избавит",
    ]

    for phrase in risky_phrases:
        if phrase in combined:
            return False, f"Обнаружена рискованная формулировка: {phrase}"

    hashtags = post.get("hashtags", [])

    if not isinstance(hashtags, list):
        return False, "Хэштеги имеют неправильный формат."

    if len(hashtags) < 3 or len(hashtags) > 5:
        return False, "Должно быть от 3 до 5 хэштегов."

    for hashtag in hashtags:
        if not re.fullmatch(r"#[A-Za-zА-Яа-яЁё0-9_]+", str(hashtag)):
            return False, f"Некорректный хэштег: {hashtag}"

    return True, "Проверка пройдена."


def format_post(post: dict) -> str:
    title = str(post.get("title", "")).strip()
    text = str(post.get("text", "")).strip()
    disclaimer = str(post.get("disclaimer", "")).strip()
    hashtags = post.get("hashtags", [])

    if isinstance(hashtags, str):
        try:
            hashtags = json.loads(hashtags)
        except json.JSONDecodeError:
            hashtags = []

    if not isinstance(hashtags, list):
        hashtags = []

    hashtag_text = " ".join(
        tag if str(tag).startswith("#") else f"#{tag}"
        for tag in hashtags
    )

    result = f"**{title}**\n\n{text}"

    if disclaimer:
        result += f"\n\n⚕️ {disclaimer}"

    if hashtag_text:
        result += f"\n\n{hashtag_text}"

    return result