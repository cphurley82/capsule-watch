"""Collectors for Capsule Watch."""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from capsule_watch.config import AppConfig, load_config
from capsule_watch.snapshot import empty_snapshot, write_snapshot


@dataclass(slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[[list[str], int], CommandResult]


def run_command(command: list[str], timeout: int = 10) -> CommandResult:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def collect_services(units: list[str], runner: Runner) -> dict:
    items: dict[str, dict] = {}
    for unit in units:
        result = runner(["systemctl", "is-active", unit], timeout=10)
        is_active = result.returncode == 0 and result.stdout.strip() == "active"
        items[unit] = {
            "active": is_active,
            "raw_status": result.stdout.strip() or result.stderr.strip() or "unknown",
        }
    status = "healthy" if all(item["active"] for item in items.values()) else "critical"
    return {"status": status, "items": items}


def collect_storage_usage(path: str, warning: int, critical: int, runner: Runner) -> dict:
    result = runner(["df", "-Pk", path], timeout=10)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "df failed")

    lines = [line for line in result.stdout.strip().splitlines() if line.strip()]
    if len(lines) < 2:
        raise RuntimeError("Unexpected df output")
    fields = lines[1].split()
    used_percent = int(fields[4].rstrip("%"))

    if used_percent >= critical:
        status = "critical"
    elif used_percent >= warning:
        status = "warning"
    else:
        status = "healthy"

    return {
        "status": status,
        "items": {
            "filesystem": fields[0],
            "total_kib": int(fields[1]),
            "used_kib": int(fields[2]),
            "available_kib": int(fields[3]),
            "used_percent": used_percent,
            "mountpoint": fields[5],
        },
    }


def collect_filesystem_health(path: str, runner: Runner) -> dict:
    result = runner(["df", "-PT", path], timeout=10)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "df -PT failed")
    lines = [line for line in result.stdout.strip().splitlines() if line.strip()]
    if len(lines) < 2:
        raise RuntimeError("Unexpected df -PT output")
    fields = lines[1].split()
    device = fields[0]
    filesystem_type = fields[1]
    if filesystem_type != "ext4":
        return {
            "status": "unsupported",
            "items": {"device": device, "filesystem_type": filesystem_type},
        }

    tune = runner(["tune2fs", "-l", device], timeout=10)
    if tune.returncode != 0:
        raise RuntimeError(tune.stderr.strip() or "tune2fs failed")
    mount_count = None
    max_mount_count = None
    for line in tune.stdout.splitlines():
        if line.startswith("Mount count:"):
            mount_count = int(line.split(":", 1)[1].strip())
        if line.startswith("Maximum mount count:"):
            max_mount_count = int(line.split(":", 1)[1].strip())

    return {
        "status": "healthy",
        "items": {
            "device": device,
            "filesystem_type": filesystem_type,
            "mount_count": mount_count,
            "max_mount_count": max_mount_count,
        },
    }


def collect_drive_health(runner: Runner) -> dict:
    scan = runner(["smartctl", "--scan"], timeout=15)
    if scan.returncode != 0 or not scan.stdout.strip():
        return {"status": "unknown", "items": {}, "message": "No SMART devices found"}

    first_line = scan.stdout.strip().splitlines()[0]
    device = first_line.split()[0]
    result = runner(["smartctl", "-H", device], timeout=15)
    if result.returncode != 0 and "PASSED" not in result.stdout:
        return {
            "status": "warning",
            "items": {"device": device},
            "message": result.stderr.strip() or "smartctl returned non-zero status",
        }

    raw = result.stdout
    if "PASSED" in raw:
        status = "healthy"
    elif "FAILED" in raw:
        status = "critical"
    else:
        status = "warning"
    return {"status": status, "items": {"device": device, "raw": raw.strip()}}


def collect_host_telemetry(runner: Runner) -> dict:
    uptime_result = runner(["uptime", "-p"], timeout=5)
    free_result = runner(["free", "-m"], timeout=5)
    if uptime_result.returncode != 0:
        raise RuntimeError("uptime command failed")
    if free_result.returncode != 0:
        raise RuntimeError("free command failed")

    lines = [line for line in free_result.stdout.splitlines() if line.strip()]
    memory_line = next((line for line in lines if line.startswith("Mem:")), "")
    fields = memory_line.split()
    memory = {
        "total_mb": int(fields[1]) if len(fields) > 1 else None,
        "used_mb": int(fields[2]) if len(fields) > 2 else None,
        "free_mb": int(fields[3]) if len(fields) > 3 else None,
    }
    return {"status": "healthy", "items": {"uptime": uptime_result.stdout.strip(), "memory": memory}}


def collect_backup_recency(
    time_machine_root: str,
    warning_hours: int,
    critical_hours: int,
    now: datetime,
) -> dict:
    root = Path(time_machine_root)
    if not root.exists():
        return {
            "status": "unknown",
            "items": [],
            "message": f"Backup root not found: {time_machine_root}",
        }

    backup_dirs = [path for path in root.glob("*.sparsebundle") if path.is_dir()]
    if not backup_dirs:
        return {"status": "warning", "items": [], "message": "No sparsebundle backups found"}

    items = []
    worst_status = "healthy"
    for backup_dir in backup_dirs:
        latest_mtime = _latest_file_mtime(backup_dir)
        age_hours = (now - datetime.fromtimestamp(latest_mtime, tz=UTC)).total_seconds() / 3600
        if age_hours >= critical_hours:
            status = "critical"
        elif age_hours >= warning_hours:
            status = "warning"
        else:
            status = "healthy"
        worst_status = _worse_status(worst_status, status)
        items.append(
            {
                "client": backup_dir.name,
                "age_hours": round(age_hours, 2),
                "status": status,
            }
        )

    return {"status": worst_status, "items": items}


def build_snapshot(
    config: AppConfig,
    runner: Runner | None = None,
    now: datetime | None = None,
) -> dict:
    runner = runner or run_command
    now = now or datetime.now(UTC)
    snapshot = empty_snapshot(now)
    errors: dict[str, str] = {}

    collectors = {
        "services": lambda: collect_services(
            [config.services.samba_unit, config.services.avahi_unit], runner
        ),
        "storage": lambda: collect_storage_usage(
            config.paths.time_machine_root,
            config.thresholds.disk_warning_percent,
            config.thresholds.disk_critical_percent,
            runner,
        ),
        "filesystem": lambda: collect_filesystem_health(config.paths.time_machine_root, runner),
        "drive_health": lambda: collect_drive_health(runner),
        "system": lambda: collect_host_telemetry(runner),
        "backups": lambda: collect_backup_recency(
            config.paths.time_machine_root,
            config.thresholds.backup_warning_hours,
            config.thresholds.backup_critical_hours,
            now,
        ),
    }

    for key, fn in collectors.items():
        try:
            snapshot[key] = fn()
        except Exception as exc:  # noqa: BLE001
            snapshot[key] = {"status": "unknown", "items": {}}
            errors[key] = str(exc)

    snapshot["collector_errors"] = errors
    snapshot["overall_status"] = _overall_status(snapshot)
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Capsule Watch collectors")
    parser.add_argument(
        "--config",
        default="/etc/capsule-watch/config.yaml",
        help="Path to Capsule Watch YAML config",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional snapshot output override",
    )
    args = parser.parse_args(argv)
    config = load_config(args.config)
    snapshot = build_snapshot(config=config)
    output_path = args.output or config.paths.snapshot_file
    write_snapshot(output_path, snapshot)
    return 0


def _latest_file_mtime(root: Path) -> float:
    mtimes = [path.stat().st_mtime for path in root.rglob("*") if path.is_file()]
    if mtimes:
        return max(mtimes)
    return root.stat().st_mtime


def _overall_status(snapshot: dict) -> str:
    statuses = []
    for section in ("backups", "storage", "drive_health", "services", "filesystem", "system"):
        value = snapshot.get(section, {})
        if isinstance(value, dict):
            statuses.append(value.get("status", "unknown"))
    worst = "healthy"
    for status in statuses:
        worst = _worse_status(worst, status)
    if worst == "healthy" and all(status == "unknown" for status in statuses):
        return "unknown"
    return worst


def _worse_status(left: str, right: str) -> str:
    order = {"critical": 4, "warning": 3, "healthy": 2, "unknown": 1, "unsupported": 1}
    return left if order.get(left, 1) >= order.get(right, 1) else right


if __name__ == "__main__":
    raise SystemExit(main())
