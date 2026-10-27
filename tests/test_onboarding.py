# Giperion/tests/test_onboarding.py                                     v001
# Онбординг: флаг показа и окно.

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from terminal.core.agent import onboarding


def test_onboarding_flag_roundtrip(tmp_path, monkeypatch) -> None:
    """Флаг онбординга сохраняется в настройках."""

    monkeypatch.setattr(
        onboarding,
        "SETTINGS_FILE",
        tmp_path / "agent_settings.json",
    )

    assert not onboarding.done()
    onboarding.set_done(True)
    assert onboarding.done()


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()

    if application is None:
        application = QApplication([])

    return application


def test_dialog_has_hide_checkbox(qapp) -> None:
    """Окно предлагает больше не показывать и закрывается."""

    from terminal.ui.onboarding import OnboardingDialog

    dialog = OnboardingDialog(None)

    assert dialog.hide_check.isChecked()
    dialog.close()
