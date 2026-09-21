import json


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

    hashtag_text = " ".join(
        tag if str(tag).startswith("#") else f"#{tag}"
        for tag in hashtags
    )

    result = f"**{title}**\n\n{text}"

    if disclaimer:
        result += f"\n\n⚕️ {disclaimer}"

    if hashtag_text:
        result += f"\n\n{hashtag_text}"

    result += f"\n\n⚕️ {MEDICAL_DISCLAIMER}"

    return result