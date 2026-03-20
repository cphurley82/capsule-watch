# Development Workflow

## Status

Planned. This document defines the intended Python workflow before we scaffold the actual app.

## Tooling baseline

- Use `uv` as the single entry point for Python setup and dependency management
- Commit both `pyproject.toml` and `uv.lock` once Phase 1 begins
- Keep the project on a pinned Python version via `.python-version`
- Use a `src/` layout for the application package

## Planned commands

These are the commands we expect to support once the scaffold exists:

- `uv sync`
- `uv run pytest`
- `uv run python -m capsule_watch.collectors`
- `uv run python -m capsule_watch.web`

## Why `uv`

- Faster environment and dependency operations
- Reproducible lockfile-based installs
- Cleaner contributor onboarding than manually managing `venv` and `pip`
- Good fit for a small Python service that will likely be run on one Ubuntu host and occasionally worked on from another machine

## Deployment expectation

- Development and packaging use `uv`
- The server setup flow will use `uv sync --frozen` once the lockfile exists
- `systemd` units should call executables from the synced environment directly, avoiding shell activation in service definitions
