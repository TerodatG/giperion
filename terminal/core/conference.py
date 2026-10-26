# Giperion/app/core/conference.py                                  v004
# Параллельный совет: несколько моделей отвечают на одну реплику.
# Последнее изменение: не больше трёх сенаторов по репутации.

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from terminal.core.chatbot import get_response
from terminal.core.conference_roster import (
    reputation_requests,
    select_conference_models,
)
from terminal.core.model_catalog import (
    DEFAULT_MODEL_ID,
)
from terminal.core.model_engine import build_external_prompt
from terminal.core.model_errors import describe_model_error
from terminal.core.model_stats import (
    record_model_request,
)
from terminal.core.opencode_client import OpenCodeError, ask_model


@dataclass
class ConferenceReply:
    """Один ответ участника сената."""

    model_id: str
    name: str
    text: str
    save_to_history: bool
    error: bool = False
    tokens: int = 0
    nickname: str = ""
    senator: int = 0


def _nickname(model: dict) -> str:
    """Короткий ник участника для терминала связи."""

    return str(model.get("nickname") or model["name"])


def _ask_participant(
    model: dict,
    text: str,
    context: str,
    senator: int = 0,
) -> ConferenceReply:
    """Спрашивает одну модель; ошибку возвращает как ответ."""

    if model["id"] == DEFAULT_MODEL_ID:
        result = get_response(text)
        answer, save = result
        external_error = str(
            getattr(result, "external_error", "")
        )

        if external_error:
            return ConferenceReply(
                model_id=model["id"],
                name=model["name"],
                text=answer,
                save_to_history=False,
                error=True,
                nickname=_nickname(model),
                senator=senator,
            )

        return ConferenceReply(
            model_id=model["id"],
            name=model["name"],
            text=answer,
            save_to_history=save,
            tokens=len(text.split()),
            nickname=_nickname(model),
            senator=senator,
        )

    if not model.get("available") or not model.get("model_id"):
        return ConferenceReply(
            model_id=model["id"],
            name=model["name"],
            text=(
                f"Модель «{model['name']}» недоступна: "
                "канал связи не настроен."
            ),
            save_to_history=False,
            error=True,
            nickname=_nickname(model),
            senator=senator,
        )

    try:
        answer, usage = ask_model(
            model["model_id"],
            build_external_prompt(
                model["name"],
                text,
                context,
            ),
            provider_id=model["provider_id"] or "opencode",
            title=f"Сенат · {model['name']}",
        )
    except OpenCodeError as error:
        return ConferenceReply(
            model_id=model["id"],
            name=model["name"],
            text=describe_model_error(model["name"], error),
            save_to_history=False,
            error=True,
            nickname=_nickname(model),
            senator=senator,
        )

    return ConferenceReply(
        model_id=model["id"],
        name=model["name"],
        text=answer,
        save_to_history=True,
        tokens=usage.get("total", 0),
        nickname=_nickname(model),
        senator=senator,
    )


def order_conference_replies(
    replies: list[ConferenceReply],
) -> list[ConferenceReply]:
    """Ставит Гипериона первым, остальных — по убыванию репутации."""

    def order_key(item: tuple[int, ConferenceReply]) -> tuple:
        index, reply = item

        return (
            0 if reply.model_id == DEFAULT_MODEL_ID else 1,
            -reputation_requests(reply.model_id),
            index,
        )

    indexed = list(enumerate(replies))

    return [
        reply
        for _, reply in sorted(indexed, key=order_key)
    ]


def ask_conference(
    participants: list[dict],
    text: str,
    context: str = "",
) -> list[ConferenceReply]:
    """Запускает участников параллельно и сохраняет порядок ответов."""

    if not participants:
        return []

    # В совет пускаются только три модели с лучшей репутацией.
    roster = select_conference_models(participants)
    senators = {
        model["id"]: index + 1
        for index, model in enumerate(roster)
    }

    replies: list[ConferenceReply | None] = [None] * len(roster)

    with ThreadPoolExecutor(
        max_workers=len(roster),
    ) as executor:
        futures = {
            executor.submit(
                _ask_participant,
                model,
                text,
                context,
                senators[model["id"]],
            ): index
            for index, model in enumerate(roster)
        }

        for future, index in futures.items():
            try:
                replies[index] = future.result()
            except Exception as error:  # noqa: BLE001 — ошибку покажет окно
                model = roster[index]
                replies[index] = ConferenceReply(
                    model_id=model["id"],
                    name=model["name"],
                    text=describe_model_error(
                        model["name"],
                        error,
                    ),
                    save_to_history=False,
                    error=True,
                    nickname=_nickname(model),
                    senator=senators[model["id"]],
                )

    # Статистику пишем последовательно: JSON-файл не любит гонок.
    for reply in replies:
        if reply is not None:
            record_model_request(reply.model_id, reply.tokens)

    ordered = [reply for reply in replies if reply is not None]

    return order_conference_replies(ordered)
