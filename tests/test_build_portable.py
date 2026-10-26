# Giperion/tests/test_build_portable.py                                v001
# Переносимая сборка: состав архива и исключения.

import zipfile

from tools import build_portable


def _tree(tmp_path):
    root = tmp_path / "root"
    (root / "terminal").mkdir(parents=True)
    (root / "terminal" / "app.py").write_text("print('ok')", encoding="utf-8")
    (root / "config.py").write_text("X = 1", encoding="utf-8")
    (root / "data").mkdir()
    (root / "data" / "secret.json").write_text("{}", encoding="utf-8")
    (root / "models").mkdir()
    (root / "models" / "m.bin").write_bytes(b"x")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("git", encoding="utf-8")
    (root / "terminal" / "__pycache__").mkdir()
    (root / "terminal" / "__pycache__" / "a.pyc").write_bytes(b"x")

    return root


def test_iter_files_skips_service_dirs(tmp_path) -> None:
    """data, models, .git и __pycache__ не попадают в архив."""

    root = _tree(tmp_path)
    names = {
        path.relative_to(root).as_posix()
        for path in build_portable.iter_files(root)
    }

    assert "config.py" in names
    assert "terminal/app.py" in names
    assert not any(name.startswith("data/") for name in names)
    assert not any(name.startswith("models/") for name in names)
    assert not any(name.startswith(".git/") for name in names)
    assert not any("__pycache__" in name for name in names)


def test_build_writes_zip(tmp_path) -> None:
    """Архив содержит файлы и PORTABLE.txt."""

    root = _tree(tmp_path)
    target = build_portable.build(
        tmp_path / "out.zip",
        root=root,
    )

    with zipfile.ZipFile(target) as archive:
        names = set(archive.namelist())

    assert "config.py" in names
    assert "terminal/app.py" in names
    assert "PORTABLE.txt" in names


def test_tests_are_optional(tmp_path) -> None:
    """tests/ добавляется только с флагом."""

    root = _tree(tmp_path)
    (root / "tests").mkdir()
    (root / "tests" / "test_x.py").write_text("", encoding="utf-8")

    without = {
        path.name for path in build_portable.iter_files(root)
    }
    with_tests = {
        path.name
        for path in build_portable.iter_files(root, include_tests=True)
    }

    assert "test_x.py" not in without
    assert "test_x.py" in with_tests
