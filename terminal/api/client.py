# Giperion/terminal/api/client.py                                      v001
# Python-SDK: тонкая обёртка над HTTP-API терминала.

import json
import os
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8777"
TOKEN_ENV = "GIPERION_API_TOKEN"
URL_ENV = "GIPERION_API_URL"


class ClientError(RuntimeError):
    """Ошибка обмена с API."""


class Client:
    """Клиент API: health, version, tools, runs и run."""

    def __init__(
        self,
        base_url: str = "",
        token: str = "",
        timeout: float = 600.0,
    ) -> None:
        self.base_url = (
            base_url
            or os.environ.get(URL_ENV, "").strip()
            or DEFAULT_URL
        ).rstrip("/")
        self.token = token or os.environ.get(TOKEN_ENV, "").strip()
        self.timeout = timeout

    # --- Чтение ---

    def health(self) -> dict:
        """Проверка живости (токен не нужен)."""

        return self._request("GET", "/health", auth=False)

    def version(self) -> dict:
        """Версия и число инструментов."""

        return self._request("GET", "/version")

    def tools(self) -> list[str]:
        """Список инструментов агента."""

        return list(self._request("GET", "/tools").get("tools") or [])

    def runs(self, limit: int = 20) -> list[dict]:
        """Последние прогоны."""

        payload = self._request("GET", f"/runs?limit={int(limit)}")

        return list(payload.get("runs") or [])

    # --- Запуск ---

    def run(
        self,
        task: str,
        project: str = ".",
        steps: int = 12,
        policy: str = "read",
    ) -> dict:
        """Выполняет задачу и возвращает итог с трейсом."""

        return self._request(
            "POST",
            "/run",
            {
                "task": task,
                "project": project,
                "steps": steps,
                "policy": policy,
            },
        )

    # --- Транспорт ---

    def _request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        auth: bool = True,
    ) -> dict:
        """Делает запрос и разбирает ответ."""

        data = None
        headers = {"Accept": "application/json"}

        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"

        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers=headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")

            try:
                message = json.loads(body).get("error") or body
            except (ValueError, AttributeError):
                message = body

            raise ClientError(
                f"{error.code}: {message}"
            ) from error
        except urllib.error.URLError as error:
            raise ClientError(f"API недоступен: {error}") from error
