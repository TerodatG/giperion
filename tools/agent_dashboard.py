# Giperion/tools/agent_dashboard.py                                    v001
# HTML-дашборд: история стенда, аудит и расписание.
# Последнее изменение: первый вариант — сводка, график и таблица.

import argparse
import html
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from config import DATA_DIR
from terminal.core import schedule

HISTORY = DATA_DIR / "agent_eval" / "history.jsonl"
AUDIT = DATA_DIR / "agent_audit.jsonl"
OUTPUT = DATA_DIR / "agent_dashboard.html"


def _jsonl(path: Path, limit: int = 500) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    rows = []

    for line in lines[-limit:]:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue

        if isinstance(value, dict):
            rows.append(value)

    return rows


def _sparkline(values: list[float], width: int = 520, height: int = 90) -> str:
    """SVG-полилиния успеха."""

    if len(values) < 2:
        return "<p>Недостаточно прогонов для графика.</p>"

    points = []
    top = max(0.01, max(values))
    step = width / (len(values) - 1)

    for index, value in enumerate(values):
        x = round(index * step, 1)
        y = round(height - (value / top) * (height - 10) - 5, 1)
        points.append(f"{x},{y}")

    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" '
        f'height="{height}" role="img" aria-label="Успех по прогонам">'
        '<polyline fill="none" stroke="#4ade80" stroke-width="2" '
        f'points="{" ".join(points)}"/></svg>'
    )


def _cards(history: list[dict], audit: list[dict], tasks: list[dict]) -> str:
    last = history[-1] if history else {}
    rate = float(last.get("success_rate") or 0.0) * 100
    events = Counter(str(item.get("event")) for item in audit)

    return f"""
    <div class="cards">
      <div class="card"><b>{rate:.0f} %</b><span>последний прогон</span></div>
      <div class="card"><b>{len(history)}</b><span>прогонов в истории</span></div>
      <div class="card"><b>{len(tasks)}</b><span>задач в расписании</span></div>
      <div class="card"><b>{len(audit)}</b><span>записей аудита</span></div>
      <div class="card"><b>{events.get("approval", 0)}</b><span>подтверждений</span></div>
    </div>
    """


def _history_table(history: list[dict]) -> str:
    rows = []

    for item in reversed(history[-20:]):
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(item.get('created_at', '')))}</td>"
            f"<td>{html.escape(str(item.get('model', '')))}</td>"
            f"<td>{item.get('passed', 0)}/{item.get('total', 0)}</td>"
            f"<td>{float(item.get('success_rate') or 0) * 100:.0f} %</td>"
            f"<td>{item.get('avg_steps', '—')}</td>"
            f"<td>{item.get('avg_duration_s', '—')} с</td>"
            f"<td>{item.get('stable_tasks', '—')} / "
            f"{item.get('flaky_tasks', '—')}</td>"
            "</tr>"
        )

    if not rows:
        return "<p>История пуста: запустите стенд.</p>"

    return (
        "<table><thead><tr><th>Когда</th><th>Модель</th><th>Успех</th>"
        "<th>%</th><th>Шаги</th><th>Время</th><th>стаб/плавает</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _schedule_table(tasks: list[dict]) -> str:
    if not tasks:
        return "<p>Расписание пустое.</p>"

    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(item.get('id', '')))}</td>"
        f"<td>{html.escape(str(item.get('task', '')))}</td>"
        f"<td>{item.get('every_minutes', '')} мин</td>"
        f"<td>{html.escape(str(item.get('last_run') or '—'))}</td>"
        "</tr>"
        for item in tasks
    )

    return (
        "<table><thead><tr><th>id</th><th>задача</th><th>интервал</th>"
        f"<th>последний запуск</th></tr></thead><tbody>{rows}</tbody></table>"
    )


def build(
    history_file: Path = HISTORY,
    audit_file: Path = AUDIT,
    output: Path = OUTPUT,
) -> Path:
    """Собирает HTML-дашборд."""

    history = _jsonl(history_file)
    audit = _jsonl(audit_file)
    tasks = schedule.load()
    rates = [float(item.get("success_rate") or 0.0) for item in history]
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    page = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<title>Giperion · панель агента</title>
<style>
body {{ font-family: system-ui, sans-serif; background:#111; color:#ddd;
       margin:0; padding:24px; }}
h1 {{ font-size:20px; color:#4ade80; }}
h2 {{ font-size:15px; margin-top:28px; color:#93c5fd; }}
.cards {{ display:flex; gap:12px; flex-wrap:wrap; }}
.card {{ background:#1b1b1b; border:1px solid #333; border-radius:8px;
        padding:12px 16px; min-width:130px; }}
.card b {{ display:block; font-size:22px; color:#4ade80; }}
.card span {{ font-size:12px; color:#999; }}
table {{ border-collapse:collapse; width:100%; font-size:13px; }}
th, td {{ border-bottom:1px solid #2a2a2a; padding:6px 8px;
         text-align:left; }}
th {{ color:#999; font-weight:500; }}
</style></head><body>
<h1>Giperion · панель агента</h1>
<p>Собрано {generated}</p>
{_cards(history, audit, tasks)}
<h2>Успех по прогонам</h2>
{_sparkline(rates)}
<h2>Последние прогоны</h2>
{_history_table(history)}
<h2>Расписание</h2>
{_schedule_table(tasks)}
</body></html>"""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")

    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Собрать HTML-дашборд агента.",
    )
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args()

    path = build(output=Path(args.output))
    print("Готово:", path)
    print(f"{path.stat().st_size / 1024:.0f} КБ")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
