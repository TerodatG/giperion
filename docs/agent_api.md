# Локальный API терминала

`python -m tools.agent_api` запускает HTTP-сервер только на `127.0.0.1`
и даёт внешним инструментам запускать **read-only** задачи агента.

## Запуск

```powershell
python -m tools.agent_api                 # 127.0.0.1:8765
python -m tools.agent_api --port 9000
python -m tools.agent_api --print-token   # показать токен и выйти
```

Токен берётся из `GIPERION_API_TOKEN`, иначе из `data/agent_api_token`
(файл создаётся при первом обращении). Сервер слушает только localhost:
наружу порт не выставляется.

## Эндпоинты

`GET /health` — без токена:

```json
{"ok": true, "service": "giperion-terminal"}
```

`POST /task` — требует `Authorization: Bearer <токен>`:

```powershell
$token = python -m tools.agent_api --print-token
$body = '{"task": "найди, где описан аудит", "max_steps": 5}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/task `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType application/json -Body $body
```

Поля запроса:

| поле | по умолчанию | смысл |
| --- | --- | --- |
| `task` | — | текст задачи, обязателен |
| `policy` | `read` | разрешена только `read` |
| `max_steps` | 5 | 1–40 шагов |

Ответ:

```json
{
  "ok": true,
  "model": "provider/model",
  "answer": "…",
  "error": "",
  "cancelled": false,
  "steps": 4
}
```

Тело ограничено 1 МБ, JSON проверяется до запуска. Запись, команды и
подтверждения через API недоступны: для них нужен обычный интерфейс
терминала. Ошибки аутентификации — `401`, кривое тело — `400`/`413`.

## Интеграция

Любой клиент с HTTP и JSON подходит: скрипт CI, редактор, бот. Задача
выполняется тем же агентом и моделью, что и в приложении, поэтому
результат совпадает с ручным запуском. Для длинных задач поднимайте
`max_steps` и таймаут клиента; сервер обрабатывает запросы в отдельных
потоках, но модель может быть занята — запускайте последовательно.
