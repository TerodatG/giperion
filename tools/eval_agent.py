# Giperion/tools/eval_agent.py                                       v001
# Стенд оценки агента: задачи в отдельном worktree, метрики и отчёт.
# Последнее изменение: первый вариант — 10 задач и сравнение прогонов.

import argparse
import json
import time
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from config import BASE_DIR, DATA_DIR
from terminal.core.agent.brain import ModelBrain
from terminal.core.agent.loop import run_agent
from terminal.core.agent.providers import NativeBrain
from terminal.core.agent.settings import (
    context_limit_chars,
    provider_from_settings,
)
from terminal.core.agent.worktrees import (
    WorktreeError,
    create_worktree,
    remove_worktree,
)
from terminal.core.helper_model import get_helper_model

OUTPUT_DIR = DATA_DIR / "agent_eval"
LATEST = OUTPUT_DIR / "latest.json"

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
        from contextlib import contextmanager
        import sys

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
    both = "providers.py" in answer and "budget.py" in answer

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
        answer_has("providers.py"),
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
            ".json" in str(answer).casefold()
            and ".py" in str(answer).casefold(),
            "оба расширения названы"
            if ".json" in str(answer).casefold()
            and ".py" in str(answer).casefold()
            else "расширения не названы",
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
        answer_has("providers.py"),
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


FATAL_MARKERS = (
    "usage limit",
    "limit reached",
    "quota",
    "insufficient",
    "неверный ключ",
    "unauthorized",
    "forbidden",
    "401",
    "403",
)


def is_fatal(error: str) -> bool:
    """Ошибка провайдера, после которой нет смысла гонять остальные задачи."""

    text = str(error or "").casefold()

    return any(marker in text for marker in FATAL_MARKERS)


def build_brain(model: str, provider: str):
    """Выбирает провайдера: аргументы, настройки, помощник."""

    if model:
        return (
            ModelBrain(model, provider or "opencode"),
            f"{provider or 'opencode'}/{model}",
        )

    native = provider_from_settings()

    if native is not None:
        from terminal.core.agent.settings import budget_limits

        limits = budget_limits()

        return NativeBrain(native, limits), f"native/{native.model}"

    helper = get_helper_model()

    if helper is None:
        raise SystemExit(
            "Нет модели: задай --model/--provider или настрой провайдера."
        )

    return (
        ModelBrain(
            helper["model_id"],
            helper.get("provider_id") or "opencode",
        ),
        helper["name"],
    )


def run_task(task: EvalTask, brain, base: Path) -> dict:
    """Выполняет задачу в отдельном worktree и проверяет результат."""

    folder, branch = create_worktree(
        base,
        f"eval-{task.id}-{int(time.time())}",
    )

    try:
        if task.setup is not None:
            task.setup(folder)

        approvals: list = []
        started = time.monotonic()
        before_tokens = int(getattr(brain, "total_tokens", 0) or 0)
        before_cost = float(getattr(brain, "cost", 0.0) or 0.0)

        context = (
            task.prepare(folder)
            if task.prepare is not None
            else nullcontext()
        )

        with context:
            result = run_agent(
                task.task,
                brain,
                folder,
                max_steps=task.max_steps,
                ground_first=True,
                approve=lambda request: approvals.append(request) or True,
                max_prompt_chars=context_limit_chars(),
            )

        duration = time.monotonic() - started

        if task.inspect is not None:
            ok, note = task.inspect(folder, result)
        else:
            ok, note = task.check(folder, result.answer)
        tokens = int(getattr(brain, "total_tokens", 0) or 0) - before_tokens
        cost = float(getattr(brain, "cost", 0.0) or 0.0) - before_cost

        return {
            "id": task.id,
            "title": task.title,
            "ok": bool(ok),
            "note": note,
            "steps": len(result.steps),
            "approvals": len(approvals),
            "duration_s": round(duration, 2),
            "context_chars": result.context_chars,
            "tokens": max(0, tokens),
            "cost": round(max(0.0, cost), 6),
            "answer": result.answer[:500],
            "error": result.error[:300],
        }
    finally:
        try:
            remove_worktree(base, folder, branch)
        except WorktreeError:
            pass


def summarize(results: list[dict]) -> dict:
    """Считает сводные метрики прогона и стабильность по задачам."""

    total = len(results)

    if not total:
        return {
            "total": 0,
            "passed": 0,
            "success_rate": 0.0,
            "avg_steps": 0.0,
            "avg_duration_s": 0.0,
            "max_context": 0,
            "tokens": 0,
            "cost": 0.0,
            "runs": 0,
            "stable_tasks": 0,
            "flaky_tasks": 0,
            "task_ids": [],
            "per_task": {},
        }

    passed = sum(1 for item in results if item["ok"])
    groups: dict[str, list[dict]] = {}

    for number, item in enumerate(results):
        key = str(item.get("id") or f"#{number}")
        groups.setdefault(key, []).append(item)

    per_task = {}
    stable_tasks = 0
    flaky_tasks = 0

    for key, items in groups.items():
        ok_count = sum(1 for item in items if item["ok"])
        count = len(items)

        per_task[key] = {
            "attempts": count,
            "passed": ok_count,
            "avg_steps": round(
                sum(item["steps"] for item in items) / count,
                1,
            ),
            "avg_duration_s": round(
                sum(item["duration_s"] for item in items) / count,
                1,
            ),
            "tokens": sum(int(item.get("tokens") or 0) for item in items),
            "cost": round(
                sum(float(item.get("cost") or 0.0) for item in items),
                6,
            ),
        }

        if count > 1:
            if ok_count == count:
                stable_tasks += 1
            elif ok_count:
                flaky_tasks += 1

    runs = max(int(item.get("attempt") or 1) for item in results)

    return {
        "total": total,
        "passed": passed,
        "success_rate": round(passed / total, 3),
        "avg_steps": round(
            sum(item["steps"] for item in results) / total,
            1,
        ),
        "avg_duration_s": round(
            sum(item["duration_s"] for item in results) / total,
            1,
        ),
        "max_context": max(item["context_chars"] for item in results),
        "tokens": sum(int(item.get("tokens") or 0) for item in results),
        "cost": round(
            sum(float(item.get("cost") or 0.0) for item in results),
            6,
        ),
        "runs": runs,
        "stable_tasks": stable_tasks,
        "flaky_tasks": flaky_tasks,
        "task_ids": sorted(groups),
        "per_task": per_task,
    }


def load_previous() -> dict:
    """Читает сводку прошлого прогона."""

    try:
        document = json.loads(LATEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    summary = document.get("summary")

    return summary if isinstance(summary, dict) else {}


HISTORY = OUTPUT_DIR / "history.jsonl"


def append_history(model_name: str, summary: dict) -> None:
    """Добавляет строку в историю прогонов."""

    record = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "model": model_name,
        "passed": int(summary.get("passed") or 0),
        "total": int(summary.get("total") or 0),
        "success_rate": float(summary.get("success_rate") or 0.0),
        "avg_steps": float(summary.get("avg_steps") or 0.0),
        "avg_duration_s": float(summary.get("avg_duration_s") or 0.0),
        "runs": int(summary.get("runs") or 1),
        "stable_tasks": int(summary.get("stable_tasks") or 0),
        "flaky_tasks": int(summary.get("flaky_tasks") or 0),
    }

    try:
        HISTORY.parent.mkdir(parents=True, exist_ok=True)

        with HISTORY.open("a", encoding="utf-8") as file:
            file.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )
    except OSError:
        pass


def read_history(limit: int = 10) -> list[dict]:
    """Последние записи истории прогонов."""

    try:
        lines = HISTORY.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    records = []

    for line in lines[-max(1, limit):]:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue

        if isinstance(value, dict):
            records.append(value)

    return records


def regression_note(
    previous: dict,
    summary: dict,
    threshold: float = 10.0,
) -> str:
    """Предупреждение, если успех упал сильнее порога."""

    if not previous or not summary.get("total"):
        return ""

    old_ids = previous.get("task_ids")
    new_ids = summary.get("task_ids")

    if (
        isinstance(old_ids, list)
        and isinstance(new_ids, list)
        and old_ids
        and new_ids
        and sorted(old_ids) != sorted(new_ids)
    ):
        return ""

    old_rate = float(previous.get("success_rate") or 0.0)
    new_rate = float(summary.get("success_rate") or 0.0)
    delta = (new_rate - old_rate) * 100

    if delta < -abs(threshold):
        return (
            f"РЕГРЕССИЯ: успех ниже прошлого на {abs(delta):.0f} п.п. "
            f"(порог {abs(threshold):.0f})."
        )

    return ""


def save_report(
    model_name: str,
    results: list[dict],
    summary: dict,
) -> Path:
    """Пишет отчёт с датой и обновляет latest.json."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    created = datetime.now()
    payload = {
        "created_at": created.isoformat(timespec="seconds"),
        "model": model_name,
        "tasks": results,
        "summary": summary,
    }

    path = OUTPUT_DIR / created.strftime("%Y%m%d-%H%M%S.json")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    LATEST.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Оценка агента на задачах проекта.",
    )
    parser.add_argument("--model", default="")
    parser.add_argument("--provider", default="")
    parser.add_argument("--only", default="")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="сколько раз прогнать набор задач (стабильность)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=10.0,
        help="порог регрессии в процентных пунктах",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="вернуть код 2, если успех упал ниже порога",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="показать историю прогонов и выйти",
    )
    args = parser.parse_args()

    if args.history:
        records = read_history(10)

        if not records:
            print("История пуста: прогонов ещё не было.")

            return

        print("=== История прогонов ===")

        for record in records:
            print(
                f"{record.get('created_at', '—')} · "
                f"{record.get('model', '—')} · "
                f"{record.get('passed', 0)}/{record.get('total', 0)} "
                f"({float(record.get('success_rate') or 0) * 100:.0f} %) · "
                f"{record.get('avg_steps', 0)} шагов · "
                f"{record.get('avg_duration_s', 0)} с"
                + (
                    f" · стабильно {record['stable_tasks']}"
                    if record.get("runs", 1) > 1
                    else ""
                )
            )

        return

    tasks = [
        task for task in TASKS
        if (args.full or not task.slow)
        and (not args.only or task.id == args.only)
    ]

    if not tasks:
        raise SystemExit("Нет задач под такие фильтры.")

    attempts = max(1, int(args.repeat))
    brain, model_name = build_brain(args.model, args.provider)
    previous = load_previous()

    print("=== Оценка агента ===")
    print("Модель:", model_name)

    if attempts > 1:
        print(f"Повторов: {attempts}")

    print()

    results: list[dict] = []
    stopped = False

    for attempt in range(1, attempts + 1):
        if attempts > 1:
            print(f"--- прогон {attempt}/{attempts} ---")

        for index, task in enumerate(tasks, start=1):
            print(f"[{index}/{len(tasks)}] {task.title}…")

            current = task

            if args.max_steps:
                current = EvalTask(
                    id=task.id,
                    title=task.title,
                    task=task.task,
                    check=task.check,
                    setup=task.setup,
                    max_steps=args.max_steps,
                    slow=task.slow,
                    notes=task.notes,
                    inspect=task.inspect,
                    prepare=task.prepare,
                )

            try:
                result = run_task(current, brain, BASE_DIR)
            except WorktreeError as error:
                result = {
                    "id": task.id,
                    "title": task.title,
                    "ok": False,
                    "note": f"worktree: {error}",
                    "steps": 0,
                    "approvals": 0,
                    "duration_s": 0.0,
                    "context_chars": 0,
                    "tokens": 0,
                    "cost": 0.0,
                    "answer": "",
                    "error": str(error),
                }

            result["attempt"] = attempt
            results.append(result)

            mark = "OK" if result["ok"] else "FAIL"

            print(
                f"    {mark} · шагов {result['steps']} · "
                f"{result['duration_s']} с · {result['note']}"
            )

            if is_fatal(result.get("error", "")):
                print(
                    "    Стоп: провайдер исчерпал лимит или отклонил "
                    "ключ — остальные задачи не запускаю."
                )
                stopped = True

                break

        if stopped:
            break

    summary = summarize(results)
    path = save_report(model_name, results, summary)
    append_history(model_name, summary)

    if attempts > 1:
        print()
        print("=== Стабильность ===")

        for task in tasks:
            stats = summary["per_task"].get(task.id)

            if not stats:
                continue

            passed = stats["passed"]
            total = stats["attempts"]
            mark = (
                "стабильно"
                if passed == total
                else ("плавает" if passed else "падает")
            )

            print(
                f"  {task.id:24} {passed}/{total} · {mark} · "
                f"{stats['avg_duration_s']} с"
            )

    print()
    print("=== Итог ===")
    print(
        f"Успех: {summary['passed']}/{summary['total']} "
        f"({summary['success_rate'] * 100:.0f} %)"
    )
    print(
        f"Среднее: {summary['avg_steps']} шагов, "
        f"{summary['avg_duration_s']} с, "
        f"контекст до {summary['max_context']} символов"
    )

    if attempts > 1:
        print(
            f"Задачи: стабильных {summary['stable_tasks']}, "
            f"плавающих {summary['flaky_tasks']}"
        )

    if summary.get("tokens"):
        money = (
            f", ${summary['cost']:.4f}"
            if summary.get("cost")
            else ""
        )
        print(f"Расход: {summary['tokens']} токенов{money}")

    expected = len(tasks) * attempts

    if len(results) < expected:
        print(
            f"Прогон остановлен на {len(results)} из {expected} попыток: "
            "провайдер исчерпал лимит."
        )

    if previous:
        old_ids = previous.get("task_ids")
        new_ids = summary.get("task_ids")
        same_set = (
            not isinstance(old_ids, list)
            or not isinstance(new_ids, list)
            or not old_ids
            or not new_ids
            or sorted(old_ids) == sorted(new_ids)
        )

        if not same_set:
            print(
                "Прошлый прогон: другой набор задач — сравнение пропущено."
            )
        else:
            old_total = int(previous.get("total") or 0)
            old_passed = int(previous.get("passed") or 0)
            old_rate = float(previous.get("success_rate") or 0.0)
            delta_points = (
                summary["success_rate"] - old_rate
            ) * 100
            sign = "+" if delta_points >= 0 else ""

            print(
                "Прошлый прогон: "
                f"{old_passed}/{old_total} "
                f"({old_rate * 100:.0f} %) · "
                f"{sign}{delta_points:.0f} п.п."
            )

    note = regression_note(previous, summary, args.threshold)

    if note:
        print(note)

    print("Отчёт:", path)

    if note and args.fail_on_regression:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
