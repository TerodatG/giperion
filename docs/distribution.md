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

`.exe` по умолчанию ставит для всех пользователей (нужен администратор).
Без прав администратора: `/CURRENTUSER` — установка в
`%LOCALAPPDATA%\Programs\Giperion`. Тихая установка:

```powershell
Giperion-1.0.0-windows-x64-setup.exe /CURRENTUSER /VERYSILENT `
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
— обёртку и `.desktop`-файл.

## macOS

- zip `Giperion-<версия>-macos-<arch>.zip`;
- `.dmg` через `packaging/macos/build_dmg.sh` (`hdiutil`).

Сборку `.app`/`.dmg` запускать на macOS: PyInstaller не кросс-компилирует.

## CI

`.github/workflows/release.yml` собирает артефакты на Windows, Ubuntu и
macOS по тегу `v*` или вручную. Артефакты складываются в `dist/` и
загружаются как `giperion-<платформа>`; по тегу дополнительно
публикуется GitHub Release с этими файлами.

## Ограничения

- PyInstaller-сборка с torch и PySide6 большая (сотни МБ); это ожидаемо.
  В CI ставится CPU-сборка torch, чтобы артефакт не тянул CUDA.
- Кросс-компиляции нет: каждая ОС собирает свой артефакт.
- Windows-установщик требует Inno Setup; Linux `.deb` — `dpkg-deb`;
  AppImage — `appimagetool`; macOS — `hdiutil`.
- Подпись кода и нотаризация macOS пока не настроены.
