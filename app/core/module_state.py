# Giperion/app/core/module_state.py                                  v002
# Текущие разрешения модулей для логики ответов.
# Последнее изменение: убрана неиспользуемая функция get_modules.

from app.core.window_settings import DEFAULT_MODULE_STATES

# Состояние живёт в памяти процесса; на диск его сохраняет окно.
_modules = dict(DEFAULT_MODULE_STATES)


def set_modules(states: dict) -> None:
    """Заменяет состояния модулей после загрузки настроек окна."""

    for key in DEFAULT_MODULE_STATES:
        if isinstance(states.get(key), bool):
            _modules[key] = states[key]


def set_module(key: str, enabled: bool) -> None:
    """Включает или выключает один модуль."""

    if key in _modules:
        _modules[key] = bool(enabled)


def is_module_enabled(key: str) -> bool:
    """Проверяет, разрешён ли модуль."""

    return bool(_modules.get(key, False))
