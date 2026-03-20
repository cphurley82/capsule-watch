# Development Workflow

## Status

Active. This document reflects the current `uv`-based workflow used in this repository.

## Tooling baseline

- Use `uv` as the single entry point for Python setup and dependency management
- Commit both `pyproject.toml` and `uv.lock`
- Keep the project on a pinned Python version via `.python-version`
- Use a `src/` layout for the application package

## Core commands

Environment setup:

- `uv sync`
- `uv sync --extra dev`

Test:

- `uv run pytest`
- `uv run pytest -q`

Run app CLIs:

- `uv run capsule-watch-collectors --config /etc/capsule-watch/config.yaml`
- `uv run capsule-watch-alerts --config /etc/capsule-watch/config.yaml`
- `uv run capsule-watch-web --config /etc/capsule-watch/config.yaml`

## TDD expectation

- Add or update tests before implementing behavior changes when practical
- Prefer small fixture-driven unit tests for parser and collector logic
- Keep integration checks lightweight and focused on snapshot generation and web endpoints

## Why `uv`

- Faster environment and dependency operations
- Reproducible lockfile-based installs
- Cleaner contributor onboarding than manually managing `venv` and `pip`
- Good fit for a small Python service that runs on one Ubuntu host and can still be developed from another machine

## Deployment expectation

- Development and packaging use `uv`
- Server installs use `uv sync --frozen`
- `systemd` units should call executables from the synced environment directly, avoiding shell activation in service definitions
