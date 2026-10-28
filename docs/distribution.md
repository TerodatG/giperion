# Поставка и установщики

Один вход для сборки:

```powershell
python -m tools.build_release --version 1.0.0
python -m tools.build_release --dry-run
python -m tools.build_release --target linux
python -m tools.build_release --skip-build --skip-installer
```

`--target` — `auto`, `windows`, `linux` или `macos`. PyInstaller собирает
GUI `Giperion` из `packaging/giperion.spec`; затем платформенный
упаковщик делает установщик. В конце пишется `SHA256SUMS` для архивов и
установщиков.

Проверка перед публикацией:

```powershell
python -m tools.verify_release --folder dist
```

## Windows

- one-dir `dist/Giperion/`;
- zip `Giperion-<версия>-windows-x64.zip` с `install.ps1` и
  `uninstall.ps1` — установка без администратора в `%LOCALAPPDATA%`;
- `.exe` через Inno Setup (`iscc`), если он установлен:
  `packaging/windows/giperion.iss`.

В сборку входят `skins/`, `knowledge/`, `docs/`, `assets/`,
`main_window.ui`, веса `models/` и стартовый `data/intents.json`.
Без `models/` окно открывается, но ассистент не отвечает.

`.exe` по умолчанию ставит в профиль пользователя
(`%LOCALAPPDATA%\Programs\Giperion`) и не требует администратора — это
рабочий вариант: приложение пишет данные рядом с собой. Для всех
пользователей: `/ALLUSERS` (нужен администратор, установщик выдаёт
права на запись в `_internal\data|logs|archive|models`). Тихая установка:

```powershell
Giperion-1.0.0-windows-x64-setup.exe /VERYSILENT `
    /SUPPRESSMSGBOXES /NORESTART /LOG=%TEMP%\giperion-install.log
```

## Проверка на чистой Windows (VirtualBox)

`tools/test_installer_vm.ps1` создаёт VM (UEFI + TPM 2.0), ставит Windows
автоматически, копирует установщик, ставит его без администратора,
проверяет файлы, ярлык, запуск приложения и удаление:

```powershell
powershell -ExecutionPolicy Bypass -File tools\test_installer_vm.ps1 `
    -Iso D:\vm\Win11LTSC.iso `
    -Installer dist\Giperion-1.0.0-windows-x64-setup.exe
```

Нужен ISO Windows 11 x64. Официальный образ без регистрации —
Windows 11 Enterprise LTSC 2024 Evaluation (Microsoft Evaluation Center,
статическая ссылка). Проверка занимает 20–40 минут.

Установка: `python -m pip install pyinstaller`, Inno Setup 6.
CI ставит Inno через Chocolatey.

## Linux

- tar.gz `Giperion-<версия>-linux-x64.tar.gz`;
- `.deb` через `packaging/linux/build_deb.sh` (`dpkg-deb`);
- AppImage через `packaging/linux/build_appimage.sh` (`appimagetool`).

`.deb` кладёт приложение в `/usr/lib/giperion`, а в `/usr/bin/giperion`
— обёртку и `.desktop`-файл. AppImage использует `AppRun`.

Обе обёртки задают `GIPERION_DATA_DIR`, `GIPERION_LOGS_DIR` и
`GIPERION_ARCHIVE_DIR` в `~/.local/share/giperion`: сам пакет только для
чтения. `GIPERION_HOME` не переопределяется — от него зависит поиск
`assets/` и `skins/`.

`.deb` объявляет `Depends` на библиотеки Qt (libgl1, libegl1,
libxkbcommon-x11-0, libxcb-*): без них плагин `xcb` не загружается.

Проверено на чистой Ubuntu 24.04: `apt install ./Giperion-1.0.0-linux-x64.deb`,
запуск, ответ ассистента, `apt purge` без остатков в `/usr`.

## macOS

- zip `Giperion-<версия>-macos-<arch>.zip`;
- `.dmg` через `packaging/macos/build_dmg.sh` (`hdiutil`).

Сборку `.app`/`.dmg` запускать на macOS: PyInstaller не кросс-компилирует.

## CI

`.github/workflows/release.yml` собирает артефакты на Windows, Ubuntu и
macOS по тегу `v*` или вручную. Артефакты складываются в `dist/` и
загружаются как `giperion-<платформа>`; по тегу дополнительно
публикуется GitHub Release с этими файлами.

### Как выпустить релиз

```powershell
git tag v1.0.0
git push origin v1.0.0
```

Workflow сам подставит версию из тега, соберёт три ОС, проверит
`SHA256SUMS` и приложит файлы к релизу. Вручную (без тега) — кнопка
«Run workflow»: версия будет `1.0.0`, релиз не создаётся.

Важно: `models/seq2seq.pt` должен быть в репозитории — без него сборка
запускается, но ассистент не отвечает. AppImage в CI собирается через
`APPIMAGE_EXTRACT_AND_RUN=1`, потому что на раннере нет FUSE.

Модель живёт в отдельном репозитории `TerodatG/kraper` (пакет
`kraper_model`). CI чекаутит оба проекта рядом (`app/giperion` и
`app/Kraper`) и ставит пакет через `pip install -e ../Kraper`.

## Автообновление

Кнопка «Обновление» в плите «Система» проверяет каталог выпусков:

```
https://github.com/TerodatG/giperion/releases/latest/download/releases-<платформа>.json
```

Платформа — `windows`, `linux` или `macos`. Адрес можно переопределить
переменной `GIPERION_UPDATE_FEED` (удобно для проверки на локальном
файле). Если канал недоступен, окно читает локальный `data/releases.json`.

Патч — zip с содержимым `_internal` (код и данные приложения).
`tools/update_feed.py pack` собирает его из `dist/Giperion`, а
`tools/update_feed.py feeds` пишет каталоги для всех `patch-<платформа>.zip`.
CI делает это в джобе `publish` и прикладывает файлы к релизу; сумма
`sha256` проверяется при скачивании, старые файлы уходят в
`updates/backup/`.

macOS-патч не собирается: внутри `.app` другая раскладка, обновление
там пока только проверяется.

Проверка канала из консоли:

```powershell
python -m tools.update_feed check
python -m tools.update_feed check --feed dist/releases-windows.json
```

При запуске приложение через 5 секунд само проверяет канал и пишет в
журнал, если есть новая версия. Отключается переменной
`GIPERION_NO_UPDATE_CHECK=1`. Кнопка «Пропустить» в окне обновления
запоминает версию в `data/update_state.json` и больше её не предлагает.
Перед скачиванием проверяется свободное место (нужно вдвое больше
размера патча), а в статусе показывается прогресс.

## Ограничения

- PyInstaller-сборка с torch и PySide6 большая (сотни МБ); это ожидаемо.
  В CI ставится CPU-сборка torch, чтобы артефакт не тянул CUDA.
- Кросс-компиляции нет: каждая ОС собирает свой артефакт.
- Windows-установщик требует Inno Setup; Linux `.deb` — `dpkg-deb`;
  AppImage — `appimagetool`; macOS — `hdiutil`.
- Подпись кода и нотаризация macOS пока не настроены.
