# Giperion/terminal/ui/model_controls_mixin.py                      v008
# Выбор модели и личностной матрицы, подсказка поля ввода.
# Последнее изменение: без подписи модели на планке заголовка.

from shared.action_log import add_action
from terminal.core.model_registry import (
    DEFAULT_MODEL_ID,
    get_current_model_id,
    load_conference_ids,
)
from terminal.core.module_state import set_module
from terminal.ui.agent_dialog import show_agent_dialog
from terminal.ui.agent_runs_dialog import show_agent_runs_dialog
from terminal.ui.conference_dialog import show_conference_dialog
from terminal.ui.models_dialog import show_models_dialog
from terminal.ui.personalities_dialog import show_personalities_dialog
from terminal.ui.skills_dialog import show_skills_dialog
from terminal.ui.workshop_dialog import show_workshop_dialog


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
        """Открывает настройки режимов сената."""

        show_conference_dialog(self.window)

    def open_workshop_dialog(self) -> None:
        """Открывает «Мастерскую» — сборку моделей и умений."""

        show_workshop_dialog(self.window, self)

    def open_agent_dialog(self) -> None:
        """Открывает read-only агента с лентой шагов."""

        show_agent_dialog(self.window)

    def open_agent_runs_dialog(self) -> None:
        """Открывает журнал прогонов агента."""

        show_agent_runs_dialog(self.window)

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

        pet_off = getattr(self, "attached_pet", None) is not None

        if pet_off:
            self.detach_pet(announce=False)

        # Выбранная модель должна отвечать одна: сенат — отдельный
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
                "Сенат выключен: теперь в чате отвечает "
                f"«{model['name']}»."
            )

        if pet_off:
            self.append_system(
                "Дрон откреплён: теперь в чате отвечает "
                f"«{model['name']}»."
            )

        # Активный терминал очищается: в нём остаётся только
        # системное сообщение о загруженной модели.
        self._update_chat_context()

    def _turn_off_conference(self) -> bool:
        """Выключает сенат, чтобы отвечала выбранная модель."""

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

        Раньше можно было включить сенат, потом активировать другую
        модель — и в чате отвечали участники совета, а не выбранная
        модель. Теперь выбор модели выключает сенат; этот метод
        исправляет состояние, сохранённое прежними версиями.
        """

        if not self.modules.get("conference"):
            return

        if get_current_model_id() in load_conference_ids():
            return

        self._turn_off_conference()
        self.append_system(
            "Сенат выключен: активная модель "
            f"«{self.bot_name}» не входила в сенат. "
            "Теперь она отвечает одна."
        )

    def update_input_placeholder(self) -> None:
        """Подсказка в поле ввода называет того, кто отвечает."""

        if getattr(self, "attached_pet", None) is not None:
            self.input.setPlaceholderText(
                f"Напиши {self.bot_nickname}…"
            )
        elif get_current_model_id() == DEFAULT_MODEL_ID:
            self.input.setPlaceholderText("Напиши Гипериону…")
        else:
            self.input.setPlaceholderText(
                f"Напиши {self.bot_nickname}…"
            )
