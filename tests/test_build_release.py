# Giperion/tests/test_build_release.py                                  v001
# Сборка релиза: имена артефактов и dry-run.

from tools import build_release


def test_target_platform_explicit() -> None:
    """Явная платформа не зависит от текущей ОС."""

    assert build_release.target_platform("linux") == "linux"
    assert build_release.target_platform("windows") == "windows"
    assert build_release.target_platform("macos") == "macos"


def test_artifact_names(monkeypatch) -> None:
    """Имена содержат версию, платформу и расширение."""

    monkeypatch.setattr(
        build_release.platform,
        "machine",
        lambda: "AMD64",
    )

    assert build_release.artifact_name(
        "windows", "1.2.3", "setup"
    ) == "Giperion-1.2.3-windows-x64.setup.exe"
    assert build_release.artifact_name(
        "linux", "1.2.3", "appimage"
    ) == "Giperion-1.2.3-linux-x64.AppImage"
    assert build_release.artifact_name(
        "macos", "1.2.3", "dmg"
    ) == "Giperion-1.2.3-macos-x64.dmg"


def test_pyinstaller_command(tmp_path) -> None:
    """Команда PyInstaller использует спек и пути."""

    command = build_release.pyinstaller_command(
        tmp_path,
        tmp_path / "dist",
        tmp_path / "work",
    )

    assert "PyInstaller" in command
    assert any("giperion.spec" in item for item in command)
    assert str(tmp_path / "dist") in command


def test_zip_dry_run_creates_nothing(tmp_path) -> None:
    """dry-run не создаёт архив."""

    source = tmp_path / "app"
    source.mkdir()
    target = tmp_path / "app.zip"

    build_release._zip_folder(source, target, dry_run=True)

    assert not target.exists()


def test_zip_includes_install_scripts(tmp_path) -> None:
    """В Windows-zip рядом с приложением лежат install/uninstall."""

    import zipfile

    source = tmp_path / "Giperion"
    source.mkdir()
    (source / "Giperion.exe").write_bytes(b"exe")
    install = tmp_path / "install.ps1"
    install.write_text("# install", encoding="utf-8")
    target = tmp_path / "Giperion.zip"

    build_release._zip_folder(
        source,
        target,
        dry_run=False,
        extras=(install,),
    )

    with zipfile.ZipFile(target) as archive:
        names = archive.namelist()

    assert "Giperion/Giperion.exe" in names
    assert "install.ps1" in names


def test_checksums_include_only_artifacts(tmp_path) -> None:
    """SHA256SUMS содержит архивы и установщики, но не текст."""

    (tmp_path / "a.zip").write_bytes(b"zip")
    (tmp_path / "b.txt").write_text("text", encoding="utf-8")

    path = build_release.write_checksums(tmp_path)
    lines = path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 1
    assert "a.zip" in lines[0]
    assert "b.txt" not in path.read_text(encoding="utf-8")
