# Giperion/tests/test_update_apply.py                                 v001
# Установка патча: распаковка, резервная копия и защита от плохих путей.

import zipfile

import pytest

from terminal.core import app_version, update_service


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """Подменяет корень проекта, папку патчей и файл состояния."""

    root = tmp_path / "app"
    root.mkdir()

    updates = tmp_path / "updates"
    updates.mkdir()

    monkeypatch.setattr(update_service, "PROJECT_ROOT", root)
    monkeypatch.setattr(update_service, "UPDATES_DIR", updates)
    monkeypatch.setattr(
        app_version,
        "STATE_FILE",
        tmp_path / "state.json",
    )

    return root, updates


def _patch(path, members: dict[str, bytes]) -> None:
    """Собирает zip-патч из словаря имя → содержимое."""

    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


def _release(patch_path, version="1.1.0", sha256="") -> update_service.Release:
    """Выпуск, указывающий на локальный патч."""

    return update_service.Release(
        version=version,
        date="2026-10-30",
        title="Тест",
        patch=str(patch_path),
        sha256=sha256,
    )


def test_apply_unpacks_files(sandbox) -> None:
    """Патч распаковывается поверх проекта и запоминает версию."""

    root, _ = sandbox
    patch = root.parent / "patch.zip"

    _patch(patch, {"pkg/module.py": b"new", "data/intents.json": b"{}"})

    result = update_service.apply_update(patch, _release(patch))

    assert (root / "pkg" / "module.py").read_bytes() == b"new"
    assert result.version == "1.1.0"
    assert app_version.current_version() == "1.1.0"


def test_apply_backs_up_replaced_files(sandbox) -> None:
    """Старый файл сохраняется в updates/backup."""

    root, _ = sandbox
    (root / "pkg").mkdir()
    (root / "pkg" / "module.py").write_bytes(b"old")

    patch = root.parent / "patch.zip"
    _patch(patch, {"pkg/module.py": b"new"})

    result = update_service.apply_update(patch, _release(patch))

    assert (root / "pkg" / "module.py").read_bytes() == b"new"
    assert result.backup_dir is not None
    backup = result.backup_dir / "pkg" / "module.py"
    assert backup.read_bytes() == b"old"


def test_apply_rejects_parent_traversal(sandbox) -> None:
    """Путь с .. не даёт выйти за папку проекта."""

    root, _ = sandbox
    patch = root.parent / "patch.zip"

    _patch(patch, {"../evil.py": b"x"})

    with pytest.raises(update_service.UpdateError):
        update_service.apply_update(patch, _release(patch))


def test_apply_rejects_bad_checksum(sandbox) -> None:
    """Несовпавшая сумма останавливает установку."""

    root, _ = sandbox
    patch = root.parent / "patch.zip"

    _patch(patch, {"pkg/module.py": b"new"})

    with pytest.raises(update_service.UpdateError):
        update_service.apply_update(
            patch,
            _release(patch, sha256="0" * 64),
        )


def test_skip_remembers_version(sandbox) -> None:
    """Пропущенная версия сохраняется в состоянии."""

    app_version.set_skipped("1.2.0")

    assert app_version.skipped_version() == "1.2.0"
