# Capsule Watch

Capsule Watch is a self-hosted monitoring dashboard for a DIY Apple Time Machine backup server running on Ubuntu. The project has two deliverables:

- A local-first monitoring app for the backup server
- A companion documentation site with setup and troubleshooting guides

This repository includes both the design baseline and an initial runnable Python scaffold for the monitoring application.

## Setup guides

- [DIY Time Capsule setup](docs/diy-time-capsule-setup.md)
- [Disk formatting for Time Machine](docs/disk-formatting-for-time-machine.md)
- [Install Capsule Watch](docs/install-capsule-watch.md)

## Python workflow

Capsule Watch uses `uv` for Python version pinning, dependency locking, environment sync, and common project commands.

Typical local commands:

- `uv sync --extra dev`
- `uv run pytest`
- `uv run capsule-watch-collectors --config /etc/capsule-watch/config.yaml`
- `uv run capsule-watch-alerts --config /etc/capsule-watch/config.yaml`
- `uv run capsule-watch-web --config /etc/capsule-watch/config.yaml`

## Project goals

- Monitor backup freshness for each Mac using the Time Machine share
- Track server health, storage usage, SMART status, and key services
- Send low-noise alerts when the backup system needs attention
- Publish clear setup instructions for building the DIY Time Capsule server and installing Capsule Watch
- Keep the operational model simple enough for a home lab or family backup server

## MVP scope

- Read-only dashboard for local network use
- JSON status snapshot generated on a schedule
- Per-Mac backup recency and storage usage checks
- SMART and temperature checks for the backup drive
- Samba and Avahi service health checks
- Optional email alerts with stateful suppression in the MVP
- Static documentation site for setup instructions

## Repo layout

- `docs/` contains user-facing setup and troubleshooting documentation
- `docs/install-capsule-watch.md` covers installing Capsule Watch after the DIY Time Capsule server is already working
- `docs/development/product-brief.md` defines the problem, users, scope, and success criteria
- `docs/development/architecture.md` defines the technical design and runtime model
- `docs/development/implementation-plan.md` breaks the build into practical phases
- `docs/development/development-workflow.md` defines the planned `uv`-based Python workflow
- `docs/development/setup-guide-plan.md` outlines the companion documentation website
- `docs/development/adrs/0001-stack-and-delivery.md` captures the first architecture decisions; ADR stands for Architecture Decision Record

## Current status

The repository now includes a tested initial implementation for config loading, snapshot persistence, collectors, alert transitions, and Flask web endpoints. The next milestone is to expand collector depth, notification delivery, and production-hardening details.
