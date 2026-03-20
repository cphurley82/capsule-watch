import json
from pathlib import Path

from capsule_watch.web import create_app


def test_health_endpoint_returns_ok(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("{}", encoding="utf-8")
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
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
paths:
  snapshot_file: {snapshot_path}
""",
        encoding="utf-8",
    )
    app = create_app(config_path=config_path)
    client = app.test_client()

    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.get_json()["overall_status"] == "healthy"
