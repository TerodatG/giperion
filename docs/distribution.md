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
упаковщик делает установщик.

## Windows

- one-dir `dist/Giperion/`;
- zip `Giperion-<версия>-windows-x64.zip`;
- `.exe` через Inno Setup (`iscc`), если он установлен:
  `packaging/windows/giperion.iss`.

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
загружаются как `giperion-<платформа>`.

## Ограничения

- PyInstaller-сборка с torch и PySide6 большая (сотни МБ); это ожидаемо.
- Кросс-компиляции нет: каждая ОС собирает свой артефакт.
- Windows-установщик требует Inno Setup; Linux `.deb` — `dpkg-deb`;
  AppImage — `appimagetool`; macOS — `hdiutil`.
- Подпись кода и нотаризация macOS пока не настроены.
