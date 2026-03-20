from pathlib import Path

import pytest

from capsule_watch.config import AppConfig, ConfigError, load_config


def test_load_config_uses_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("{}", encoding="utf-8")

    config = load_config(config_path)

    assert isinstance(config, AppConfig)
    assert config.server.host == "0.0.0.0"
    assert config.server.port == 8080
    assert config.paths.time_machine_root == "/srv/timecapsule"
    assert config.services.samba_unit == "smbd"
    assert config.thresholds.backup_warning_hours == 26
    assert config.alerts.email.enabled is False


def test_load_config_applies_overrides(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
server:
  host: 127.0.0.1
  port: 9090
paths:
  time_machine_root: /mnt/backups
thresholds:
  disk_critical_percent: 92
alerts:
  email:
    enabled: true
    to:
      - admin@example.com
""",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.server.host == "127.0.0.1"
    assert config.server.port == 9090
    assert config.paths.time_machine_root == "/mnt/backups"
    assert config.thresholds.disk_critical_percent == 92
    assert config.alerts.email.enabled is True
    assert config.alerts.email.to == ["admin@example.com"]


def test_load_config_rejects_invalid_port(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
server:
  port: 70000
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="server.port"):
        load_config(config_path)


def test_load_config_reports_permission_denied(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("{}", encoding="utf-8")
    config_path.chmod(0)

    with pytest.raises(ConfigError, match="Permission denied reading config file"):
        load_config(config_path)
