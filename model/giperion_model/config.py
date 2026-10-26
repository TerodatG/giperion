# GiperionModel/giperion_model/config.py                                v001
# Пути модели: по умолчанию текущая папка, переопределяются env.
# Последнее изменение: отделено от приложения Giperion.

import os
from pathlib import Path

BASE_DIR = Path(
    os.environ.get("GIPERION_HOME", Path.cwd())
).resolve()
DATA_DIR = Path(
    os.environ.get("GIPERION_DATA_DIR", BASE_DIR / "data")
).resolve()
MODELS_DIR = Path(
    os.environ.get("GIPERION_MODELS_DIR", BASE_DIR / "models")
).resolve()
ARCHIVE_DIR = Path(
    os.environ.get("GIPERION_ARCHIVE_DIR", BASE_DIR / "archive")
).resolve()
LOGS_DIR = Path(
    os.environ.get("GIPERION_LOGS_DIR", BASE_DIR / "logs")
).resolve()

BOT_NAME = "Giperion"

USER_PROFILE_FILE = DATA_DIR / "user_profile.json"
CONVERSATIONS_FILE = DATA_DIR / "conversations.json"
UNKNOWN_MESSAGES_FILE = DATA_DIR / "unknown_messages.json"
ACTIONS_LOG_FILE = LOGS_DIR / "actions.log"
