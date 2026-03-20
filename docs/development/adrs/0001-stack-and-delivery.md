# ADR 0001: Initial Stack And Delivery Model

## Status

Accepted

## Context

Capsule Watch needs to run reliably on a single Ubuntu host, remain easy to understand, and serve two related but different needs:

- Runtime monitoring for the backup server
- Human-readable setup documentation for building and maintaining the system

The first release should favor simplicity, low operational risk, and easy debugging over flexibility.

## Decision

We will:

- Build the monitor in Python 3.12
- Use `uv` for Python version management, dependency locking, and project command execution
- Use Flask and Jinja templates for the dashboard and small JSON API
- Run metric collection outside the request path and persist snapshots to local disk
- Use `systemd` services and timers instead of cron for recurring jobs
- Publish the setup guide as a static documentation site generated from Markdown

## Rationale

- Python is a good fit for invoking Linux utilities, parsing output, and keeping the codebase approachable
- `uv` keeps setup fast and reproducible while giving us a clean path to locked environments
- Flask is sufficient for a local dashboard without adding unnecessary framework complexity
- Persisted snapshots make the UI fast and keep failures in external commands away from user requests
- `systemd` gives better restart behavior, logs, and operational consistency than scattered cron jobs
- Static docs are easy to version, preview, and publish to GitHub Pages

## Consequences

Positive:

- Clear separation between collection, presentation, and alerting
- Reproducible Python setup from the beginning of the project
- Easy local debugging with standard Linux tools
- Documentation can be hosted independently from the monitor

Trade-offs:

- There are two delivery surfaces to maintain: the monitor app and the docs site
- `systemd` units and timers require a bit more setup than a single cron entry
- Filesystem-specific checks need graceful fallbacks for non-ext4 environments
