# Giperion/terminal/core/agent/registry_plugins.py                    v001
# Плагины инструментов: манифесты, разрешения и кэш.
# Последнее изменение: вынесено из registry.

import json
import re
import threading
from pathlib import Path

from config import DATA_DIR
from terminal.core.agent.protocol import ToolSpec
from terminal.core.agent.registry_catalog import (
    DEFAULT_PERMISSIONS,
    PLUGIN_PERMISSIONS,
    TOOL_SPECS,
)

PLUGIN_DIR = DATA_DIR / "agent_tools"
PLUGIN_NAME = re.compile(r"^[a-z][a-z0-9_]{2,30}$")

_plugin_cache: tuple[tuple[ToolSpec, ...], dict] | None = None
_plugin_lock = threading.Lock()


def _permissions(document: dict, risk: str) -> tuple[str, ...]:
    """Разрешения плагина: по умолчанию — по уровню риска."""

    raw = document.get("permissions")

    if raw is None:
        return DEFAULT_PERMISSIONS[risk]

    if not isinstance(raw, list) or not all(
        isinstance(item, str) for item in raw
    ):
        raise ValueError("permissions должен быть списком строк.")

    unknown = set(raw) - PLUGIN_PERMISSIONS

    if unknown:
        raise ValueError(
            "Неизвестные разрешения: " + ", ".join(sorted(unknown))
        )

    permissions = tuple(dict.fromkeys(raw))

    if "fs:write" in permissions and risk == "read":
        raise ValueError("fs:write требует risk=write или exec.")

    if "net" in permissions and risk != "exec":
        raise ValueError("net требует risk=exec.")

    if "exec" in permissions and risk != "exec":
        raise ValueError("exec требует risk=exec.")

    return permissions


def _manifest_header(document: dict) -> tuple[str, str]:
    """Имя и описание плагина."""

    name = str(document.get("name") or "").strip()

    if not PLUGIN_NAME.fullmatch(name):
        raise ValueError(f"Недопустимое имя плагина: {name}")

    description = str(document.get("description") or "").strip()

    if not description:
        raise ValueError("У плагина нет описания.")

    return name, description


def _manifest_args(document: dict) -> tuple[dict, tuple]:
    """Аргументы и обязательные имена."""

    args = document.get("args") or {}

    if not isinstance(args, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in args.items()
    ):
        raise ValueError("args плагина должен быть словарём строк.")

    required = document.get("required") or ()

    if not isinstance(required, (list, tuple)) or not all(
        isinstance(item, str) and item in args for item in required
    ):
        raise ValueError("required должен ссылаться на args.")

    return args, tuple(required)


def _manifest_risk(document: dict) -> str:
    """Риск плагина."""

    risk = str(document.get("risk") or "read")

    if risk not in ("read", "write", "exec"):
        raise ValueError("risk должен быть read, write или exec.")

    return risk


def _manifest_module(document: dict, path: Path) -> Path:
    """Путь к модулю рядом с манифестом."""

    module = str(document.get("module") or "").strip()

    if not module.endswith(".py"):
        raise ValueError("module должен указывать на .py.")

    module_path = (path.parent / module).resolve()

    if module_path.parent != path.parent.resolve():
        raise ValueError("Модуль плагина должен лежать рядом.")

    if not module_path.is_file():
        raise ValueError(f"Нет модуля плагина: {module}")

    return module_path


def _manifest_handler(document: dict) -> str:
    """Имя функции-обработчика."""

    handler = str(document.get("handler") or "handler").strip()

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", handler):
        raise ValueError("Недопустимое имя обработчика.")

    return handler


def _parse_manifest(
    document: object,
    path: Path,
) -> tuple[ToolSpec, Path, str]:
    """Проверяет JSON-манифест, не исполняя код плагина."""

    if not isinstance(document, dict):
        raise ValueError("Манифест должен быть объектом.")

    name, description = _manifest_header(document)
    args, required = _manifest_args(document)
    risk = _manifest_risk(document)
    module_path = _manifest_module(document, path)
    handler = _manifest_handler(document)
    permissions = _permissions(document, risk)

    return (
        ToolSpec(
            name=name,
            description=description,
            args=dict(args),
            risk=risk,
            required=required,
            permissions=permissions,
        ),
        module_path,
        handler,
    )


def _unsafe_allowed(spec: ToolSpec) -> bool:
    """Плагин с сетью или запуском программ грузится только по разрешению."""

    dangerous = {"net", "exec"} & set(spec.permissions or ())

    if not dangerous:
        return True

    try:
        from terminal.core.agent import settings

        return settings.allow_unsafe_plugins()
    except Exception:  # noqa: BLE001 — без настроек считаем запрещённым
        return False


def plugin_tools() -> tuple[tuple[ToolSpec, ...], dict]:
    """Читает манифесты плагинов, если они разрешены в настройках."""

    global _plugin_cache

    with _plugin_lock:
        if _plugin_cache is not None:
            return _plugin_cache

        specs: list[ToolSpec] = []
        plugins: dict[str, tuple[Path, str]] = {}

        try:
            from terminal.core.agent import settings

            enabled = settings.plugins_enabled()
        except Exception:  # noqa: BLE001 — без настроек плагинов нет
            enabled = False

        if enabled and PLUGIN_DIR.is_dir():
            builtin = {spec.name for spec in TOOL_SPECS}

            for path in sorted(PLUGIN_DIR.glob("*.json")):
                if path.name.startswith("_"):
                    continue

                try:
                    document = json.loads(
                        path.read_text(encoding="utf-8")
                    )
                    spec, module_path, handler = _parse_manifest(
                        document,
                        path,
                    )
                except (OSError, ValueError, json.JSONDecodeError):
                    continue

                if not _unsafe_allowed(spec):
                    continue

                if spec.name in builtin or spec.name in plugins:
                    continue

                specs.append(spec)
                plugins[spec.name] = (
                    module_path,
                    handler,
                    spec.permissions,
                )

        _plugin_cache = (tuple(specs), plugins)

        return _plugin_cache


def reload_plugins() -> None:
    """Сбрасывает кэш плагинов после изменения настроек."""

    global _plugin_cache

    with _plugin_lock:
        _plugin_cache = None


def _plugin_handler(name: str):
    """Модуль, обработчик и разрешения плагина."""

    return plugin_tools()[1].get(name)

