# Giperion/app/core/model_files.py                                v001
# Пути к файлам каталога моделей, настроек и статистики.
# Последнее изменение: пути вынесены отдельно, чтобы тесты подменяли их в одном месте.

from config import DATA_DIR

MODELS_FILE = DATA_DIR / "models.json"
CUSTOM_MODELS_FILE = DATA_DIR / "custom_models.json"
SETTINGS_FILE = DATA_DIR / "model_settings.json"
STATS_FILE = DATA_DIR / "model_stats.json"
