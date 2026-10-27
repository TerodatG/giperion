# GiperionModel/giperion_model/config.py                                v001
# Пути модели: по умолчанию текущая папка, переопределяются env.
# Последнее изменение: отделено от приложения Giperion.

import os
from pathlib import Path


def _path(name: str, default: Path) -> Path:
    """Путь из env; пустая переменная не должна превращаться в cwd."""

    value = os.environ.get(name, "").strip()

    return Path(value or default).expanduser().resolve()


BASE_DIR = _path("GIPERION_HOME", Path.cwd())
DATA_DIR = _path("GIPERION_DATA_DIR", BASE_DIR / "data")
MODELS_DIR = _path("GIPERION_MODELS_DIR", BASE_DIR / "models")
ARCHIVE_DIR = _path("GIPERION_ARCHIVE_DIR", BASE_DIR / "archive")
LOGS_DIR = _path("GIPERION_LOGS_DIR", BASE_DIR / "logs")
DEVICE = os.environ.get("GIPERION_DEVICE", "auto").strip().lower() or "auto"

BOT_NAME = "Giperion"


def resolve_device():
    """Возвращает torch.device по GIPERION_DEVICE.

    torch импортируется здесь, чтобы конфиг оставался лёгким для
    сценариев, которым нейросеть не нужна.
    """

    import torch

    if DEVICE == "cpu":
        return torch.device("cpu")

    if DEVICE.startswith("cuda"):
        if not torch.cuda.is_available():
            return torch.device("cpu")

        return torch.device(DEVICE)

    return torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )


USER_PROFILE_FILE = DATA_DIR / "user_profile.json"
CONVERSATIONS_FILE = DATA_DIR / "conversations.json"
UNKNOWN_MESSAGES_FILE = DATA_DIR / "unknown_messages.json"
ACTIONS_LOG_FILE = LOGS_DIR / "actions.log"
