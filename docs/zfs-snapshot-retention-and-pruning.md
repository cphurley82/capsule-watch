# ZFS Snapshot Retention and Pruning for rsync Backups

This guide covers retention and pruning for the rsync + ZFS backup path.

TODO: This guide has not been validated end to end on the live system yet. The retention model matches the validated rsync + ZFS design, but the actual pruning workflow still needs operator testing.

It assumes:

- you already have `backupz/rsync` working
- per-Mac datasets such as `backupz/rsync/<mac-name>` already exist
- successful rsync runs are creating snapshots such as `auto-2026-03-22-1001`

Use this guide when you want to:

- understand what ZFS does and does not prune automatically
- trim older rsync snapshot history on the primary pool
- keep a shorter history on the primary and a longer history on external replica disks

If you are looking for Time Machine capacity management instead, use [Time Machine Retention and Archive Rollover](time-machine-retention-and-rollover.md).

## What ZFS does not do for you

ZFS does not have a built-in retention policy engine that automatically keeps "24 hourly, 30 daily, 12 monthly" snapshots on its own.

That means:

- snapshots do not auto-prune when a dataset quota fills
- snapshots do not auto-prune when the pool gets tight on space
- if you want pruning, you must explicitly destroy snapshots or automate that with a tool or script

For this backup design, that is a good thing. Snapshot retention stays under your control.

## Recommended operator rules

Use these rules unless you have a reason to do something more complicated:

1. replicate before pruning
2. prune rsync snapshots, not Time Machine sparsebundle internals
3. keep pruning policy simple and predictable
4. keep a shorter history on the primary pool than on removable replica media if space is tight

If a snapshot is still needed for replication, do not destroy it until the replica has a newer safe checkpoint.

## Snapshot layout to expect

The rsync side usually looks like this:

```text
backupz/rsync
backupz/rsync/chris-macbookair16c12
backupz/rsync/another-mac
```

Operator-visible history usually lives on the per-Mac datasets, for example:

```text
backupz/rsync/chris-macbookair16c12@auto-2026-03-22-0945
backupz/rsync/chris-macbookair16c12@auto-2026-03-22-1001
```

The parent `backupz/rsync` dataset may also have replication checkpoints from [ZFS Replication and Backup Rotation](zfs-replication-and-rotation.md), but those are not the main restore history for individual Macs.

## 1. Inspect existing snapshots

List all rsync snapshots:

```bash
sudo zfs list -t snapshot -o name,creation -s creation -r backupz/rsync
```

List snapshots for one Mac:

```bash
MAC_NAME="chris-macbookair16c12"
sudo zfs list -t snapshot -o name,creation -s creation backupz/rsync/"$MAC_NAME"
```

## 2. Manually prune one snapshot

Destroy a single old rsync snapshot only after you have replicated and verified anything you still want to keep:

```bash
MAC_NAME="chris-macbookair16c12"
SNAPSHOT="auto-2026-03-01-0100"

sudo zfs destroy backupz/rsync/"$MAC_NAME"@"$SNAPSHOT"
```

If the snapshot has a hold on it, remove the hold first:

```bash
MAC_NAME="chris-macbookair16c12"
SNAPSHOT="replica-2026-03-22-1545"

sudo zfs holds backupz/rsync/"$MAC_NAME"@"$SNAPSHOT"
sudo zfs release keep backupz/rsync/"$MAC_NAME"@"$SNAPSHOT"
```

Replication checkpoints taken recursively on `backupz@"$STAMP"` are often held and released at the `backupz` level as part of the replication workflow. Make sure you are not destroying a checkpoint that your next incremental send still needs.

## 3. Use a simple starting retention policy

A reasonable starting point for a personal system is:

- keep recent `auto-*` snapshots on the primary pool
- keep deeper history on removable replica disks

If you want a concrete first policy, start with:

- primary pool: recent snapshots only
- external replica disks: older and deeper history

The exact count depends on your disk size and how much the Macs change. Simpler is better than clever here.

## 4. Decide how to automate pruning

There are two practical paths:

### Option A: small custom script

Good when:

- you want very explicit behavior
- you only have a few Macs
- you want to keep the system easy to audit

Typical behavior:

- enumerate `backupz/rsync/<mac-name>` datasets
- list `auto-*` snapshots oldest first
- keep the newest N
- destroy older ones

### Option B: a dedicated snapshot management tool

Good when:

- you want more advanced hourly/daily/weekly/monthly retention
- you are comfortable adopting another operational dependency

Examples include `sanoid` or another ZFS snapshot manager you already trust.

## 5. Keep pruning safe with replication

The safest pattern is:

1. run backups normally
2. take a replication checkpoint
3. replicate to removable media
4. verify the replica
5. prune old primary snapshots if needed

That lets the primary pool stay focused on current backups and recent history while removable replica disks preserve deeper history.

## 6. What not to prune with this guide

This guide is for rsync-side ZFS snapshots.

Do not use it to:

- manually delete files inside Time Machine sparsebundles
- treat `backupz/timemachine` like a normal snapshot-history dataset
- prune snapshots you still need for your next incremental replication

If the Time Machine side is getting too full, use [Time Machine Retention and Archive Rollover](time-machine-retention-and-rollover.md).
