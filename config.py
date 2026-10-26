# Giperion/config.py                                              v004
# Общие настройки и пути проекта Giperion.
# Последнее изменение: добавлен путь к каталогу обученных моделей.

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ARCHIVE_DIR = BASE_DIR / "archive"
LOGS_DIR = BASE_DIR / "logs"
MODELS_DIR = BASE_DIR / "models"

# Модель живёт отдельным пакетом и читает пути из окружения.
os.environ.setdefault("GIPERION_HOME", str(BASE_DIR))
os.environ.setdefault("GIPERION_DATA_DIR", str(DATA_DIR))
os.environ.setdefault("GIPERION_MODELS_DIR", str(MODELS_DIR))
os.environ.setdefault("GIPERION_LOGS_DIR", str(LOGS_DIR))

BOT_NAME = "Giperion"

USER_PROFILE_FILE = DATA_DIR / "user_profile.json"
CONVERSATIONS_FILE = DATA_DIR / "conversations.json"
UNKNOWN_MESSAGES_FILE = DATA_DIR / "unknown_messages.json"

ACTIONS_LOG_FILE = LOGS_DIR / "actions.log"