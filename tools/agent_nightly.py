# Giperion/tools/agent_nightly.py                                     v001
# Ночной отчёт: прогоны, очередь, ошибки и алерт.
# Последнее изменение: первый вариант — Markdown и вебхук.

import argparse
import sys
from datetime import datetime
from pathlib import Path

from config import DATA_DIR
from terminal.core.agent import alerts
from terminal.core.agent import queue as task_queue
from terminal.core.agent.runs import read_runs

REPORT_DIR = DATA_DIR / "agent_nightly"


def build(runs: list[dict], queue_stats: dict) -> str:
    """Markdown-отчёт по прогонам и очереди."""

    stats = alerts.summary(runs, len(runs) or 1)
    lines = [
        "# Ночной отчёт Giperion",
        "",
        f"Сформирован: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Прогоны",
        "",
        f"- всего: {stats['total']}",
        f"- успех: {stats['ok']}",
        f"- падений: {stats['failed']}",
        f"- доля успеха: {stats['rate']:.0%}",
    ]

    if stats["last_error"]:
        lines.append(f"- последняя ошибка: {stats['last_error'][:300]}")

    lines += [
        "",
        "## Очередь",
        "",
        f"- ждут: {queue_stats.get('pending', 0)}",
        f"- в работе: {queue_stats.get('running', 0)}",
        f"- готово: {queue_stats.get('done', 0)}",
        f"- ошибок: {queue_stats.get('failed', 0)}",
        "",
        "## Последние прогоны",
        "",
        "| время | успех | шаги | ошибка |",
        "|---|---|---|---|",
    ]

    for item in list(runs)[-10:]:
        mark = "да" if item.get("ok") is True else "нет"
        error = str(item.get("error") or "")[:80]
        lines.append(
            f"| {item.get('created_at') or item.get('started_at') or ''} "
            f"| {mark} | {item.get('steps', '')} | {error} |"
        )

    return "\n".join(lines) + "\n"


def write_report(
    runs: list[dict],
    queue_stats: dict,
    target: Path | None = None,
) -> Path:
    """Пишет отчёт в data/agent_nightly."""

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = Path(target or REPORT_DIR / f"report-{stamp}.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build(runs, queue_stats), encoding="utf-8")

    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Сформировать ночной отчёт и отправить алерт.",
    )
    parser.add_argument("--target", default="")
    parser.add_argument("--window", type=int, default=50)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--webhook", default="")
    parser.add_argument("--fail", action="store_true")
    args = parser.parse_args()

    runs = read_runs(max(1, args.window))
    stats = task_queue.summary()
    path = write_report(
        runs,
        stats,
        Path(args.target) if args.target else None,
    )
    print("Отчёт:", path)

    _summary, alert = alerts.check(
        runs,
        threshold=max(0.0, min(1.0, args.threshold)),
        window=args.window,
        url=args.webhook,
    )

    if alert:
        print("АЛЕРТ: успех ниже порога.")

    return 2 if args.fail and alert else 0


if __name__ == "__main__":
    sys.exit(main())
