# Giperion/terminal/core/agent/plan.py                                 v001
# План задачи: разбор редактируемого текста в пункты и обратно.
# Последнее изменение: первый вариант — [ ]/[>]/[x] и нумерация.

import re

LINE = re.compile(
    r"^\s*(?:\d+[.)]\s*)?(?:\[(?P<mark>[ xX>])\]\s*)?(?P<text>.+?)\s*$"
)
STATUS_BY_MARK = {" ": "pending", ">": "doing", "x": "done", "X": "done"}


def parse(text: str) -> list[dict]:
    """Строки плана в пункты; пустые строки пропускаются."""

    result = []

    for line in str(text or "").splitlines():
        match = LINE.match(line)

        if match is None:
            continue

        value = match.group("text").strip()

        if not value:
            continue

        result.append(
            {
                "text": value[:200],
                "status": STATUS_BY_MARK.get(
                    match.group("mark") or " ",
                    "pending",
                ),
            }
        )

    return result[:12]


def cycle(status: str) -> str:
    """Следующий статус пункта."""

    return {
        "pending": "doing",
        "doing": "done",
        "done": "pending",
    }.get(str(status), "pending")
