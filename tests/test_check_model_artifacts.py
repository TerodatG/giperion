# Giperion/tests/test_check_model_artifacts.py                        v001
# Согласованность артефакта, eval-набора и паспорта.
# Последнее изменение: первый вариант — хеши и счётчики.

import json

from tools.check_model_artifacts import (
    DEFAULT_ARTIFACT,
    check_artifact,
)


def test_current_artifacts_are_consistent() -> None:
    """Рабочие артефакты не должны расходиться."""

    assert check_artifact() == []


def test_missing_artifact_is_reported(tmp_path) -> None:
    """Отсутствие артефакта — ошибка."""

    problems = check_artifact(tmp_path / "none.json")

    assert problems
    assert "нет артефакта" in problems[0]


def test_hash_mismatch_is_reported(tmp_path) -> None:
    """Подменённый eval-хеш ловится."""

    document = json.loads(
        DEFAULT_ARTIFACT.read_text(encoding="utf-8")
    )
    document["meta"]["eval_sha256"] = "0" * 64
    broken = tmp_path / "artifact.json"
    broken.write_text(
        json.dumps(document, ensure_ascii=False),
        encoding="utf-8",
    )

    problems = check_artifact(broken)

    assert any("eval_sha256" in problem for problem in problems)
