# Development Docs

This section collects contributor-focused documentation for Capsule Watch.

If you are new to the project, start here instead of reading individual planning docs in isolation.

## Start here

- [Local development guide](local-development.md): practical day-to-day commands, test flows, and the fast systemd-backed iteration workflow
- [Development standards](development-standards.md): commit expectations, testing rules, and tooling conventions
- [Architecture](architecture.md): runtime model, core components, security boundaries, and deployment assumptions

For Mac-side rsync backup setup and automation, use the operator guide in the top-level docs directory:

- [Set Up rsync Backups from macOS](../rsync-backups-from-macos.md): Mac-side rsync setup, manual backup workflow, and laptop-friendly `launchd` automation

## Product and roadmap context

- [Implementation plan](implementation-plan.md): shipped phases, remaining work, and roadmap direction
- [Recovery Assistant design](recovery-assistant-design.md): design background for the recovery workflow in the web UI
- [Parallel Time Machine + rsync + ZFS design](parallel-time-machine-rsync-zfs-design.md): design for running Apple-native backups and directly accessible ZFS-backed backups side by side

Current product TODO:

- Make Capsule Watch work well for `rsync + ZFS`-only deployments and for parallel Time Machine + rsync deployments, not just Time Machine-centric setups.

## Historical planning docs

- [Setup guide website plan](setup-guide-plan.md)
- [ADR 0001: stack and delivery](adrs/0001-stack-and-delivery.md)

Use the operator-facing guides in the top-level `docs/` directory for installation, Samba setup, and recovery testing.
