from pathlib import Path

import pytest

from capsule_watch import parsers


FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_df_pk() -> None:
    parsed = parsers.parse_df_pk(_read("df_pk.txt"))

    assert parsed["filesystem"] == "/dev/sda1"
    assert parsed["total_kib"] == 1000
    assert parsed["used_kib"] == 100
    assert parsed["available_kib"] == 900
    assert parsed["used_percent"] == 10
    assert parsed["mountpoint"] == "/mnt/backups"


def test_parse_df_pt() -> None:
    parsed = parsers.parse_df_pt(_read("df_pt.txt"))

    assert parsed["device"] == "/dev/sda1"
    assert parsed["filesystem_type"] == "ext4"
    assert parsed["mountpoint"] == "/mnt/backups"


def test_parse_tune2fs() -> None:
    parsed = parsers.parse_tune2fs(_read("tune2fs.txt"))

    assert parsed["volume_name"] == "timecapsule-data"
    assert parsed["mount_count"] == 3
    assert parsed["max_mount_count"] == 39


def test_parse_smartctl_scan() -> None:
    parsed = parsers.parse_smartctl_scan(_read("smartctl_scan.txt"))

    assert parsed[0]["device"] == "/dev/sda"
    assert parsed[0]["driver_type"] == "scsi"
    assert parsed[1]["device"] == "/dev/nvme0"
    assert parsed[1]["driver_type"] == "nvme"


def test_parse_smartctl_health() -> None:
    passed = parsers.parse_smartctl_health(_read("smartctl_health_passed.txt"))
    failed = parsers.parse_smartctl_health(_read("smartctl_health_failed.txt"))
    unknown = parsers.parse_smartctl_health("some other output")

    assert passed == "healthy"
    assert failed == "critical"
    assert unknown == "warning"


def test_parse_free_m() -> None:
    parsed = parsers.parse_free_m(_read("free_m.txt"))

    assert parsed["total_mb"] == 16000
    assert parsed["used_mb"] == 2000
    assert parsed["free_mb"] == 500


def test_parse_df_pk_rejects_unexpected_output() -> None:
    with pytest.raises(ValueError):
        parsers.parse_df_pk("header only")
