"""Parsers for command output used by collectors."""

from __future__ import annotations

import re


def parse_df_pk(output: str) -> dict[str, int | str]:
    lines = [line for line in output.strip().splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("Unexpected df -Pk output")

    fields = lines[1].split()
    if len(fields) < 6:
        raise ValueError("Unable to parse df -Pk data row")

    return {
        "filesystem": fields[0],
        "total_kib": int(fields[1]),
        "used_kib": int(fields[2]),
        "available_kib": int(fields[3]),
        "used_percent": int(fields[4].rstrip("%")),
        "mountpoint": fields[5],
    }


def parse_df_pt(output: str) -> dict[str, str]:
    lines = [line for line in output.strip().splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("Unexpected df -PT output")

    fields = lines[1].split()
    if len(fields) < 7:
        raise ValueError("Unable to parse df -PT data row")

    return {
        "device": fields[0],
        "filesystem_type": fields[1],
        "mountpoint": fields[6],
    }


def parse_tune2fs(output: str) -> dict[str, int | str | None]:
    metadata: dict[str, int | str | None] = {
        "volume_name": None,
        "mount_count": None,
        "max_mount_count": None,
    }

    for line in output.splitlines():
        if line.startswith("Filesystem volume name:"):
            metadata["volume_name"] = line.split(":", 1)[1].strip()
        elif line.startswith("Mount count:"):
            metadata["mount_count"] = int(line.split(":", 1)[1].strip())
        elif line.startswith("Maximum mount count:"):
            metadata["max_mount_count"] = int(line.split(":", 1)[1].strip())

    return metadata


def parse_smartctl_scan(output: str) -> list[dict[str, str | None]]:
    devices: list[dict[str, str | None]] = []
    for line in output.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        # Example: /dev/sda -d scsi # /dev/sda, SCSI device
        match = re.match(r"^(?P<device>\S+)(?:\s+-d\s+(?P<driver>\S+))?", cleaned)
        if match:
            devices.append(
                {
                    "device": match.group("device"),
                    "driver_type": match.group("driver"),
                }
            )
    return devices


def parse_smartctl_health(output: str) -> str:
    upper = output.upper()
    if "PASSED" in upper:
        return "healthy"
    if "FAILED" in upper:
        return "critical"
    return "warning"


def parse_free_m(output: str) -> dict[str, int | None]:
    memory_line = next((line for line in output.splitlines() if line.startswith("Mem:")), "")
    fields = memory_line.split()
    if len(fields) < 4:
        return {"total_mb": None, "used_mb": None, "free_mb": None}
    return {
        "total_mb": int(fields[1]),
        "used_mb": int(fields[2]),
        "free_mb": int(fields[3]),
    }
