# Giperion/shared/process_tools.py                                   v001
# Запуск служебных консольных программ без мигающего окна.
# Последнее изменение: общий скрытый запуск для Windows.

import os
import subprocess


def hidden_process_options() -> dict:
    """Прячет консольное окно дочернего процесса на Windows."""

    if os.name != "nt":
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE

    return {
        "creationflags": getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0,
        ),
        "startupinfo": startupinfo,
    }
