# GiperionModel/tests/test_storage.py                                  v001
# Атомарная запись: резервная копия, чтение и отсутствие temp.

import json

import torch

from giperion_model.storage import save_json, save_text, save_torch


def test_text_save_keeps_backup(tmp_path) -> None:
    """Вторая запись оставляет предыдущую версию в .bak."""

    target = tmp_path / "a.txt"

    save_text(target, "первая")
    save_text(target, "вторая")

    assert target.read_text(encoding="utf-8") == "вторая"
    assert (
        tmp_path / "a.txt.bak"
    ).read_text(encoding="utf-8") == "первая"
    assert not (tmp_path / "a.txt.tmp").exists()


def test_json_save_is_utf8(tmp_path) -> None:
    """JSON пишется без escape-последовательностей."""

    target = tmp_path / "a.json"
    save_json(target, {"текст": "привет"})

    assert json.loads(target.read_text(encoding="utf-8")) == {
        "текст": "привет"
    }


def test_torch_save_roundtrip(tmp_path) -> None:
    """Чекпоинт читается с weights_only=True и имеет .bak."""

    target = tmp_path / "m.pt"
    save_torch(target, {"format_version": 1, "w": torch.ones(2)})
    save_torch(target, {"format_version": 1, "w": torch.zeros(2)})

    loaded = torch.load(target, weights_only=True)

    assert loaded["format_version"] == 1
    assert loaded["w"].tolist() == [0.0, 0.0]
    assert (tmp_path / "m.pt.bak").is_file()
    assert not (tmp_path / "m.pt.tmp").exists()
