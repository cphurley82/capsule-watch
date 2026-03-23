# Implementation Plan

## Current snapshot (March 2026)

- Phase 0 is complete.
- Phase 1 scaffold is complete (`pyproject.toml`, `uv.lock`, package layout, config, snapshot helpers, web shell).
- Phase 2 collector baseline is complete and tested.
- Phase 3 dashboard, Recovery Assistant, and API endpoints are complete.
- Phase 4 scheduling and alert state transitions are complete at baseline level; notification transport is still pending.
- Phase 5 docs content exists in-repo; static-site build/publish automation is still pending.
- Phase 6 hardening and release polish is in progress.

## Phase 0: Planning baseline

Deliverables:

- Repository created
- Architecture and roadmap committed
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
- Recovery Assistant page
- `/api/status` endpoint

Acceptance criteria:

- Dashboard renders correctly from a saved snapshot
- Recovery page generates usable backup browse and restore commands
- Status color rules match the documented thresholds
- UI stays useful even when one collector has failed

## Phase 4: Alerting and scheduling

Goals:

- Add practical notifications without alert spam
- Replace ad hoc scheduling with durable service management

Deliverables:

- Alert evaluator
- Alert state persistence
- `systemd` units and timers for web app, collectors, and alert checks
- Notification transport design and implementation follow-up

Acceptance criteria:

- Alert state transitions are computed when thresholds are crossed
- Duplicate transitions are suppressed until state changes
- Web, collector, and alert services run reliably under `systemd`

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
- Recovery Assistant helps an operator mount, browse, and copy files from a backup
- Collector and alert services run under `systemd`
- Docs are usable directly from the repository
- Installation instructions are tested on the target Ubuntu server

## Post-MVP candidates

- Add a local web UI setting for monitor check frequency that updates the collector schedule through validated bounds and clear operator feedback
- Add push notification delivery such as `ntfy` after the email-based MVP alert flow is working
- Add a local-only maintenance action that gracefully takes the Time Machine share offline and runs a user-requested disk check
- Broaden Capsule Watch beyond its current Time Machine-centric assumptions so it works well for `rsync + ZFS`-only deployments and for parallel Time Machine + rsync setups, including collector coverage, dashboard language, and recovery guidance
