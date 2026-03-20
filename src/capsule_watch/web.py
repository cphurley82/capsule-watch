"""Web app for Capsule Watch."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template

from capsule_watch.config import load_config
from capsule_watch.snapshot import read_snapshot


SECTION_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("backups", "Backups"),
    ("storage", "Storage"),
    ("filesystem", "Filesystem"),
    ("drive_health", "Drive Health"),
    ("services", "Services"),
    ("system", "System"),
    ("maintenance", "Maintenance"),
)
VALID_STATUSES = {"healthy", "warning", "critical", "unknown", "unsupported"}
STALE_AFTER_SECONDS = 30 * 60


def create_app(
    config_path: str | Path | None = None,
    now_provider: Callable[[], datetime] | None = None,
) -> Flask:
    effective_path = config_path or os.environ.get(
        "CAPSULE_WATCH_CONFIG", "/etc/capsule-watch/config.yaml"
    )
    config = load_config(effective_path)
    now_provider = now_provider or (lambda: datetime.now(UTC))

    app = Flask(__name__)
    app.config["capsule_watch"] = config

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.get("/api/status")
    def api_status():
        snapshot = read_snapshot(config.paths.snapshot_file)
        return jsonify(snapshot)

    @app.get("/")
    def index():
        snapshot = read_snapshot(config.paths.snapshot_file)
        dashboard_data = _build_dashboard_data(snapshot, now_provider())
        return render_template("dashboard.html", **dashboard_data)

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Capsule Watch web app")
    parser.add_argument(
        "--config",
        default=os.environ.get("CAPSULE_WATCH_CONFIG", "/etc/capsule-watch/config.yaml"),
        help="Path to Capsule Watch YAML config",
    )
    args = parser.parse_args(argv)
    app = create_app(args.config)
    app_config = app.config["capsule_watch"]
    app.run(host=app_config.server.host, port=app_config.server.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def _build_dashboard_data(snapshot: dict[str, Any], now: datetime) -> dict[str, Any]:
    generated_raw = str(snapshot.get("generated_at", "unknown"))
    generated_at = _parse_timestamp(generated_raw)
    age_seconds = _age_in_seconds(generated_at, now)

    meta = {
        "generated_at": generated_raw,
        "overall_status": _normalize_status(snapshot.get("overall_status", "unknown")),
        "age_label": _format_age_label(age_seconds),
    }
    freshness = _freshness_state(age_seconds)
    meta.update(freshness)

    sections = [
        _format_section(section_key, title, snapshot.get(section_key, {}))
        for section_key, title in SECTION_DEFINITIONS
    ]
    collector_errors = _format_collector_errors(snapshot.get("collector_errors", {}))

    return {
        "meta": meta,
        "sections": sections,
        "collector_errors": collector_errors,
    }


def _format_section(section_key: str, title: str, raw_section: Any) -> dict[str, Any]:
    section = raw_section if isinstance(raw_section, Mapping) else {}
    status = _normalize_status(section.get("status", "unknown"))
    message = section.get("message") if isinstance(section.get("message"), str) else ""
    items = section.get("items", {})

    formatted = {
        "key": section_key,
        "test_id": section_key.replace("_", "-"),
        "title": title,
        "status": status,
        "message": message,
        "rows": [],
        "table_headers": [],
        "table_rows": [],
        "raw_blocks": [],
    }

    if section_key == "backups":
        _format_backups_section(items, formatted)
    elif section_key == "services":
        _format_services_section(items, formatted)
    elif section_key == "drive_health":
        _format_drive_health_section(items, formatted)
    else:
        formatted["rows"] = _flatten_rows(items)

    return formatted


def _format_backups_section(items: Any, formatted: dict[str, Any]) -> None:
    if not isinstance(items, list):
        formatted["rows"] = _flatten_rows(items)
        return

    table_rows: list[list[str]] = []
    for entry in items:
        if not isinstance(entry, Mapping):
            continue
        age_hours = entry.get("age_hours")
        age_text = (
            f"{float(age_hours):.2f}h"
            if isinstance(age_hours, int | float)
            else _format_scalar("age_hours", age_hours)
        )
        table_rows.append(
            [
                _format_scalar("client", entry.get("client")),
                age_text,
                _normalize_status(entry.get("status", "unknown")),
            ]
        )

    formatted["table_headers"] = ["Client", "Age", "Status"]
    formatted["table_rows"] = table_rows


def _format_services_section(items: Any, formatted: dict[str, Any]) -> None:
    if not isinstance(items, Mapping):
        formatted["rows"] = _flatten_rows(items)
        return

    table_rows: list[list[str]] = []
    for service, detail in sorted(items.items()):
        if isinstance(detail, Mapping):
            active = "yes" if detail.get("active") else "no"
            raw_status = _format_scalar("raw_status", detail.get("raw_status", "unknown"))
        else:
            active = "no"
            raw_status = _format_scalar("raw_status", detail)
        table_rows.append([str(service), active, raw_status])

    formatted["table_headers"] = ["Service", "Active", "Raw status"]
    formatted["table_rows"] = table_rows


def _format_drive_health_section(items: Any, formatted: dict[str, Any]) -> None:
    if not isinstance(items, Mapping):
        formatted["rows"] = _flatten_rows(items)
        return

    rows: list[tuple[str, str]] = []
    raw_output = ""
    for key, value in items.items():
        if key == "raw":
            raw_output = str(value)
            continue
        rows.append((_humanize_key(key), _format_scalar(key, value)))

    formatted["rows"] = rows
    if raw_output:
        formatted["raw_blocks"] = [("SMART raw output", raw_output)]


def _flatten_rows(items: Any) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if isinstance(items, Mapping):
        _flatten_mapping(items, rows)
    elif isinstance(items, list):
        for index, value in enumerate(items):
            rows.append((f"Item {index + 1}", _format_scalar(f"item_{index + 1}", value)))
    return rows


def _flatten_mapping(items: Mapping[str, Any], rows: list[tuple[str, str]], prefix: str = "") -> None:
    for key, value in items.items():
        full_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, Mapping):
            _flatten_mapping(value, rows, prefix=full_key)
            continue
        rows.append((_humanize_key(full_key), _format_scalar(full_key, value)))


def _format_collector_errors(raw_errors: Any) -> list[tuple[str, str]]:
    if not isinstance(raw_errors, Mapping):
        return []
    errors: list[tuple[str, str]] = []
    for collector, error in sorted(raw_errors.items()):
        errors.append((str(collector), _format_scalar("error", error)))
    return errors


def _normalize_status(raw_status: Any) -> str:
    candidate = str(raw_status).strip().lower()
    return candidate if candidate in VALID_STATUSES else "unknown"


def _parse_timestamp(raw_text: str) -> datetime | None:
    normalized = raw_text.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _age_in_seconds(generated_at: datetime | None, now: datetime) -> float | None:
    if generated_at is None:
        return None
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return (now.astimezone(UTC) - generated_at).total_seconds()


def _freshness_state(age_seconds: float | None) -> dict[str, str]:
    if age_seconds is None:
        return {"freshness_status": "unknown", "freshness_label": "unknown"}
    if age_seconds < -300:
        return {"freshness_status": "warning", "freshness_label": "future timestamp"}
    if age_seconds <= STALE_AFTER_SECONDS:
        return {"freshness_status": "healthy", "freshness_label": "fresh"}
    if age_seconds <= STALE_AFTER_SECONDS * 4:
        return {"freshness_status": "warning", "freshness_label": "stale"}
    return {"freshness_status": "critical", "freshness_label": "stale"}


def _format_age_label(age_seconds: float | None) -> str:
    if age_seconds is None:
        return "unknown"

    if age_seconds < 0:
        future_seconds = abs(age_seconds)
        if future_seconds < 60:
            return "in under 1m"
        if future_seconds < 3600:
            return f"in {int(future_seconds // 60)}m"
        if future_seconds < 86400:
            return f"in {future_seconds / 3600:.1f}h"
        return f"in {future_seconds / 86400:.1f}d"

    if age_seconds < 60:
        return "just now"
    if age_seconds < 3600:
        return f"{int(age_seconds // 60)}m ago"
    if age_seconds < 86400:
        return f"{age_seconds / 3600:.1f}h ago"
    return f"{age_seconds / 86400:.1f}d ago"


def _humanize_key(key: str) -> str:
    return key.replace(".", " / ").replace("_", " ").strip().title()


def _format_scalar(key: str, value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        if key.endswith("_kib"):
            return f"{value:,} KiB ({_kib_to_human(value)})"
        if key.endswith("_percent"):
            return f"{value}%"
        return f"{value:,}"
    if isinstance(value, float):
        if key.endswith("_hours"):
            return f"{value:.2f}h"
        return f"{value:.2f}"
    if isinstance(value, Mapping) or isinstance(value, list):
        return json.dumps(value, sort_keys=True)
    text = str(value).strip()
    return text or "n/a"


def _kib_to_human(kib_value: int) -> str:
    value = float(kib_value)
    units = ("KiB", "MiB", "GiB", "TiB", "PiB")
    unit_index = 0
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024
        unit_index += 1
    return f"{value:.1f} {units[unit_index]}"
