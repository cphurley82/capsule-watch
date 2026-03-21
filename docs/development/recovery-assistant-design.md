# Recovery Assistant Design

## Summary

This document proposes a Capsule Watch web UI feature that helps an operator mount, browse, and recover files from Time Machine backups using another Mac.

The feature is meant to reduce terminal guesswork during recovery. It does not try to fully replace macOS recovery tools. Instead, it gathers the server-side facts Capsule Watch already knows, adds a small amount of new discovery data, and turns that into clear recovery guidance and copyable commands.

## Why this feature matters

Time Machine recovery works, but it can be stressful when:

- the source Mac has failed
- the operator does not remember the SMB share name
- the operator is unsure which sparsebundle belongs to which Mac
- `hdiutil attach` fails with `Resource busy`
- the operator wants confidence that data can actually be browsed and copied out

Capsule Watch already runs on the server that hosts the backups, so it is well positioned to answer the key questions:

- Which Time Machine share is active?
- Which backups exist?
- When were they last updated?
- What is the exact sparsebundle name for each Mac?
- Which recovery commands should the operator run on a different Mac?
- Is a stale Samba session likely blocking recovery?

## Goals

- Make cross-Mac recovery understandable to a human under pressure.
- Show all discovered backups in the web UI.
- Generate copyable Mac commands using server-side facts.
- Support both Finder-oriented and terminal-oriented recovery flows.
- Provide troubleshooting guidance and copyable server-side commands for common recovery issues.
- Keep the feature local-first and suitable for a home lab or small self-hosted deployment.

## Non-goals

- No browser-based file explorer into backup contents in the first version.
- No remote execution on the recovery Mac.
- No attempt to mount backups directly from the Linux server for macOS browsing.
- No full replacement for Migration Assistant.
- No general-purpose privileged command runner.

## User stories

### 1. Failed source Mac

As an operator, when my original Mac is unavailable, I want Capsule Watch to tell me:

- which SMB share to mount
- which sparsebundle belongs to the failed Mac
- what commands to run on another Mac to mount and browse the backup

### 2. Recovery confidence check

As an operator, before I need a disaster recovery, I want to verify that I can:

- mount the backup from another Mac
- browse files inside the mounted backup
- copy one file out successfully

### 3. Lock issue recovery

As an operator, when `hdiutil attach` reports `Resource busy`, I want Capsule Watch to:

- explain the likely cause
- show whether active Samba clients exist
- show the server commands that are most likely to fix the issue

## Proposed UX

Add a Recovery Assistant page linked from the main dashboard, for example at `/recovery`.

The main dashboard should stay focused on status and alerts. It should include a clear link or button that takes the operator to the dedicated recovery page.

Recommended structure:

### 1. Backup inventory

Show one row per discovered sparsebundle with:

- source Mac name
- sparsebundle path
- last modified time
- backup freshness status
- approximate size if cheap to gather

Primary actions:

- `Show recovery steps`
- `Copy terminal commands`
- `Show Finder workflow`

### 2. Recovery targets

Show server connection details the operator needs on another Mac:

- recommended server hostnames or IPs
- share name
- mount point example
- detected source Mac sparsebundle names

### 3. Recovery workflow cards

For a selected backup, show:

- `Mount SMB share`
- `Find sparsebundle`
- `Attach backup read-only`
- `Browse snapshots`
- `Copy file out`

Each card should include:

- a one-sentence explanation
- a copy button for the command block
- an optional expanded troubleshooting note

### 4. Finder-friendly mode

Some users are more comfortable with Finder than terminal. Provide a Finder-oriented flow that still uses terminal only where necessary:

- connect to the SMB share
- identify the sparsebundle name
- run the minimal `hdiutil attach -readonly` command
- open the mounted backup volume in Finder

Example final helper command:

```bash
open "/Volumes/Backups of My-Source-Mac"
```

### 5. Troubleshooting helpers

Start with a small `Troubleshooting` panel:

- `Show active Samba sessions`
- `Show recommended recovery commands`

The UI should stay read-only for this feature. It should explain why these commands matter and let the operator copy them into a terminal.

## Data needed from the server

### Already available or easy to derive

- `time_machine_root` from config
- sparsebundle names by scanning `*.sparsebundle`
- backup freshness from the existing backup recency collector
- Samba service status from the existing service collector

### New discovery data

The Recovery Assistant should add a small recovery metadata collector that gathers:

- share name mapped to `time_machine_root`
- available server addresses for SMB access
- sparsebundle inventory
- active Samba session summary
- troubleshooting command snippets for common failure modes

Suggested snapshot section:

```json
{
  "recovery": {
    "status": "healthy",
    "items": {
      "share_name": "timemachine",
      "server_hosts": [
        "192.168.1.10",
        "backup-server.local"
      ],
      "backups": [
        {
          "source_mac_name": "My-Source-Mac",
          "bundle_path": "/mnt/timemachine/My-Source-Mac.sparsebundle",
          "last_modified": "2026-03-20T21:49:51Z"
        }
      ],
      "samba_sessions": [
        {
          "username": "backupuser",
          "client_host": "192.168.1.25",
          "share_name": "timemachine"
        }
      ]
    }
  }
}
```

## How to discover the share name effectively

The cleanest server-side approach is:

1. Read `time_machine_root` from config.
2. Run `testparm -s`.
3. Parse Samba shares and find the share whose `path` matches `time_machine_root`.
4. If exactly one match exists, use it as the canonical Time Machine share.
5. If there is no match, mark recovery metadata as partial and ask the operator to configure the share name explicitly later.

This is more robust than asking the operator to remember the share name during recovery.

## Command generation strategy

The UI should generate commands from discovered facts plus one operator-provided value: SMB username.

The server can know:

- `SERVER_HOST`
- `SHARE_NAME`
- `SOURCE_BUNDLE`
- `SOURCE_MAC_NAME`

The server may not safely know which SMB username the recovery Mac should use. The UI should therefore provide:

- a small text field for `SMB username`
- a preview that updates command blocks as the user types

For the first version, keep this as simple as possible:

- ask for SMB username on each page load
- do not persist it server-side
- do not try to remember it in browser storage

### Command sets to generate

#### Terminal recovery flow

For each backup:

1. Mount SMB share with `mount_smbfs`
2. Locate selected sparsebundle
3. Attach read-only with `hdiutil`
4. Find mounted `Backups of ...` volume
5. List snapshots with `tmutil`
6. Browse with `ls` and `find`
7. Copy out via `rsync` as the default, with `tmutil restore` as an alternative

#### Finder-assisted flow

For each backup:

1. Finder or `open` to the SMB share
2. Minimal terminal command to attach sparsebundle
3. `open "/Volumes/Backups of ..."` to browse the mounted backup volume

### Output style

The UI should generate:

- short command blocks
- plain-language explanations
- success examples, such as the expected `hdiutil attach` output pattern
- `rsync`-first copy examples for both single files and directories

## Troubleshooting guidance

### Troubleshooting commands

Instead of server-side action buttons, the UI should generate copyable troubleshooting commands such as:

```bash
sudo smbstatus
sudo systemctl restart smbd
```

This keeps the feature read-only while still giving the operator practical recovery help.

### Show Samba sessions

This is read-only and should likely come from the recovery metadata collector or a dedicated lightweight endpoint. It is useful before suggesting troubleshooting commands.

## Security model

This feature should remain read-only in its first versions.

Recommended security boundaries:

- Keep the feature local-only.
- Do not accept arbitrary shell input from the browser.
- Keep generated recovery commands as plain text only; do not execute them remotely.

Optional later hardening:

- add simple local authentication if write actions are ever introduced later
- add an allowlist of local-network source addresses for the Recovery Assistant page if needed

## Proposed implementation shape

### Phase 1: read-only Recovery Assistant

Deliver:

- recovery metadata collector
- new snapshot section for recovery inventory
- web UI page or panel showing discovered backups
- generated terminal and Finder command blocks
- no write actions yet

Success criteria:

- operator can identify the right backup without SSHing to the server
- operator can copy a known-good command sequence from the UI

### Phase 2: guided troubleshooting helpers

Deliver:

- active Samba session display
- recommended troubleshooting command blocks for `Resource busy` and related recovery issues

Success criteria:

- operator can resolve common `Resource busy` cases using the UI-generated commands
- the web UI remains read-only

### Phase 3: polish

Deliver:

- friendlier empty/error states
- per-backup copy buttons
- optional “last tested recovery” note or checklist

## Backend changes

### Config

Likely additions:

- optional explicit `samba_share_name`
- optional explicit preferred server hostname for generated commands

These should be optional because auto-discovery should work in the common case.

### Collectors

Add a recovery metadata collector that:

- parses `testparm -s`
- maps share name to configured backup path
- inventories sparsebundles under the backup root
- optionally summarizes `smbstatus`

### Web app

Add:

- recovery section formatter for the snapshot
- dedicated `/recovery` route
- link from the main dashboard to the recovery page

## Frontend design direction

This page should feel calmer and more task-oriented than the main status dashboard.

Recommended UI approach:

- one selected backup at a time
- clear step cards with plain-English titles
- prominent copy buttons
- obvious “what success looks like” snippets
- warning panel only when lock/session issues are detected

Avoid:

- giant walls of shell text
- showing every backup detail at once
- hiding key recovery facts behind too many clicks

## Design decisions

- The recovery experience should live on its own route such as `/recovery`, with a clear link from the main dashboard.
- The UI should ask for SMB username on each page load because that is the simplest behavior to implement and test.
- The first versions should focus on easy copy-and-paste command blocks rather than downloadable scripts.

## Recommendation

This feature is very doable and is a strong fit for Capsule Watch.

The most effective first version is:

1. add a read-only Recovery Assistant page
2. generate recovery commands from server-side discovery data
3. add troubleshooting command generation for common lock/session issues

That gets the biggest usability win with the lowest security risk.
