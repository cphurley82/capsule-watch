import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from capsule_watch.collectors import CommandResult, build_snapshot
from capsule_watch import collectors
from capsule_watch.config import load_config


def _runner_for_success(command: list[str], timeout: int = 10) -> CommandResult:
    if command[:3] == ["systemctl", "is-active", "smbd"]:
        return CommandResult(returncode=0, stdout="active\n", stderr="")
    if command[:3] == ["systemctl", "is-active", "avahi-daemon"]:
        return CommandResult(returncode=0, stdout="active\n", stderr="")
    if command[:2] == ["df", "-Pk"]:
        return CommandResult(
            returncode=0,
            stdout=(
                "Filesystem 1024-blocks Used Available Capacity Mounted on\n"
                "/dev/sda1 1000 100 900 10% /mnt/backups\n"
            ),
            stderr="",
        )
    if command[:2] == ["df", "-PT"]:
        return CommandResult(
            returncode=0,
            stdout=(
                "Filesystem Type 1024-blocks Used Available Capacity Mounted on\n"
                "/dev/sda1 ext4 1000 100 900 10% /mnt/backups\n"
            ),
            stderr="",
        )
    if command[:3] == ["tune2fs", "-l", "/dev/sda1"]:
        return CommandResult(
            returncode=0,
            stdout=(
                "Filesystem volume name: timecapsule-data\n"
                "Mount count: 3\n"
                "Maximum mount count: 39\n"
            ),
            stderr="",
        )
    if command[:2] == ["smartctl", "--scan"]:
        return CommandResult(
            returncode=0,
            stdout="/dev/sda -d scsi # /dev/sda, SCSI device\n",
            stderr="",
        )
    if command[:3] == ["smartctl", "-H", "/dev/sda"]:
        return CommandResult(
            returncode=0,
            stdout="SMART overall-health self-assessment test result: PASSED\n",
            stderr="",
        )
    if command[:2] == ["uptime", "-p"]:
        return CommandResult(returncode=0, stdout="up 1 hour\n", stderr="")
    if command[:2] == ["free", "-m"]:
        return CommandResult(
            returncode=0,
            stdout=(
                "               total        used        free      shared  buff/cache   available\n"
                "Mem:           16000        2000         500         100       13500       14000\n"
                "Swap:           4096           1        4095\n"
            ),
            stderr="",
        )
    raise AssertionError(f"Unexpected command: {command}")


def test_build_snapshot_healthy(tmp_path: Path) -> None:
    backup_root = tmp_path / "time-machine"
    backup_root.mkdir()
    sparsebundle = backup_root / "macbook.sparsebundle"
    sparsebundle.mkdir()

    now = datetime.now(UTC)
    stale_time = now - timedelta(hours=2)
    sparsebundle.touch()
    sparsebundle_file = sparsebundle / "Info.plist"
    sparsebundle_file.write_text("x", encoding="utf-8")
    timestamp = stale_time.timestamp()
    Path(sparsebundle_file).touch()
    Path(sparsebundle).touch()
    os.utime(sparsebundle_file, (timestamp, timestamp))

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
paths:
  time_machine_root: {backup_root}
""",
        encoding="utf-8",
    )
    config = load_config(config_path)

    snapshot = build_snapshot(config=config, runner=_runner_for_success, now=now)

    assert snapshot["overall_status"] == "healthy"
    assert snapshot["services"]["status"] == "healthy"
    assert snapshot["storage"]["status"] == "healthy"
    assert snapshot["drive_health"]["status"] == "healthy"
    assert snapshot["backups"]["status"] == "healthy"
    assert snapshot["filesystem"]["status"] == "healthy"
    assert snapshot["collector_errors"] == {}


def test_privileged_command_retries_with_sudo() -> None:
    calls: list[list[str]] = []

    def fake_runner(command: list[str], timeout: int = 10) -> CommandResult:
        calls.append(command)
        if command == ["smartctl", "-H", "/dev/sda"]:
            return CommandResult(returncode=2, stdout="", stderr="Permission denied")
        if command == ["sudo", "-n", "smartctl", "-H", "/dev/sda"]:
            return CommandResult(
                returncode=0,
                stdout="SMART overall-health self-assessment test result: PASSED\n",
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {command}")

    result = collectors.run_command_with_optional_sudo(
        ["smartctl", "-H", "/dev/sda"],
        base_runner=fake_runner,
    )

    assert result.returncode == 0
    assert calls == [
        ["smartctl", "-H", "/dev/sda"],
        ["sudo", "-n", "smartctl", "-H", "/dev/sda"],
    ]


def test_non_privileged_command_is_not_retried_with_sudo() -> None:
    calls: list[list[str]] = []

    def fake_runner(command: list[str], timeout: int = 10) -> CommandResult:
        calls.append(command)
        return CommandResult(returncode=1, stdout="", stderr="some other failure")

    result = collectors.run_command_with_optional_sudo(
        ["df", "-Pk", "/tmp"],
        base_runner=fake_runner,
    )

    assert result.returncode == 1
    assert calls == [["df", "-Pk", "/tmp"]]


def test_collect_filesystem_health_retries_tune2fs_with_sudo() -> None:
    calls: list[list[str]] = []

    def fake_runner(command: list[str], timeout: int = 10) -> CommandResult:
        calls.append(command)
        if command == ["df", "-PT", "/mnt/backups"]:
            return CommandResult(
                returncode=0,
                stdout=(
                    "Filesystem Type 1024-blocks Used Available Capacity Mounted on\n"
                    "/dev/sda1 ext4 1000 100 900 10% /mnt/backups\n"
                ),
                stderr="",
            )
        if command == ["tune2fs", "-l", "/dev/sda1"]:
            return CommandResult(returncode=1, stdout="", stderr="Permission denied")
        if command == ["sudo", "-n", "tune2fs", "-l", "/dev/sda1"]:
            return CommandResult(
                returncode=0,
                stdout=(
                    "Filesystem volume name: timecapsule-data\n"
                    "Mount count: 3\n"
                    "Maximum mount count: 39\n"
                ),
                stderr="",
            )
        raise AssertionError(f"Unexpected command: {command}")

    result = collectors.collect_filesystem_health("/mnt/backups", fake_runner)

    assert result["status"] == "healthy"
    assert result["items"]["device"] == "/dev/sda1"
    assert calls == [
        ["df", "-PT", "/mnt/backups"],
        ["tune2fs", "-l", "/dev/sda1"],
        ["sudo", "-n", "tune2fs", "-l", "/dev/sda1"],
    ]
