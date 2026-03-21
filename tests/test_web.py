import json
from datetime import UTC, datetime
from pathlib import Path

from capsule_watch.web import create_app


def _write_config(
    tmp_path: Path,
    snapshot_path: Path,
    *,
    time_machine_root: str = "/srv/timecapsule",
    server_host: str = "0.0.0.0",
) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
server:
  host: {server_host}
paths:
  time_machine_root: {time_machine_root}
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
                        {"client": "source-mac.sparsebundle", "age_hours": 31.5, "status": "warning"}
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
                        "mountpoint": "/srv/timecapsule",
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
    assert "source-mac.sparsebundle" in html
    assert "collector-errors" in html
    assert "Permission denied" in html
    assert 'href="/recovery"' in html


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


def test_recovery_page_renders_backup_inventory_and_commands(tmp_path: Path) -> None:
    backup_root = tmp_path / "time-machine-share"
    backup_root.mkdir()
    bundle = backup_root / "source-mac.sparsebundle"
    bundle.mkdir()
    (bundle / "Info.plist").write_text("ok", encoding="utf-8")

    snapshot_path = tmp_path / "status.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-03-20T20:00:00+00:00",
                "overall_status": "healthy",
                "backups": {
                    "status": "healthy",
                    "items": [{"client": "source-mac.sparsebundle", "age_hours": 2.0, "status": "healthy"}],
                },
                "collector_errors": {},
            }
        ),
        encoding="utf-8",
    )
    config_path = _write_config(
        tmp_path,
        snapshot_path,
        time_machine_root=str(backup_root),
        server_host="backup-server.local",
    )
    app = create_app(config_path=config_path)
    client = app.test_client()

    response = client.get("/recovery?smb_user=backupuser", headers={"Host": "backup-server.local:8080"})
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-testid="recovery-page"' in html
    assert "source-mac.sparsebundle" in html
    assert '<code>backup-server.local</code>' in html
    assert '<code>backupuser</code>' in html
    assert "<server-host-or-ip>" not in html
    assert "<smb-username>" not in html
    assert '/Volumes/$SHARE_NAME' in html
    assert "hdiutil info | awk" in html
    assert "for mp in $(mount | awk" in html
    assert "find &#34;$SHARE_MOUNT&#34; -maxdepth 1 -type d -name &#34;*.sparsebundle&#34; -print" in html
    assert "test -d &#34;$SOURCE_BUNDLE&#34;" in html
    assert "mount_smbfs" in html
    assert "hdiutil attach -readonly" in html
    assert "BACKUP_VOLUME=&#34;/Volumes/Backups of ${BUNDLE_NAME%.sparsebundle}&#34;" in html
    assert "SNAPSHOT_NAME=&#34;&lt;snapshot-name&gt;.previous&#34;" in html
    assert "SOURCE_VOLUME=&#34;&lt;source-volume&gt;&#34;" in html
    assert "SOURCE_REL_PATH=&#34;&lt;path-inside-source-volume&gt;&#34;" in html
    assert "SOURCE_PATH=&#34;$BACKUP_VOLUME/$SNAPSHOT_NAME/$SOURCE_VOLUME/$SOURCE_REL_PATH&#34;" in html
    assert "echo &#34;$SOURCE_PATH&#34;" in html
    assert "rsync -avh" in html
    assert "rsync -avh &#34;$SOURCE_PATH&#34; &#34;$HOME/Recovered-from-TimeMachine/&#34;" in html
    assert "/Users/<username>/" not in html
    assert "Full Disk Access" in html
    assert "sudo smbstatus" in html
    assert "sudo systemctl restart smbd" in html
    assert "time-machine-share" in html


def test_recovery_page_prefers_snapshot_recovery_metadata(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "status.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-03-20T20:00:00+00:00",
                "overall_status": "healthy",
                "recovery": {
                    "status": "healthy",
                    "items": {
                        "share_name": "tm-share",
                        "server_hosts": ["backup.local"],
                        "backups": [
                            {
                                "source_mac_name": "Source-Mac",
                                "bundle_name": "Source-Mac.sparsebundle",
                                "bundle_path": "/srv/timecapsule/Source-Mac.sparsebundle",
                                "status": "healthy",
                            }
                        ],
                    },
                },
                "collector_errors": {},
            }
        ),
        encoding="utf-8",
    )
    config_path = _write_config(tmp_path, snapshot_path, time_machine_root=str(tmp_path / "missing"))
    app = create_app(config_path=config_path)
    client = app.test_client()

    response = client.get("/recovery")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Source-Mac.sparsebundle" in html
    assert "tm-share" in html
    assert "backup.local" in html


def test_recovery_page_uses_request_host_when_server_host_is_unspecified(tmp_path: Path) -> None:
    backup_root = tmp_path / "backup-empty"
    backup_root.mkdir()
    snapshot_path = tmp_path / "status.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-03-20T20:00:00+00:00",
                "overall_status": "unknown",
                "collector_errors": {},
            }
        ),
        encoding="utf-8",
    )
    config_path = _write_config(tmp_path, snapshot_path, time_machine_root=str(backup_root), server_host="0.0.0.0")
    app = create_app(config_path=config_path)
    client = app.test_client()

    response = client.get("/recovery", headers={"Host": "10.20.30.40:8080"})
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '<code>10.20.30.40</code>' in html


def test_recovery_page_shows_empty_state_when_no_backups_found(tmp_path: Path) -> None:
    backup_root = tmp_path / "backup-empty"
    backup_root.mkdir()
    snapshot_path = tmp_path / "status.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-03-20T20:00:00+00:00",
                "overall_status": "unknown",
                "collector_errors": {},
            }
        ),
        encoding="utf-8",
    )
    config_path = _write_config(tmp_path, snapshot_path, time_machine_root=str(backup_root))
    app = create_app(config_path=config_path)
    client = app.test_client()

    response = client.get("/recovery")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "No sparsebundle backups found under the configured Time Machine root." in html
