# Giperion Terminal для VS Code

Минимальное расширение: запускает read-only задачу через локальный API
терминала и показывает ответ и трейс в канале «Giperion».

## Запуск

1. В терминале:

   ```powershell
   python -m tools.agent_api
   python -m tools.agent_api --print-token
   ```

2. В VS Code открыть папку `integrations/vscode` и нажать `F5`
   (Extension Development Host).
3. В настройках указать `giperion.apiUrl` (по умолчанию
   `http://127.0.0.1:8765`) и `giperion.token`.
4. Команда **«Giperion: запустить задачу»** из палитры команд.

Расширение ничего не пишет в проект: API разрешает только `policy=read`.
Для правок используйте обычное окно терминала.
