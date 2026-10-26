# Giperion/tests/test_action_log.py                               v001
# Проверки журнала действий Giperion.
# Последнее изменение: добавлены тесты номера, времени и вывода записей.

import re
import threading

import pytest

from shared import action_log


@pytest.fixture
def isolated_log(
    tmp_path,
    monkeypatch,
):
    """Направляет журнал действий во временный файл."""

    log_file = (
        tmp_path
        / "logs"
        / "actions.log"
    )

    monkeypatch.setattr(
        action_log,
        "LOG_FILE",
        log_file,
    )

    return log_file


def test_action_numbers_increase(
    isolated_log,
) -> None:
    """Каждая следующая запись получает новый номер."""

    first_number = action_log.add_action(
        "Giperion запущен"
    )
    second_number = action_log.add_action(
        "Создан архив 00001"
    )

    lines = (
        isolated_log.read_text(
            encoding="utf-8"
        )
        .splitlines()
    )

    assert first_number == 1
    assert second_number == 2
    assert lines[0].startswith(
        "000001 | "
    )
    assert lines[1].startswith(
        "000002 | "
    )


def test_action_contains_date_and_time(
    isolated_log,
) -> None:
    """Запись содержит дату, время и описание."""

    action_log.add_action(
        "Создан архив 00001"
    )

    line = (
        isolated_log.read_text(
            encoding="utf-8"
        )
        .strip()
    )

    assert re.fullmatch(
        r"000001 \| "
        r"\d{2}\.\d{2}\.\d{4} "
        r"\d{2}:\d{2}:\d{2} \| "
        r"Создан архив 00001",
        line,
    )


def test_recent_actions_respects_limit(
    isolated_log,
) -> None:
    """Показываются только последние записи."""

    action_log.add_action(
        "Первое действие"
    )
    action_log.add_action(
        "Второе действие"
    )
    action_log.add_action(
        "Третье действие"
    )

    recent = action_log.get_recent_actions(
        limit=2
    )

    assert len(recent) == 2
    assert "Второе действие" in recent[0]
    assert "Третье действие" in recent[1]


def test_log_number_survives_new_read(
    isolated_log,
) -> None:
    """Номер продолжается после повторного чтения файла."""

    action_log.add_action(
        "Первое действие"
    )

    assert (
        action_log.get_last_record_number()
        == 1
    )

    next_number = (
        action_log.add_action(
            "Второе действие"
        )
    )

    assert next_number == 2


def test_invalid_description_is_rejected(
    isolated_log,
) -> None:
    """Пустое описание не создаёт запись."""

    with pytest.raises(ValueError):
        action_log.add_action("   ")

    assert not isolated_log.exists()


def test_damaged_log_is_not_renumbered(
    isolated_log,
) -> None:
    """Повреждённый журнал не обнуляет нумерацию."""

    isolated_log.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    isolated_log.write_text(
        "неверная запись\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        action_log.add_action(
            "Новое действие"
        )

    assert (
        isolated_log.read_text(
            encoding="utf-8"
        )
        == "неверная запись\n"
    )


def test_concurrent_actions_keep_numbering(
    isolated_log,
) -> None:
    """Параллельные записи не дублируют номера и не ломают журнал."""

    workers = 8
    rounds = 10
    start = threading.Barrier(workers)
    numbers: list[int] = []
    errors: list[BaseException] = []

    def write_actions(worker: int) -> None:
        try:
            start.wait()

            for round_number in range(rounds):
                numbers.append(
                    action_log.add_action(
                        f"Поток {worker}, запись {round_number}"
                    )
                )
        except BaseException as error:  # noqa: BLE001 — покажем в тесте
            errors.append(error)

    threads = [
        threading.Thread(target=write_actions, args=(worker,))
        for worker in range(workers)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert not errors
    assert len(numbers) == workers * rounds
    assert sorted(numbers) == list(range(1, workers * rounds + 1))
    assert action_log.get_last_record_number() == workers * rounds