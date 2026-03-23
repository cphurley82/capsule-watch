# Time Machine Retention and Archive Rollover

This guide covers capacity management for the Time Machine side of the backup system.

TODO: This guide has not been validated end to end on the live system yet. The rollover model matches the validated Time Machine and replication design, but the actual archive-and-reset workflow still needs operator testing.

It assumes:

- Time Machine is backing up to `backupz/timemachine` over SMB
- Time Machine history lives inside a sparsebundle
- you may also be replicating the backup pool to removable ZFS replica disks

Use this guide when:

- the Time Machine area is getting too full
- you want to preserve an older Time Machine generation on removable media
- you want to start a fresh active Time Machine generation on the primary pool

If you are looking for rsync-side ZFS snapshot pruning instead, use [ZFS Snapshot Retention and Pruning for rsync Backups](zfs-snapshot-retention-and-pruning.md).

## What Time Machine does and does not manage

Apple Time Machine manages its own normal backup history inside the sparsebundle.

That means:

- the normal restore timeline is owned by Time Machine
- `backupz/timemachine` is not the same kind of operator-facing snapshot-history dataset as `backupz/rsync/<mac-name>`
- you should not manually prune sparsebundle internals on the server

Time Machine may delete older backups internally as space becomes tight, but do not build your whole capacity plan around that behavior alone.

For this design, the safer long-term approach is:

- keep the active Time Machine generation on the primary pool
- archive older generations to removable replica disks when needed

## Recommended operator rule

When the Time Machine side gets too full and you want to preserve older history:

- archive the whole Time Machine dataset externally
- then intentionally start a fresh Time Machine generation on the primary

That is safer than trying to surgically trim sparsebundle contents from the server side.

## Signs you may want a rollover

Consider rollover when:

- `backupz/timemachine` is approaching its `refquota`
- the primary `backupz` pool is getting too full
- you want to preserve the current Time Machine generation before reclaiming primary space

## 1. Make sure no Time Machine backup is active

Before taking an archive checkpoint, make sure the Mac is not actively writing to the Time Machine destination.

You can check from the Mac with `tmutil`, or from the server by watching whether the sparsebundle is still being actively modified.

## 2. Take an archive checkpoint

Create a snapshot that will be used only for transport or archive purposes:

```bash
STAMP="archive-$(date +%Y-%m-%d-%H%M)"
sudo zfs snapshot backupz/timemachine@"$STAMP"
```

If you want to be extra careful until replication finishes, place a hold on it:

```bash
sudo zfs hold keep backupz/timemachine@"$STAMP"
```

## 3. Replicate the archived Time Machine generation

Send that snapshot to a removable archive or replica pool:

```bash
ARCHIVE_POOL="your-existing-archive-pool-name"

sudo zfs send backupz/timemachine@"$STAMP" | \
  sudo zfs receive -uF "$ARCHIVE_POOL"/timemachine-"$STAMP"
```

This gives you a whole-dataset archive generation on the removable disk.

## 4. Verify the archive copy

Check that the archive dataset and snapshot exist:

```bash
ARCHIVE_POOL="your-existing-archive-pool-name"

sudo zfs list "$ARCHIVE_POOL"/timemachine-"$STAMP"
sudo zfs list -t snapshot -o name,creation -s creation "$ARCHIVE_POOL"/timemachine-"$STAMP"
```

If you used a hold, release it after verification:

```bash
sudo zfs release keep backupz/timemachine@"$STAMP"
```

## 5. Recreate the live Time Machine dataset on the primary

Only do this after you have confirmed the archive copy is good.

Destroy and recreate the live dataset:

```bash
sudo zfs destroy -r backupz/timemachine
sudo zfs create -o mountpoint=/backupz/timemachine -o snapdir=hidden backupz/timemachine
sudo chown root:tmbackup /backupz/timemachine
sudo chmod 2770 /backupz/timemachine
```

If you use Samba ACLs or local ACLs on `/backupz/timemachine`, reapply them now.

## 6. Let Time Machine start a fresh active generation

After the live dataset is recreated:

1. reconnect the Mac if needed
2. confirm the SMB Time Machine share is still reachable
3. let Time Machine start a fresh backup generation on the primary pool

At that point:

- recent active history lives on the primary pool
- older archived history lives on the removable archive disk

## Operational notes

- This workflow breaks the Time Machine history into generations.
- Recent restores come from the current active generation.
- Older restores come from the archived removable generation.
- That tradeoff is usually worth it when you need to reclaim primary space safely.
