# Giperion/tests/test_agent_diff_marks.py                            v001
# Подсветка изменённых строк для side-by-side.

from terminal.core.agent.diff_marks import changed_lines


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
