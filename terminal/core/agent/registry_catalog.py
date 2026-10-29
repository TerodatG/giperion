# Giperion/terminal/core/agent/registry_catalog.py                    v001
# Статический каталог инструментов и разрешения плагинов.
# Последнее изменение: вынесено из registry_specs.

from terminal.core.agent.protocol import ToolSpec

TOOL_SPECS = (
    ToolSpec(
        name="list_dir",
        description="Показать файлы и папки внутри проекта.",
        args={"path": "путь относительно корня проекта, по умолчанию '.'"},
    ),
    ToolSpec(
        name="read_file",
        description=(
            "Прочитать текстовый файл проекта или его часть по строкам. "
            "start — первая строка (с 1), limit — сколько строк."
        ),
        args={
            "path": "путь к файлу относительно корня проекта",
            "start": "номер первой строки, по умолчанию 1",
            "limit": "сколько строк вернуть, по умолчанию весь файл",
        },
        types={"start": "integer", "limit": "integer"},
        required=("path",),
    ),
    ToolSpec(
        name="find_symbol",
        description=(
            "Найти функцию, метод или класс по части имени в индексе "
            "проекта. Быстрее, чем search_text."
        ),
        args={"query": "часть имени, минимум 2 символа"},
        required=("query",),
    ),
    ToolSpec(
        name="lsp_diagnostics",
        description=(
            "Ошибки и предупреждения файла от языкового сервера (LSP). "
            "Точнее, чем глазами: показывает типы и несуществующие имена."
        ),
        args={"path": "путь к файлу относительно проекта"},
        required=("path",),
        permissions=("fs:read",),
    ),
    ToolSpec(
        name="lsp_definition",
        description=(
            "Перейти к определению символа по позиции (строка и колонка "
            "с единицы, как в редакторе)."
        ),
        args={
            "path": "путь к файлу относительно проекта",
            "line": "номер строки с единицы",
            "character": "номер колонки с единицы",
        },
        types={"line": "integer", "character": "integer"},
        required=("path", "line", "character"),
        permissions=("fs:read",),
    ),
    ToolSpec(
        name="lsp_references",
        description=(
            "Все ссылки на символ по позиции: где ещё используется "
            "функция, класс или переменная."
        ),
        args={
            "path": "путь к файлу относительно проекта",
            "line": "номер строки с единицы",
            "character": "номер колонки с единицы",
        },
        types={"line": "integer", "character": "integer"},
        required=("path", "line", "character"),
        permissions=("fs:read",),
    ),
    ToolSpec(
        name="find_relevant",
        description=(
            "Найти по смыслу, где в проекте говорится о задаче: код, "
            "документация и конфиги. Лучше search_text, когда не знаешь "
            "точных слов; возвращает путь, строку и отрывок."
        ),
        args={
            "query": "описание задачи словами",
            "limit": "сколько фрагментов, по умолчанию 8",
        },
        types={"limit": "integer"},
        required=("query",),
    ),
    ToolSpec(
        name="search_text",
        description="Найти строку в файлах проекта (регистр не важен).",
        args={
            "query": "искомая строка, минимум 2 символа",
            "path": "где искать, по умолчанию весь проект",
        },
        required=("query",),
    ),
    ToolSpec(
        name="apply_patch",
        description=(
            "Заменить один уникальный фрагмент в файле. "
            "Требует подтверждения пользователя."
        ),
        args={
            "path": "путь к файлу",
            "old": "точный фрагмент, который меняем",
            "new": "чем заменить (пустая строка — удалить)",
        },
        risk="write",
        required=("path", "old", "new"),
    ),
    ToolSpec(
        name="write_file",
        description=(
            "Создать или полностью перезаписать текстовый файл. "
            "Требует подтверждения; лучше apply_patch."
        ),
        args={
            "path": "путь к файлу",
            "content": "полный новый текст файла",
        },
        risk="write",
        required=("path", "content"),
    ),
    ToolSpec(
        name="run_tests",
        description=(
            "Запустить pytest в папке проекта и показать итог. "
            "dry_run=true — только показать команду."
        ),
        args={"dry_run": "true — не запускать, только показать"},
        types={"dry_run": "boolean"},
        risk="exec",
    ),
    ToolSpec(
        name="git_status",
        description="Показать состояние рабочей копии git.",
        args={},
        risk="read",
    ),
    ToolSpec(
        name="git_diff",
        description="Показать незакоммиченные изменения.",
        args={"path": "файл или пусто для всего проекта"},
        risk="read",
    ),
    ToolSpec(
        name="git_log",
        description="Показать последние коммиты.",
        args={"limit": "сколько коммитов, по умолчанию 5"},
        risk="read",
    ),
    ToolSpec(
        name="git_commit",
        description=(
            "Закоммитить один или несколько изменённых файлов с сообщением. "
            "Требует подтверждения."
        ),
        args={
            "paths": "список путей к файлам",
            "message": "сообщение коммита",
        },
        types={"paths": "array"},
        risk="write",
        required=("paths", "message"),
    ),
    ToolSpec(
        name="git_restore",
        description=(
            "Откатить незакоммиченные изменения файла. "
            "Требует подтверждения."
        ),
        args={"path": "путь к файлу"},
        risk="write",
        required=("path",),
    ),
    ToolSpec(
        name="run_command",
        description=(
            "Разрешённая команда: git status/diff/log/show, "
            "python -m pytest, python -m compileall. "
            "dry_run=true — только показать команду."
        ),
        args={
            "command": "команда одной строкой",
            "dry_run": "true — не запускать, только показать",
        },
        types={"dry_run": "boolean"},
        risk="exec",
        required=("command",),
    ),
    ToolSpec(
        name="ask_subagent",
        description=(
            "Поручить чтение подзадач отдельным читающим агентам: "
            "они ищут и читают файлы, но не меняют их. Передай task "
            "(одна) или tasks (массив — выполняются параллельно)."
        ),
        args={
            "task": "одна подзадача",
            "tasks": "несколько независимых подзадач (массив)",
            "role": "роль: researcher, reviewer или tester",
        },
        types={"tasks": "array"},
        risk="read",
        required=(),
    ),
    ToolSpec(
        name="lsp_symbols",
        description=(
            "Список функций, классов и методов файла с номерами строк. "
            "Удобно, чтобы быстро понять структуру модуля."
        ),
        args={"path": "путь к файлу относительно проекта"},
        required=("path",),
        permissions=("fs:read",),
    ),
    ToolSpec(
        name="lsp_hover",
        description=(
            "Подсказка типа или документация символа в позиции "
            "(строка и колонка с единицы)."
        ),
        args={
            "path": "путь к файлу относительно проекта",
            "line": "номер строки с единицы",
            "character": "номер колонки с единицы",
        },
        types={"line": "integer", "character": "integer"},
        required=("path", "line", "character"),
        permissions=("fs:read",),
    ),
    ToolSpec(
        name="remember",
        description=(
            "Записать важное решение, ограничение или договорённость в "
            "память проекта (data/agent_memory.md). Она попадёт в "
            "следующие задачи. Требует подтверждения."
        ),
        args={"text": "что запомнить, одна-две фразы"},
        risk="write",
        required=("text",),
    ),
    ToolSpec(
        name="update_plan",
        description=(
            "Составить или обновить план задачи. Вызывай в начале "
            "многошаговой задачи и обновляй статусы по ходу."
        ),
        args={"steps": "пункты плана со статусами"},
        risk="read",
        required=("steps",),
        schema={
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "description": "пункты плана по порядку",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "что сделать",
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "doing", "done"],
                                "description": "состояние пункта",
                            },
                        },
                        "required": ["text", "status"],
                    },
                }
            },
            "required": ["steps"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="browser_read",
        description=(
            "Открыть страницу в headless-браузере с JavaScript и получить "
            "текст после выполнения скриптов. Для страниц, которые "
            "fetch_url видит пустыми. Требует подтверждения; локальные "
            "адреса запрещены."
        ),
        args={
            "url": "адрес страницы или current для уже открытой",
            "wait": "CSS-селектор, которого дождаться (необязательно)",
        },
        risk="exec",
        required=("url",),
    ),
    ToolSpec(
        name="browser_act",
        description=(
            "Открыть страницу в браузере с JavaScript, выполнить клики, "
            "ввод, прокрутку или паузы и вернуть текст. Можно сделать "
            "скриншот. Требует подтверждения; локальные адреса запрещены."
        ),
        args={},
        risk="exec",
        required=("url", "actions"),
        schema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": (
                        "адрес страницы или current — действовать на "
                        "уже открытой в сессии"
                    ),
                },
                "actions": {
                    "type": "array",
                    "description": (
                        "до 12 действий по порядку: click/fill/press/"
                        "scroll/wait/wait_text/wait_url/goto/back/download"
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": [
                                    "click",
                                    "fill",
                                    "press",
                                    "hover",
                                    "select",
                                    "scroll",
                                    "wait",
                                    "wait_text",
                                    "wait_url",
                                    "new_tab",
                                    "switch_tab",
                                    "close_tab",
                                    "goto",
                                    "back",
                                    "download",
                                ],
                            },
                            "selector": {"type": "string"},
                            "text": {"type": "string"},
                            "key": {"type": "string"},
                            "value": {"type": "string"},
                            "url": {"type": "string"},
                            "pixels": {"type": "integer"},
                            "ms": {"type": "integer"},
                        },
                        "required": ["type"],
                    },
                },
                "wait": {
                    "type": "string",
                    "description": "CSS-селектор до действий",
                },
                "shot": {
                    "type": "boolean",
                    "description": "сохранить скриншот в data/agent_browser",
                },
                "full_page": {
                    "type": "boolean",
                    "description": "скриншот всей страницы, а не экрана",
                },
                "record": {
                    "type": "string",
                    "description": (
                        "путь .json внутри проекта для записи сценария"
                    ),
                },
            },
            "required": ["url", "actions"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="fetch_url",
        description=(
            "Прочитать веб-страницу по http/https и получить текст без "
            "разметки. Требует подтверждения; локальные адреса запрещены."
        ),
        args={"url": "адрес страницы"},
        risk="exec",
        required=("url",),
    ),
)

PLUGIN_PERMISSIONS = {"fs:read", "fs:write", "net", "exec"}

DEFAULT_PERMISSIONS = {
    "read": ("fs:read",),
    "write": ("fs:read", "fs:write"),
    "exec": ("fs:read", "fs:write", "exec"),
}
