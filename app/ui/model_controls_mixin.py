# Giperion/app/ui/model_controls_mixin.py                           v006
# Выбор модели и личностной матрицы, подсказка поля ввода.
# Последнее изменение: ник модели в чате и подсказке ввода.

from PySide6.QtCore import QTimer

from shared.action_log import add_action
from app.core.model_registry import (
    DEFAULT_MODEL_ID,
    get_current_model_id,
    load_conference_ids,
)
from app.core.module_state import set_module
from app.ui.conference_dialog import show_conference_dialog
from app.ui.models_dialog import show_models_dialog
from app.ui.personalities_dialog import show_personalities_dialog
from app.ui.skills_dialog import show_skills_dialog


class ModelControlsMixin:
    """Методы окна для выбора модели, личности и списка умений."""

    def open_skills_dialog(self) -> None:
        """Открывает окно «Умения» со списком навыков ядра."""

        show_skills_dialog(self.window)

    def open_models_dialog(self) -> None:
        """Открывает окно «Модель» и применяет выбранную модель."""

        show_models_dialog(
            self.window,
            on_activate=self.activate_model,
        )

    def open_conference_dialog(self) -> None:
        """Открывает настройки режимов конференции."""

        show_conference_dialog(self.window)

    def open_personalities_dialog(self) -> None:
        """Открывает каталог личностных матриц."""

        show_personalities_dialog(
            self.window,
            on_select=self._personality_selected,
        )

    def _personality_selected(self, matrix: dict) -> None:
        """Запоминает будущую матрицу поведения без смены ответов."""

        add_action(
            f"Выбрана личностная матрица: {matrix['name']}"
        )
        self.append_system(
            f"Личностная матрица «{matrix['name']}» выбрана "
            "для будущего режима. Влияние на ответы пока не подключено."
        )

        if hasattr(self, "title_status"):
            self.title_status.setText(
                f"матрица: {matrix['name']}"
            )

            QTimer.singleShot(
                2500,
                self._restore_title_status,
            )

    def _personality_module_unavailable(self) -> None:
        """Сообщает, что модуль личности ещё не подключён."""

        self.append_system(
            "Модуль «Личностная матрица» пока недоступен. "
            "Каталог будущих матриц можно открыть кнопкой "
            "«Личностные матрицы» на левой панели."
        )

    def activate_model(self, model: dict) -> None:
        """Переключает окно на выбранную модель: портрет, панель, чат."""

        add_action(f"Активирована модель: {model['name']}")

        # Выбранная модель должна отвечать одна: конференция — отдельный
        # режим, и её участники иначе перехватывают ответы.
        conference_off = self._turn_off_conference()

        # Главное окно целиком переходит на новую модель.
        self.bot_name = model["name"]
        self.bot_nickname = (
            model.get("nickname") or model["name"]
        )
        self.apply_model_avatar()
        self.update_input_placeholder()
        self.update_core_panel()

        self.append_system(f"Активна модель «{model['name']}».")

        if conference_off:
            self.append_system(
                "Конференция выключена: теперь в чате отвечает "
                f"«{model['name']}»."
            )

        # Активный терминал очищается: в нём остаётся только
        # системное сообщение о загруженной модели.
        self._update_chat_context()

        if hasattr(self, "title_status"):
            self.title_status.setText(f"модель: {model['name']}")

            QTimer.singleShot(
                2500,
                self._restore_title_status,
            )

    def _turn_off_conference(self) -> bool:
        """Выключает конференцию, чтобы отвечала выбранная модель."""

        if not self.modules.get("conference"):
            return False

        self.modules["conference"] = False
        set_module("conference", False)
        self._save_window_settings()

        button = getattr(self, "module_buttons", {}).get(
            "conference"
        )

        if button is not None:
            button.blockSignals(True)
            button.setChecked(False)
            button.blockSignals(False)
            button.refresh_tooltip()

        return True

    def _reconcile_conference_state(self) -> None:
        """Убирает старое противоречие: совет включён, а модель вне его.

        Раньше можно было включить конференцию, потом активировать другую
        модель — и в чате отвечали участники совета, а не выбранная
        модель. Теперь выбор модели выключает конференцию; этот метод
        исправляет состояние, сохранённое прежними версиями.
        """

        if not self.modules.get("conference"):
            return

        if get_current_model_id() in load_conference_ids():
            return

        self._turn_off_conference()
        self.append_system(
            "Конференция выключена: активная модель "
            f"«{self.bot_name}» не входила в совет. "
            "Теперь она отвечает одна."
        )

    def update_input_placeholder(self) -> None:
        """Подсказка в поле ввода называет того, кто отвечает."""

        if get_current_model_id() == DEFAULT_MODEL_ID:
            self.input.setPlaceholderText("Напиши Гипериону…")
        else:
            self.input.setPlaceholderText(
                f"Напиши {self.bot_nickname}…"
            )
