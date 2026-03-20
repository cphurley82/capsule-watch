# Development Standards

## Purpose

This document defines development standards and expectations.

For setup and day-to-day commands, use the canonical runbook:
- [Local development guide](local-development.md)

## Tooling baseline

- Use `uv` as the single entry point for Python setup and dependency management
- Commit both `pyproject.toml` and `uv.lock`
- Keep the project on a pinned Python version via `.python-version`
- Use a `src/` layout for the application package

## Development expectations

- Add or update tests before implementing behavior changes when practical
- Prefer small fixture-driven unit tests for parser and collector logic
- Keep integration checks lightweight and focused on snapshot generation and web endpoints
- Keep user and development docs aligned with implementation changes

## Definition of ready-to-commit

- `uv run pytest -q` passes locally
- New behavior is covered by tests
- Docs are updated for user-visible or operator-visible changes
- Staged changes avoid machine-specific paths, hostnames, and secrets

## Why `uv`

- Faster environment and dependency operations
- Reproducible lockfile-based installs
- Cleaner contributor onboarding than manually managing `venv` and `pip`
- Good fit for a small Python service that runs on one Ubuntu host and can still be developed from another machine

## Deployment expectation

- Development and packaging use `uv`
- Server installs use `uv sync --frozen`
- `systemd` units should call executables from the synced environment directly, avoiding shell activation in service definitions
