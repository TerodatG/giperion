# Giperion/config.py                                              v004
# Общие настройки и пути проекта Giperion.
# Последнее изменение: добавлен путь к каталогу обученных моделей.

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ARCHIVE_DIR = BASE_DIR / "archive"
LOGS_DIR = BASE_DIR / "logs"
MODELS_DIR = BASE_DIR / "models"

BOT_NAME = "Giperion"

USER_PROFILE_FILE = DATA_DIR / "user_profile.json"
CONVERSATIONS_FILE = DATA_DIR / "conversations.json"
UNKNOWN_MESSAGES_FILE = DATA_DIR / "unknown_messages.json"

ACTIONS_LOG_FILE = LOGS_DIR / "actions.log"