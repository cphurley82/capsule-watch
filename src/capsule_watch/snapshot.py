"""Snapshot helpers for Capsule Watch."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


def empty_snapshot(generated_at: datetime | None = None) -> dict[str, Any]:
    timestamp = generated_at or datetime.now(UTC)
    return {
        "generated_at": timestamp.isoformat(),
        "overall_status": "unknown",
        "backups": {"status": "unknown", "items": []},
        "storage": {"status": "unknown", "items": {}},
        "drive_health": {"status": "unknown", "items": {}},
        "services": {"status": "unknown", "items": {}},
        "filesystem": {"status": "unknown", "items": {}},
        "system": {"status": "unknown", "items": {}},
        "maintenance": {"status": "unknown", "items": {}},
        "collector_errors": {},
    }


def read_snapshot(path: str | Path) -> dict[str, Any]:
    path_obj = Path(path)
    if not path_obj.exists():
        missing_snapshot = empty_snapshot()
        missing_snapshot["collector_errors"] = {
            "snapshot": "Snapshot file not found yet. Waiting for collector run."
        }
        return missing_snapshot

    return json.loads(path_obj.read_text(encoding="utf-8"))


def write_snapshot(path: str | Path, snapshot: dict[str, Any]) -> None:
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path_obj.parent,
        prefix=f"{path_obj.name}.",
        suffix=".tmp",
        delete=False,
    ) as temp_file:
        json.dump(snapshot, temp_file, indent=2, sort_keys=True)
        temp_name = temp_file.name

    Path(temp_name).replace(path_obj)
