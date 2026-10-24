# Giperion/app/ui/dashboard_mixin.py                                v001
# Панели состояния: параметры ядра и карточка активной модели.
# Последнее изменение: методы вынесены из GiperionWindow как отдельный слой.

from app.core.character_service import get_characteristics
from app.core.model_registry import (
    DEFAULT_MODEL_ID,
    build_stars,
    get_active_model,
    get_reputation,
    get_usage,
)
from app.ui.value_text import (
    format_percent,
    format_tokens,
    make_progress_bar,
    tokens_word,
)

# Соответствие подписей панели ядра ключам характеристик.
CORE_FIELDS = (
    ("identifierLabel", "identifier"),
    ("coreVersionLabel", "core_version"),
    ("developmentLevelLabel", "level"),
    ("evolutionLabel", "experience"),
    ("activeSkillsLabel", "skills_count"),
    ("memoryEntriesLabel", "memory_records_count"),
    ("unrecognizedPhrasesLabel", "unknown_messages_count"),
)

# Подписи виджетов-значений панели ядра, в порядке строк.
CORE_VALUE_LABELS = (
    "label",
    "label_3",
    "label_4",
    "label_5",
    "label_6",
    "label_7",
    "label_8",
)

# Русские подписи строк панели ядра.
CORE_FIELD_TITLES = {
    "identifier": "Идентификатор",
    "core_version": "Версия ядра",
    "level": "Уровень",
    "experience": "Опыт",
    "skills_count": "Активные навыки",
    "memory_records_count": "Записей памяти",
    "unknown_messages_count": "Непонятых фраз",
}


class DashboardMixin:
    """Методы окна для панелей параметров ядра и модели."""

    def update_core_panel(self) -> None:
        """Обновляет левую панель: параметры ядра или активной модели."""

        model = get_active_model()

        if model is not None and model["id"] != DEFAULT_MODEL_ID:
            self._update_model_panel(model)

            return

        if hasattr(self, "personality_title"):
            self.personality_title.setText("Параметры ИИ-ядра")

        if hasattr(self, "led_caption"):
            self.led_caption.setText("РОСТ ЯДРА")

        characteristics = get_characteristics()

        # Версия ядра видна и на планке заголовка.
        if hasattr(self, "title_status"):
            self.title_status.setText(
                f"ядро v{characteristics['core_version']}"
            )

        # Шкала роста ядра в панели инструментов.
        if hasattr(self, "led_meter"):
            self.led_meter.set_level(
                characteristics["level_percent"]
            )

        # Уровень в панели дополняем прогресс-баром роста.
        bar = make_progress_bar(
            int(characteristics["level_percent"])
        )

        display_values = {
            "identifier": characteristics["identifier"],
            "core_version": characteristics["core_version"],
            "level": (
                f"{characteristics['level_number']} "
                f"[{bar}] {characteristics['level_percent']}%"
            ),
            "experience": self._format_experience(
                characteristics
            ),
            "skills_count": characteristics["skills_count"],
            "memory_records_count": (
                characteristics["memory_records_count"]
            ),
            "unknown_messages_count": (
                characteristics["unknown_messages_count"]
            ),
        }

        for label_name, field_key in CORE_FIELDS:
            label = self.window.findChild(
                object,
                label_name,
            )

            if label is None:
                continue

            label.setText(
                f"{CORE_FIELD_TITLES[field_key]}:"
            )

        for value_name, (_, field_key) in zip(
            CORE_VALUE_LABELS,
            CORE_FIELDS,
        ):
            value_label = self.window.findChild(
                object,
                value_name,
            )

            if value_label is None:
                continue

            value_label.setText(
                str(display_values[field_key])
            )

    def _update_model_panel(self, model: dict) -> None:
        """Показывает в левой панели личное дело внешней модели."""

        usage = get_usage(model["id"])
        reputation = get_reputation(model["id"])

        limit = usage["context_limit"]
        used = usage["tokens_used"]

        # Для внешней модели «уровень» — это её репутация.
        context_text = (
            f"{format_tokens(limit)} {tokens_word(limit)}"
            if limit
            else "не указан"
        )

        tokens_text = (
            f"{format_tokens(used)} "
            f"({format_percent(used * 100 / usage['token_budget'])}"
            " % бюджета)"
            if usage["token_budget"]
            else f"{format_tokens(used)}"
        )

        requests_text = (
            f"{reputation['requests']} · "
            f"{build_stars(reputation['stars'])}"
        )

        # В строке «Что умеет» только те умения, где оценка больше нуля.
        # Названия сокращены, чтобы строка помещалась в панель.
        short_names = {
            "Текст": "Текст",
            "Графика": "Граф.",
            "Видео": "Видео",
            "Кодинг": "Код",
            "Творчество": "Творч.",
        }

        strengths = " · ".join(
            f"{short_names.get(name, name)} {value}"
            for name, value in model["strengths"].items()
            if value > 0
        )

        if not strengths:
            strengths = "пока ничего"

        access_text = {
            "бесплатно": "бесплатно (OpenCode)",
            "локально": "локально, без интернета",
        }.get(model["price"], model["price"] or "не указан")

        values = (
            ("Идентификатор", model["id"]),
            ("Поставщик", model["provider"]),
            ("Контекст", context_text),
            ("Токены", tokens_text),
            ("Обращений", requests_text),
            ("Доступ", access_text),
            ("Что умеет", strengths),
        )

        for (label_name, _), (title, _) in zip(CORE_FIELDS, values):
            label = self.window.findChild(object, label_name)

            if label is not None:
                label.setText(f"{title}:")

        for value_name, (_, value) in zip(CORE_VALUE_LABELS, values):
            value_label = self.window.findChild(object, value_name)

            if value_label is not None:
                value_label.setText(str(value))

        if hasattr(self, "personality_title"):
            self.personality_title.setText("Параметры модели")

        if hasattr(self, "led_caption"):
            self.led_caption.setText("РЕПУТАЦИЯ МОДЕЛИ")

        if hasattr(self, "led_meter"):
            self.led_meter.set_level(reputation["percent"])

        if hasattr(self, "title_status"):
            self.title_status.setText(f"модель: {model['name']}")

    @staticmethod
    def _format_experience(characteristics: dict) -> str:
        """Показывает общий опыт и его источники в столбик."""

        breakdown = characteristics["breakdown"]

        lines = [
            f"{characteristics['experience']}",
            f"навыки: {breakdown['skills']}",
            f"память: {breakdown['memory']}",
            f"знания: {breakdown['knowledge']}",
        ]

        return "\n".join(lines)
