from datetime import UTC, datetime
from pathlib import Path

from capsule_watch.snapshot import empty_snapshot, read_snapshot, write_snapshot


def test_write_and_read_snapshot_round_trip(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "status.json"
    snapshot = empty_snapshot(datetime(2026, 1, 1, 0, 0, tzinfo=UTC))
    snapshot["overall_status"] = "healthy"
    snapshot["services"] = {"status": "healthy", "items": {"smbd": {"active": True}}}

    write_snapshot(snapshot_path, snapshot)
    loaded = read_snapshot(snapshot_path)

    assert loaded["overall_status"] == "healthy"
    assert loaded["services"]["items"]["smbd"]["active"] is True
    assert loaded["generated_at"] == "2026-01-01T00:00:00+00:00"


def test_read_snapshot_missing_file_returns_empty_snapshot(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "missing.json"

    loaded = read_snapshot(snapshot_path)

    assert loaded["overall_status"] == "unknown"
    assert "collector_errors" in loaded
