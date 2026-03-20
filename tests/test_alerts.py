from capsule_watch.alerts import evaluate_alert_transitions


def test_alert_transitions_new_and_resolved() -> None:
    previous = {
        "active": {
            "backup_recency": {"severity": "warning", "message": "Stale backup"},
            "services": {"severity": "critical", "message": "smbd down"},
        }
    }
    snapshot = {
        "backups": {"status": "healthy"},
        "services": {"status": "critical", "message": "avahi-daemon inactive"},
        "storage": {"status": "warning", "message": "Disk usage high"},
    }

    result = evaluate_alert_transitions(previous_state=previous, snapshot=snapshot)

    assert "backup_recency" in result["resolved"]
    assert "services" in result["active"]
    assert "storage" in result["new"]
    assert result["active"]["storage"]["severity"] == "warning"
