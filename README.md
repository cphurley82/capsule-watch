# Capsule Watch

Capsule Watch is a self-hosted monitoring dashboard for a DIY Apple Time Machine backup server running on Ubuntu.

The project has two deliverables:

- A local-first monitoring app for the backup server
- A companion documentation set with setup and troubleshooting guides

## What works today

The repository includes a tested initial implementation with:

- Config loading and validation from YAML
- Snapshot persistence and loading from local disk
- Collectors for backup recency, storage, SMART health, services, filesystem metadata, and host telemetry
- Alert transition evaluation with persisted active state
- Flask web endpoints for `/`, `/recovery`, `/healthz`, and `/api/status`
- Versioned `systemd` units and timers for web, collector, and alert jobs

Email delivery and push channels are still planned enhancements. The current alert service computes transitions and stores state.

## User docs

- [DIY Time Capsule setup](docs/diy-time-capsule-setup.md) (Ubuntu + Samba)
- [Disk formatting for Time Machine](docs/disk-formatting-for-time-machine.md)
- [Verify and restore Time Machine backups (CLI)](docs/verify-and-restore-time-machine-backups.md)
- [Install Capsule Watch](docs/install-capsule-watch.md) (service user, config, sudoers, `systemd`)

## Python workflow

Capsule Watch uses `uv` for Python version pinning, dependency locking, environment sync, and common project commands.

Typical local development commands:

- `uv sync --extra dev`
- `uv run pytest -q`
- `uv run capsule-watch-collectors --config /etc/capsule-watch/config.yaml`
- `uv run capsule-watch-alerts --config /etc/capsule-watch/config.yaml`
- `uv run capsule-watch-web --config /etc/capsule-watch/config.yaml`

For command-by-command setup and iteration, see [Local development guide](docs/development/local-development.md).  
For development standards and commit expectations, see [Development standards](docs/development/development-standards.md).

## Repo layout

- `docs/` contains user-facing setup and troubleshooting documentation
- `docs/development/` contains development-focused docs, plans, and ADRs
- `config/config.example.yaml` is the versioned baseline runtime config
- `deploy/systemd/` contains versioned `systemd` unit and timer files
- `src/capsule_watch/` contains the application package
- `tests/` contains unit and fixture-based tests

## Current status

The foundation is in place and running locally with `systemd`. Next milestones are production hardening, richer dashboard UX, and full notification delivery.
