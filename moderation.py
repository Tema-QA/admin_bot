import json
import re


MEDICAL_DISCLAIMER = (
    "Информация предоставлена в образовательных целях и не заменяет "
    "профессиональную медицинскую консультацию."
)


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

    hashtags = post.get("hashtags", [])

    if not isinstance(hashtags, list):
        return False, "Хэштеги имеют неправильный формат."

    if len(hashtags) > 5:
        return False, "Слишком много хэштегов: максимум 5."

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

    text = text.replace(MEDICAL_DISCLAIMER, "").strip()
    disclaimer = disclaimer.replace(MEDICAL_DISCLAIMER, "").strip(" .\n")

    normalized_hashtags = []
    for hashtag in hashtags:
        value = str(hashtag).strip()
        if not value:
            continue
        if not value.startswith("#"):
            value = f"#{value}"
        if value not in normalized_hashtags:
            normalized_hashtags.append(value)

    text_lines = []
    for line in text.splitlines():
        tokens = line.split()
        if tokens and all(re.fullmatch(r"#[\wА-Яа-яЁё-]+", token) for token in tokens):
            continue
        text_lines.append(line)
    text = "\n".join(text_lines).strip()

    hashtag_text = " ".join(normalized_hashtags)

    result = f"**{title}**\n\n{text}"

    if hashtag_text:
        result += f"\n\n{hashtag_text}"

    if disclaimer:
        result += f"\n\n⚠️ {disclaimer}"

    result += f"\n\n⚕️ {MEDICAL_DISCLAIMER}"

    return result