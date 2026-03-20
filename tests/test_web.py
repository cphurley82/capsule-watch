import json
from datetime import UTC, datetime
from pathlib import Path

from capsule_watch.web import create_app


def _write_config(tmp_path: Path, snapshot_path: Path) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
paths:
  snapshot_file: {snapshot_path}
""",
        encoding="utf-8",
    )
    return config_path


def test_health_endpoint_returns_ok(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "status.json"
    snapshot_path.write_text("{}", encoding="utf-8")
    config_path = _write_config(tmp_path, snapshot_path)
    app = create_app(config_path=config_path)
    client = app.test_client()

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_status_endpoint_reads_snapshot(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "status.json"
    snapshot_path.write_text(
        json.dumps({"generated_at": "2026-01-01T00:00:00+00:00", "overall_status": "healthy"}),
        encoding="utf-8",
    )
    config_path = _write_config(tmp_path, snapshot_path)
    app = create_app(config_path=config_path)
    client = app.test_client()

    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.get_json()["overall_status"] == "healthy"


def test_index_renders_all_sections_and_collector_errors(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "status.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-03-20T20:00:00+00:00",
                "overall_status": "warning",
                "backups": {
                    "status": "warning",
                    "items": [
                        {"client": "MacBook-Air.sparsebundle", "age_hours": 31.5, "status": "warning"}
                    ],
                },
                "storage": {
                    "status": "healthy",
                    "items": {
                        "filesystem": "/dev/sda1",
                        "total_kib": 7751271852,
                        "used_kib": 1407544424,
                        "available_kib": 5953009784,
                        "used_percent": 20,
                        "mountpoint": "/mnt/backup",
                    },
                },
                "drive_health": {
                    "status": "healthy",
                    "items": {
                        "device": "/dev/sda",
                        "driver_type": "scsi",
                        "raw": "SMART overall-health self-assessment test result: PASSED",
                    },
                },
                "services": {
                    "status": "healthy",
                    "items": {
                        "smbd": {"active": True, "raw_status": "active"},
                        "avahi-daemon": {"active": True, "raw_status": "active"},
                    },
                },
                "filesystem": {
                    "status": "healthy",
                    "items": {
                        "device": "/dev/sda1",
                        "filesystem_type": "ext4",
                        "mount_count": 1,
                        "max_mount_count": -1,
                        "volume_name": "backup",
                    },
                },
                "system": {
                    "status": "healthy",
                    "items": {
                        "uptime": "up 8 hours",
                        "memory": {"total_mb": 15805, "used_mb": 3331, "free_mb": 220},
                    },
                },
                "maintenance": {"status": "unknown", "items": {}},
                "collector_errors": {"filesystem": "Permission denied"},
            }
        ),
        encoding="utf-8",
    )
    config_path = _write_config(tmp_path, snapshot_path)
    app = create_app(
        config_path=config_path,
        now_provider=lambda: datetime(2026, 3, 20, 20, 15, tzinfo=UTC),
    )
    client = app.test_client()

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-testid="overall-status"' in html
    assert "warning" in html
    assert 'data-testid="snapshot-freshness"' in html
    assert ">fresh<" in html
    assert 'data-testid="section-backups"' in html
    assert 'data-testid="section-storage"' in html
    assert 'data-testid="section-drive-health"' in html
    assert 'data-testid="section-services"' in html
    assert 'data-testid="section-filesystem"' in html
    assert 'data-testid="section-system"' in html
    assert "MacBook-Air.sparsebundle" in html
    assert "collector-errors" in html
    assert "Permission denied" in html


def test_index_marks_snapshot_as_stale_when_old(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "status.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-03-20T18:00:00+00:00",
                "overall_status": "healthy",
                "collector_errors": {},
            }
        ),
        encoding="utf-8",
    )
    config_path = _write_config(tmp_path, snapshot_path)
    app = create_app(
        config_path=config_path,
        now_provider=lambda: datetime(2026, 3, 20, 20, 15, tzinfo=UTC),
    )
    client = app.test_client()

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-testid="snapshot-freshness"' in html
    assert ">stale<" in html


def test_index_shows_snapshot_waiting_message_when_snapshot_missing(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "status.json"
    config_path = _write_config(tmp_path, snapshot_path)
    app = create_app(
        config_path=config_path,
        now_provider=lambda: datetime(2026, 3, 20, 20, 15, tzinfo=UTC),
    )
    client = app.test_client()

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-testid="collector-errors"' in html
    assert "Snapshot file not found yet. Waiting for collector run." in html
