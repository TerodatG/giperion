# Giperion/tests/test_system_info.py                               v001
# Проверки сведений о компьютере для закладки «Система».

from terminal.core.system_info import format_bytes, get_system_info


def test_format_bytes() -> None:
    """Размеры переводятся в удобные единицы."""

    assert format_bytes(0) == "—"
    assert format_bytes(1024**3) == "1,0 ГБ"
    assert format_bytes(512 * 1024**2) == "512 МБ"


def test_system_info_has_required_fields() -> None:
    """Основные параметры системы заполнены."""

    info = get_system_info(force=True)

    assert info["os"]
    assert info["processor"]
    assert info["cpu_cores"] > 0
    assert info["ram_total"] > 0
    assert info["python"]
    assert info["project"]
