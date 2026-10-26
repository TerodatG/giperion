# Giperion/tools/eval_prepares.py                                    v001
# Подготовка окружения и инспекторы задач стенда.
# Последнее изменение: вынесено из eval_tasks.

import json
import sys
from pathlib import Path

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


def _browser_prepare(word: str):
    """Подменяет browser_read готовой страницей со словом."""

    def prepare(folder: Path):
        from contextlib import contextmanager

        @contextmanager
        def context():
            from terminal.core.agent import browser_js, settings
            from terminal.core.agent.protocol import ToolResult

            old_enabled = settings.browser_js_enabled
            old_read = browser_js.read
            old_act = browser_js.act

            settings.browser_js_enabled = lambda: True
            browser_js.read = lambda root, url, wait="", timeout=60: (
                ToolResult(
                    True,
                    f"источник: {url}\nзаголовок: JS-страница\n\n"
                    f"слово: {word}",
                )
            )
            browser_js.act = lambda root, url, actions=None, wait="", shot=False, timeout=60: (
                ToolResult(
                    True,
                    f"источник: {url}\nзаголовок: JS-страница\n\n"
                    f"слово: {word}",
                )
            )

            try:
                yield
            finally:
                settings.browser_js_enabled = old_enabled
                browser_js.read = old_read
                browser_js.act = old_act

        return context()

    return prepare


def _mcp_prepare():
    """Поднимает локальный MCP-стаб на время задачи."""

    def prepare(folder: Path):
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


def _semantic_inspect(folder: Path, result) -> tuple[bool, str]:
    """Проверяет, что модель звала find_relevant и назвала файл."""

    used = any(
        step.kind == "tool" and "find_relevant" in step.title
        for step in result.steps
    )
    named = "semantic" in str(result.answer).casefold()

    if used and named:
        return True, "find_relevant вызван, файл назван"

    return (
        False,
        f"find_relevant: {'да' if used else 'нет'}, "
        f"файл: {'да' if named else 'нет'}",
    )
