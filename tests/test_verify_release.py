# Giperion/tests/test_verify_release.py                                 v001
# Проверка SHA256SUMS и артефактов.

from tools import build_release, verify_release


def test_verify_ok(tmp_path) -> None:
    """Совпадающие суммы проходят проверку."""

    (tmp_path / "a.zip").write_bytes(b"zip")
    build_release.write_checksums(tmp_path)

    assert verify_release.verify(tmp_path) == []


def test_missing_sum(tmp_path) -> None:
    """Артефакт без суммы — ошибка."""

    (tmp_path / "a.zip").write_bytes(b"zip")
    (tmp_path / "SHA256SUMS").write_text("", encoding="utf-8")

    errors = verify_release.verify(tmp_path)

    assert any("нет суммы" in error for error in errors)


def test_tampered_file(tmp_path) -> None:
    """Подмена файла ловится."""

    path = tmp_path / "a.zip"
    path.write_bytes(b"zip")
    build_release.write_checksums(tmp_path)
    path.write_bytes(b"evil")

    errors = verify_release.verify(tmp_path)

    assert any("не совпала" in error for error in errors)


def test_missing_checksum_file(tmp_path) -> None:
    """Без SHA256SUMS проверка не проходит."""

    assert verify_release.verify(tmp_path) == ["нет SHA256SUMS"]
