# Giperion/terminal/core/agent/diff_marks.py                        v002
# Подсветка диффа: строки целиком и изменённые слова внутри строк.
# Последнее изменение: пословная подсветка заменённых строк.

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

WORD = re.compile(r"\S+")


@dataclass(frozen=True)
class LineSpan:
    """Диапазон символов внутри строки."""

    line: int
    start: int
    end: int


@dataclass(frozen=True)
class DiffMarks:
    """Что подсветить слева и справа."""

    old_lines: frozenset[int]
    new_lines: frozenset[int]
    old_spans: tuple[LineSpan, ...]
    new_spans: tuple[LineSpan, ...]


def _tokens(text: str) -> list[tuple[str, int, int]]:
    """Слова строки вместе с позициями."""

    return [
        (match.group(), match.start(), match.end())
        for match in WORD.finditer(text)
    ]


def _word_spans(
    old_line: str,
    new_line: str,
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Возвращает изменённые диапазоны слов в двух строках."""

    old_tokens = _tokens(old_line)
    new_tokens = _tokens(new_line)

    matcher = SequenceMatcher(
        None,
        [token[0] for token in old_tokens],
        [token[0] for token in new_tokens],
    )

    old_spans: list[tuple[int, int]] = []
    new_spans: list[tuple[int, int]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            old_spans.extend(
                (old_tokens[index][1], old_tokens[index][2])
                for index in range(i1, i2)
            )

        if tag in ("replace", "insert"):
            new_spans.extend(
                (new_tokens[index][1], new_tokens[index][2])
                for index in range(j1, j2)
            )

    return old_spans, new_spans


def diff_marks(old_text: str, new_text: str) -> DiffMarks:
    """Строит полную разметку: строки и слова."""

    old_lines = str(old_text or "").splitlines()
    new_lines = str(new_text or "").splitlines()

    matcher = SequenceMatcher(None, old_lines, new_lines)

    old_whole: set[int] = set()
    new_whole: set[int] = set()
    old_spans: list[LineSpan] = []
    new_spans: list[LineSpan] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "delete":
            old_whole.update(range(i1, i2))

            continue

        if tag == "insert":
            new_whole.update(range(j1, j2))

            continue

        if tag != "replace":
            continue

        paired = min(i2 - i1, j2 - j1)

        for offset in range(paired):
            old_index = i1 + offset
            new_index = j1 + offset

            spans_old, spans_new = _word_spans(
                old_lines[old_index],
                new_lines[new_index],
            )

            old_spans.extend(
                LineSpan(old_index, start, end)
                for start, end in spans_old
            )
            new_spans.extend(
                LineSpan(new_index, start, end)
                for start, end in spans_new
            )

        if i2 - i1 > paired:
            old_whole.update(range(i1 + paired, i2))

        if j2 - j1 > paired:
            new_whole.update(range(j1 + paired, j2))

    return DiffMarks(
        old_lines=frozenset(old_whole),
        new_lines=frozenset(new_whole),
        old_spans=tuple(old_spans),
        new_spans=tuple(new_spans),
    )


def changed_lines(
    old_text: str,
    new_text: str,
) -> tuple[set[int], set[int]]:
    """Совместимость: номера изменённых строк с обеих сторон."""

    marks = diff_marks(old_text, new_text)

    old_changed = set(marks.old_lines) | {
        span.line for span in marks.old_spans
    }
    new_changed = set(marks.new_lines) | {
        span.line for span in marks.new_spans
    }

    return old_changed, new_changed


@dataclass(frozen=True)
class Hunk:
    """Один изменённый участок файла для частичного применения."""

    index: int
    old_start: int
    old_lines: tuple[str, ...]
    new_lines: tuple[str, ...]


def hunks(old_text: str, new_text: str) -> list[Hunk]:
    """Список изменённых участков; пустые участки не входят."""

    old_lines = str(old_text or "").splitlines()
    new_lines = str(new_text or "").splitlines()
    matcher = SequenceMatcher(None, old_lines, new_lines)
    result: list[Hunk] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        result.append(
            Hunk(
                index=len(result),
                old_start=i1 + 1,
                old_lines=tuple(old_lines[i1:i2]),
                new_lines=tuple(new_lines[j1:j2]),
            )
        )

    return result


def apply_hunks(
    old_text: str,
    new_text: str,
    selected: set[int] | None = None,
) -> str:
    """Собирает текст, применяя только выбранные участки.

    selected=None — применить всё. Переводы строк сохраняются как в
    исходных текстах.
    """

    old_raw = str(old_text or "").splitlines(keepends=True)
    new_raw = str(new_text or "").splitlines(keepends=True)
    matcher = SequenceMatcher(
        None,
        [line.rstrip("\r\n") for line in old_raw],
        [line.rstrip("\r\n") for line in new_raw],
    )
    result: list[str] = []
    index = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            result.extend(old_raw[i1:i2])
            continue

        if selected is None or index in selected:
            result.extend(new_raw[j1:j2])
        else:
            result.extend(old_raw[i1:i2])

        index += 1

    return "".join(result)
