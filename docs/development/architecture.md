# Architecture

## Summary

Capsule Watch will be a small Python application paired with scheduled collectors and a static documentation site. The operational principle is simple: collect system and backup metrics on a schedule, persist a snapshot locally, and render the latest known state through a read-only web dashboard.

## System context

The target environment is an Ubuntu server already configured as a Time Machine destination via Samba. Capsule Watch runs on that same machine and reads local system state from standard Linux commands and files.

## Core components

### 1. Web application

- Python application using Flask and Jinja templates
- Serves the dashboard UI and a small JSON API
- Reads the latest snapshot from disk instead of running expensive checks in the request path
- Intended for local-network access only

### 2. Collector service

- Runs on a schedule via `systemd` timer
- Keeps the collection cadence outside the web UI in the MVP; a later enhancement can let the local dashboard write a validated timer override
- Executes read-mostly collectors and writes a normalized snapshot file
- Handles timeouts and partial failures per collector
- Produces both a machine-readable snapshot and operator-friendly log messages

### 3. Alert service

- Runs on a separate schedule via `systemd` timer
- Evaluates thresholds against the latest snapshot
- Persists alert state so it only notifies on transitions
- Sends resolved notifications when an alert condition clears
- Uses email for MVP alert delivery; push channels such as `ntfy` are a later enhancement

### 4. Static documentation site

- Maintained as Markdown in the repo
- Built as a static site for GitHub Pages and optional local hosting
- Contains both DIY Time Capsule setup instructions and Capsule Watch install/configuration steps

## Python environment strategy

- Use `uv` as the canonical tool for Python version management, dependency resolution, lockfile generation, and task execution
- Keep project metadata in `pyproject.toml` with a committed `uv.lock`
- Use `uv sync --frozen` for reproducible installs once the project scaffold exists
- For production services, prefer explicit executables from the project virtual environment over shell activation

## Proposed runtime layout

- `/opt/capsule-watch/` application code and templates
- `/etc/capsule-watch/config.yaml` operator configuration
- `/var/lib/capsule-watch/status.json` latest collected snapshot
- `/var/lib/capsule-watch/alerts.json` alert state cache
- `/var/log/capsule-watch/` service and maintenance logs

## Data model

The snapshot should be versioned and structured so the UI and alerting logic share the same source of truth.

Suggested top-level sections:

- `generated_at`
- `overall_status`
- `backups`
- `storage`
- `drive_health`
- `services`
- `filesystem`
- `system`
- `maintenance`
- `collector_errors`

## Collectors

### Backup recency

- Inspect configured sparsebundle paths or backup directories
- Determine most recent meaningful file modification time
- Compute age in hours and classify against thresholds

### Storage usage

- Read filesystem usage from `df`
- Track total, used, available, and utilization percentage
- Associate usage with either the shared volume or per-client data where feasible

### SMART health

- Use `smartctl` with tightly scoped sudo permissions
- Capture overall health, drive temperature, power-on hours, key attributes, and latest self-test

### Services

- Check `smbd` and `avahi-daemon` via `systemctl`
- Treat `nmbd` as optional because many modern Samba Time Machine setups do not require it

### Filesystem health

- For ext4 volumes, use `tune2fs` to read mount count and fsck scheduling metadata
- If the filesystem is not ext4, mark this panel as unsupported rather than failing the whole snapshot

### Host telemetry

- Use `uptime`, `/proc/loadavg`, `free`, and `/sys/class/thermal` where available
- Keep collection lightweight enough for low-power hardware

## Request flow

1. Collector timer triggers the collector service.
2. Collectors run independently with timeouts.
3. Service writes a complete snapshot and notes any partial failures.
4. Web app reads the latest snapshot and renders the dashboard.
5. Alert timer evaluates thresholds and sends transition-based notifications.

## Security model

- Dashboard is read-only in the MVP
- No public internet exposure
- Use a dedicated service user with no shell
- Limit sudo access to specific commands such as `smartctl`
- Keep disruptive maintenance actions out of the MVP dashboard; a later local-only workflow can let an operator gracefully take the Time Machine share offline before starting a disk check
- Prefer reverse proxy or SSH port forwarding over exposing raw application ports externally

## Privileged command strategy

- Run the web app, collectors, and alert service as an unprivileged `capsule-watch` service user
- Do not run the full application as `root`
- Do not prompt for or store a human sudo password in the web UI
- Grant narrowly scoped `sudoers` access only for the exact commands that require elevation, preferably through root-owned wrapper scripts
- For disruptive repair workflows, prefer starting a dedicated one-shot `systemd` service over letting the app execute arbitrary privileged commands directly

## Deployment model

Initial deployment should be simple:

- Flask app managed by `systemd`
- Collector and alert jobs managed by `systemd` timers
- Python environment provisioned through `uv`, with services pointing at the synced project environment
- Optional reverse proxy later for nicer routing and TLS on the local network
- Docs site deployable to GitHub Pages, with optional local hosting behind the same reverse proxy

## Boot and service startup

- Enable the web application as a `systemd` service so it starts automatically on boot
- Run collectors and alert checks through `systemd` timers instead of long-lived background loops
- Use `OnBootSec` and `OnUnitActiveSec` for recurring jobs, with `Persistent=true` so missed runs are handled after downtime
- Use `WantedBy=multi-user.target` for the web service and `WantedBy=timers.target` for timers
- Configure services with `Restart=on-failure` and explicit paths into the synced project environment

## Notable design choices

- Avoid collecting live metrics during page loads so the dashboard stays responsive
- Prefer `systemd` timers over cron for better observability and service-level control
- Keep scheduler changes out of the MVP dashboard, then consider a guarded local-only UI control for adjusting check frequency later
- Treat manual repair flows separately from passive monitoring; a future enhancement can add a guided "take share offline and run disk check" action
- Keep the docs site separate from the runtime dashboard so instructional content can evolve independently
- Support graceful degradation where host-specific tools or filesystems differ
