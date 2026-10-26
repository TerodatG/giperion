# Giperion/terminal/ui/dashboard_mixin.py                            v003
# Панели состояния: параметры модели ИИ и карточка активной модели.
# Последнее изменение: обновление чисел агента вместе с панелью ядра.

from terminal.core.model_catalog import (
    DEFAULT_MODEL_ID,
)
from terminal.core.model_passport import (
    compact_metrics,
    get_passport,
    passport_accuracy,
)
from terminal.core.model_settings import (
    get_active_model,
)
from terminal.core.model_stats import (
    build_stars,
    get_reputation,
    get_usage,
)
from terminal.ui.value_text import (
    format_percent,
    format_tokens,
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


class DashboardMixin:
    """Методы окна для панелей параметров модели и активной модели."""

    def update_core_panel(self) -> None:
        """Обновляет левую панель: паспорт модели или активной внешней."""

        model = get_active_model()

        if model is not None and model["id"] != DEFAULT_MODEL_ID:
            self._update_model_panel(model)
            self._refresh_executive_panel()

            return

        passport = get_passport(DEFAULT_MODEL_ID)
        metrics = compact_metrics(passport or {})

        if hasattr(self, "personality_title"):
            self.personality_title.setText("Параметры ИИ")

        if hasattr(self, "led_caption"):
            self.led_caption.setText("ТОЧНОСТЬ МОДЕЛИ")

        accuracy = passport_accuracy(passport)

        if hasattr(self, "led_meter"):
            self.led_meter.set_level(
                round(accuracy * 100)
                if accuracy is not None
                else 0
            )

        for (label_name, _), (title, _) in zip(
            CORE_FIELDS,
            metrics, strict=False,
        ):
            label = self.window.findChild(object, label_name)

            if label is not None:
                label.setText(f"{title}:")

        for value_name, (_, value) in zip(
            CORE_VALUE_LABELS,
            metrics, strict=False,
        ):
            value_label = self.window.findChild(
                object,
                value_name,
            )

            if value_label is not None:
                value_label.setText(str(value))

        self._refresh_executive_panel()

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

        for (label_name, _), (title, _) in zip(CORE_FIELDS, values, strict=False):
            label = self.window.findChild(object, label_name)

            if label is not None:
                label.setText(f"{title}:")

        for value_name, (_, value) in zip(CORE_VALUE_LABELS, values, strict=False):
            value_label = self.window.findChild(
                object,
                value_name,
            )

            if value_label is not None:
                value_label.setText(str(value))

        if hasattr(self, "personality_title"):
            self.personality_title.setText("Параметры модели")

        if hasattr(self, "led_caption"):
            self.led_caption.setText("РЕПУТАЦИЯ МОДЕЛИ")

        if hasattr(self, "led_meter"):
            self.led_meter.set_level(reputation["percent"])

    def _refresh_executive_panel(self) -> None:
        """Обновляет числовые показатели агента, если панель собрана."""

        if hasattr(self, "update_executive_panel"):
            self.update_executive_panel()
