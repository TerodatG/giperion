# Giperion/tools/agent_pr.py                                          v001
# Публикация ветки агента и создание pull request через gh.
# Последнее изменение: первый вариант — push и gh pr create.

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from config import BASE_DIR

GIT = r"C:\Program Files\Git\cmd\git.exe"


def _git() -> str:
    return GIT if Path(GIT).is_file() else "git"


def _run(command: list[str]) -> tuple[int, str]:
    """Запускает команду и возвращает код и хвост вывода."""

    try:
        done = subprocess.run(
            command,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, str(error)

    output = (done.stdout or "") + (done.stderr or "")

    return done.returncode, output.strip()[-1000:]


def publish(
    branch: str,
    title: str,
    body: str = "",
    base: str = "",
    dry_run: bool = False,
) -> list[tuple[str, int, str]]:
    """Публикует ветку и создаёт PR; возвращает шаги."""

    steps = []
    git = _git()
    push = [git, "push", "-u", "origin", branch]

    if dry_run:
        steps.append(("push", 0, " ".join(push)))
    else:
        steps.append(("push", *_run(push)))

    if not dry_run and not shutil.which("gh"):
        steps.append(
            (
                "pr",
                1,
                "GitHub CLI (gh) не найден: создайте PR вручную.",
            )
        )

        return steps

    command = [
        "gh",
        "pr",
        "create",
        "--head",
        branch,
        "--title",
        title,
    ]

    if body:
        command += ["--body", body]

    if base:
        command += ["--base", base]

    if dry_run:
        steps.append(("pr", 0, " ".join(command)))
    else:
        steps.append(("pr", *_run(command)))

    return steps


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Отправить ветку агента в origin и создать pull request. "
            "Требует настроенный git remote и GitHub CLI."
        ),
    )
    parser.add_argument("branch")
    parser.add_argument("--title", required=True)
    parser.add_argument("--body", default="")
    parser.add_argument("--base", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    steps = publish(
        args.branch,
        args.title,
        args.body,
        args.base,
        args.dry_run,
    )

    for name, code, output in steps:
        mark = "OK" if code == 0 else "ОШИБКА"
        print(f"{mark} · {name}: {output}")

    return 0 if all(code == 0 for _name, code, _out in steps) else 1


if __name__ == "__main__":
    sys.exit(main())
