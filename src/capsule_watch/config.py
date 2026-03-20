"""Configuration loading for Capsule Watch."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when config validation fails."""


@dataclass(slots=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8080


@dataclass(slots=True)
class PathsConfig:
    time_machine_root: str = "/srv/timecapsule"
    snapshot_file: str = "/var/lib/capsule-watch/status.json"
    alerts_file: str = "/var/lib/capsule-watch/alerts.json"


@dataclass(slots=True)
class ServicesConfig:
    samba_unit: str = "smbd"
    avahi_unit: str = "avahi-daemon"


@dataclass(slots=True)
class ThresholdsConfig:
    backup_warning_hours: int = 26
    backup_critical_hours: int = 48
    disk_warning_percent: int = 85
    disk_critical_percent: int = 95


@dataclass(slots=True)
class EmailAlertConfig:
    enabled: bool = False
    from_address: str = "capsule-watch@example.com"
    to: list[str] = field(default_factory=list)
    smtp_host: str = "localhost"
    smtp_port: int = 25
    username: str = ""
    password: str = ""
    starttls: bool = False


@dataclass(slots=True)
class AlertsConfig:
    email: EmailAlertConfig = field(default_factory=EmailAlertConfig)


@dataclass(slots=True)
class AppConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    services: ServicesConfig = field(default_factory=ServicesConfig)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    alerts: AlertsConfig = field(default_factory=AlertsConfig)


def load_config(path: str | Path) -> AppConfig:
    """Load and validate configuration from YAML."""
    path_obj = Path(path)
    try:
        raw_text = path_obj.read_text(encoding="utf-8")
    except FileNotFoundError:
        return AppConfig()
    except PermissionError as exc:
        raise ConfigError(f"Permission denied reading config file: {path_obj}") from exc

    raw = yaml.safe_load(raw_text)
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ConfigError("Top-level config must be a mapping")

    server_data = _as_mapping(raw.get("server"), "server")
    paths_data = _as_mapping(raw.get("paths"), "paths")
    services_data = _as_mapping(raw.get("services"), "services")
    thresholds_data = _as_mapping(raw.get("thresholds"), "thresholds")
    alerts_data = _as_mapping(raw.get("alerts"), "alerts")
    email_data = _as_mapping(alerts_data.get("email"), "alerts.email")

    port = int(server_data.get("port", 8080))
    if port < 1 or port > 65535:
        raise ConfigError("Invalid server.port, expected 1-65535")

    smtp_port = int(email_data.get("smtp_port", 25))
    if smtp_port < 1 or smtp_port > 65535:
        raise ConfigError("Invalid alerts.email.smtp_port, expected 1-65535")

    to_addresses = email_data.get("to", [])
    if not isinstance(to_addresses, list):
        raise ConfigError("alerts.email.to must be a list")
    to_addresses = [str(item) for item in to_addresses]

    return AppConfig(
        server=ServerConfig(
            host=str(server_data.get("host", "0.0.0.0")),
            port=port,
        ),
        paths=PathsConfig(
            time_machine_root=str(paths_data.get("time_machine_root", "/srv/timecapsule")),
            snapshot_file=str(
                paths_data.get("snapshot_file", "/var/lib/capsule-watch/status.json")
            ),
            alerts_file=str(paths_data.get("alerts_file", "/var/lib/capsule-watch/alerts.json")),
        ),
        services=ServicesConfig(
            samba_unit=str(services_data.get("samba_unit", "smbd")),
            avahi_unit=str(services_data.get("avahi_unit", "avahi-daemon")),
        ),
        thresholds=ThresholdsConfig(
            backup_warning_hours=int(thresholds_data.get("backup_warning_hours", 26)),
            backup_critical_hours=int(thresholds_data.get("backup_critical_hours", 48)),
            disk_warning_percent=int(thresholds_data.get("disk_warning_percent", 85)),
            disk_critical_percent=int(thresholds_data.get("disk_critical_percent", 95)),
        ),
        alerts=AlertsConfig(
            email=EmailAlertConfig(
                enabled=bool(email_data.get("enabled", False)),
                from_address=str(
                    email_data.get("from", email_data.get("from_address", "capsule-watch@example.com"))
                ),
                to=to_addresses,
                smtp_host=str(email_data.get("smtp_host", "localhost")),
                smtp_port=smtp_port,
                username=str(email_data.get("username", "")),
                password=str(email_data.get("password", "")),
                starttls=bool(email_data.get("starttls", False)),
            )
        ),
    )


def _as_mapping(value: Any, key: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"{key} must be a mapping")
    return value
