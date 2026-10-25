# Giperion/tests/test_performance_monitor.py                        v003
# Показатели компьютера: единицы измерения и живой замер.
# Последнее изменение: две видеокарты и скрытые служебные процессы.

import time

import pytest

from terminal.core.performance_monitor import (
    VolumeUsage,
    _clamp,
    _sum_filtered,
    create_monitor,
    format_bitrate,
    format_rate,
)


def test_format_rate_chooses_units() -> None:
    """Скорость обмена растёт по единицам: байты, килобайты, мегабайты."""

    assert format_rate(0) == "0 Б/с"
    assert format_rate(999) == "999 Б/с"
    assert format_rate(2048) == "2,0 КБ/с"
    assert format_rate(5 * 1024 * 1024) == "5,0 МБ/с"


def test_format_bitrate_counts_bits() -> None:
    """Сеть считается в битах: так понятнее скорость подключения."""

    assert format_bitrate(0) == "0 бит/с"
    assert format_bitrate(125_000) == "1,0 Мбит/с"
    assert format_bitrate(12_500_000) == "100,0 Мбит/с"


def test_sum_filtered_skips_service_interfaces() -> None:
    """Служебные интерфейсы не попадают в общий трафик."""

    values = [
        ("Intel[R] Ethernet", 1500.0),
        ("Loopback Pseudo-Interface 1", 9000.0),
        ("isatap.example", 700.0),
        ("Teredo Tunneling", 300.0),
    ]

    assert _sum_filtered(values) == 1500.0


def test_sum_filtered_can_pick_one_engine() -> None:
    """Занятость видеокарты считают только по 3D-движку."""

    values = [
        ("pid_1_luid_0_phys_0_eng_0_engtype_3D", 12.0),
        ("pid_1_luid_0_phys_0_eng_1_engtype_Copy", 40.0),
        ("pid_2_luid_0_phys_0_eng_0_engtype_3D", 8.0),
    ]

    assert _sum_filtered(values, contains="engtype_3d") == 20.0


def test_clamp_keeps_percent_in_range() -> None:
    """Проценты не выходят за границы шкалы."""

    assert _clamp(-5) == 0.0
    assert _clamp(42.5) == 42.5
    assert _clamp(140) == 100.0


def test_service_processes_are_hidden() -> None:
    """nvidia-smi и opencode-cli запускаются без окна консоли."""

    import os
    import subprocess

    from shared.process_tools import hidden_process_options

    options = hidden_process_options()

    if os.name != "nt":
        assert options == {}

        return

    assert options["creationflags"] & subprocess.CREATE_NO_WINDOW
    assert (
        options["startupinfo"].dwFlags
        & subprocess.STARTF_USESHOWWINDOW
    )


def test_gpu_details_read_all_cards(monkeypatch) -> None:
    """При двух видеокартах nvidia-smi отдаёт две строки."""

    from terminal.core import performance_monitor

    class Result:
        stdout = (
            "NVIDIA GeForce RTX 5080, 2000, 16000, 48, 40, 6\n"
            "NVIDIA GeForce RTX 3080, 1000, 10000, 35, 20, 12\n"
        )

    monkeypatch.setattr(
        performance_monitor.subprocess,
        "run",
        lambda *args, **kwargs: Result(),
    )
    monkeypatch.setattr(
        performance_monitor,
        "_GPU_DETAILS",
        {"value": None, "values": None, "time": 0.0},
    )

    cards = performance_monitor.read_gpu_details_list()

    assert len(cards) == 2
    assert cards[0]["name"] == "NVIDIA GeForce RTX 5080"
    assert cards[0]["utilization"] == 6.0
    assert cards[1]["name"] == "NVIDIA GeForce RTX 3080"
    assert cards[1]["utilization"] == 12.0
    assert cards[1]["temperature"] == 35.0

    primary = performance_monitor.read_gpu_details()

    assert primary["name"] == "NVIDIA GeForce RTX 5080"


def test_monitor_samples_real_system() -> None:
    """Настоящий источник отдаёт правдоподобный снимок."""

    monitor = create_monitor()

    if monitor is None:
        pytest.skip("нет доступа ни к счётчикам Windows, ни к psutil")

    try:
        # Два замера подряд: счётчикам нужна разница во времени.
        monitor.sample()
        time.sleep(0.2)
        sample = monitor.sample()
    finally:
        monitor.close()

    assert 0.0 <= sample.cpu_percent <= 100.0
    assert 0.0 <= sample.ram_percent <= 100.0
    assert sample.ram_total > 0
    assert 0 <= sample.ram_available <= sample.ram_total
    assert 0.0 <= sample.disk_percent <= 100.0
    assert sample.net_down_bps >= 0.0
    assert sample.net_up_bps >= 0.0
    assert sample.uptime >= 0.0
    assert sample.source

    for volume in sample.volumes:
        assert isinstance(volume, VolumeUsage)
        assert volume.total > 0
        assert 0 <= volume.free <= volume.total
