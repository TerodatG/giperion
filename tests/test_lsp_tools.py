# Giperion/tests/test_lsp_tools.py                                     v001
# Инструменты LSP: диагностика, определения и ссылки на заглушке сервера.

import sys
from pathlib import Path

import pytest

from terminal.core.agent import lsp_tools

FIXTURE = Path(__file__).parent / "fixtures" / "fake_lsp.py"


@pytest.fixture()
def project(tmp_path, monkeypatch):
    """Проект с одним файлом и заглушкой LSP вместо настоящего сервера."""

    root = tmp_path / "project"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")

    command = [sys.executable, str(FIXTURE)]
    monkeypatch.setattr(lsp_tools, "server_command", lambda: command)

    lsp_tools.reset_cache()

    yield root

    lsp_tools.reset_cache()


def test_diagnostics_reports_problems(project) -> None:
    """Диагностика приходит с severity, кодом и позицией."""

    result = lsp_tools.diagnostics(project, "a.py")

    assert result.ok is True
    assert "Проблем: 2" in result.text
    assert "a.py:3:5: ошибка: неизвестное имя [E001]" in result.text
    assert "предупреждение: не используется" in result.text


def test_definition_returns_location(project) -> None:
    """Определение печатается как файл:строка:колонка."""

    result = lsp_tools.definition(project, "a.py", 10, 1)

    assert result.ok is True
    assert "a.py:5:3" in result.text


def test_references_lists_all(project) -> None:
    """Ссылки перечисляются по одной на строку."""

    result = lsp_tools.references(project, "a.py", 5, 3)

    assert result.ok is True
    assert len(result.text.splitlines()) == 2


def test_missing_file_is_reported(project) -> None:
    """Файл вне проекта — понятная ошибка, а не падение."""

    result = lsp_tools.diagnostics(project, "../outside.py")

    assert result.ok is False
    assert "вне проекта" in result.text


def test_no_server_is_reported(monkeypatch) -> None:
    """Без сервера инструмент отвечает подсказкой."""

    monkeypatch.setattr(lsp_tools, "server_command", lambda: None)

    result = lsp_tools.diagnostics(Path("."), "a.py")

    assert result.ok is False
    assert "LSP-сервер не найден" in result.text


def test_symbols_lists_functions_and_classes(project) -> None:
    """Символы печатаются с видом и строкой."""

    result = lsp_tools.symbols(project, "a.py")

    assert result.ok is True
    assert "Символов: 2" in result.text
    assert "функция main" in result.text
    assert "класс Helper" in result.text


def test_hover_returns_type(project) -> None:
    """Подсказка типа приходит текстом."""

    result = lsp_tools.hover(project, "a.py", 1, 1)

    assert result.ok is True
    assert "def main() -> None" in result.text
