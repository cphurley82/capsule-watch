# Setup Guide Website Plan

## Purpose

The documentation site should help someone go from "I have an Ubuntu box" to "I have a working Time Machine server with Capsule Watch monitoring" without needing to piece together forum posts.

## Audience

- Home users building a Time Machine server from a standard PC
- Existing DIY Time Capsule operators who already have Samba working and want monitoring

## Site structure

- `Overview`
- `Hardware and software prerequisites`
- `Set up Ubuntu for Time Machine with Samba`
- `Verify backups from macOS`
- `Install Capsule Watch`
- `Configure alerts and thresholds`
- `Run as services with systemd`
- `Troubleshooting`
- `Maintenance and upgrade guide`

## Content approach

- Use short task-focused pages instead of a single long guide
- Include copy-paste commands with explanation
- Call out which steps need `sudo`
- Include screenshots of the dashboard once the UI exists
- Include recovery and verification steps, not just install steps

## Publishing plan

- Author content as Markdown in-repo
- Build to a static site for GitHub Pages
- Keep local hosting optional in the first release
- If local hosting is added, serve the static site behind the same reverse proxy as the dashboard

## Initial page outline

### Overview

- What Capsule Watch does
- What it does not do
- Architecture at a glance

### Time Machine server setup

- Ubuntu packages
- Samba share configuration
- Avahi advertisement
- Time Machine quota configuration
- macOS connection and first backup verification

### Capsule Watch install

- Dependencies
- Config file
- Service user
- `systemd` unit files and timers
- Optional email relay setup

### Troubleshooting

- Backup share not visible on macOS
- Backup appears stale in the dashboard
- SMART checks require sudo configuration
- Alerts not sending

## Definition of success

- The guide is readable both on GitHub and as a rendered website
- A technically comfortable user can complete setup without external references for the common path
