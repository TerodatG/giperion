# Автоматизация: расписание, параллельные задачи, плагины и поставка

## База знаний

```
python -m tools.knowledge_add docs/architecture.md
python -m tools.knowledge_add --text "Redis не используем" --title "Хранилище"
```

Документ попадает в `knowledge/`, индексируется смысловым поиском и
находится через `find_relevant`. Форматы: `.md`, `.txt`, `.rst`,
`.json`, `.yaml`, `.yml`, `.csv`; до 200 КБ.

## Расписание read-only задач

```
python -m tools.agent_schedule add "Проверь git status и найди ошибки" --every 60
python -m tools.agent_schedule list
python -m tools.agent_schedule due
python -m tools.agent_schedule run-due --limit 2
python -m tools.agent_schedule disable <id>
python -m tools.agent_schedule remove <id>
```

- Только `policy=read`: запись и команды планировщик не запускает.
- Состояние — `data/agent_schedule.json`, итоги — `agent_schedule_runs.jsonl`.
- Сам по себе не тикает: добавьте `run-due` в Планировщик Windows
  (например, каждый час) или в cron.
- Готовый скрипт:

  ```powershell
  powershell -ExecutionPolicy Bypass -File tools/install_schedule_task.ps1
  powershell -ExecutionPolicy Bypass -File tools/install_schedule_task.ps1 -EveryMinutes 30
  powershell -ExecutionPolicy Bypass -File tools/install_schedule_task.ps1 -Remove
  ```

Демон на время сеанса (проверяет расписание каждые 5 минут):

```powershell
python -m tools.agent_daemon --interval 300
python -m tools.agent_daemon --once
```

Пауза — создать `data/agent_daemon.pause` (или указать другой путь
через `--pause-file`); пока файл существует, due-задачи не
запускаются. Уведомление о цикле можно отправить в вебхук:

```powershell
$env:GIPERION_WEBHOOK_URL = "https://example.com/hook"
```

После запуска демон делает JSON POST с текстом и кодом; секреты
вырезаются. Без переменной вебхук не отправляется.

Служба Windows (нужны права администратора):

```powershell
python -m tools.agent_service --install --interval 300 --dry-run
python -m tools.agent_service --install --interval 300
python -m tools.agent_service --query
python -m tools.agent_service --remove
```

`--dry-run` печатает команду `sc.exe` без изменений в системе.

## Очередь задач

```powershell
python -m tools.agent_queue add "проверь git status" --priority 5
python -m tools.agent_queue list
python -m tools.agent_queue run --limit 2
python -m tools.agent_queue clear --all
```

Очередь лежит в `data/agent_queue.json`; берётся задача с большим
приоритетом, затем более старая. `run` выполняет read-only задачи и
пишет статус, ответ и ошибку. Это ручной/скриптовый аналог расписания
без службы Windows.

## Ночной отчёт

```powershell
python -m tools.agent_nightly --window 50 --threshold 0.5 --fail
```

Пишет `data/agent_nightly/report-*.md`: успех прогонов, ошибки,
состояние очереди и последние 10 задач. При падении ниже порога
отправляет вебхук (если задан) и с `--fail` возвращает код 2. Запуск
по расписанию — внешним планировщиком или `tools.agent_daemon`.

## Дашборд

```powershell
python -m tools.agent_dashboard
python -m tools.agent_alerts --window 20 --threshold 0.5 --fail
```

Собирает `data/agent_dashboard.html`: последний успех, число прогонов,
задачи расписания, записи аудита, график успеха и таблицу последних
20 прогонов. Открывается в браузере, ничего не отправляет наружу.

`agent_alerts` считает успех последних прогонов; при падении ниже
порога печатает предупреждение и отправляет вебхук, если задан
`GIPERION_WEBHOOK_URL` или `--webhook`. С `--fail` возвращает код 2 —
удобно для ночного CI.

## Сравнение моделей и запуск

```powershell
python -m tools.eval_compare --last 5
python -m tools.eval_ab "где считается бюджет" --a-model m1 --b-model m2
python -m tools.profile_startup
python -m tools.profile_startup --budget 2500
```

`eval_compare` берёт историю стенда и показывает средний успех, шаги,
время и стабильность по каждой модели. `eval_ab` прогоняет одну и ту же
задачу двумя моделями и печатает успех, шаги, токены и стоимость.
`profile_startup` меряет импорт ключевых модулей.
- Модель и провайдер берутся из настроек; можно передать `--model`,
  `--provider`.

## Параллельные задачи

```
python -m tools.agent_parallel "Найди, где считается бюджет" "Найди, где MCP-allowlist"
python -m tools.agent_parallel --write "Поправь опечатки в docs/a.md" --steps 8
```

- Без `--write` — чтение в основном дереве, до 4 задач, 2 воркера.
- С `--write` каждая задача получает свой `git worktree` и ветку
  `agent/parallel-*`; подтверждения автоматически одобряются, поэтому
  флаг явный.
- `--merge` сливает успешные ветки в текущую через `git merge --no-ff`;
  конфликт показывается, рабочее дерево остаётся как есть.
- `--branch-tokens N` даёт каждой пишущей ветке свой лимит токенов.
- `--merge-strategy ours|theirs` разрешает конфликт в пользу текущей или
  вливаемой ветки; по умолчанию конфликт останавливает слияние.
- Слияние веток — вручную после просмотра диффа, если `--merge` не
  указан. Автоматического разрешения конфликтов нет.

### Граф задач

```
python -m tools.agent_dag plan.json --workers 2
python -m tools.agent_dag plan.json --write --merge
```

`plan.json`:

```json
{
  "tasks": [
    {"id": "schema", "task": "Найди схему БД"},
    {"id": "api", "task": "Опиши API", "depends": ["schema"]},
    {"id": "docs", "task": "Обнови docs", "depends": ["api"], "write": true}
  ]
}
```

Задачи идут уровнями: потомок ждёт все зависимости. Если зависимость
упала, потомок помечается `ПРОПУСК` и не запускается. Цикл или
неизвестная зависимость отклоняются до старта. `write: true` отправляет
задачу в отдельный worktree; `--merge` сливает успешные ветки.

## Установка плагинов

```
python -m tools.plugin_install path/to/plugin --check
python -m tools.plugin_install path/to/plugin
python -m tools.plugin_install path/to/plugin --force
```

Проверяются имя, описание, `risk`, разрешения, наличие модуля. Плагин
копируется в `data/agent_tools/<name>`, в манифест добавляются
`installed_at` и `sha256` файлов. Это контроль целостности, **не**
подпись автора.

Подпись (HMAC-SHA256 по файлам):

```
python -m tools.plugin_sign path/to/plugin --gen-key
python -m tools.plugin_sign path/to/plugin
python -m tools.plugin_sign path/to/plugin --verify
python -m tools.plugin_install path/to/plugin
python -m tools.plugin_install path/to/plugin --allow-unsigned  # разработка
```

Ключ лежит в `data/plugin_signing.key` (вне git). Подпись обязательна по
умолчанию: неподписанный или изменённый плагин не устанавливается.
`--allow-unsigned` отключает проверку только для локальной разработки.
Это защита от подмены файлов, но не удостоверение личности автора: ключ
можно передать вместе с плагином.

Локальный каталог `data/plugin_catalog.json`:

```json
{"plugins": [{"name": "word", "path": "plugins/word", "description": "Слова"}]}
```

```powershell
python -m tools.plugin_catalog --list
python -m tools.plugin_catalog --install word
```

Путь относительно JSON-файла; установка идёт через тот же
`plugin_install` с проверкой подписи.

## Публикация ветки и PR

```
python -m tools.agent_issue 42 --provider github --repo org/repo
python -m tools.agent_issue 42 --provider gitlab --project group/repo
python -m tools.agent_pr agent/parallel-123 --title "Задача" --body "Что сделано" --dry-run
python -m tools.agent_pr agent/parallel-123 --title "Задача"
```

`agent_issue` читает issue через `gh` или GitLab REST (`GITLAB_TOKEN`) и
печатает готовый текст задачи. С `--worktree` создаёт ветку
`agent/issue-<номер>-<слаг>` и отдельную папку. С `--run` выполняет
задачу агентом, коммитит изменения, а с `--pr` создаёт PR. `agent_pr`
делает `git push -u origin <branch>` и `gh pr create`, если установлен
GitHub CLI. Без `gh` печатает команду для ручного создания PR.

## Переносимая сборка

```
python -m tools.build_portable --check
python -m tools.build_portable
python -m tools.build_portable --with-tests --output dist/giperion.zip
```

Zip без `data/`, `models/`, `.git`, worktrees и кешей; внутри
`PORTABLE.txt` с инструкцией. Данные создаются заново при первом
запуске.

## Резервная копия данных

```
python -m tools.backup_data --create
python -m tools.backup_data --create --with-secrets
python -m tools.backup_data --restore data/backups/giperion-data-....zip
```

Архив `data/` с `manifest.json`; токены и ключи по умолчанию
исключены. Восстановление не перезаписывает существующие файлы без
`--force` и отклоняет пути с `..`.

## Миграции данных

```
python -m tools.migrate_data --check
python -m tools.migrate_data --dry-run
python -m tools.migrate_data
```

Миграция хранит версию в `data/schema_version.json`, создаёт нужные
каталоги и перед изменениями делает `pre-migrate-*.zip` со всеми
данными, включая секреты.

## Ограничения

- Расписание не демон и не служба: его запускает внешний планировщик.
- Параллельная запись требует ручного слияния и доверия к модели.
- Установщик плагинов не проверяет подпись и не сканирует код; плагины
  по-прежнему включаются отдельной галочкой.
- `gh` и `git` должны быть установлены; путь к Git на Windows берётся из
  стандартного каталога.
- Переносимая сборка не включает зависимости: их ставит пользователь.
- AppContainer доступен только на Windows; на Linux/macOS плагины
  работают в режиме «процесс + сторож», браузер и агент — так же.
- Установщик плагинов не проверяет подпись автора, только манифест и
  хеши файлов.
