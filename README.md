# Capsule Watch

Capsule Watch is a self-hosted monitoring and recovery dashboard for DIY Mac backup servers on Ubuntu.

It is for people who already run, or are building, their own backup server and want clear answers to the questions that matter after setup:

- Are Macs still backing up recently enough?
- Is the backup volume getting full?
- Is the drive healthy?
- Are Samba and Avahi running?
- Can I still mount a backup and recover files from another Mac?

Capsule Watch is designed for local-network, single-host deployments where you want practical status and recovery guidance without logging into Ubuntu for every check.

Capsule Watch does not create backups by itself. It monitors a backup server that you set up separately and helps you verify that recovery is still possible.

The setup guides in this repo support three backup layouts:

- Time Machine only
- rsync + ZFS snapshots only
- Time Machine plus rsync + ZFS snapshots together

The most complete documented setup is the combined Time Machine + rsync + ZFS path. Capsule Watch's current monitoring features are still most focused on the Time Machine side, while the rsync/ZFS guides are useful for building and operating the rsync backup path.

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

Capsule Watch assumes you already have, or are about to set up:

- an Ubuntu host for your backup server
- at least one backup path you want to monitor
- `systemd` as the service manager
- Python 3.12+ and `uv`
- `smartctl`, `df`, `free`, `uptime`, and `systemctl` available on the host
- local or LAN access to the dashboard

Recommended for the documented setup path:

- a ZFS-backed backup volume
- `avahi-daemon` if you rely on Bonjour discovery from Macs

For the Time Machine path, you also need Samba. For the rsync path, you also need SSH access and ZFS snapshots if you want versioned history.

## Setup Overview

If you are starting from scratch and want a basic Time Machine server, use these guides:

1. Prepare the backup disk and ZFS datasets:
   [Prepare a ZFS Backup Disk for Time Machine and rsync](docs/disk-formatting-for-time-machine.md)
2. Set up the backup server and get Time Machine working:
   [DIY Time Capsule setup](docs/diy-time-capsule-setup.md)
3. Install Capsule Watch on the Ubuntu server:
   [Install Capsule Watch](docs/install-capsule-watch.md)
4. Validate recovery from another Mac:
   [Verify and restore Time Machine backups](docs/verify-and-restore-time-machine-backups.md)

If you want to add an rsync-based backup path with ZFS snapshots alongside Time Machine, or build that rsync path on its own, use these guides:

1. Configure the rsync destination on the Ubuntu server:
   [Add the rsync Backup Path on Ubuntu](docs/configure-rsync-backup-on-ubuntu.md)
2. Configure the Mac-side rsync job:
   [Set Up rsync Backups from macOS](docs/rsync-backups-from-macos.md)
3. Validate rsync latest-state and snapshot restores:
   [Verify and restore rsync + ZFS backups](docs/verify-and-restore-rsync-backups.md)
4. Plan replication and rotated backup disks:
   [ZFS Replication and Backup Rotation](docs/zfs-replication-and-rotation.md)
5. If you need retention policy details later:
   [ZFS Snapshot Retention and Pruning for rsync Backups](docs/zfs-snapshot-retention-and-pruning.md)
   and [Time Machine Retention and Archive Rollover](docs/time-machine-retention-and-rollover.md)

If you want both backup paths, follow the Time Machine sequence first and then add the rsync + ZFS sequence.

After installation, open:

- `http://<server-ip>:8080/` for the dashboard
- `http://<server-ip>:8080/recovery` for guided recovery commands

## Operator Guides

- [Prepare a ZFS Backup Disk for Time Machine and rsync](docs/disk-formatting-for-time-machine.md)
- [DIY Time Capsule setup](docs/diy-time-capsule-setup.md)
- [Add the rsync Backup Path on Ubuntu](docs/configure-rsync-backup-on-ubuntu.md)
- [Install Capsule Watch](docs/install-capsule-watch.md)
- [Verify and restore Time Machine backups](docs/verify-and-restore-time-machine-backups.md)
- [Verify and restore rsync + ZFS backups](docs/verify-and-restore-rsync-backups.md)
- [Set Up rsync Backups from macOS](docs/rsync-backups-from-macos.md)
- [ZFS Replication and Backup Rotation](docs/zfs-replication-and-rotation.md)
- [ZFS Snapshot Retention and Pruning for rsync Backups](docs/zfs-snapshot-retention-and-pruning.md)
- [Time Machine Retention and Archive Rollover](docs/time-machine-retention-and-rollover.md)

## Contributor Docs

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
