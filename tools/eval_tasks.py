# Giperion/tools/eval_tasks.py                                        v001
# Задачи стенда: проверки, подготовка, инспекторы и каталог.
# Последнее изменение: вынесено из eval_agent.

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

Check = Callable[[Path, str], tuple[bool, str]]
Inspect = Callable[[Path, object], tuple[bool, str]]
Prepare = Callable[[Path], object]


@dataclass(frozen=True)
class EvalTask:
    """Одна проверяемая задача."""

    id: str
    title: str
    task: str
    check: Check
    setup: Callable[[Path], None] | None = None
    max_steps: int = 8
    slow: bool = False
    notes: str = ""
    # Проверка по всему результату (шаги, ответ), а не только по тексту.
    inspect: Inspect | None = None
    # Контекст, который включается на время прогона (сеть, MCP-стаб).
    prepare: Prepare | None = None


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def answer_has(*needles: str) -> Check:
    """Ответ должен содержать все фрагменты."""

    def check(_root: Path, answer: str) -> tuple[bool, str]:
        text = str(answer or "").casefold()
        missing = [
            needle for needle in needles
            if needle.casefold() not in text
        ]

        if not missing:
            return True, "в ответе есть " + ", ".join(needles)

        return False, "в ответе нет: " + ", ".join(missing)

    return check


def file_has(relative: str, needle: str) -> Check:
    """Файл должен существовать и содержать фрагмент."""

    def check(root: Path, _answer: str) -> tuple[bool, str]:
        text = _text(root / relative)
        ok = bool(text) and needle.casefold() in text.casefold()

        return (
            ok,
            f"{relative}: {'есть' if ok else 'нет'} «{needle}»",
        )

    return check


def file_equals(relative: str, expected: str) -> Check:
    """Файл должен совпасть с ожидаемым текстом."""

    def check(root: Path, _answer: str) -> tuple[bool, str]:
        actual = _text(root / relative).strip()
        ok = actual == expected.strip()

        return ok, f"{relative}: {'совпал' if ok else 'не совпал'}"

    return check


def readme_line_count() -> Check:
    """Ответ должен содержать число строк README."""

    def check(root: Path, answer: str) -> tuple[bool, str]:
        count = len(_text(root / "README.md").splitlines())
        ok = str(count) in str(answer or "")

        return ok, f"ожидали {count}"

    return check


def tests_passed() -> Check:
    """Ответ должен сообщать об успешных тестах — на любом языке."""

    markers = (
        "passed",
        "код 0",
        "пройдено",
        "прошли",
        "успешно",
        "зелён",
        "зелен",
    )

    def check(_root: Path, answer: str) -> tuple[bool, str]:
        text = str(answer or "").casefold()
        ok = any(marker in text for marker in markers)

        return ok, "есть результат тестов" if ok else "нет результата"

    return check


def _setup_note(root: Path) -> None:
    (root / "eval_note.md").write_text("# Заметка\n", encoding="utf-8")

from tools.eval_prepares import (
    _browser_prepare,
    _mcp_prepare,
    _plan_inspect,
    _semantic_inspect,
    _subagents_inspect,
    _web_prepare,
)

TASKS = (
    EvalTask(
        "find-load-models",
        "Поиск функции",
        "Где объявлена функция load_models? Найди и назови файл.",
        answer_has("model_catalog.py"),
        max_steps=5,
    ),
    EvalTask(
        "readme-lines",
        "Сколько строк в README",
        "Прочитай README.md и скажи, сколько в нём строк.",
        readme_line_count(),
        max_steps=4,
    ),
    EvalTask(
        "find-merge-worktree",
        "Поиск merge_worktree",
        "Найди функцию merge_worktree и назови файл, где она объявлена.",
        answer_has("worktrees.py"),
        max_steps=5,
    ),
    EvalTask(
        "architecture-agent-section",
        "Раздел про агента",
        "Прочитай docs/architecture.md и скажи, как называется раздел про агента.",
        answer_has("агент"),
        max_steps=4,
    ),
    EvalTask(
        "find-command-whitelist",
        "Белый список команд",
        "Где проверяется, какие команды агенту разрешены (validate_command)? "
        "Найди и назови файл.",
        answer_has("commands.py"),
        max_steps=7,
    ),
    EvalTask(
        "write-note",
        "Создать файл",
        "В корне проекта создай файл eval_note.md с текстом «# Заметка».",
        file_equals("eval_note.md", "# Заметка"),
        max_steps=5,
    ),
    EvalTask(
        "patch-note",
        "Точечная правка",
        "Замени в eval_note.md слово «Заметка» на «Готово».",
        file_has("eval_note.md", "Готово"),
        setup=_setup_note,
        max_steps=6,
    ),
    EvalTask(
        "two-files",
        "Две записи за задачу",
        "В корне проекта создай за одну задачу два файла: eval_a.txt "
        "с текстом «альфа» и eval_b.txt с текстом «бета».",
        lambda root, _answer: (
            (
                _text(root / "eval_a.txt").strip() == "альфа"
                and _text(root / "eval_b.txt").strip() == "бета"
            ),
            "оба файла в корне"
            if (
                _text(root / "eval_a.txt").strip() == "альфа"
                and _text(root / "eval_b.txt").strip() == "бета"
            )
            else "файлы не в корне или текст другой",
        ),
        max_steps=10,
    ),
    EvalTask(
        "run-tests",
        "Запуск тестов",
        "Запусти тесты и коротко скажи, сколько прошло.",
        tests_passed(),
        max_steps=6,
        slow=True,
    ),
    EvalTask(
        "two-functions",
        "Две функции",
        "Найди, где объявлены create_worktree и merge_worktree, "
        "и назови файл.",
        answer_has("worktrees.py"),
        max_steps=6,
    ),
    EvalTask(
        "find-base-dir",
        "Где BASE_DIR",
        "Где в проекте задан BASE_DIR? Назови файл.",
        answer_has("config.py"),
        max_steps=5,
    ),
    EvalTask(
        "find-native-brain",
        "Где NativeBrain",
        "Найди, в каком файле объявлен класс NativeBrain.",
        answer_has("native_brain.py"),
        max_steps=5,
    ),
    EvalTask(
        "find-max-prompt",
        "Лимит контекста",
        "Где задан MAX_PROMPT — лимит контекста агента? Назови файл.",
        answer_has("context.py"),
        max_steps=5,
    ),
    EvalTask(
        "docs-passport",
        "Раздел про паспорт",
        "Прочитай docs/architecture.md через read_file и назови раздел "
        "про паспорт модели. Ответ — заголовок раздела.",
        answer_has("паспорт"),
        max_steps=5,
    ),
    EvalTask(
        "docs-plugins",
        "Плагины в документации",
        "Прочитай docs/agent_tools.md и скажи, из каких двух файлов "
        "состоит плагин. Назови расширения файлов.",
        lambda root, answer: (
            (
                ".json" in str(answer).casefold()
                and ".py" in str(answer).casefold()
            )
            or (
                "json" in str(answer).casefold()
                and "python" in str(answer).casefold()
            ),
            "оба формата названы"
            if (
                (
                    ".json" in str(answer).casefold()
                    and ".py" in str(answer).casefold()
                )
                or (
                    "json" in str(answer).casefold()
                    and "python" in str(answer).casefold()
                )
            )
            else "форматы не названы",
        ),
        max_steps=6,
    ),
    EvalTask(
        "create-two-lines",
        "Файл из двух строк",
        "В корне проекта создай файл eval_lines.txt с двумя строками: "
        "«альфа» и «бета».",
        lambda root, _answer: (
            (
                _text(root / "eval_lines.txt").strip().splitlines()
                == ["альфа", "бета"]
            ),
            "две строки на месте"
            if _text(root / "eval_lines.txt").strip().splitlines()
            == ["альфа", "бета"]
            else "строки не совпали",
        ),
        max_steps=7,
    ),
    EvalTask(
        "symbol-nativebrain",
        "Символ через индекс",
        "Где объявлен класс NativeBrain? Используй find_symbol и назови файл.",
        answer_has("native_brain.py"),
        max_steps=5,
    ),
    EvalTask(
        "symbol-budget",
        "Символ BudgetLimits",
        "Найди класс BudgetLimits через find_symbol и назови файл.",
        answer_has("budget.py"),
        max_steps=5,
    ),
    EvalTask(
        "plan-max-prompt",
        "План и поиск",
        "Составь план из трёх пунктов через update_plan, затем найди, "
        "где задан MAX_PROMPT, и назови файл.",
        answer_has("context.py"),
        max_steps=7,
        inspect=_plan_inspect,
    ),
    EvalTask(
        "subagents-two-files",
        "Два подагента",
        "Через ask_subagent с tasks выполни два поиска: где объявлен "
        "NativeBrain и где BudgetLimits. В ответе назови оба файла.",
        answer_has("providers.py"),
        max_steps=6,
        inspect=_subagents_inspect,
    ),
    EvalTask(
        "semantic-embeddings",
        "Поиск по смыслу",
        "Через find_relevant найди, где в проекте описан смысловой поиск "
        "и эмбеддинги, и назови файл. Точных имён не подсказываю.",
        answer_has("semantic"),
        max_steps=5,
        inspect=_semantic_inspect,
    ),
    EvalTask(
        "mcp-echo",
        "MCP-инструмент",
        "Вызови MCP-инструмент echo с текстом «проверка» и назови "
        "ответ, который он вернул.",
        lambda root, answer: (
            "эхо" in str(answer).casefold()
            and "проверка" in str(answer).casefold(),
            "эхо названо"
            if "эхо" in str(answer).casefold()
            else "ответа эхо нет",
        ),
        max_steps=6,
        prepare=_mcp_prepare(),
    ),
    EvalTask(
        "browser-read-js",
        "Браузер с JavaScript",
        "Пользователь разрешил браузер. Вызови browser_read с url "
        "https://example.com/js и назови слово со страницы.",
        lambda root, answer: (
            "кипарис" in str(answer).casefold(),
            "слово найдено"
            if "кипарис" in str(answer).casefold()
            else "слово не названо",
        ),
        max_steps=6,
        prepare=_browser_prepare("кипарис"),
    ),
    EvalTask(
        "browser-actions",
        "Действия в браузере",
        "Пользователь разрешил браузер. Через browser_act открой "
        "https://example.com/js, нажми #next и назови слово со страницы.",
        lambda root, answer: (
            "кипарис" in str(answer).casefold(),
            "слово найдено"
            if "кипарис" in str(answer).casefold()
            else "слово не названо",
        ),
        max_steps=6,
        prepare=_browser_prepare("кипарис"),
    ),
    EvalTask(
        "web-fetch-word",
        "Страница по URL",
        "Пользователь разрешил веб-доступ. Вызови fetch_url с url "
        "https://example.com/secret и назови слово со страницы.",
        lambda root, answer: (
            "кипарис" in str(answer).casefold(),
            "слово найдено"
            if "кипарис" in str(answer).casefold()
            else "слово не названо",
        ),
        max_steps=6,
        prepare=_web_prepare("кипарис"),
    ),
)

