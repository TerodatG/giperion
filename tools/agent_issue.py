# Giperion/tools/agent_issue.py                                       v001
# Issue → задача агента: GitHub CLI и GitLab REST.
# Последнее изменение: первый вариант — fetch/task и CLI.

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from config import BASE_DIR

MAX_BODY = 20_000


def fetch_github(number: int, repo: str = "") -> dict:
    """Читает issue через gh CLI."""

    command = ["gh", "issue", "view", str(int(number))]

    if repo:
        command += ["--repo", repo]

    command += ["--json", "number,title,body"]

    try:
        done = subprocess.run(
            command,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError(f"gh недоступен: {error}") from error

    if done.returncode != 0:
        raise ValueError(
            "gh issue view: " + (done.stderr or done.stdout).strip()[:300]
        )

    try:
        document = json.loads(done.stdout)
    except json.JSONDecodeError as error:
        raise ValueError(f"gh вернул не JSON: {error}") from error

    return _clean(document)


def fetch_gitlab(
    number: int,
    project: str,
    url: str = "https://gitlab.com",
    token: str = "",
) -> dict:
    """Читает issue через GitLab REST API."""

    if not project or not token:
        raise ValueError("GitLab: нужны project и token.")

    base = str(url or "https://gitlab.com").rstrip("/")
    encoded = urllib.parse.quote(project, safe="")
    target = f"{base}/api/v4/projects/{encoded}/issues/{int(number)}"
    request = urllib.request.Request(
        target,
        headers={"PRIVATE-TOKEN": token},
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read(200_000)
    except (OSError, urllib.error.URLError) as error:
        raise ValueError(f"GitLab недоступен: {error}") from error

    try:
        document = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ValueError(f"GitLab вернул не JSON: {error}") from error

    return _clean(document)


def _clean(document: dict) -> dict:
    """Оставляет номер, заголовок и описание."""

    if not isinstance(document, dict):
        raise ValueError("Issue должен быть объектом.")

    return {
        "number": int(document.get("number") or document.get("iid") or 0),
        "title": str(document.get("title") or "").strip()[:300],
        "body": str(document.get("description") or document.get("body") or "")[
            :MAX_BODY
        ],
    }


def task_text(issue: dict) -> str:
    """Текст задачи для агента."""

    title = str(issue.get("title") or "").strip()
    body = str(issue.get("body") or "").strip()

    return (title + ("\n\n" + body if body else "")).strip()


def create_branch(issue: dict, root: Path | None = None) -> tuple[Path, str]:
    """Создаёт worktree и ветку agent/issue-<номер>."""

    from terminal.core.agent.worktrees import create_worktree

    number = int(issue.get("number") or 0)
    title = str(issue.get("title") or "").strip()
    slug = "".join(
        char if char.isalnum() else "-"
        for char in title.lower()
    ).strip("-")[:40]
    name = f"issue-{number}-{slug or 'task'}"

    return create_worktree(Path(root or BASE_DIR), name)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Прочитать issue и превратить в задачу.",
    )
    parser.add_argument("number", type=int)
    parser.add_argument("--provider", choices=("github", "gitlab"), default="github")
    parser.add_argument("--repo", default="")
    parser.add_argument("--project", default="")
    parser.add_argument("--url", default="https://gitlab.com")
    parser.add_argument("--token-env", default="GITLAB_TOKEN")
    parser.add_argument(
        "--worktree",
        action="store_true",
        help="создать worktree и ветку agent/issue-*",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        if args.provider == "github":
            issue = fetch_github(args.number, args.repo)
        else:
            issue = fetch_gitlab(
                args.number,
                args.project,
                args.url,
                os.environ.get(args.token_env, ""),
            )
    except ValueError as error:
        print("Не прочитано:", error)

        return 1

    if args.json:
        print(json.dumps(issue, ensure_ascii=False, indent=2))
    else:
        print(task_text(issue))

    if args.worktree:
        try:
            folder, branch = create_branch(issue)
        except Exception as error:  # noqa: BLE001 — покажем причину
            print("Ветка не создана:", error)

            return 1

        print("Ветка:", branch)
        print("Папка:", folder)

    return 0


if __name__ == "__main__":
    sys.exit(main())
