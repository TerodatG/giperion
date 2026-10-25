# Giperion/terminal/core/agent/tools.py                               v002
# Совместимый фасад файловых инструментов; код в tools_policy/read/write/exec.
# Последнее изменение: разнесено по модулям.

import subprocess  # noqa: F401 — реэкспорт для тестов

from terminal.core.agent.tools_exec import run_command, run_tests
from terminal.core.agent.tools_policy import (
    BACKUP_DIR,
    DENIED_NAMES,
    DENIED_PREFIXES,
    DENIED_RELATIVE,
    DENIED_SUFFIXES,
    DIFF_LIMIT,
    MAX_LIST_ENTRIES,
    MAX_READ_BYTES,
    MAX_READ_CHARS,
    MAX_SEARCH_FILE_BYTES,
    MAX_SEARCH_FILES,
    MAX_SEARCH_HITS,
    MAX_WRITE_CHARS,
    SKIP_DIRS,
    TEST_TIMEOUT,
    TEXT_SUFFIXES,
    ToolError,
    safe_path,
)
from terminal.core.agent.tools_read import (
    _iter_text_files,
    list_dir,
    read_file,
    search_text,
)
from terminal.core.agent.tools_write import (
    apply_patch,
    prepare_patch,
    prepare_write,
    write_file,
)

__all__ = [
    "BACKUP_DIR",
    "DENIED_NAMES",
    "DENIED_PREFIXES",
    "DENIED_RELATIVE",
    "DENIED_SUFFIXES",
    "DIFF_LIMIT",
    "MAX_LIST_ENTRIES",
    "MAX_READ_BYTES",
    "MAX_READ_CHARS",
    "MAX_SEARCH_FILE_BYTES",
    "MAX_SEARCH_FILES",
    "MAX_SEARCH_HITS",
    "MAX_WRITE_CHARS",
    "SKIP_DIRS",
    "TEST_TIMEOUT",
    "TEXT_SUFFIXES",
    "ToolError",
    "_iter_text_files",
    "apply_patch",
    "list_dir",
    "prepare_patch",
    "prepare_write",
    "read_file",
    "run_command",
    "run_tests",
    "safe_path",
    "search_text",
    "write_file",
]
