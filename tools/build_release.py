# Giperion/tools/build_release.py                                     v001
# Сборка установщиков: PyInstaller + Windows/Linux/macOS пакеты.
# Последнее изменение: первый вариант — dry-run и нативные упаковщики.

import argparse
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

from config import BASE_DIR
from terminal.core.app_version import current_version

SPEC = "packaging/giperion.spec"
APP_NAME = "Giperion"


def target_platform(value: str = "auto") -> str:
    """windows, linux или macos."""

    if value != "auto":
        return value

    if sys.platform == "win32":
        return "windows"

    if sys.platform == "darwin":
        return "macos"

    return "linux"


def artifact_name(platform_name: str, version: str, kind: str) -> str:
    """Имя артефакта с версией и платформой."""

    arch = "arm64" if platform.machine().lower() in (
        "arm64",
        "aarch64",
    ) else "x64"
    suffix = {
        "zip": "zip",
        "setup": "setup.exe",
        "deb": "deb",
        "appimage": "AppImage",
        "dmg": "dmg",
        "tar": "tar.gz",
    }.get(kind, kind)

    return f"{APP_NAME}-{version}-{platform_name}-{arch}.{suffix}"


def pyinstaller_command(
    root: Path,
    dist: Path,
    work: Path,
) -> list[str]:
    """Команда one-dir сборки GUI."""

    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(dist),
        "--workpath",
        str(work),
        str(root / SPEC),
    ]


def _run(command: list[str], cwd: Path, dry_run: bool) -> int:
    print("+", " ".join(command))

    if dry_run:
        return 0

    try:
        return int(
            subprocess.run(
                command,
                cwd=str(cwd),
                check=False,
            ).returncode
        )
    except OSError as error:
        print("Ошибка:", error)

        return 1


def build_pyinstaller(
    root: Path,
    dist: Path,
    work: Path,
    dry_run: bool = False,
) -> int:
    """Запускает PyInstaller."""

    return _run(
        pyinstaller_command(root, dist, work),
        root,
        dry_run,
    )


def _zip_folder(source: Path, target: Path, dry_run: bool) -> None:
    print("+ zip", source, "->", target)

    if dry_run:
        return

    with zipfile.ZipFile(
        target,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for path in source.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source.parent))


def package_windows(
    root: Path,
    dist: Path,
    version: str,
    dry_run: bool = False,
) -> None:
    """Zip + Inno Setup, если iscc найден."""

    app = dist / APP_NAME

    if app.is_dir():
        _zip_folder(
            app,
            dist / artifact_name("windows", version, "zip"),
            dry_run,
        )

    iscc = shutil.which("iscc") or shutil.which("ISCC.exe")

    if not iscc:
        print("Inno Setup (iscc) не найден: .exe не собран.")

        return

    _run(
        [
            iscc,
            f"/DAppVersion={version}",
            f"/DSourceDir={app}",
            f"/DOutputDir={dist}",
            str(root / "packaging/windows/giperion.iss"),
        ],
        root,
        dry_run,
    )


def package_linux(
    root: Path,
    dist: Path,
    version: str,
    dry_run: bool = False,
) -> None:
    """Tar.gz, .deb и AppImage, если есть инструменты."""

    app = dist / APP_NAME
    target = dist / artifact_name("linux", version, "tar")
    print("+ tar", app, "->", target)

    if not dry_run and app.is_dir():
        with tarfile.open(target, "w:gz") as archive:
            archive.add(app, arcname=APP_NAME)

    if shutil.which("dpkg-deb"):
        _run(
            [
                "bash",
                str(root / "packaging/linux/build_deb.sh"),
                version,
                str(app),
                str(dist),
            ],
            root,
            dry_run,
        )
    else:
        print("dpkg-deb не найден: .deb не собран.")

    if shutil.which("appimagetool"):
        _run(
            [
                "bash",
                str(root / "packaging/linux/build_appimage.sh"),
                version,
                str(app),
                str(dist),
            ],
            root,
            dry_run,
        )
    else:
        print("appimagetool не найден: AppImage не собран.")


def package_macos(
    root: Path,
    dist: Path,
    version: str,
    dry_run: bool = False,
) -> None:
    """Zip и .dmg из .app."""

    app = dist / f"{APP_NAME}.app"

    if app.is_dir() or dry_run:
        _run(
            [
                "bash",
                str(root / "packaging/macos/build_dmg.sh"),
                version,
                str(app),
                str(dist),
            ],
            root,
            dry_run,
        )
    else:
        print("Нет .app: PyInstaller не собрал GUI.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Собрать установщики Giperion для текущей ОС.",
    )
    parser.add_argument("--target", default="auto")
    parser.add_argument("--version", default="")
    parser.add_argument("--output", default="dist")
    parser.add_argument("--work", default="build/pyinstaller")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--skip-installer", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    platform_name = target_platform(args.target)
    version = args.version.strip() or current_version()
    root = BASE_DIR
    dist = Path(args.output)

    if not dist.is_absolute():
        dist = root / dist

    work = Path(args.work)

    if not work.is_absolute():
        work = root / work

    dist.mkdir(parents=True, exist_ok=True)

    if not args.skip_build:
        code = build_pyinstaller(root, dist, work, args.dry_run)

        if code != 0:
            return code

    if not args.skip_installer:
        if platform_name == "windows":
            package_windows(root, dist, version, args.dry_run)
        elif platform_name == "macos":
            package_macos(root, dist, version, args.dry_run)
        else:
            package_linux(root, dist, version, args.dry_run)

    print("Версия:", version, "· платформа:", platform_name)
    print("Артефакты:", dist)

    return 0


if __name__ == "__main__":
    sys.exit(main())
