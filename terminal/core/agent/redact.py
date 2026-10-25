# Giperion/terminal/core/agent/redact.py                              v001
# Редакция секретов: найденные ключи и пароли не уходят модели.
# Последнее изменение: первый вариант — шаблоны токенов, присваиваний,
# приватных ключей и строк подключения.

import re
from dataclasses import dataclass

MASK = "[скрыто]"

# Приватные ключи целиком: между BEGIN и END нет ничего полезного модели.
_PRIVATE_KEY = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"
    r".*?"
    r"-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)

# Токены с узнаваемым префиксом.
_TOKEN = re.compile(
    r"\b(?:"
    r"sk-[A-Za-z0-9_\-]{16,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|xox[abposr]-[A-Za-z0-9\-]{10,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|AIza[0-9A-Za-z_\-]{30,}"
    r"|glpat-[A-Za-z0-9_\-]{16,}"
    r"|hf_[A-Za-z0-9]{20,}"
    r"|eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"
    r")\b"
)

_BEARER = re.compile(
    r"(?i)\b(bearer\s+)([A-Za-z0-9._\-]{8,})"
)

# api_key = "...", "token": "..." — имя оставляем, значение скрываем.
_ASSIGN = re.compile(
    r"(?i)\b("
    r"api[_-]?key|apikey|secret|token|password|passwd|pwd|"
    r"access[_-]?key|secret[_-]?key|client[_-]?secret|private[_-]?key|"
    r"auth[_-]?token|refresh[_-]?token"
    r")\b(\s*[:=]\s*)([\"']?)([^\s\"',;]{6,})"
)

# postgres://user:пароль@host — прячем только пароль.
_URL_CRED = re.compile(r"(://[^/\s:@]+:)([^/\s@]{3,})(@)")

_PLACEHOLDER = re.compile(
    r"(?i)^(?:"
    r"x{3,}|\*+|\.{3,}|<[^>]*>|\$\{?[\w.]+\}?|%\(?\w+\)?s?|"
    r"none|null|true|false|your[_-].*|example.*|change[_-]?me|"
    r"placeholder|todo|hidden|скрыто|\[скрыто\]"
    r")$"
)


@dataclass(frozen=True)
class Redaction:
    """Текст после редакции и число скрытых фрагментов."""

    text: str
    hidden: int


def _is_reference(value: str) -> bool:
    """Значение — ссылка на переменную, а не сам секрет."""

    if any(char in value for char in "([{"):
        return True

    if "." in value and re.fullmatch(r"[A-Za-z_][\w.]*", value):
        return True

    # os.environ, API_KEY — имя, а не значение.
    if re.fullmatch(r"[A-Z][A-Z0-9_]+", value):
        return True

    return bool(re.fullmatch(r"[a-z_]+", value) and len(value) < 12)


def _assign_value(match: re.Match) -> str:
    """Скрывает значение присваивания, если это похоже на секрет."""

    name, separator, quote, value = match.groups()

    if _PLACEHOLDER.match(value) or _is_reference(value):
        return match.group(0)

    return f"{name}{separator}{quote}{MASK}"


def _hide_assignments(text: str) -> tuple[str, int]:
    """Скрывает значения присваиваний и считает только реальные замены."""

    changes = 0

    def replace(match: re.Match) -> str:
        nonlocal changes

        replacement = _assign_value(match)

        if replacement != match.group(0):
            changes += 1

        return replacement

    return _ASSIGN.sub(replace, text), changes


def redact(text: str) -> Redaction:
    """Скрывает секреты и сообщает, сколько фрагментов найдено."""

    source = str(text or "")

    if not source:
        return Redaction(source, 0)

    hidden = 0
    result = source

    result, count = _PRIVATE_KEY.subn(MASK, result)
    hidden += count

    result, count = _TOKEN.subn(MASK, result)
    hidden += count

    result, count = _BEARER.subn(
        lambda match: match.group(1) + MASK,
        result,
    )
    hidden += count

    result, count = _URL_CRED.subn(
        lambda match: match.group(1) + MASK + match.group(3),
        result,
    )
    hidden += count

    result, count = _hide_assignments(result)
    hidden += count

    return Redaction(result, hidden)
