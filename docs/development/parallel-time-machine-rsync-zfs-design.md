# Parallel Backup Design: Time Machine + rsync + ZFS

## Summary

This design keeps Apple Time Machine for native macOS backups while adding a second, simpler backup path that is easy to browse from Linux and non-Apple tooling.

The idea is:

- keep the existing Samba Time Machine destination for native macOS backups
- add a separate rsync-based backup from the Mac to the Linux server
- store the rsync backup on ZFS and use ZFS snapshots for history
- run both in parallel so each system covers different recovery needs

That gives two recovery modes:

- **Time Machine** for Apple-native restore flows, Migration Assistant, and versioned Mac recovery
- **rsync + ZFS** for direct file access, straightforward copy-out, and non-Apple recovery workflows

## Why this design exists

Time Machine is still useful, but APFS-era sparsebundle backups are more opaque than a normal file tree. They work best when you stay inside Apple's recovery tooling.

An rsync-to-ZFS path solves a different problem:

- the backup data stays visible as normal files on the server
- version history is provided by ZFS snapshots rather than Apple backup metadata
- files can be restored with ordinary tools such as `ls`, `find`, `cp`, `rsync`, or an SMB share
- Linux-side inspection and verification are much simpler

The systems are intentionally overlapping but not identical.

## Goals

- Keep Time Machine working as the native macOS backup path.
- Add a second backup path that is easy to inspect and restore without Apple-specific tooling.
- Preserve historical versions for the rsync backup using ZFS snapshots.
- Keep the Time Machine area and rsync area operationally separate.
- Make it possible to restore files to a replacement Mac with simple copy or `rsync`.
- Let Capsule Watch eventually monitor both backup systems side by side.

## Non-goals

- Replacing Time Machine completely on day one
- Creating a bootable clone of the Mac
- Capturing every macOS system detail with perfect fidelity
- Protecting against failure of the single backup disk itself

That last point matters: if both backup systems live on the same physical disk, the design improves usability and recovery flexibility, but it does **not** remove the single-disk failure risk.

## Recommended architecture

### High-level flow

```text
Mac
  |- Time Machine over SMB
  |    -> Linux server
  |    -> ZFS dataset for Time Machine (no automated ZFS snapshots)
  |
  |- rsync over SSH
       -> Linux server
       -> ZFS dataset
       -> post-backup ZFS snapshot
```

### Recommended starting layout

For a greenfield setup, use one physical backup disk as a single ZFS pool with separate datasets:

```text
backupz
backupz/timemachine
backupz/rsync
backupz/rsync/macbook-air
backupz/rsync/macbook-pro
```

Recommended responsibilities:

- **`backupz/timemachine`**
  - mounted at `/srv/timemachine`
  - exported via Samba
  - used only for Time Machine sparsebundles
  - no automated ZFS snapshotting
  - controlled with quota or reservation so it cannot consume the whole pool

- **`backupz/rsync`**
  - mounted at `/backupz/rsync` or another clear path
  - contains one child dataset per Mac
  - receives normal-file backups over SSH/rsync
  - uses ZFS snapshots for history

This keeps the two backup systems operationally separate while still giving you the flexibility of one shared ZFS pool.

## Why separate datasets are better than one undifferentiated backup tree

Keeping the two backup systems in distinct datasets gives you:

- clearer failure boundaries
- simpler troubleshooting
- easier space accounting
- freedom to tune snapshotting, quotas, and visibility properties only where they belong
- less risk that rsync-side policy changes bleed into the Time Machine side

It also makes it obvious which tool is responsible for version history:

- Time Machine history lives inside the sparsebundle
- rsync history lives in ZFS snapshots

## Storage layout details

### Option A: Recommended for greenfield setups

Put the whole disk under one ZFS pool and create separate datasets:

- `backupz/timemachine`
- `backupz/rsync`
- `backupz/rsync/<mac-name>`

Example:

```text
backupz/timemachine     -> /srv/timemachine
backupz/rsync           -> /backupz/rsync
backupz/rsync/macbook   -> /backupz/rsync/macbook
```

Pros:

- flexible shared capacity across one disk
- simple to manage and expand
- quotas and reservations can enforce space boundaries between backup modes
- one storage stack instead of two

Cons:

- Time Machine and rsync both depend on the same pool
- you need to be deliberate about dataset-level policy so snapshots only apply where intended

Suggested dataset controls:

- set a quota or refquota on `backupz/timemachine` to cap Time Machine growth
- optionally set a reservation or refreservation on the rsync side if you want guaranteed recovery space
- set `snapdir=visible` on the rsync datasets if you want easy snapshot browsing
- leave `snapdir=hidden` on the Time Machine dataset
- set `atime=off` and `compression=lz4` on the rsync datasets
- consider a `canmount=off` parent dataset purely for inheriting common properties

### Option B: Lower-risk migration path for an existing Time Machine disk

If you already have a working non-ZFS Time Machine disk and want to add rsync + ZFS with the least disruption, keep the Time Machine side as-is and add a second storage area for rsync backups.

Pros:

- avoids migrating a working Time Machine setup immediately
- reduces the risk of breaking the Apple backup path while you validate the rsync side

Cons:

- more operational complexity
- less elegant long-term design
- fixed size split if you partition a single disk

For your stated greenfield goal, **Option A is the better fit**.

## Important implementation caveat: single existing disk

If your current Time Machine backup disk is already in use, converting it into the greenfield all-ZFS design is still a risky migration.

Practical guidance:

- safest path: start with an empty disk or a second disk
- riskier path: fully back up the existing backup disk somewhere else, rebuild the disk as ZFS, then restore what you want to keep
- avoid in-place surgery on your only known-good backup disk unless you are comfortable losing that backup set

This is probably the biggest real-world constraint in the design.

## rsync backup model

### Push from the Mac

The simplest model is:

- the Mac initiates the backup
- it connects to the Linux server over SSH
- it writes into a dedicated path for that Mac

This fits laptops and personal Macs well because the source machine already knows:

- what to back up
- when it is online
- which paths need Full Disk Access

### Automation on macOS

Use `launchd`, not `cron`, for the automated rsync job.

Why:

- it is the native macOS scheduler
- it behaves better around login state and laptop sleep/wake patterns
- it is the normal way to run recurring user-level jobs on macOS

### Recommended rsync implementation on macOS

Standardize on a modern rsync build on the Mac rather than the old built-in implementation.

That makes it easier to rely on current rsync behavior, metadata handling, and flags consistently across machines.

The simplest path on macOS is Homebrew:

```bash
brew install rsync
RSYNC_BIN="$(brew --prefix rsync)/bin/rsync"
"$RSYNC_BIN" --version
```

Then point automation at Homebrew's rsync binary rather than assuming `rsync` on `PATH` is the right one.

For this design, assume:

- modern `rsync` 3.x on the Mac
- SSH transport to the Linux server
- explicit testing of any data set that depends on extended attributes, ACLs, or application package directories

### Recommended rsync source strategy

Do **not** start by trying to mirror the entire Mac.

Instead, back up an explicit allowlist of high-value data such as:

- `Documents`
- `Desktop`
- `Pictures`
- `Movies`
- project directories
- exported app data
- package directories you intentionally want to preserve, such as photo libraries

That keeps the design understandable and avoids treating ephemeral system state as if it were a portable file backup.

### Recommended rsync destination layout

On the server:

```text
/backupz/rsync/<mac-name>/current/
```

Example:

```text
/backupz/rsync/macbook-air/current/
```

The rsync job always updates `current`, and snapshots preserve history.

That keeps restore logic simple:

- restore latest state from `current`
- restore old state from a ZFS snapshot of the same dataset

### Preserve history with ZFS, not with rsync itself

Do not build historical versions with rotating rsync target directories if you are already using ZFS snapshots.

The recommended model is:

1. rsync updates `current`
2. a successful backup triggers a ZFS snapshot
3. retention is managed by snapshot policy

That avoids double-versioning and keeps the live tree easy to browse.

## ZFS layout for the rsync side

Example pool and datasets:

```text
backupz
backupz/rsync
backupz/rsync/macbook-air
backupz/rsync/macbook-pro
```

Recommended ZFS properties for the rsync datasets:

- `compression=lz4`
- `atime=off`
- `xattr=sa` if you are staying within OpenZFS-compatible systems and want better xattr performance
- `snapdir=visible` if you want easy snapshot browsing from the filesystem

If `snapdir=visible` is enabled, old versions can be browsed directly under paths such as:

```text
/backupz/rsync/macbook-air/.zfs/snapshot/<snapshot-name>/current/
```

That is a major usability advantage over Time Machine sparsebundles when the goal is simple file recovery.

## Snapshot strategy

### Trigger point

Take a ZFS snapshot only after a successful rsync run.

That ensures each snapshot represents a known-good backup point rather than an arbitrary timer tick.

### Suggested retention

A reasonable starting policy is:

- keep 24 hourly snapshots
- keep 30 daily snapshots
- keep 12 weekly snapshots
- keep 12 monthly snapshots

Adjust based on capacity and how often the Mac actually changes.

### Snapshot naming

Use timestamped names that sort naturally, for example:

```text
auto-2026-03-21-0100
auto-2026-03-21-1300
```

You can manage retention with:

- a small custom script
- `sanoid`
- another ZFS snapshot management tool you already trust

For a single-host personal system, a small explicit policy is usually easier to reason about than a complicated orchestration stack.

### Time Machine dataset snapshots

For the Time Machine dataset, the design still avoids user-facing snapshot history because Time Machine already manages its own history inside the sparsebundle.

However, if you want ZFS replication for redundancy, it is reasonable to create **replication-only snapshots** on `backupz/timemachine`:

- use them only as send/receive checkpoints
- do not expose them as part of the normal restore workflow
- prune them independently from the rsync snapshot retention policy

That keeps the operator mental model simple:

- Time Machine history is still "owned" by Time Machine
- ZFS snapshots on the Time Machine dataset exist only to move data safely to another disk or pool

## Server-side access model

### Separate identities

Use different accounts for different jobs:

- `timemachine` or similar for SMB Time Machine access
- `rsync-backup` or one user per Mac for SSH/rsync writes

Do not reuse the Time Machine Samba account for rsync.

### Restrict the rsync account

The rsync backup user should be limited to:

- key-based SSH authentication
- write access only to its assigned backup path
- no general administrative role on the server

The cleaner the identity separation is, the easier it will be to audit and recover later.

## Restore model

### When to use Time Machine

Use Time Machine when you want:

- Migration Assistant
- Apple-native restore behavior
- the familiar Time Machine browsing experience

### When to use rsync + ZFS

Use the rsync side when you want:

- straightforward file copy-out
- recovery from Linux without a Mac
- recovery to a different Mac without Time Machine tooling
- inspection with ordinary filesystem tools

### Typical restore workflows from the rsync side

1. **Latest version restore**
   - browse `current`
   - copy the file or directory back

2. **Historical restore**
   - browse `/.zfs/snapshot/<snapshot-name>/current/`
   - copy the desired version back

3. **Replacement Mac restore**
   - mount the restore share or SSH into the server
   - `rsync` data from the server to the new Mac

This is the strongest argument for the rsync side: the restore path stays normal and obvious.

## Recommended restore exposure

For human-friendly recovery, consider exporting the rsync backup area read-only in one of these ways:

- a read-only Samba share for the latest `current` trees
- a read-only Samba share for snapshot browsing if you want Finder-based recovery
- SSH-only access if you prefer CLI restores

If you expose snapshots over SMB, keep that share read-only.

## Redundancy, replication, and disk rotation

Your current habit of rotating disks is still valuable. ZFS gives you more options, but it does not make offline copies obsolete.

### Keep stable names for the live system

For the always-online pool and datasets, prefer stable functional names:

- pool: `backupz`
- datasets: `backupz/timemachine`, `backupz/rsync`, `backupz/rsync/<mac-name>`

That keeps Samba config, monitoring, mount points, and restore docs stable.

### Use the `YYYYMMa` / `YYYYMMb` convention for removable replica media

Your existing naming scheme is still useful. The best place to use it is on removable replica disks or replica pools, for example:

- `backupz-replica-202603a`
- `backupz-replica-202603b`

That tells you when the replica disk entered service without forcing the primary pool name to change.

If you also label the physical disks externally with the same convention, the operational story stays very clear.

### Option 1: Always-attached replica disk

Use a second local disk as a second ZFS pool and replicate to it automatically.

Example:

- primary pool: `backupz`
- replica pool: `backupz-replica`

Replication options:

- native `zfs send` / `zfs receive`
- `zrepl` if you want a more managed replication workflow

Pros:

- low operational overhead
- no manual disk swaps
- near-continuous second copy

Cons:

- the replica is always online
- accidental deletion, major operator mistakes, or host compromise can affect both copies more easily than with an offline disk

### Option 2: Rotating removable replica disks

Use one or two removable ZFS replica disks and rotate them in on a schedule.

Example:

- `backupz-replica-202603a`
- `backupz-replica-202603b`

Workflow:

1. attach the removable replica disk
2. import its pool
3. replicate incremental snapshots from `backupz`
4. export the replica pool
5. disconnect and store it offline

Pros:

- preserves your current "swap disks for redundancy" workflow
- gives you an offline copy
- improves resilience against operator error, malware, or host failure

Cons:

- more manual handling
- the offline replica is only current as of the last sync

### Option 3: Hybrid recommendation

If you want the most practical long-term design, use both:

- one always-attached replica disk for convenience and fast local redundancy
- one periodically updated removable replica disk for offline protection

That is meaningfully better than either approach alone.

### Replication scope

For the rsync datasets:

- snapshot after a successful backup
- replicate those snapshots to the replica pool

For the Time Machine dataset:

- keep normal Time Machine history inside the sparsebundles
- take replication-only ZFS snapshots when you need to send changes to the replica pool

That distinction is important. The Time Machine dataset can still be replicated with ZFS even if you do not use ZFS snapshots there as an operator-facing history mechanism.

### When rotating disks is still useful

ZFS replication can reduce the need to swap disks for redundancy, but not necessarily for all goals.

Disk rotation is still useful when you want:

- an offline copy
- offsite storage
- a clear archive of "what was current in March 2026"

ZFS does not replace that operational benefit by itself.

### When replication is better than swapping

Replication is better when you want:

- less manual work
- more frequent redundant copies
- a faster recovery path after a single-disk failure

### Capacity note

Replication solves redundancy more cleanly than manual file copying, but it does **not** solve the problem of a disk eventually filling up.

When the primary pool no longer has enough space, you still need one of these:

- replace it with a larger pool
- add a larger new primary disk and migrate
- reduce retention
- reduce what is being backed up

### External archive, pruning, and rollover workflow

For this design, the cleanest capacity-management model is:

- keep the **primary pool** focused on current backups and recent history
- keep one or more **external replica disks** as the deeper-history or archive tier

That lets you reclaim primary space without losing older backup generations.

### rsync side: replicate, then prune

On the rsync side, pruning after replication is a normal part of the design.

Recommended workflow:

1. snapshot the rsync dataset after a successful backup
2. replicate those snapshots to an external replica pool
3. verify the replica contains the snapshots you intend to preserve
4. destroy older snapshots on the primary pool
5. keep a longer retention window on the external replica if desired

This works well because the rsync backup history is explicitly owned by ZFS snapshots.

That means the rsync side can naturally support:

- short retention on the primary pool
- longer retention on external replica media
- periodic space reclamation on the primary without breaking the restore model

### Time Machine side: archive rollover, not surgical pruning

On the Time Machine side, the preferred space-management pattern is different.

Do **not** treat the sparsebundle internals as something to prune manually on the server.

Instead, use **archive rollover**:

1. make sure no Time Machine backup is actively running
2. take a replication-only ZFS snapshot of `backupz/timemachine`
3. replicate that dataset to an external replica pool or removable replica disk
4. verify the external copy is complete
5. destroy and recreate the primary `backupz/timemachine` dataset, or otherwise clear it intentionally
6. reconnect the Mac and let Time Machine start a fresh backup generation on the primary

This is much safer than trying to trim old history inside sparsebundles while keeping the active set alive.

### What rollover gives you

After a rollover, you effectively have:

- an **archived Time Machine generation** on an external replica disk
- a **new active Time Machine generation** on the primary pool

That is a good fit for your current habits because it mirrors how you already think about rotating backup media.

It also pairs well with your `YYYYMMa` / `YYYYMMb` convention:

- external archive disk or pool: `backupz-replica-202603a`
- later archive disk or pool: `backupz-replica-202603b`

You can think of those names as marking when that archive generation became current.

### Important implication of Time Machine rollover

After rollover, the Time Machine history is no longer one continuous timeline on the active primary.

Instead:

- recent restores come from the current primary Time Machine dataset
- older restores come from the archived replica generation

That is usually a reasonable tradeoff if your priority is preserving history while reclaiming primary capacity safely.

### Recommended operator policy

A practical long-term policy would be:

- primary pool keeps active Time Machine backups plus recent rsync snapshot history
- always-attached or external replica media keep older rsync snapshots
- when the Time Machine area becomes too full, replicate it off as an archive and start a new Time Machine generation on the primary

In other words:

- **rsync history** is usually trimmed incrementally
- **Time Machine history** is usually rolled over in larger generations

That distinction should be treated as a deliberate part of the system design, not just an emergency cleanup procedure.

## Monitoring implications for Capsule Watch

This hybrid model is a good fit for future Capsule Watch expansion.

Potential new checks:

- last successful rsync run age per Mac
- ZFS pool health
- available space on the ZFS pool
- latest snapshot age per dataset
- snapshot retention drift
- mismatch between Time Machine recency and rsync recency

That would let the dashboard answer a stronger question:

"Are both my Apple-native backups and my directly accessible file backups current?"

## Main risks and tradeoffs

### Single disk risk

If you only deploy the primary pool, both backup systems still depend on one physical disk.

If the disk dies, both the Time Machine and rsync backup are gone.

This design improves restore flexibility, not physical redundancy.

### Shared-pool contention risk

With the recommended all-ZFS design, Time Machine and rsync share one pool.

Without quotas or reservations, one side can crowd out the other.

### rsync is not a full system image

A file-level rsync backup is excellent for user data and many application data sets, but it is not the same thing as a full macOS restore image.

That is exactly why keeping Time Machine in parallel makes sense.

### macOS permissions and protected data

Some user data on macOS requires Full Disk Access for the backup process.

This is operationally manageable, but it should be treated as part of the design rather than a surprise.

## Recommended first version

If you build this incrementally, the first useful version should be:

1. Stand up the primary ZFS pool with separate `timemachine` and `rsync` datasets.
2. Add a second backup path for a single Mac.
3. Back up a small allowlist of high-value directories with rsync.
4. Store that backup on a ZFS dataset with post-backup snapshots.
5. Validate restore by copying files out from both `current` and an older snapshot.
6. Add replication to a second pool once the primary path is trustworthy.

That proves the design before you try to cover the whole Mac.

## Suggested next decisions

Before implementation, decide these items explicitly:

1. Which data should the rsync backup cover in version 1?
2. Do you want one shared `rsync-backup` user or one backup user per Mac?
3. Do you want snapshot browsing exposed over SMB, SSH, or both?
4. What retention policy fits the disk capacity you actually have?
5. Do you want only an always-attached replica, only rotated offline replicas, or a hybrid of both?
6. Should the `YYYYMMa` / `YYYYMMb` naming convention apply to removable replica pools, physical disk labels, or both?
7. What primary-pool fullness threshold should trigger rsync pruning versus Time Machine archive rollover?

## Recommendation

This is a strong design if your priorities are:

- keep Time Machine available for native Mac recovery
- gain a second backup path with simpler restore behavior
- make the backed-up files accessible without depending on Apple tooling

The main caution is storage layout: on a single already-in-use disk, the migration path may be harder than the design itself.

If you proceed, the safest order is:

1. finalize the primary ZFS dataset layout and quota plan
2. stand up the rsync + ZFS path for one Mac
3. validate real restores from both `current` and snapshots
4. add replication to a second pool or rotated replica disk
5. only then broaden the scope of what the Mac backs up
