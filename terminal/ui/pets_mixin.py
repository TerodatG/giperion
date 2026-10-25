# Giperion/terminal/ui/pets_mixin.py                                 v002
# Питомец терминала: закрепление, личность и локальный ответ.
# Последнее изменение: без упоминания внутреннего ядра в сообщениях.

from terminal.core.model_registry import get_active_model
from terminal.core.pets import get_active_pet, set_active_pet_id
from terminal.ui.pets_dialog import show_pets_dialog
from terminal.ui.theme import BOT_NAME, BOT_NICKNAME


class PetsMixin:
    """Методы окна для питомцев терминала."""

    def open_pets_dialog(self) -> None:
        """Открывает окно с карточками питомцев."""

        show_pets_dialog(
            self.window,
            on_change=self._pets_changed,
        )

    def _apply_pet_identity(self, pet: dict | None) -> None:
        """Переключает имя отвечающего на питомца или обратно."""

        self.attached_pet = pet

        if pet is not None:
            self.bot_name = pet["name"]
            self.bot_nickname = pet.get("nickname") or pet["name"]
        else:
            active = get_active_model()
            self.bot_name = active["name"] if active else BOT_NAME
            self.bot_nickname = (
                (active.get("nickname") or active["name"])
                if active
                else BOT_NICKNAME
            )

        self.update_input_placeholder()

    def _pets_changed(self) -> None:
        """Применяет новое закрепление питомца после окна."""

        previous = getattr(self, "attached_pet", None)
        pet = get_active_pet()

        self._apply_pet_identity(pet)

        if pet is None:
            if previous is not None:
                self.append_system(
                    "Питомец откреплён. В чате снова отвечает "
                    "активная модель."
                )

            return

        self._turn_off_conference()
        self.append_system(
            f"Питомец «{pet['name']}» закреплён за терминалом. "
            "Теперь он отвечает в чате."
        )

        if previous is None or previous.get("id") != pet["id"]:
            self.append_bot(
                pet["greeting"],
                name=pet.get("nickname") or pet["name"],
                role="bot",
                with_copy=False,
            )

    def detach_pet(self, announce: bool = True) -> None:
        """Открепляет питомца и возвращает активную модель."""

        if not getattr(self, "attached_pet", None):
            return

        set_active_pet_id("")
        self._apply_pet_identity(None)

        if announce:
            self.append_system(
                "Питомец откреплён. В чате снова отвечает "
                "активная модель."
            )
