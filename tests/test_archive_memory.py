# Giperion/tests/test_archive_memory.py                         v004
# Проверки архивов памяти и системных команд Giperion.
# Последнее изменение: создание архива в тесте подтверждается ответом «да».

import json

import pytest

from shared import action_log
from terminal.core.chatbot import get_response
from terminal.memory import archive_service, system_handler


@pytest.fixture
def isolated_archive(tmp_path, monkeypatch):
    """Направляет архив, память и журнал во временную папку теста."""

    archive_dir = tmp_path / "archive"
    data_dir = tmp_path / "data"
    log_file = tmp_path / "logs" / "actions.log"

    data_dir.mkdir()

    profile_file = data_dir / "user_profile.json"
    conversations_file = data_dir / "conversations.json"
    unknown_file = data_dir / "unknown_messages.json"

    profile_file.write_text(
        json.dumps({"name": "Алексей"}, ensure_ascii=False),
        encoding="utf-8",
    )
    conversations_file.write_text(
        json.dumps(
            [{"role": "user", "text": "Привет"}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    unknown_file.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(
        archive_service,
        "ARCHIVE_DIR",
        archive_dir,
    )
    monkeypatch.setattr(
        archive_service,
        "MEMORY_FILES",
        [
            profile_file,
            conversations_file,
            unknown_file,
        ],
    )
    monkeypatch.setattr(
        action_log,
        "LOG_FILE",
        log_file,
    )

    system_handler.clear_pending_action()

    yield {
        "archive_dir": archive_dir,
        "profile_file": profile_file,
        "conversations_file": conversations_file,
        "unknown_file": unknown_file,
        "log_file": log_file,
    }

    system_handler.clear_pending_action()


def test_archive_copies_memory_files(isolated_archive) -> None:
    """Архив содержит три файла памяти и описание."""

    archive_info = archive_service.create_archive()
    archive_path = (
        isolated_archive["archive_dir"]
        / archive_info["archive_id"]
    )

    assert archive_info["archive_id"] == "00001"
    assert archive_path.is_dir()
    assert {
        path.name
        for path in archive_path.iterdir()
    } == {
        "user_profile.json",
        "conversations.json",
        "unknown_messages.json",
        "archive_info.json",
    }

    saved_profile = json.loads(
        (archive_path / "user_profile.json").read_text(
            encoding="utf-8"
        )
    )

    assert saved_profile["name"] == "Алексей"


def test_restore_archive_restores_memory(
    isolated_archive,
) -> None:
    """Восстановление возвращает данные из архива."""

    archive_id = archive_service.create_archive()[
        "archive_id"
    ]

    isolated_archive["profile_file"].write_text(
        json.dumps(
            {"name": "Другое имя"},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    isolated_archive["conversations_file"].write_text(
        "[]",
        encoding="utf-8",
    )

    restored = archive_service.restore_archive(
        archive_id
    )

    profile = json.loads(
        isolated_archive["profile_file"].read_text(
            encoding="utf-8"
        )
    )
    conversations = json.loads(
        isolated_archive["conversations_file"].read_text(
            encoding="utf-8"
        )
    )

    assert restored is True
    assert profile["name"] == "Алексей"
    assert conversations[0]["text"] == "Привет"


def test_cancel_does_not_delete_archive(
    isolated_archive,
) -> None:
    """Отмена удаления оставляет архив на месте."""

    archive_id = archive_service.create_archive()[
        "archive_id"
    ]
    archive_path = (
        isolated_archive["archive_dir"] / archive_id
    )

    request, save_request = get_response(
        f"удалить архив {archive_id}"
    )
    cancellation, save_cancellation = get_response(
        "отмена"
    )

    assert "подтверждаю" in request
    assert save_request is False
    assert "отменена" in cancellation
    assert save_cancellation is False
    assert archive_path.is_dir()


def test_confirm_deletes_selected_archive(
    isolated_archive,
) -> None:
    """Подтверждение удаляет только выбранный архив."""

    first_id = archive_service.create_archive()[
        "archive_id"
    ]
    second_id = archive_service.create_archive()[
        "archive_id"
    ]

    get_response(f"удалить архив {first_id}")
    confirmation, save_confirmation = get_response(
        "подтверждаю"
    )

    assert f"Архив {first_id} удалён" in confirmation
    assert save_confirmation is False
    assert not (
        isolated_archive["archive_dir"] / first_id
    ).exists()
    assert (
        isolated_archive["archive_dir"] / second_id
    ).is_dir()


def test_system_commands_are_not_saved_to_history(
    isolated_archive,
) -> None:
    """Архивные команды и ответы исключаются из истории."""

    request_response, save_request = get_response(
        "архив ядра"
    )
    archive_response, save_archive = get_response(
        "да"
    )
    list_response, save_list = get_response(
        "покажи архивы"
    )
    files_response, save_files = get_response(
        "покажи файлы архива"
    )

    assert "Создать архив" in request_response
    assert "Архив создан" in archive_response
    assert "Доступные архивы" in list_response
    assert "Файлы архива" in files_response
    assert save_request is False
    assert save_archive is False
    assert save_list is False
    assert save_files is False

    log_text = isolated_archive["log_file"].read_text(
        encoding="utf-8"
    )
    assert "Создан архив 00001" in log_text


def test_invalid_archive_number_cannot_escape_archive_folder(
    isolated_archive,
) -> None:
    """Неверный номер не даёт обратиться к посторонним файлам."""

    assert archive_service.get_archive_path(
        "../data"
    ) is None
    assert archive_service.get_archive_path(
        "123456"
    ) is None
    assert archive_service.delete_archive(
        "../data"
    ) is False
    assert isolated_archive["profile_file"].exists()


def test_deleted_latest_number_is_not_reused(
    isolated_archive,
) -> None:
    """Удаление последнего архива не освобождает его номер."""

    first_id = archive_service.create_archive()[
        "archive_id"
    ]
    second_id = archive_service.create_archive()[
        "archive_id"
    ]

    assert first_id == "00001"
    assert second_id == "00002"
    assert archive_service.delete_archive(
        second_id
    ) is True

    next_id = archive_service.create_archive()[
        "archive_id"
    ]

    assert next_id == "00003"
    assert (
        isolated_archive["archive_dir"] / first_id
    ).is_dir()
    assert (
        isolated_archive["archive_dir"] / next_id
    ).is_dir()


def test_deleted_only_archive_number_is_not_reused(
    isolated_archive,
) -> None:
    """Номер сохраняется, даже если удалён единственный архив."""

    first_id = archive_service.create_archive()[
        "archive_id"
    ]

    assert archive_service.delete_archive(
        first_id
    ) is True

    next_id = archive_service.create_archive()[
        "archive_id"
    ]

    assert next_id == "00002"


def test_existing_archives_initialize_counter(
    isolated_archive,
) -> None:
    """Старые архивы учитываются при первом создании счётчика."""

    old_archive = (
        isolated_archive["archive_dir"] / "00021"
    )
    old_archive.mkdir(parents=True)

    archive_info = archive_service.create_archive()

    assert archive_info["archive_id"] == "00022"


def test_damaged_counter_does_not_create_archive(
    isolated_archive,
) -> None:
    """Повреждённый счётчик не заменяется номером с начала."""

    archive_dir = isolated_archive["archive_dir"]
    archive_dir.mkdir()

    counter_path = (
        archive_dir
        / archive_service.ARCHIVE_COUNTER_FILE_NAME
    )
    counter_path.write_text(
        "не JSON",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        archive_service.create_archive()

    assert not (archive_dir / "00001").exists()