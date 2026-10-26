# Giperion/terminal/core/agent/semantic_text.py                        v001
# Токенизация и грубый стемминг для смыслового поиска.
# Последнее изменение: вынесено из semantic.py.

import re

WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+")
CAMEL_LOWER_RE = re.compile(r"([a-z0-9])([A-Z])")
CAMEL_UPPER_RE = re.compile(r"([A-Z]+)([A-Z][a-z])")
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")

RU_ENDINGS = (
    "ениями", "ениям", "ением", "ении", "ение", "ений", "ения",
    "ями", "ами", "ов", "ев", "ий", "ия", "ию", "ей", "ой", "ый",
    "ая", "ое", "ые", "ых", "им", "ым", "ом", "ем", "ах", "ях",
    "ам", "ям", "ую", "юю", "ешь", "ишь", "ет", "ит", "ут", "ют",
    "ат", "ят", "ть", "ются", "ется", "ится", "атся",
    "ла", "ло", "ли", "а", "я", "ы", "и", "е", "о", "у", "ю", "ь",
)
MIN_STEM = 4

STOPWORDS = frozenset(
    """
    и в во не что он на я с со как а то все она так его но да ты к у же вы
    за бы по только ее мне было вот от меня еще нет о из ему теперь когда
    даже ну вдруг ли если уже или ни быть был него до вас нибудь опять уж
    вам ведь там потом себя ничего ей может они тут где есть надо ней для
    мы тебя их чем была сам чтоб без будто чего раз тоже себе под будет ж
    тогда кто этот того потому этого какой совсем ним здесь этом один
    почти мой тем чтобы нее сейчас были куда зачем сказать всех никогда
    сегодня можно при наконец два об другой хоть после над больше тот через
    эти нас про всего них какая много разве три эту моя впрочем хорошо свою
    этой перед иногда лучше чуть том нельзя такой им более всегда конечно
    всю между the a an and or if in on at to for of is are was were be been
    it this that with as by not from but you your we our they their he she
    his her have has had do does did can could should would may might will
    just than then there here what which who whom whose when where why how
    all any both each few more most other some such no nor only own same so
    too very s t don now
    """.split()
)


def _parts(word: str) -> list[str]:
    """Делит латинский camelCase, кириллицу оставляет целым словом."""

    if CYRILLIC_RE.search(word):
        return [word]

    spaced = CAMEL_LOWER_RE.sub(r"\1 \2", word)
    spaced = CAMEL_UPPER_RE.sub(r"\1 \2", spaced)

    return spaced.split()


def stem(word: str) -> str:
    """Грубая основа слова: срезает частые русские окончания и plural -s."""

    text = str(word or "").casefold()

    if CYRILLIC_RE.search(text):
        for ending in RU_ENDINGS:
            if not text.endswith(ending):
                continue

            candidate = text[: -len(ending)]

            if len(candidate) >= MIN_STEM:
                return candidate

        return text

    if len(text) > 3 and text.endswith("s") and not text.endswith("ss"):
        return text[:-1]

    return text


def tokens(text: str) -> list[str]:
    """Слова запроса и текста: camelCase и snake_case делятся на части."""

    result: list[str] = []

    for word in WORD_RE.findall(str(text)):
        for part in _parts(word):
            lowered = part.casefold()

            if len(lowered) < 2 or lowered in STOPWORDS:
                continue

            result.append(lowered)

    return result


def index_tokens(text: str) -> list[str]:
    """Слова для BM25: основы, чтобы падежи совпадали."""

    return [stem(word) for word in tokens(text)]
