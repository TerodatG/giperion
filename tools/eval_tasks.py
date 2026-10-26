# Giperion/tools/eval_tasks.py                                        v001
# Задачи стенда: проверки, подготовка, инспекторы и каталог.
# Последнее изменение: вынесено из eval_agent.

import json
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


MCP_STUB = '''
import json
import sys


def send(message):
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\\n")
    sys.stdout.flush()


for line in sys.stdin:
    line = line.strip()

    if not line:
        continue

    message = json.loads(line)
    method = message.get("method")
    request_id = message.get("id")

    if method == "initialize":
        send({"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "stub", "version": "1"},
        }})
    elif method == "notifications/initialized":
        continue
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": request_id, "result": {"tools": [{
            "name": "echo",
            "description": "Вернуть текст обратно",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "текст"},
                },
                "required": ["text"],
            },
            "annotations": {"readOnlyHint": True},
        }]}})
    elif method == "tools/call":
        params = message.get("params") or {}
        arguments = params.get("arguments") or {}
        text = str(arguments.get("text", ""))
        send({"jsonrpc": "2.0", "id": request_id, "result": {
            "content": [{"type": "text", "text": "эхо: " + text}],
        }})
'''


def _web_prepare(word: str):
    """Подменяет сеть на одну страницу с секретным словом."""

    def prepare(folder: Path):
        from contextlib import contextmanager

        @contextmanager
        def context():
            from terminal.core.agent import settings, web

            old_enabled = settings.browser_enabled
            old_get = web.HTTP_GET
            old_public = web.is_public_host

            settings.browser_enabled = lambda: True
            web.HTTP_GET = lambda url: (
                url,
                "text/html; charset=utf-8",
                (
                    "<html><body><h1>Страница</h1>"
                    f"<p>секретное слово: {word}</p></body></html>"
                ).encode("utf-8"),
            )
            web.is_public_host = lambda host: True

            try:
                yield
            finally:
                settings.browser_enabled = old_enabled
                web.HTTP_GET = old_get
                web.is_public_host = old_public

        return context()

    return prepare


def _mcp_prepare():
    """Поднимает локальный MCP-стаб на время задачи."""

    def prepare(folder: Path):
        import sys
        from contextlib import contextmanager

        from terminal.core.agent import mcp, settings

        server = folder / "mcp_stub_server.py"
        server.write_text(MCP_STUB, encoding="utf-8")

        config = folder / "mcp_stub.json"
        config.write_text(
            json.dumps(
                {
                    "servers": [
                        {
                            "name": "stub",
                            "command": sys.executable,
                            "args": [str(server)],
                            "enabled": True,
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        @contextmanager
        def context():
            old_file = mcp.CONFIG_FILE
            old_enabled = settings.mcp_enabled
            mcp.CONFIG_FILE = config
            settings.mcp_enabled = lambda: True
            mcp.reload_mcp()

            try:
                yield
            finally:
                mcp.CONFIG_FILE = old_file
                settings.mcp_enabled = old_enabled
                mcp.reload_mcp()

        return context()

    return prepare


def _plan_inspect(folder: Path, result) -> tuple[bool, str]:
    """Проверяет, что модель составила план и нашла файл."""

    plans = [step for step in result.steps if step.kind == "plan"]
    items = plans[-1].detail.count("\n") + 1 if plans else 0
    answer_ok = "context.py" in str(result.answer)

    if items >= 3 and answer_ok:
        return True, "план из трёх пунктов и context.py"

    return (
        False,
        f"план: {items} пунктов, ответ: "
        f"{'есть' if answer_ok else 'нет'} context.py",
    )


def _subagents_inspect(folder: Path, result) -> tuple[bool, str]:
    """Проверяет шаг с двумя подагентами и оба файла в ответе."""

    steps = [step for step in result.steps if step.kind == "subagent"]
    parallel = any("Подагенты · 2" in step.title for step in steps)

    answer = str(result.answer).casefold()
    both = "native_brain.py" in answer and "budget.py" in answer

    if parallel and both:
        return True, "два подагента и оба файла"

    return (
        False,
        f"подагенты: {'да' if parallel else 'нет'}, "
        f"файлы: {'оба' if both else 'не все'}",
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
        "Где задан белый список команд агента? Назови файл.",
        answer_has("commands.py"),
        max_steps=7,
    ),
    EvalTask(
        "write-note",
        "Создать файл",
        "Создай файл eval_note.md с текстом «# Заметка».",
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
        "Создай eval_a.txt с текстом «альфа» и eval_b.txt с текстом «бета».",
        lambda root, _answer: (
            _text(root / "eval_a.txt").strip() == "альфа"
            and _text(root / "eval_b.txt").strip() == "бета",
            "оба файла на месте",
        ),
        max_steps=8,
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
        "Прочитай docs/architecture.md и назови раздел про паспорт модели.",
        answer_has("паспорт"),
        max_steps=4,
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
        "Создай файл eval_lines.txt с двумя строками: «альфа» и «бета».",
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
        max_steps=5,
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
        "web-fetch-word",
        "Страница по URL",
        "Прочитай страницу https://example.com/secret через fetch_url "
        "и назови секретное слово с неё.",
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

