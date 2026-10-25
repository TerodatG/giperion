# Giperion/tests/test_agent_diff_marks.py                            v001
# Подсветка изменённых строк для side-by-side.

from terminal.core.agent.diff_marks import (
    LineSpan,
    changed_lines,
    diff_marks,
)


def test_replaced_line_is_marked_on_both_sides() -> None:
    """Заменённая строка красится слева и справа."""

    old_changed, new_changed = changed_lines(
        "альфа\nбета\n",
        "альфа\nгамма\n",
    )

    assert old_changed == {1}
    assert new_changed == {1}


def test_inserted_lines_are_marked_on_the_right() -> None:
    """Вставка отмечается только справа."""

    old_changed, new_changed = changed_lines(
        "альфа\n",
        "альфа\nбета\n",
    )

    assert old_changed == set()
    assert new_changed == {1}


def test_deleted_lines_are_marked_on_the_left() -> None:
    """Удаление отмечается только слева."""

    old_changed, new_changed = changed_lines(
        "альфа\nбета\nгамма\n",
        "альфа\nгамма\n",
    )

    assert old_changed == {1}
    assert new_changed == set()


def test_same_text_has_no_marks() -> None:
    """Без изменений подсветки нет."""

    old_changed, new_changed = changed_lines("текст", "текст")

    assert old_changed == set()
    assert new_changed == set()


def test_only_changed_word_is_marked() -> None:
    """В заменённой строке красятся только изменённые слова."""

    marks = diff_marks(
        "альфа бета гамма",
        "альфа дельта гамма",
    )

    assert marks.old_lines == frozenset()
    assert marks.new_lines == frozenset()

    assert marks.old_spans == (LineSpan(0, 6, 10),)
    assert marks.new_spans == (LineSpan(0, 6, 12),)


def test_inserted_word_span() -> None:
    """Вставленное слово получает диапазон только справа."""

    marks = diff_marks("альфа гамма", "альфа новая гамма")

    assert marks.old_spans == ()
    assert marks.new_spans == (LineSpan(0, 6, 11),)


def test_extra_lines_are_marked_whole() -> None:
    """Если строк больше, лишние красятся целиком."""

    marks = diff_marks(
        "одна\nдве",
        "одна\nдве\nтри",
    )

    assert marks.new_lines == frozenset({2})
    assert marks.new_spans == ()
