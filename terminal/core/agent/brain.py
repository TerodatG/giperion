# Giperion/terminal/core/agent/brain.py                              v001
# Мозг агента: внешняя модель через локальный сервис OpenCode.
# Последнее изменение: первый вариант — один запрос на шаг.

from terminal.core.opencode_client import ask_model


class ModelBrain:
    """Отдаёт промпт выбранной модели и возвращает её JSON-ответ."""

    def __init__(
        self,
        model_id: str,
        provider_id: str,
        timeout: int = 120,
    ) -> None:
        self.model_id = model_id
        self.provider_id = provider_id
        self.timeout = timeout

    def decide(self, prompt: str) -> str:
        """Спрашивает модель; ошибки пробрасываются в цикл агента."""

        answer, _usage = ask_model(
            self.model_id,
            prompt,
            provider_id=self.provider_id,
            title="Агент · шаг",
            timeout=self.timeout,
        )

        return answer
