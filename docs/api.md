# HTTP-API терминала

Запуск задач агента из других программ: скриптов, CI, редакторов.

## Сервер

```powershell
python -m terminal.api.cli serve --port 8777
```

Сервер слушает `127.0.0.1` и печатает токен. Токен хранится в
`data/api_token.txt` (права 600) или задаётся переменной
`GIPERION_API_TOKEN`.

| Переменная | Смысл |
|---|---|
| `GIPERION_API_HOST` | адрес (по умолчанию `127.0.0.1`) |
| `GIPERION_API_PORT` | порт (по умолчанию `8777`) |
| `GIPERION_API_TOKEN` | токен доступа |
| `GIPERION_API_ROOTS` | разрешённые каталоги через `;` |

## Эндпоинты

| Метод | Путь | Что делает |
|---|---|---|
| GET | `/health` | живость, без токена |
| GET | `/version` | версия и число инструментов |
| GET | `/tools` | список инструментов |
| GET | `/runs?limit=20` | последние прогоны |
| POST | `/run` | выполнить задачу |

`POST /run`:

```json
{
  "task": "найди, где настраивается провайдер",
  "project": "D:/Projects/Giperion",
  "steps": 12,
  "policy": "read"
}
```

`policy`: `read` (по умолчанию, только чтение), `confirm` (спрашивать
некого — фактически read), `trust` (разрешить запись и команды).

Ответ: `ok`, `answer`, `steps` (трейс), `usage`, `cost`, `error`,
`project`, `version`.

### Фоновый запуск и отмена

```json
{"task": "...", "project": ".", "wait": false}
```

Ответ `202` с `id`. Дальше:

```
GET  /run/{id}          — статус и результат
POST /run/{id}/cancel   — попросить остановиться
```

Статусы: `queued`, `running`, `cancelling`, `done`, `failed`,
`cancelled`.

### Журнал и лимиты

Каждый запрос пишется в `data/api_calls.jsonl` (время, путь, код,
миллисекунды). Лимит частоты — 60 запросов в минуту на токен, сверх
него `429`.


## SDK

```python
from terminal.api import Client

client = Client("http://127.0.0.1:8777", token="...")
result = client.run("что в папке?", project=".")
print(result["answer"])
```

## CLI

```powershell
python -m terminal.api.cli version
python -m terminal.api.cli tools
python -m terminal.api.cli run "что в папке?" --project .
```

## Ограничения

- Сервер работает из исходников (`python -m ...`); в собранный `.exe`
  он пока не входит.
- Задача выполняется синхронно: запрос ждёт ответа, таймаут клиента
  по умолчанию 600 секунд.
- Одновременные запросы обслуживаются потоками; провайдер должен
  выдерживать параллельные вызовы.
