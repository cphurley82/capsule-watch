# macOS rsync Automation Handoff

Use this document when resuming work on the Mac-side rsync automation path.

Read this first, then go to [Set Up rsync Backups from macOS](../rsync-backups-from-macos.md).

## Current state

The repo has gone through a long operator-style validation pass for the backup docs.

Validated on live systems:

- Time Machine setup and restore workflow
- Ubuntu-side rsync destination setup
- manual Mac-side rsync backup runs
- rsync latest-state restore from `current`
- rsync historical restore from ZFS snapshots
- source-side replication checkpoint creation and `zfs send -n -v -R` dry run
- `backupreaders` group-based read access on the Ubuntu host

Not yet validated end to end:

- Mac-side `launchd` automation for rsync
- removable external-disk `zpool import` plus `zfs receive` replication path
- rsync pruning workflow
- Time Machine archive rollover workflow

Those unvalidated areas now have TODO notes near the top of their operator guides.

## Live system details from the validation pass

These values came from the live test environment used during the doc review:

- Ubuntu host: `Chris-Vostro3470`
- Mac host: `Chris-MacBookAir16c12`
- primary ZFS pool: `backupz`
- rsync parent dataset: `backupz/rsync`
- validated per-Mac rsync dataset: `backupz/rsync/chris-macbookair16c12`
- current rsync tree: `/backupz/rsync/chris-macbookair16c12/current`

Validated rsync snapshots on the Ubuntu side:

- `backupz/rsync/chris-macbookair16c12@auto-2026-03-21-2251`
- `backupz/rsync/chris-macbookair16c12@auto-2026-03-22-0945`
- `backupz/rsync/chris-macbookair16c12@auto-2026-03-22-1001`

Validated replication dry-run checkpoint:

- `backupz@replica-test-2026-03-22-203404`

That replication test proved:

- `sudo zfs snapshot -r backupz@"$STAMP"` works
- recursive checkpoints appear on `backupz`, `backupz/rsync`, `backupz/rsync/<mac-name>`, and `backupz/timemachine`
- `sudo zfs send -n -v -R backupz@"$STAMP"` produces a valid stream plan

## Access model that was validated

The rsync operator access model on Ubuntu is now:

- writer identity: `rsync-backup`
- reader group: `backupreaders`
- operator account example: `chris`

Important behavior:

- add the operator to `backupreaders`
- apply ACLs to the live rsync tree
- create at least one fresh snapshot after the ACL change
- start a fresh login session before expecting non-`sudo` access to work

This was validated for:

- browsing `current/` without `sudo`
- browsing the new rsync snapshot without `sudo`

Older snapshots created before the ACL change may still require `sudo`.

## Important doc changes already made

The following operator guides were heavily updated to match the live setup:

- [Prepare a ZFS Backup Disk for Time Machine and rsync](../disk-formatting-for-time-machine.md)
- [DIY Time Capsule setup](../diy-time-capsule-setup.md)
- [Add the rsync Backup Path on Ubuntu](../configure-rsync-backup-on-ubuntu.md)
- [Set Up rsync Backups from macOS](../rsync-backups-from-macos.md)
- [Verify and restore rsync + ZFS backups](../verify-and-restore-rsync-backups.md)
- [ZFS Replication and Backup Rotation](../zfs-replication-and-rotation.md)
- [ZFS Snapshot Retention and Pruning for rsync Backups](../zfs-snapshot-retention-and-pruning.md)
- [Time Machine Retention and Archive Rollover](../time-machine-retention-and-rollover.md)

Important specific updates:

- the Mac rsync script uses broad sources plus a separate exclude file
- the Ubuntu rsync guide now documents the `backupreaders` model
- restore docs now assume normal read access first and `sudo` as fallback
- replication guide now treats the whole `backupz` tree as one recursive replication unit

## Important Mac-side automation change

One real automation bug was found in the Mac rsync script:

- the script used `brew` from `PATH`
- that is risky under `launchd`, which often has a minimal environment

The doc now resolves Homebrew explicitly from:

- `/opt/homebrew/bin/brew`
- `/usr/local/bin/brew`

If you already created `~/bin/backup-to-capsule-rsync.zsh` on the Mac before this fix, update the live script from the current doc before testing `launchd`.

## Next recommended step on the Mac

Focus on validating the automation path, not the manual rsync path again.

Suggested order:

1. clone the repo on the Mac and open this handoff doc
2. compare the live `~/bin/backup-to-capsule-rsync.zsh` with the current version from [Set Up rsync Backups from macOS](../rsync-backups-from-macos.md)
3. make sure the LaunchAgent plist matches the current doc
4. lint the plist with `plutil -lint`
5. load the LaunchAgent and force a run with `launchctl kickstart -k`
6. inspect `launchctl print` and the log file
7. verify on Ubuntu that a new rsync snapshot appears after the automated run

Useful Mac-side commands for that validation:

```bash
plutil -lint "$HOME/Library/LaunchAgents/local.capsule-backup.rsync.plist"
launchctl unload "$HOME/Library/LaunchAgents/local.capsule-backup.rsync.plist" 2>/dev/null || true
launchctl load "$HOME/Library/LaunchAgents/local.capsule-backup.rsync.plist"
launchctl kickstart -k "gui/$(id -u)/local.capsule-backup.rsync"
launchctl print "gui/$(id -u)/local.capsule-backup.rsync"
tail -n 100 "$HOME/Library/Logs/capsule-backup-rsync.log"
```

Useful Ubuntu-side verification after the automated run:

```bash
MAC_NAME="chris-macbookair16c12"
find "/backupz/rsync/$MAC_NAME/current" -maxdepth 3 | head -n 40
zfs list -t snapshot -o name,creation -s creation backupz/rsync/"$MAC_NAME"
```

## Process that has been working well

This is the working loop that produced the best results in this validation pass:

1. review one guide at a time
2. run the guide on the real system
3. fix the guide immediately when reality disagrees with it
4. keep commands concrete and copy-pasteable
5. prefer exact paths and exact dataset names over placeholders where that improves clarity
6. use TODO notes for anything not yet validated end to end
7. separate validated workflows from design ideas
8. do not leave important caveats only in chat; put them in the docs

In practice, that meant:

- validate manual behavior before automating it
- avoid broad theory sections when a short operator step is clearer
- prefer read-access-first docs, with `sudo` only as fallback
- keep advanced workflows in separate docs instead of overloading the main guide

## If resuming in a new chat

The shortest useful prompt is:

```text
Read docs/development/macos-rsync-automation-handoff.md first, then help me validate the macOS launchd automation in docs/rsync-backups-from-macos.md on this Mac.
```

