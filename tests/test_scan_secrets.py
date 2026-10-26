# Giperion/tests/test_scan_secrets.py                                  v001
# Сканер секретов перед коммитом.

from tools import scan_secrets


def test_scanner_finds_fake_key(tmp_path) -> None:
    """Ключ с узнаваемым префиксом считается секретом."""

    target = tmp_path / "config.py"
    target.write_text(
        'api_key = "sk-1234567890abcdef"\n',
        encoding="utf-8",
    )

    problems = scan_secrets.scan([str(target)], include_tests=True)

    assert problems
    assert problems[0]["hidden"] >= 1


def test_scanner_ignores_clean_file(tmp_path) -> None:
    """Обычный код не считается секретом."""

    target = tmp_path / "clean.py"
    target.write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )

    assert scan_secrets.scan([str(target)], include_tests=True) == []


def test_scanner_skips_redact_module() -> None:
    """Файл с шаблонами секретов не поднимает ложную тревогу."""

    problems = scan_secrets.scan(
        ["terminal/core/agent/redact.py"],
        include_tests=True,
    )

    assert problems == []
