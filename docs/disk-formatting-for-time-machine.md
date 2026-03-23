# Prepare a ZFS Backup Disk for Time Machine and rsync

This guide prepares a single ZFS backup disk for any of these layouts:

- a Samba Time Machine destination at `/backupz/timemachine`
- an rsync backup area at `/backupz/rsync`
- later snapshot-based history and replication

It is the storage foundation for:

- Time Machine only
- rsync + ZFS snapshots only
- Time Machine + rsync together

## Before you begin

This guide is destructive.

If you run the pool-creation steps against the wrong disk, you can erase the wrong device. Double-check the device path before you continue.

These instructions assume Ubuntu and a single whole backup disk that can be wiped.

## ZFS vs ext4 in this project

For this documentation set, ZFS is the recommended default because it gives you:

- snapshots for the rsync backup history
- `zfs send` / `zfs receive` replication for later disk rotation
- checksumming and dataset-level controls such as `refquota`, `snapdir`, and per-dataset properties

If you only want a basic Time Machine share and do not need snapshots or replication, ext4 is simpler operationally and typically uses less RAM.

That trade-off is documented by the upstream projects:

- OpenZFS recommends at least 4 GiB of memory for normal performance in basic workloads and notes that, on Linux, the ARC cache limit defaults to up to half of system memory. See the [OpenZFS Ubuntu guide](https://openzfs.github.io/openzfs-docs/Getting%20Started/Ubuntu/Ubuntu%2022.04%20Root%20on%20ZFS.html) and the [`zfs(4)` module parameter reference](https://openzfs.github.io/openzfs-docs/man/v2.2/4/zfs.4.html).
- The Linux kernel ext4 docs describe ext4 journaling as protection against metadata inconsistencies after a crash. See the [ext4 admin guide](https://docs.kernel.org/6.18/admin-guide/ext4.html) and the [ext4 journal documentation](https://docs.kernel.org/6.17/filesystems/ext4/journal.html).
- OpenZFS documents snapshots as atomic and documents native send/receive replication. See [`zfs-snapshot(8)`](https://openzfs.github.io/openzfs-docs/man/v2.2/8/zfs-snapshot.8.html), [`zfs-send(8)`](https://openzfs.github.io/openzfs-docs/man/master/8/zfs-send.8.html), and [`zfs-receive(8)`](https://openzfs.github.io/openzfs-docs/man/master/8/zfs-receive.8.html).

This guide does not claim that ext4 is generally safer than ZFS during power loss. The practical comparison here is simpler: ext4 is the simpler filesystem if you do not need ZFS features, while ZFS is the better fit if you want snapshots and replication from day one.

## Planned storage layout

The rest of the docs assume this layout:

```text
backupz
backupz/timemachine            -> /backupz/timemachine
backupz/rsync                  -> /backupz/rsync
backupz/rsync/macbook-air      -> /backupz/rsync/macbook-air
```

You can add more per-Mac datasets later under `backupz/rsync`.

## 1. Install ZFS tools

```bash
sudo apt update
sudo apt install -y zfsutils-linux
```

Confirm the tools are available:

```bash
command -v zpool
command -v zfs
```

## 2. Identify the target disk

List disks and confirm the one you intend to wipe:

```bash
lsblk -o NAME,SIZE,FSTYPE,LABEL,MODEL,SERIAL,MOUNTPOINTS
ls -l /dev/disk/by-id
```

Prefer a stable `/dev/disk/by-id/...` path for pool creation rather than `/dev/sdX`.

Example:

```bash
DISK_ID="/dev/disk/by-id/wwn-0x5000c500abcd1234"
readlink -f "$DISK_ID"
```

## 3. Wipe existing filesystem signatures

Replace `DISK_ID` with your real device path:

```bash
DISK_ID="/dev/disk/by-id/wwn-0x5000c500abcd1234"
findmnt -S "$(readlink -f "$DISK_ID")" || true
sudo umount "$(readlink -f "$DISK_ID")"* 2>/dev/null || true
sudo wipefs -a "$DISK_ID"
```

If you are repurposing an existing backup disk, disable any old mount and share configuration before you wipe it.

For example, if the old disk is mounted through `/etc/fstab`, comment that line out first so the host does not try to remount a filesystem that no longer exists:

```bash
sudo cp /etc/fstab "/etc/fstab.bak.$(date +%Y%m%d-%H%M%S)"
sudoedit /etc/fstab
```

If Samba is still exporting the old path, stop `smbd` until you update the share in the next guide:

```bash
sudo systemctl stop smbd
```

## 4. Create the pool

This creates a single-disk pool named `backupz` with sensible defaults for this project:

```bash
DISK_ID="/dev/disk/by-id/wwn-0x5000c500abcd1234"

sudo zpool create -f \
  -o ashift=12 \
  -O mountpoint=none \
  -O compression=lz4 \
  -O atime=off \
  -O acltype=posixacl \
  -O xattr=sa \
  backupz "$DISK_ID"
```

Check the result:

```bash
sudo zpool status backupz
sudo zpool list backupz
```

Expected result:

- the pool exists with the name `backupz`
- pool state is `ONLINE`
- the whole-disk device under `config:` matches your chosen `/dev/disk/by-id/...` path

## 5. Create the base datasets

Create the Time Machine dataset:

```bash
sudo zfs create \
  -o mountpoint=/backupz/timemachine \
  -o snapdir=hidden \
  backupz/timemachine
```

Create the rsync parent dataset:

```bash
sudo zfs create \
  -o mountpoint=/backupz/rsync \
  backupz/rsync
```

Create the first per-Mac rsync dataset if you already know the Mac name:

```bash
MAC_NAME="macbook-air"

sudo zfs create \
  -o mountpoint="/backupz/rsync/$MAC_NAME" \
  -o snapdir=visible \
  backupz/rsync/"$MAC_NAME"
```

If you are only setting up Time Machine first, you can create the per-Mac rsync dataset later in [Add the rsync Backup Path on Ubuntu](configure-rsync-backup-on-ubuntu.md).

## 6. Apply capacity controls

The Time Machine and rsync areas share the same pool, so set at least one space boundary before you start writing backups.

For this example, assume a single advertised 8 TB backup drive.

In practice, an advertised 8 TB disk does not provide a full 8 TiB of usable space, and ZFS also needs some headroom. A safer starting split is:

- 3.5T for Time Machine
- 3.5T for rsync + ZFS snapshots

Set a 3.5T `refquota` on the Time Machine dataset:

```bash
sudo zfs set refquota=3.5T backupz/timemachine
```

Reserve 3.5T for the rsync side:

```bash
sudo zfs set refreservation=3.5T backupz/rsync
```

That leaves some breathing room for the pool itself instead of overcommitting the disk with a nominal 4T / 4T split.

If you later use a different drive size, scale those numbers to match your real capacity and priorities.

## 7. Verify the layout

```bash
sudo zfs list -o name,mountpoint,used,avail,refer
sudo zfs get -o name,property,value compression,atime,snapdir,refquota,refreservation \
  backupz/timemachine backupz/rsync
```

Expected shape:

```text
backupz
backupz/timemachine      /backupz/timemachine
backupz/rsync            /backupz/rsync
backupz/rsync/macbook-air /backupz/rsync/macbook-air
```

You can also confirm the mountpoints directly:

```bash
findmnt /backupz/timemachine
findmnt /backupz/rsync
```

## 8. What to do next

- For a basic Time Machine server, continue with [DIY Time Capsule: Ubuntu + Samba on ZFS](diy-time-capsule-setup.md) and stop after the Time Machine sections.
- For an rsync + ZFS setup, continue with [Add the rsync Backup Path on Ubuntu](configure-rsync-backup-on-ubuntu.md), then [Set Up rsync Backups from macOS](rsync-backups-from-macos.md).
- To run both paths in parallel, complete the Time Machine guide and the rsync guides.
- For later replica disks and pool rotation, use [ZFS Replication and Backup Rotation](zfs-replication-and-rotation.md).
