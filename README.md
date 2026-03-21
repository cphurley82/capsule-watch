# Capsule Watch

Capsule Watch is a self-hosted monitoring and recovery dashboard for DIY Apple Time Machine servers running on Ubuntu.

It helps you answer the questions that matter after setup:

- Are Macs still backing up recently enough?
- Is the backup volume getting full?
- Is the drive healthy?
- Are Samba and Avahi running?
- Can I still mount a backup and recover files from another Mac?

Capsule Watch is designed for local-network, single-host deployments where you want clear status and practical recovery guidance without logging into Ubuntu to manually check everything.

## Features

- Read-only web dashboard with overall health status and per-section detail
- Backup freshness checks based on sparsebundle activity
- Storage usage reporting for the Time Machine volume
- SMART overall health collection for the backup drive
- Service checks for Samba and Avahi
- ext4 filesystem metadata checks when supported
- Host telemetry such as uptime and memory usage
- Recovery Assistant page that generates validated Mac recovery commands
- JSON status API at `/api/status`
- `systemd` services and timers for web, collectors, and alert evaluation

Current releases focus on local monitoring, recovery guidance, and persisted alert state. Outbound notification delivery is not wired in yet.

## Requirements

Capsule Watch assumes:

- an Ubuntu host already configured as a working Samba Time Machine destination
- `systemd` as the service manager
- Python 3.12+ and `uv`
- `smartctl`, `df`, `free`, `uptime`, and `systemctl` available on the host
- local or LAN access to the dashboard

Recommended:

- ext4 for the backup volume if you want filesystem metadata checks
- `avahi-daemon` if you rely on Bonjour discovery from Macs

## Quick Start

1. Prepare the backup disk and mount point:
   [Disk formatting for Time Machine](docs/disk-formatting-for-time-machine.md)
2. Configure Samba and verify Time Machine backups are working:
   [DIY Time Capsule setup](docs/diy-time-capsule-setup.md)
3. Install Capsule Watch on the Ubuntu server:
   [Install Capsule Watch](docs/install-capsule-watch.md)
4. Validate recovery from another Mac:
   [Verify and restore Time Machine backups](docs/verify-and-restore-time-machine-backups.md)

After installation, open:

- `http://<server-ip>:8080/` for the dashboard
- `http://<server-ip>:8080/recovery` for guided recovery commands

## Documentation

### For Operators

- [Install Capsule Watch](docs/install-capsule-watch.md)
- [DIY Time Capsule setup](docs/diy-time-capsule-setup.md)
- [Disk formatting for Time Machine](docs/disk-formatting-for-time-machine.md)
- [Verify and restore Time Machine backups](docs/verify-and-restore-time-machine-backups.md)

### For Contributors

- [Development docs index](docs/development/README.md)

## How It Works

Capsule Watch keeps expensive checks out of the request path.

1. Scheduled collectors gather backup and host state on the Ubuntu server.
2. The latest snapshot is written to local disk.
3. The web UI reads that snapshot and renders the dashboard and recovery workflow.
4. A separate alert evaluator tracks state transitions for future notification delivery.

That model keeps the web UI fast, predictable, and safe to expose on a trusted local network.

## Contributing

Capsule Watch uses `uv` for environment management and test execution.

Typical contributor workflow:

```bash
uv sync --extra dev
uv run pytest -q
```

For the full contributor workflow, coding expectations, and architecture notes, start with [Development docs index](docs/development/README.md).
