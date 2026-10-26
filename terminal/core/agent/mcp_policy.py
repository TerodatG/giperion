# Giperion/terminal/core/agent/mcp_policy.py                       v001
# Конфиг и политика MCP: серверы, allowlist инструментов и доменов.
# Последнее изменение: вынесено из mcp.py.

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from config import DATA_DIR
from shared.storage.json_store import read_json_object

CONFIG_FILE = DATA_DIR / "agent_mcp.json"
NAME_RE = re.compile(r"[^a-z0-9_]+")


@dataclass(frozen=True)
class McpServer:
    """Описание сервера из data/agent_mcp.json."""

    name: str
    command: str
    args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    # Пустой список — разрешены все инструменты сервера.
    tools: tuple[str, ...] = ()
    # Пустые домены — URLs не ограничиваются.
    domains: tuple[str, ...] = ()


def _string_list(value) -> tuple[str, ...]:
    """Список непустых строк без повторов, в нижнем регистре."""

    if not isinstance(value, list):
        return ()

    result: list[str] = []
    seen: set[str] = set()

    for item in value:
        if not isinstance(item, str):
            continue

        text = item.strip().lower()

        if not text or text in seen:
            continue

        seen.add(text)
        result.append(text)

    return tuple(result)


def _tool_allowed(server: McpServer, name: str) -> bool:
    """Разрешён ли инструмент сервера списком tools."""

    if not server.tools:
        return True

    return str(name).strip().lower() in server.tools


URL_KEYS = ("url", "uri", "href", "link")


def _url_hosts(arguments: dict) -> list[str]:
    """Домены из URL-аргументов вызова."""

    import urllib.parse

    hosts: list[str] = []

    for key in URL_KEYS:
        value = arguments.get(key)

        if not isinstance(value, str) or "://" not in value:
            continue

        try:
            host = urllib.parse.urlsplit(value).hostname
        except ValueError:
            continue

        if host:
            hosts.append(host.lower())

    return hosts


def domain_allowed(host: str, patterns: tuple[str, ...]) -> bool:
    """Домен подходит под allowlist (точный или *.пример)."""

    if not patterns:
        return True

    name = str(host or "").lower().strip(".")

    for pattern in patterns:
        if pattern == name:
            return True

        if pattern.startswith("*."):
            suffix = pattern[2:]

            if name.endswith("." + suffix):
                return True

    return False


def check_domains(server: McpServer, arguments: dict) -> str:
    """Ошибка, если URL-аргумент ведёт на запрещённый домен."""

    for host in _url_hosts(arguments):
        if not domain_allowed(host, server.domains):
            return f"Домен не разрешён для MCP «{server.name}»: {host}"

        if not _global_allowed(host):
            return f"Домен «{host}» не входит в общий allowlist."

    return ""


def _global_allowed(host: str) -> bool:
    """Проверяет общий allowlist из настроек агента."""

    from terminal.core.agent import settings

    patterns = settings.egress_domains()

    if not patterns:
        return True

    return domain_allowed(host, patterns)


def _expand(value: str) -> str:
    """Подставляет ${VAR} из окружения, если переменная задана."""

    text = str(value or "")

    def replace(match: re.Match) -> str:
        return os.environ.get(match.group(1), "")

    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", replace, text)


def _safe_name(value: str) -> str:
    """Имя для инструмента: только латиница, цифры и подчёркивания."""

    text = NAME_RE.sub("_", str(value or "").strip().lower())
    text = re.sub(r"_+", "_", text).strip("_")

    return text[:40] or "server"


def load_servers(
    document: dict | None = None,
    config_file: Path | None = None,
) -> list[McpServer]:
    """Читает конфиг серверов, пропуская битые записи."""

    data = (
        document
        if document is not None
        else read_json_object(config_file or CONFIG_FILE)
    )
    raw = data.get("servers")

    if not isinstance(raw, list):
        return []

    servers: list[McpServer] = []
    seen: set[str] = set()

    for item in raw:
        if not isinstance(item, dict):
            continue

        name = _safe_name(item.get("name") or "")

        if not name or name in seen:
            continue

        command = str(item.get("command") or "").strip()

        if not command:
            continue

        args = item.get("args")

        if not isinstance(args, list):
            args = []

        env = item.get("env")
        clean_env: dict[str, str] = {}

        if isinstance(env, dict):
            for key, value in env.items():
                if isinstance(key, str) and isinstance(value, str):
                    clean_env[key] = _expand(value)

        seen.add(name)
        servers.append(
            McpServer(
                name=name,
                command=command,
                args=tuple(str(arg) for arg in args),
                env=clean_env,
                enabled=item.get("enabled") is not False,
                tools=_string_list(item.get("tools")),
                domains=_string_list(item.get("domains")),
            )
        )

    return servers
