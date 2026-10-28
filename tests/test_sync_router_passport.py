# Giperion/tests/test_sync_router_passport.py                         v001
# Автоматическая синхронизация паспорта с артефактом роутера.
# Последнее изменение: первый вариант — качество и тренировка.

import json

from tools.sync_router_passport import main, sync


def write_fixtures(tmp_path):
    """Готовит минимальные артефакт и паспорт."""

    artifact = tmp_path / "linear_intent.json"
    artifact.write_text(
        json.dumps(
            {
                "meta": {
                    "eval_top1": 0.84,
                    "eval_macro_f1": 0.85,
                    "eval_correct": 646,
                    "eval_size": 770,
                    "eval_ci": 0.02,
                    "eval_coverage": 0.6,
                    "eval_selective_accuracy": 0.94,
                    "template_top1": 0.91,
                    "template_macro_f1": 0.92,
                    "template_coverage": 0.75,
                    "template_size": 770,
                    "answer_threshold": 0.65,
                }
            }
        ),
        encoding="utf-8",
    )
    passports = tmp_path / "passports.json"
    passports.write_text(
        json.dumps(
            {
                "passports": {
                    "giperion": {
                        "architecture": {},
                        "training": {},
                        "quality": {},
                        "speed": {},
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    return artifact, passports


def test_sync_fills_quality_and_training(tmp_path) -> None:
    """Паспорт получает актуальные метрики и счётчики."""

    artifact, passports = write_fixtures(tmp_path)
    passport = sync(artifact, passports, today="2026-10-28")

    assert passport["updated"] == "2026-10-28"
    assert passport["quality"]["accuracy"] == 0.84
    assert passport["quality"]["fallback"] == 0.4
    assert passport["training"]["eval_phrases"] == 770
    assert passport["training"]["template_phrases"] == 770


def test_missing_artifact_is_reported(tmp_path) -> None:
    """Без артефакта команда возвращает ошибку."""

    _artifact, passports = write_fixtures(tmp_path)

    assert (
        main(
            [
                "--artifact",
                str(tmp_path / "none.json"),
                "--passports",
                str(passports),
            ]
        )
        == 1
    )
