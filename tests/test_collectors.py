import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from capsule_watch.collectors import CommandResult, build_snapshot
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
                "Filesystem volume name: backup-202603a\n"
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
