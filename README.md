# Capsule Watch

Capsule Watch is a self-hosted monitoring dashboard for a DIY Apple Time Machine backup server running on Ubuntu. The project has two deliverables:

- A local-first monitoring app for the backup server
- A companion documentation site with setup and troubleshooting guides

This repository currently contains the design baseline and implementation plan so we can build from a clear, versioned foundation.

## Python workflow

Capsule Watch will use `uv` from the start for Python version pinning, dependency locking, environment sync, and common project commands. We are not bootstrapping that tooling yet, but the architecture and implementation plan now assume an `uv`-managed workflow for both development and deployment preparation.

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

Planning and design are complete enough to begin implementation. The next milestone is to scaffold the Python application and define the snapshot schema used by the collectors, API, and UI.
