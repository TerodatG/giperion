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
| `project` | рабочая папка | подкаталог проекта внутри неё |

`project` не может выйти за рабочую папку приложения: абсолютный или
относительный путь разрешается и проверяется, иначе ответ `ok=false`.
Так один API не открывает доступ ко всему диску.

Ответ:

```json
{
  "ok": true,
  "model": "provider/model",
  "project": "Giperion",
  "answer": "…",
  "error": "",
  "cancelled": false,
  "steps": 4,
  "trace": [
    {"index": 0, "kind": "tool", "title": "read_file", "detail": "…"}
  ]
}
```

Тело ограничено 1 МБ, JSON проверяется до запуска. Запись, команды и
подтверждения через API недоступны: для них нужен обычный интерфейс
терминала. Ошибки аутентификации — `401`, кривое тело — `400`/`413`,
превышение частоты — `429`.

## Журнал и лимиты

Каждый вызов пишется в `data/agent_api_calls.jsonl`: время, клиент,
проект, задача (с вырезанными секретами), успех, число шагов и время
ответа. Токен туда не попадает. Частота — не больше 30 запросов в
минуту с одного адреса; окно скользящее.

Сервер обрабатывает запросы в отдельных потоках, но модель может быть
занята — запускайте последовательно. Для длинных задач поднимайте
`max_steps` и таймаут клиента.
