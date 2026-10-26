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
- Слияние веток — вручную после просмотра диффа. Автоматического merge
  нет.

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

## Публикация ветки и PR

```
python -m tools.agent_pr agent/parallel-123 --title "Задача" --body "Что сделано" --dry-run
python -m tools.agent_pr agent/parallel-123 --title "Задача"
```

Делает `git push -u origin <branch>` и `gh pr create`, если установлен
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

## Ограничения

- Расписание не демон и не служба: его запускает внешний планировщик.
- Параллельная запись требует ручного слияния и доверия к модели.
- Установщик плагинов не проверяет подпись и не сканирует код; плагины
  по-прежнему включаются отдельной галочкой.
- `gh` и `git` должны быть установлены; путь к Git на Windows берётся из
  стандартного каталога.
- Переносимая сборка не включает зависимости: их ставит пользователь.
