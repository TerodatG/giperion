# Giperion/app/core/model_errors.py                                 v001
# Понятные сообщения об ошибках внешних моделей.
# Последнее изменение: лимит OpenCode распознаётся и переводится.

# Признаки исчерпанного лимита или квоты в ответе OpenCode.
LIMIT_MARKERS = (
    "free usage limit",
    "usage limit",
    "rate limit",
    "quota",
    "insufficient",
    "limit reached",
)


def describe_model_error(model_name: str, error: object) -> str:
    """Переводит техническую ошибку модели в короткую понятную фразу."""

    reason = str(error).strip()

    if reason.lower().startswith("модель сообщила об ошибке:"):
        reason = reason.split(":", 1)[1].strip()

    lowered = reason.lower()

    if any(marker in lowered for marker in LIMIT_MARKERS):
        return (
            f"Модель «{model_name}»: бесплатный лимит исчерпан. "
            "Подключи провайдера или подписку OpenCode Go, либо "
            "выбери Гипериона — он отвечает локально."
        )

    if len(reason) > 220:
        reason = reason[:220].rstrip() + "…"

    if not reason:
        reason = "нет ответа от сервиса."

    return f"Модель «{model_name}» не ответила: {reason}"
