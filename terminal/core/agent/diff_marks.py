# Giperion/terminal/core/agent/diff_marks.py                        v001
# Подсветка изменённых строк для side-by-side диффа.
# Последнее изменение: первый вариант — opcodes difflib.

from difflib import SequenceMatcher


def changed_lines(
    old_text: str,
    new_text: str,
) -> tuple[set[int], set[int]]:
    """Возвращает номера изменённых строк слева и справа (с нуля)."""

    old_lines = str(old_text or "").splitlines()
    new_lines = str(new_text or "").splitlines()

    matcher = SequenceMatcher(None, old_lines, new_lines)
    old_changed: set[int] = set()
    new_changed: set[int] = set()

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            old_changed.update(range(i1, i2))

        if tag in ("replace", "insert"):
            new_changed.update(range(j1, j2))

    return old_changed, new_changed
