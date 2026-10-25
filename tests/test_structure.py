# Giperion/tests/test_structure.py                                    v001
# Структурные лимиты проекта: файлы, функции и сложность.
# Последнее изменение: лимиты закреплены после разбора крупных модулей.

from tools import check_structure


def test_no_overloaded_files_or_functions() -> None:
    """Новый перегруженный модуль должен падать здесь, а не в ревью."""

    files: list[str] = []
    functions: list[str] = []
    complex_functions: list[str] = []

    for path in check_structure.source_files():
        file_notes, function_notes, complexity_notes = (
            check_structure.inspect(path)
        )
        files.extend(file_notes)
        functions.extend(function_notes)
        complex_functions.extend(complexity_notes)

    problems = files + functions + complex_functions

    assert not problems, "Перегруженные места:\n" + "\n".join(problems)
