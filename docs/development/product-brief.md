# Product Brief

## Vision

Capsule Watch helps a home server owner trust their DIY Time Machine setup without logging into Ubuntu and manually checking Samba, disk space, SMART output, or the age of the latest backup.

## Problem statement

DIY Time Machine servers are achievable with Samba on Ubuntu, but ongoing confidence is harder than initial setup. Failures tend to be silent until a restore is needed. The owner needs a lightweight way to answer a few critical questions quickly:

- Are Macs still backing up recently enough?
- Is the backup volume running out of space?
- Is the drive healthy?
- Are the required services running?
- Is the server itself behaving normally?

## Target user

- A home lab user or technically comfortable household admin
- Runs a single Ubuntu server that exposes a Time Machine share over Samba
- Values low maintenance, visibility, and simple recovery steps over enterprise features

## Goals

- Provide an at-a-glance dashboard with actionable health states
- Keep monitoring passive and low-risk by default
- Minimize privileged operations and make them explicit
- Make installation and troubleshooting approachable from a browser
- Support a small number of Macs without requiring external services

## Non-goals

- Replacing Time Machine itself
- Managing backups on the Macs
- Providing cloud sync or off-site replication in the MVP
- Exposing the dashboard publicly on the internet
- Becoming a full infrastructure monitoring suite

## MVP capabilities

- Health summary banner driven by warning and error thresholds
- Per-client backup freshness based on sparsebundle activity
- Per-client storage usage and quota visibility where possible
- SMART health, temperature, and recent self-test status
- Samba and Avahi service checks
- Basic host telemetry: uptime, load, memory, and CPU temperature when available
- Email alerting in the MVP, with de-duplication and resolved notifications
- Setup guide website for both the Time Machine server and Capsule Watch

## Success criteria

- A user can tell within 30 seconds whether backups appear healthy
- A stale backup condition is detected within one collection cycle
- A stopped critical service is visible on the dashboard and triggers an alert
- The app can be installed on a fresh Ubuntu Time Machine server in under 30 minutes using the guide
- The guide is usable as a standalone website and is easy to update in Git

## Assumptions

- Samba Time Machine sharing is already functional on the target Ubuntu machine
- The initial target filesystem is ext4, with graceful degradation for other filesystems
- The initial target is a single host with one primary backup volume
- Local-network-only access is acceptable for the MVP

## Open questions

- Whether quota information should come from Samba configuration parsing, sparsebundle metadata, or both
- Whether the local docs should be served by the monitor app, a reverse proxy, or only GitHub Pages in the first release
- Which push channel should be the first post-MVP addition after the email-based MVP alert flow
