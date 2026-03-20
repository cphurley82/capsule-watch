# Implementation Plan

## Phase 0: Planning baseline

Deliverables:

- Repository created
- Product brief, architecture, and roadmap committed
- Initial architecture decision record committed

Exit criteria:

- The project has a stable name, scope, and implementation direction

## Phase 1: Project scaffold

Goals:

- Create the Python package layout
- Establish the `uv`-based Python workflow
- Add local development tooling
- Define configuration loading and the snapshot schema

Deliverables:

- `.python-version`
- `pyproject.toml`
- `uv.lock`
- `src/capsule_watch/` package
- Config model and example config file
- Snapshot schema module
- Basic Flask app shell with health endpoint
- Documented `uv` commands for sync, run, and test workflows

Acceptance criteria:

- A contributor can prepare the project with `uv sync`
- App starts locally and returns a placeholder dashboard page
- Configuration can be loaded from file and validated
- Snapshot schema is documented in code and fixtures

## Phase 2: Metric collectors

Goals:

- Implement the first working collectors
- Write snapshot output to disk
- Handle partial failures cleanly

Deliverables:

- Backup recency collector
- Storage usage collector
- Service status collector
- SMART collector
- Host telemetry collector
- Collector runner CLI

Acceptance criteria:

- A single command generates a valid snapshot on the Ubuntu host
- Collector failures are isolated and visible in the snapshot
- Snapshot generation works without the web UI running

## Phase 3: Dashboard UI and API

Goals:

- Build the local dashboard experience
- Expose the current snapshot through a small JSON API

Deliverables:

- Dashboard landing page
- Health banner and status cards
- Auto-refresh behavior
- `/api/status` endpoint

Acceptance criteria:

- Dashboard renders correctly from a saved snapshot
- Status color rules match the documented thresholds
- UI stays useful even when one collector has failed

## Phase 4: Alerting and scheduling

Goals:

- Add practical notifications without alert spam
- Replace ad hoc scheduling with durable service management

Deliverables:

- Alert evaluator
- Email notifier
- Alert state persistence
- `systemd` units and timers for web app, collectors, and alert checks

Acceptance criteria:

- Alert fires when a threshold is crossed
- Duplicate alerts are suppressed until state changes
- Resolved notifications are sent

## Phase 5: Documentation website

Goals:

- Publish the setup guide as a versioned website
- Cover both the DIY Time Capsule server and Capsule Watch installation

Deliverables:

- Static site generator config
- Initial docs pages
- Local preview workflow
- GitHub Pages deployment workflow or equivalent build instructions

Acceptance criteria:

- A new user can follow the guide to install the monitor
- The docs can be previewed locally and built reproducibly

## Phase 6: Hardening and first release

Goals:

- Improve reliability, packaging, and onboarding
- Cut a documented MVP release

Deliverables:

- Installation script or packaged deploy steps
- Troubleshooting guide
- Sample screenshots
- Release checklist

Acceptance criteria:

- Fresh-host install tested end to end
- README reflects actual install steps
- First tagged release created

## Cross-cutting work

### Testing

- Unit tests for parsers, threshold logic, and snapshot shaping
- Fixture-based tests for collector command output
- Lightweight integration test for snapshot generation

### Observability

- Structured logs for collectors and alert transitions
- Clear operator-facing error messages in the UI

### Configuration

- Keep host-specific paths and thresholds in config, not code
- Provide sane defaults with clear override examples

### Tooling

- Treat `uv` as the default interface for project setup and command execution
- Keep contributor docs aligned with the actual `uv` workflow as the scaffold evolves

## MVP definition of done

- Dashboard shows current status for backup freshness, storage, SMART, services, and host telemetry
- Collector and alert services run under `systemd`
- Email alerts work and avoid repeated noise
- Setup guide website is published from the repo
- Installation instructions are tested on the target Ubuntu server

## Post-MVP candidates

- Add a local web UI setting for monitor check frequency that updates the collector schedule through validated bounds and clear operator feedback
- Add push notification delivery such as `ntfy` after the email-based MVP alert flow is working
- Add a local-only maintenance action that gracefully takes the Time Machine share offline and runs a user-requested disk check
