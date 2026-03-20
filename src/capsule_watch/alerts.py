"""Alert evaluation for Capsule Watch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from capsule_watch.config import load_config
from capsule_watch.snapshot import read_snapshot


def evaluate_alert_transitions(previous_state: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    previous_active = previous_state.get("active", {})
    current_active = _active_alerts_from_snapshot(snapshot)

    previous_keys = set(previous_active.keys())
    current_keys = set(current_active.keys())

    resolved = sorted(previous_keys - current_keys)
    new_keys = sorted(current_keys - previous_keys)

    return {
        "active": current_active,
        "new": {key: current_active[key] for key in new_keys},
        "resolved": resolved,
    }


def load_alert_state(path: str | Path) -> dict[str, Any]:
    path_obj = Path(path)
    if not path_obj.exists():
        return {"active": {}}
    return json.loads(path_obj.read_text(encoding="utf-8"))


def write_alert_state(path: str | Path, state: dict[str, Any]) -> None:
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    path_obj.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate Capsule Watch alerts")
    parser.add_argument(
        "--config",
        default="/etc/capsule-watch/config.yaml",
        help="Path to Capsule Watch YAML config",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)
    snapshot = read_snapshot(config.paths.snapshot_file)
    previous_state = load_alert_state(config.paths.alerts_file)
    transitions = evaluate_alert_transitions(previous_state=previous_state, snapshot=snapshot)
    write_alert_state(config.paths.alerts_file, {"active": transitions["active"]})
    return 0


def _active_alerts_from_snapshot(snapshot: dict[str, Any]) -> dict[str, dict[str, str]]:
    active: dict[str, dict[str, str]] = {}
    mapping = {
        "backups": "backup_recency",
        "storage": "storage",
        "services": "services",
        "drive_health": "drive_health",
    }
    for section, alert_key in mapping.items():
        section_data = snapshot.get(section, {})
        status = section_data.get("status", "unknown") if isinstance(section_data, dict) else "unknown"
        if status in {"warning", "critical"}:
            active[alert_key] = {
                "severity": status,
                "message": section_data.get("message", f"{section} is {status}"),
            }
    return active


if __name__ == "__main__":
    raise SystemExit(main())
