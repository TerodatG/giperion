# Giperion/terminal/ui/models/state.py                                v001
# Состояние окна «Модель»: каталог, выбор, списки и группы.
# Последнее изменение: вынесено из show_models_dialog.

from dataclasses import dataclass, field

from terminal.core.conference_roster import order_models_by_reputation
from terminal.core.model_registry import (
    COMPANION_GROUP,
    CONFERENCE_GROUP,
    get_current_model_id,
    load_companion_ids,
    load_conference_ids,
    load_models,
)
from terminal.core.model_settings import (
    load_model_group_flags,
    model_group_key,
)


@dataclass
class ModelsState:
    """Всё, что окно помнит между перерисовками."""

    current: str = ""
    models: list[dict] = field(default_factory=list)
    companions: set[str] = field(default_factory=set)
    conference: set[str] = field(default_factory=set)
    groups: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "ModelsState":
        """Читает каталог и настройки один раз при открытии окна."""

        return cls(
            current=get_current_model_id(),
            models=load_models(),
            companions=set(load_companion_ids()),
            conference=set(load_conference_ids()),
            groups=load_model_group_flags(),
        )

    def find(self, model_id: str) -> dict | None:
        """Модель каталога по идентификатору."""

        return next(
            (
                model
                for model in self.models
                if model["id"] == model_id
            ),
            None,
        )

    def model_enabled(self, model: dict | None) -> bool:
        """Включена ли группа модели (флаги уже в памяти окна)."""

        if model is None:
            return False

        return self.groups.get(model_group_key(model), True)

    def model_usable(self, model: dict | None) -> bool:
        """Можно ли задействовать модель: группа и канал."""

        if model is None or not self.model_enabled(model):
            return False

        if model_group_key(model) == "core" and not (
            bool(model.get("available"))
            or str(model.get("api") or "") == "local"
        ):
            return False

        return True

    def visible(self, group: str) -> list[dict]:
        """Модели текущей закладки."""

        if group == COMPANION_GROUP:
            return [
                model
                for model in self.models
                if model["id"] in self.companions
            ]

        if group == CONFERENCE_GROUP:
            return order_models_by_reputation(
                [
                    model
                    for model in self.models
                    if model["id"] in self.conference
                ]
            )

        return [
            model
            for model in self.models
            if model["group"] == group
        ]

    def reload_models(self) -> None:
        """Перечитывает каталог после добавления или удаления модели."""

        self.models = load_models()

    def reload_lists(self) -> None:
        """Перечитывает компаньонов и сенат из настроек."""

        self.companions = set(load_companion_ids())
        self.conference = set(load_conference_ids())

    def reload_groups(self) -> None:
        """Перечитывает флаги групп и связанные с ними списки."""

        self.groups = load_model_group_flags()
        self.reload_lists()
