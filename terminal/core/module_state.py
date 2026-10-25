# Giperion/app/core/module_state.py                                  v003
# Текущие разрешения модулей для логики ответов.
# Последнее изменение: доступ к файлам включён всегда, без выключателя.

from terminal.core.window_settings import (
    ALWAYS_ON_MODULES,
    DEFAULT_MODULE_STATES,
)

# Состояние живёт в памяти процесса; на диск его сохраняет окно.
_modules = dict(DEFAULT_MODULE_STATES)


def _apply_always_on() -> None:
    """Возвращает постоянные модули во включённое состояние."""

    for key in ALWAYS_ON_MODULES:
        _modules[key] = True


def set_modules(states: dict) -> None:
    """Заменяет состояния модулей после загрузки настроек окна."""

    for key in DEFAULT_MODULE_STATES:
        if isinstance(states.get(key), bool):
            _modules[key] = states[key]

    _apply_always_on()


def set_module(key: str, enabled: bool) -> None:
    """Включает или выключает один модуль."""

    if key not in _modules:
        return

    if key in ALWAYS_ON_MODULES:
        _modules[key] = True

        return

    _modules[key] = bool(enabled)


def is_module_enabled(key: str) -> bool:
    """Проверяет, разрешён ли модуль."""

    return bool(_modules.get(key, False))
