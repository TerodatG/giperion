# Giperion/terminal/core/agent_stats.py                              v001
# Числовые показатели развития агента «Терминал».
# Последнее изменение: первый вариант — прогоны, ресурсы, арсенал, уровень.

from datetime import datetime

from giperion.identity_matrix import IDENTITY_MATRIX
from terminal.core.agent import mcp, registry
from terminal.core.agent.runs import read_all_runs

# Опыт за разные виды работы агента.
XP_PER_RUN = 10
XP_PER_STEP = 2
XP_PER_FILE = 5

# Сколько опыта нужно на новый уровень.
XP_PER_LEVEL = 500


def format_duration(seconds: float) -> str:
    """Пишет длительность по-русски: 2 ч 14 мин, 3 мин 8 с, 82 мс."""

    total = max(0.0, float(seconds))

    if total >= 3600:
        hours = int(total // 3600)
        minutes = int((total % 3600) // 60)

        return f"{hours} ч {minutes} мин"

    if total >= 60:
        minutes = int(total // 60)
        secs = int(round(total % 60))

        return f"{minutes} мин {secs} с"

    if total >= 10:
        return f"{int(round(total))} с"

    if total >= 1:
        return f"{total:.1f}".replace(".", ",") + " с"

    if total > 0:
        return f"{total * 1000:.0f} мс"

    return "0 с"


def format_cost(value: float) -> str:
    """Пишет стоимость прогонов; ноль — прочерк."""

    amount = float(value or 0.0)

    if amount <= 0:
        return "—"

    return f"$ {amount:.2f}".replace(".", ",")


def format_stamp(value: str) -> str:
    """Превращает ISO-время прогона в понятную подпись."""

    text = str(value or "").strip()

    if not text:
        return ""

    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return text[:16]

    return moment.strftime("%d.%m.%Y %H:%M")


def read_agent_stats() -> dict:
    """Считает показатели агента по журналу прогонов.

    Уровень и опыт растут от реальной работы: успешный прогон, шаг
    инструмента и изменённый файл дают опыт. Поэтому по цифрам видно,
    как терминал набирает форму.
    """

    runs = read_all_runs()

    total = len(runs)
    ok = 0
    failed = 0
    cancelled = 0

    steps = 0
    approvals = 0
    tokens = 0
    retries = 0
    seconds = 0.0
    cost = 0.0
    files: set[str] = set()

    for run in runs:
        steps += max(0, int(run.get("steps") or 0))
        approvals += max(0, int(run.get("approvals") or 0))
        tokens += max(0, int(run.get("tokens") or 0))
        retries += max(0, int(run.get("retries") or 0))
        seconds += max(0.0, float(run.get("duration_s") or 0.0))
        cost += max(0.0, float(run.get("cost") or 0.0))

        for path in run.get("files") or []:
            clean = str(path).strip()

            if clean:
                files.add(clean)

        if run.get("cancelled"):
            cancelled += 1
        elif run.get("error"):
            failed += 1
        else:
            ok += 1

    experience = (
        ok * XP_PER_RUN
        + steps * XP_PER_STEP
        + len(files) * XP_PER_FILE
    )

    level = 1 + experience // XP_PER_LEVEL

    progress = (
        round((experience % XP_PER_LEVEL) * 100 / XP_PER_LEVEL)
        if XP_PER_LEVEL
        else 0
    )

    plugins = len(registry.plugin_tools()[0])

    try:
        mcp_servers = len(mcp.load_servers())
    except Exception:  # noqa: BLE001 — настройки MCP могут быть битыми
        mcp_servers = 0

    success_percent = (
        round(ok * 100 / total) if total else 0
    )

    last_run = format_stamp(runs[-1].get("created_at", "")) if runs else ""

    return {
        "runs_total": total,
        "runs_ok": ok,
        "runs_failed": failed,
        "runs_cancelled": cancelled,
        "success_percent": success_percent,
        "steps_total": steps,
        "files_total": len(files),
        "approvals_total": approvals,
        "retries_total": retries,
        "tokens_total": tokens,
        "cost_total": cost,
        "duration_total": seconds,
        "duration_average": seconds / total if total else 0.0,
        "experience": experience,
        "level": level,
        "level_progress": max(0, min(100, progress)),
        "to_next_level": XP_PER_LEVEL - experience % XP_PER_LEVEL,
        "tools_builtin": len(registry.TOOL_SPECS),
        "plugins": plugins,
        "mcp_servers": mcp_servers,
        "skills": len(IDENTITY_MATRIX["skills"]),
        "last_run": last_run,
    }
