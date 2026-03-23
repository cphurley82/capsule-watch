# ZFS Replication and Backup Rotation

This guide is the next step after the primary backup pool is working.

TODO: The source-side snapshot and `zfs send -n -v -R` flow has been validated on a live system, but the removable-disk `zpool import` and `zfs receive` path still needs end-to-end validation with a real external replica disk.

It covers:

- copying the backup datasets from the primary `backupz` pool to one or more removable external ZFS replica disks
- replicating both the Time Machine and rsync sides of the backup to that external location

It assumes the primary pool layout from [Prepare a ZFS Backup Disk for Time Machine and rsync](disk-formatting-for-time-machine.md):

```text
backupz/timemachine
backupz/rsync
backupz/rsync/<mac-name>
```

## Why this guide looks at both backup paths

The main goal here is simple:

- keep the live backups on the internal primary drive
- copy those backup datasets to removable external ZFS disks

At replication time, both backup paths are just ZFS datasets you want to send somewhere safer. The reason this guide still talks about Time Machine and rsync separately is that they store and age history differently on the primary side:

- rsync history lives in normal ZFS snapshots
- Time Machine history lives inside the sparsebundle itself. If you take ZFS snapshots of `backupz/timemachine`, those are mainly replication or archive checkpoints, not the normal day-to-day backup history.

That difference matters for retention and archive rollover, but the high-level replication goal is the same for both: copy the backup data off the primary drive.

## Assumed replica model

This guide assumes:

- one internal primary backup drive that hosts the live `backupz` pool
- one or more removable ZFS replica disks
- replica disks are attached only when you are sending or verifying snapshots

That model fits a simple home setup well:

- the internal drive stays online for normal Time Machine and rsync backups
- removable replica disks give you offline and offsite options
- rotation is explicit and easy to reason about

## Example rotation model

A good concrete model for this guide is:

- 1 internal backup drive that holds the live `backupz` pool
- 2 removable external ZFS replica disks of at least the same usable size
- 1 external replica disk is on-site for the next replication run
- 1 external replica disk is off-site and disconnected

Normal cycle:

1. attach the on-site external replica disk
2. replicate the backup datasets from the internal `backupz` pool
3. verify the replica
4. export and disconnect that disk
5. move it off-site
6. bring back the other replica disk for the next cycle

Long-term cycle:

1. once a year, replace one rotating external disk with a new disk
2. take the older retired disk out of the normal rotation
3. label it as a long-term archive generation
4. store it offline in a safe place

This is not the only workable model, but it is a strong and realistic one for a home setup.

## Replica naming and identification

Keep the live pool stable:

- primary pool: `backupz`
- live datasets: `backupz/timemachine`, plus parent dataset `backupz/rsync` with one child dataset per Mac such as `backupz/rsync/<mac-name>`

Give each physical replica disk a permanent identity that never changes.

A good pattern is a timestamp:

- `backupz-20260322-1545`
- `backupz-20260409-1010`
- `backupz-20270314-0905`

That works well because you can generate it programmatically when you first prepare the disk, and you do not have to invent letters or remember which suffix is still unused.

Use a generated name only when creating a brand-new replica disk. After that, always refer to the disk by its existing permanent pool name.

If you later retire `backupz-20260322-1545` into archive storage, keep that pool name. Do not reuse it for a new physical disk.

That makes it much easier to answer questions like:

- which disk is supposed to be on-site right now?
- which disk is the off-site rotating copy?
- which disk is a retired archive from an older period?
- what service window did this disk cover?

## How to identify a drive later

Do not rely on memory alone. Use all three of these:

- a pool name that permanently identifies the physical disk
- a physical label on the drive enclosure
- metadata stored on the ZFS root dataset

Recommended physical label fields:

- pool name
- role: `rotating replica` or `archive`
- first placed in service
- if retired, the service window such as `2026-03 to 2027-03`

Recommended on-disk metadata:

- `comment`: short human-readable summary
- `org.capsule:role`: `rotating-replica` or `archive`
- `org.capsule:first-used`: when the disk first entered service
- `org.capsule:last-sync`: most recent successful replication date
- `org.capsule:service-window`: archive coverage period for a retired disk

Quick identification check later:

```bash
POOL="your-existing-replica-pool-name"

zpool get comment "$POOL"
zfs get -H -o property,value \
  org.capsule:role,org.capsule:first-used,org.capsule:last-sync,org.capsule:service-window \
  "$POOL"
```

For a retired archive disk, update the metadata before storage:

```bash
POOL="your-existing-replica-pool-name"

sudo zpool set comment="Capsule archive disk; first-used=2026-03; service-window=2026-03_to_2027-03" "$POOL"
sudo zfs set org.capsule:role="archive" "$POOL"
sudo zfs set org.capsule:service-window="2026-03_to_2027-03" "$POOL"
```

If a pile of drives ever gets mixed up, this combination of physical label plus ZFS metadata makes recovery much easier.

## Snapshot strategy before replication

At replication time, the simplest approach is to treat the whole backup tree as one replication unit:

- create a recursive checkpoint at `backupz@"$STAMP"`
- send that recursive tree to the removable replica disk
- keep the replica disk's own identity metadata on the replica pool root, separate from the received `backupz` dataset

That means the default replication flow copies everything in one pass. The main reason this guide still talks about Time Machine and rsync separately below is that they age and prune differently on the primary side.

### rsync datasets

The rsync side already uses normal ZFS snapshots for operator-visible history on each per-Mac dataset.

In the validated setup, the regular backup workflow creates `auto-YYYY-MM-DD-HHMM` snapshots after each successful rsync run on datasets such as `backupz/rsync/macbook-air`.

For replica-disk copying, the simpler default is not to send the rsync side separately at all. Instead:

1. the Mac runs rsync
2. the server already has normal per-Mac `auto-...` snapshots from successful backup runs
3. before replication, the server takes one recursive checkpoint on `backupz`
4. the removable replica pool receives the whole backup tree in one send

### Time Machine dataset

Time Machine history stays inside the sparsebundle.

That means you should not think of `backupz/timemachine` as a dataset that needs regular ZFS snapshots for normal backup history. Apple Time Machine already manages the real backup history inside the sparsebundle.

If you take ZFS snapshots of `backupz/timemachine` in this guide, treat them as transport checkpoints for `zfs send` / `zfs receive` or as archive checkpoints for whole-dataset rollover, not as the normal restore workflow.

Recommended pattern:

1. make sure Time Machine is not actively backing up
2. take one recursive replication checkpoint on `backupz`
3. send that full checkpoint to the removable replica pool

## 1. Prepare a removable replica pool

This overlaps slightly with [Prepare a ZFS Backup Disk for Time Machine and rsync](disk-formatting-for-time-machine.md), but it is repeated here so removable replica setup is self-contained.

Before you create the replica pool, prepare the new removable disk the same careful way you prepared the primary backup disk:

1. identify the correct removable disk by its stable `/dev/disk/by-id/...` path
2. confirm nothing important is mounted from it
3. wipe old filesystem signatures
4. create a new single-disk ZFS pool on it

If you just plugged the disk in and do not know its ID yet, the easiest method is:

1. run the disk-listing commands before attaching it
2. plug in the removable disk
3. run the same commands again
4. look for the new size, model, or serial number
5. use the matching `/dev/disk/by-id/...` path, not `/dev/sdX`

Example:

```bash
lsblk -o NAME,SIZE,FSTYPE,LABEL,MODEL,SERIAL,MOUNTPOINTS
ls -l /dev/disk/by-id

REPLICA_DISK="/dev/disk/by-id/wwn-0x5000c500ffff1234"
readlink -f "$REPLICA_DISK"

findmnt -S "$(readlink -f "$REPLICA_DISK")" || true
sudo umount "$(readlink -f "$REPLICA_DISK")"* 2>/dev/null || true
sudo wipefs -a "$REPLICA_DISK"
```

If the disk was previously part of a ZFS pool, clear any old pool labels too:

```bash
REPLICA_DISK="/dev/disk/by-id/wwn-0x5000c500ffff1234"
sudo zpool labelclear -f "$REPLICA_DISK" 2>/dev/null || true
```

Once a removable replica disk exists, create a pool on it using the same ZFS storage practices as the primary.

Example:

```bash
REPLICA_DISK="/dev/disk/by-id/wwn-0x5000c500ffff1234"
REPLICA_POOL="backupz-$(date +%Y%m%d-%H%M)"

sudo zpool create -f \
  -o ashift=12 \
  -O mountpoint=none \
  -O compression=lz4 \
  -O atime=off \
  "$REPLICA_POOL" "$REPLICA_DISK"
```

Create a parent dataset for the replicated backup tree:

```bash
sudo zfs create -o mountpoint=none "$REPLICA_POOL"/backupz
```

You do not need to pre-create `timemachine` or `rsync` under the replica tree. `zfs receive` will populate those descendants from the send stream.

Add identification metadata immediately after creation:

```bash
FIRST_USED="$(date +%Y-%m)"

sudo zpool set comment="Capsule replica disk; first-used=$FIRST_USED; role=rotating-replica" "$REPLICA_POOL"
sudo zfs set org.capsule:role="rotating-replica" "$REPLICA_POOL"
sudo zfs set org.capsule:first-used="$FIRST_USED" "$REPLICA_POOL"
```

## 2. Take a recursive replication checkpoint on the primary

Choose a timestamp that sorts naturally:

```bash
STAMP="replica-$(date +%Y-%m-%d-%H%M)"
```

Take one recursive checkpoint for the whole backup tree:

```bash
sudo zfs snapshot -r backupz@"$STAMP"
```

You can optionally place a hold on snapshots you do not want deleted before replication completes:

```bash
sudo zfs hold -r keep backupz@"$STAMP"
```

## 3. Run the initial full replication

Use the same `STAMP` you created in the checkpoint step above.

```bash
REPLICA_POOL="your-existing-replica-pool-name"
sudo zfs send -R backupz@"$STAMP" | \
  sudo zfs receive -uF "$REPLICA_POOL"/backupz
```

The first replication is a full send. Later runs can be incremental.

If the rsync datasets already carry `backupreaders` ACLs for normal operator access, those filesystem ACLs are part of the replicated backup tree. In practice, that means mounted replica copies of the rsync side should preserve the same read-access model.

## 4. Run later incremental replications

Import the removable replica pool, pick the previous replication checkpoint, and generate a new one:

```bash
REPLICA_POOL="your-existing-replica-pool-name"
PREV="replica-2026-03-21-0100"
NEXT="replica-$(date +%Y-%m-%d-%H%M)"

sudo zpool import "$REPLICA_POOL"
sudo zfs snapshot -r backupz@"$NEXT"
```

`PREV` must already exist on both the primary and the replica from the last successful replication. `NEXT` is the new replication checkpoint you just created on the primary.

```bash
sudo zfs send -RI backupz@"$PREV" backupz@"$NEXT" | \
  sudo zfs receive -uF "$REPLICA_POOL"/backupz
```

If you use snapshot holds in your workflow, place the hold on `backupz@"$NEXT"` before the send and release it after verification.

## 5. Verify the replica

Check the replica datasets:

```bash
REPLICA_POOL="your-existing-replica-pool-name"

sudo zfs list "$REPLICA_POOL"/backupz
sudo zfs list "$REPLICA_POOL"/backupz/timemachine
sudo zfs list "$REPLICA_POOL"/backupz/rsync
sudo zfs list -r "$REPLICA_POOL"/backupz/rsync
sudo zfs list -t snapshot -o name,creation -s creation "$REPLICA_POOL"/backupz
zpool get comment "$REPLICA_POOL"
zfs get -H -o property,value \
  org.capsule:role,org.capsule:first-used,org.capsule:last-sync,org.capsule:service-window \
  "$REPLICA_POOL"
```

If you want a deeper spot check, first list the replicated per-Mac datasets under the replica rsync tree:

```bash
REPLICA_POOL="your-existing-replica-pool-name"
sudo zfs list -r -o name,mountpoint "$REPLICA_POOL"/backupz/rsync
```

Then pick one replica rsync dataset and temporarily give it a throwaway mountpoint so you can confirm that its `current/` tree is present:

```bash
REPLICA_POOL="your-existing-replica-pool-name"
MAC_NAME="macbook-air"
TEMP_MOUNT="/mnt/replica-rsync-$MAC_NAME"
sudo mkdir -p "$TEMP_MOUNT"
sudo zfs set mountpoint="$TEMP_MOUNT" "$REPLICA_POOL"/backupz/rsync/"$MAC_NAME"
sudo zfs mount "$REPLICA_POOL"/backupz/rsync/"$MAC_NAME" 2>/dev/null || true
find "$TEMP_MOUNT" -maxdepth 3 | head -n 40
sudo zfs unmount "$REPLICA_POOL"/backupz/rsync/"$MAC_NAME"
sudo zfs inherit mountpoint "$REPLICA_POOL"/backupz/rsync/"$MAC_NAME"
```

If you normally rely on `backupreaders`, remember that read access on the replica only matters after the replica dataset is mounted and the operator account is in a fresh session with the right group membership.

If you used snapshot holds, release them after verification:

```bash
STAMP="replica-2026-03-21-0100"
sudo zfs release -r keep backupz@"$STAMP"
```

Use the actual checkpoint name you held earlier.

## 6. Update Metadata and Remove the Replica Disk

After a successful replication and verification cycle:

1. update any replica metadata you maintain
2. export the replica pool
3. disconnect the disk
4. move or store it as planned

Update the last successful sync date:

```bash
REPLICA_POOL="your-existing-replica-pool-name"
SYNC_DATE="$(date +%F)"
FIRST_USED="$(zfs get -H -o value org.capsule:first-used "$REPLICA_POOL")"

sudo zfs set org.capsule:last-sync="$SYNC_DATE" "$REPLICA_POOL"
sudo zpool set comment="Capsule replica disk; first-used=$FIRST_USED; role=rotating-replica; last-sync=$SYNC_DATE" "$REPLICA_POOL"
```

Export it cleanly:

```bash
REPLICA_POOL="your-existing-replica-pool-name"

sudo zpool status "$REPLICA_POOL"
sudo zpool export "$REPLICA_POOL"
```

After export completes, unplug the disk and move it to its next storage location.

## 7. Optional: manage retention after replication

After the replica disk has been updated and verified, you may want to free space on the primary `backupz` pool.

The two common reasons are:

- the internal backup disk is getting too full
- you want the removable replica disks to keep older history than the primary disk

Use one of these next:

- rsync-side ZFS snapshot pruning: [ZFS Snapshot Retention and Pruning for rsync Backups](zfs-snapshot-retention-and-pruning.md)
- Time Machine capacity management and archive rollover: [Time Machine Retention and Archive Rollover](time-machine-retention-and-rollover.md)
