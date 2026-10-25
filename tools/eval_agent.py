# Giperion/tools/eval_agent.py                                       v001
# Стенд оценки агента: задачи в отдельном worktree, метрики и отчёт.
# Последнее изменение: первый вариант — 10 задач и сравнение прогонов.

import argparse
import json
import time
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
        "состоит плагин.",
        lambda root, answer: (
            ".json" in str(answer).casefold()
            and ".py" in str(answer).casefold(),
            "оба расширения названы"
            if ".json" in str(answer).casefold()
            and ".py" in str(answer).casefold()
            else "расширения не названы",
        ),
        max_steps=4,
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
    """Считает сводные метрики прогона."""

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
        }

    passed = sum(1 for item in results if item["ok"])

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
    }


def load_previous() -> dict:
    """Читает сводку прошлого прогона."""

    try:
        document = json.loads(LATEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    summary = document.get("summary")

    return summary if isinstance(summary, dict) else {}


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
    args = parser.parse_args()

    tasks = [
        task for task in TASKS
        if (args.full or not task.slow)
        and (not args.only or task.id == args.only)
    ]

    if not tasks:
        raise SystemExit("Нет задач под такие фильтры.")

    brain, model_name = build_brain(args.model, args.provider)
    previous = load_previous()

    print("=== Оценка агента ===")
    print("Модель:", model_name)
    print()

    results = []

    for index, task in enumerate(tasks, start=1):
        print(f"[{index}/{len(tasks)}] {task.title}…")

        if args.max_steps:
            task = EvalTask(
                task.id,
                task.title,
                task.task,
                task.check,
                task.setup,
                args.max_steps,
                task.slow,
                task.notes,
            )

        try:
            result = run_task(task, brain, BASE_DIR)
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

        results.append(result)

        mark = "OK" if result["ok"] else "FAIL"

        print(
            f"    {mark} · шагов {result['steps']} · "
            f"{result['duration_s']} с · {result['note']}"
        )

        if is_fatal(result.get("error", "")):
            print(
                "    Стоп: провайдер исчерпал лимит или отклонил ключ — "
                "остальные задачи не запускаю."
            )
            break

    summary = summarize(results)
    path = save_report(model_name, results, summary)

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

    if summary.get("tokens"):
        money = (
            f", ${summary['cost']:.4f}"
            if summary.get("cost")
            else ""
        )
        print(f"Расход: {summary['tokens']} токенов{money}")

    if len(results) < len(tasks):
        print(
            f"Прогон остановлен на {len(results)} из {len(tasks)} задач: "
            "провайдер исчерпал лимит."
        )

    if previous:
        delta = summary["passed"] - int(
            previous.get("passed", 0)
        )
        sign = "+" if delta >= 0 else ""
        print(
            "Прошлый прогон: "
            f"{previous.get('passed', 0)}/"
            f"{previous.get('total', 0)} "
            f"({sign}{delta})"
        )

    print("Отчёт:", path)


if __name__ == "__main__":
    main()
