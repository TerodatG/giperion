# Установка и перенос

## Windows

1. Python 3.13 и зависимости:
   ```powershell
   python -m pip install -r requirements.txt
   ```
2. Запуск:
   ```powershell
   python main.py
   ```
3. Провайдер: «Провайдер…» → адрес, ключ, модель. Для LM Studio —
   `http://127.0.0.1:1234/v1`, любой непустой ключ.
4. Браузер с JavaScript (по желанию):
   ```powershell
   python -m pip install ".[browser]"
   python -m playwright install chromium
   ```

AppContainer для плагинов (только Windows):
```powershell
python -m tools.setup_plugin_container --prepare
python -m tools.setup_plugin_container --check
python -m tools.setup_plugin_container --remove
```

## Linux / macOS

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

- AppContainer недоступен: плагины работают в режиме «процесс + сторож»
  (отдельный процесс, лимиты, разрешения), сеть/запись — по манифесту.
- Браузер и агент работают так же; Chromium ставится через Playwright.
- Пути в `data/` и `tools/agent_pr.py` к Git на Windows не привязаны:
  если `C:\Program Files\Git\cmd\git.exe` нет, берётся `git` из PATH.
- LM Studio доступна для Linux/macOS; адрес тот же.

## Переносимая сборка

```powershell
python -m tools.build_portable
python -m tools.build_portable --with-tests
```

Zip содержит код, документацию, скины и `knowledge/`, но не `data/`,
`models/`, `.git` и кеши. Данные создаются заново; перенести их можно
вручную, скопировав нужные файлы из `data/`.

## Обновление

Автообновления нет: замените файлы проекта (или распакуйте новый zip),
сохранив `data/`, `models/` и `skins/`. Перед обновлением полезно
сделать `python -m tools.clean_caches --yes` и резервную копию `data/`.

## Ограничения

- AppContainer и часть системных метрик — только Windows.
- Установщика (exe/msi) пока нет: запуск из папки проекта.
- Модели и Chromium не входят в архив: их ставит пользователь.
