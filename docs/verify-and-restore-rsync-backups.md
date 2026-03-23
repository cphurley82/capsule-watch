# Verify and Restore rsync + ZFS Backups

This guide covers two jobs:

- proving that your rsync + ZFS backup path is really usable
- restoring files after a Mac has failed

It assumes you are using the rsync backup path described in:

- [Add the rsync Backup Path on Ubuntu](configure-rsync-backup-on-ubuntu.md)
- [Set Up rsync Backups from macOS](rsync-backups-from-macos.md)

## Command context

Unless explicitly marked as Ubuntu server commands, run commands in this guide on a Mac terminal.

- `Mac` means run on the Mac you are using for verification or recovery.
- `Ubuntu server` means run on the backup server host over SSH or local terminal.
- If you use `zsh`, avoid pasting comment lines into the shell unless you first run `setopt interactivecomments`.

## 1. Verify that the rsync backup path is writing

### 1.0 List the available Mac backup names

If you do not remember the exact `MAC_NAME`, list the per-Mac datasets first.

`Ubuntu server`:

```bash
zfs list -r -o name,mountpoint backupz/rsync
```

Look for dataset names such as:

```text
backupz/rsync/macbook-air
backupz/rsync/office-mac-mini
```

Use the last path segment as `MAC_NAME`.

### 1.1 Confirm the latest tree exists on the server

`Ubuntu server`:

```bash
MAC_NAME="macbook-air"
find "/backupz/rsync/$MAC_NAME/current" -maxdepth 3 -type f | head -n 20
```

You should see normal files, not a sparsebundle.

If you did not configure the `backupreaders` group from [Add the rsync Backup Path on Ubuntu](configure-rsync-backup-on-ubuntu.md), rerun the inspection command with `sudo`.

### 1.2 Confirm snapshots are being created

`Ubuntu server`:

```bash
MAC_NAME="macbook-air"
zfs list -t snapshot -o name,creation -s creation backupz/rsync/"$MAC_NAME"
```

You should see snapshots with names such as:

```text
backupz/rsync/macbook-air@auto-2026-03-21-0100
```

### 1.3 Confirm the latest backup changed after a run

`Ubuntu server`:

```bash
MAC_NAME="macbook-air"
find "/backupz/rsync/$MAC_NAME/current" -type f -printf '%TY-%Tm-%Td %TH:%TM:%TS %p\n' | sort | tail -n 20
```

On a large backup tree, this command can take a while because it walks the full dataset and sorts every matching file.

If timestamps move forward after a backup run, the latest tree is updating.

## 2. Restore the latest version from rsync

This is the simplest restore path.

`Mac`:

```bash
SERVER_HOST="<server-ip-or-hostname>"
MAC_NAME="macbook-air"
MACOS_USER="your-macos-username"
KEY_FILE="$HOME/.ssh/id_ed25519_capsule_backup"
RESTORE_PATH="Users/$MACOS_USER/Documents"
mkdir -p "$HOME/Recovered-from-rsync-latest"
rsync -avh -e "ssh -i $KEY_FILE" \
  "rsync-backup@$SERVER_HOST:/backupz/rsync/$MAC_NAME/current/$RESTORE_PATH/" \
  "$HOME/Recovered-from-rsync-latest/Documents/"
```

Adjust `RESTORE_PATH` to the path you want to recover from inside the mirrored backup tree.

If your source list used absolute paths such as `/Users` and `/Applications`, the restore path should match that mirrored shape, for example `Users/$MACOS_USER/Documents` or `Applications`.

If the copy succeeds, latest-state restore from the rsync path is working.

## 3. Restore an older version from a ZFS snapshot

This is the main reason the rsync path lives on ZFS.

First list snapshots:

`Ubuntu server`:

```bash
MAC_NAME="macbook-air"
zfs list -t snapshot -o name,creation -s creation backupz/rsync/"$MAC_NAME"
```

Choose one snapshot and restore from its `.zfs/snapshot/...` path:

`Mac`:

```bash
SERVER_HOST="<server-ip-or-hostname>"
MAC_NAME="macbook-air"
SNAPSHOT_NAME="auto-2026-03-21-0100"
MACOS_USER="your-macos-username"
KEY_FILE="$HOME/.ssh/id_ed25519_capsule_backup"
RESTORE_PATH="Users/$MACOS_USER/Documents"
mkdir -p "$HOME/Recovered-from-rsync-snapshot"
rsync -avh -e "ssh -i $KEY_FILE" \
  "rsync-backup@$SERVER_HOST:/backupz/rsync/$MAC_NAME/.zfs/snapshot/$SNAPSHOT_NAME/current/$RESTORE_PATH/" \
  "$HOME/Recovered-from-rsync-snapshot/Documents/"
```

If the copy succeeds, historical restore from the snapshot path is working.

Use the same mirrored-path logic for snapshot restores. For example, if the original source was `/Users/chris/Documents`, restore from `Users/chris/Documents` inside the snapshot tree.

If you use the `backupreaders` model, snapshots created after that ACL change should be readable to normal operator accounts. Older snapshots may still require `sudo`.

## 4. Restore to a replacement Mac from rsync

On a replacement Mac, the simplest flow is:

1. create the destination directories you want locally
2. copy from `current` for the latest version
3. copy from `/.zfs/snapshot/...` if you need an older version

Example:

`Mac (replacement Mac)`:

```bash
SERVER_HOST="<server-ip-or-hostname>"
MAC_NAME="macbook-air"
MACOS_USER="your-macos-username"
KEY_FILE="$HOME/.ssh/id_ed25519_capsule_backup"
mkdir -p "$HOME/Restored-home"
rsync -avh -e "ssh -i $KEY_FILE" \
  "rsync-backup@$SERVER_HOST:/backupz/rsync/$MAC_NAME/current/Users/$MACOS_USER/" \
  "$HOME/Restored-home/"
```

This is not a full macOS system image restore. It is a straightforward file restore.

## 5. Troubleshooting

### `Permission denied` while restoring from rsync

Verify that:

- the SSH key matches the one installed for `rsync-backup`
- the per-Mac dataset exists
- `current/` is owned by `rsync-backup`
- your normal operator account is either using `sudo` for inspection or is in `backupreaders`
- if you expect non-`sudo` snapshot browsing, you created at least one fresh snapshot after the `backupreaders` ACL change

Useful checks on the server:

`Ubuntu server`:

```bash
MAC_NAME="macbook-air"
sudo ls -ld /home/rsync-backup /home/rsync-backup/.ssh /backupz/rsync/"$MAC_NAME" /backupz/rsync/"$MAC_NAME"/current
```

If you configured read-only operator access, also check:

`Ubuntu server`:

```bash
getent group backupreaders
getfacl -p /backupz/rsync/"$MAC_NAME"/current | sed -n '1,20p'
```

### `.zfs/snapshot/...` is missing

Check both of these:

`Ubuntu server`:

```bash
MAC_NAME="macbook-air"
zfs get snapdir backupz/rsync/"$MAC_NAME"
zfs list -t snapshot backupz/rsync/"$MAC_NAME"
```

For snapshot browsing through the filesystem, `snapdir` must be `visible` and at least one snapshot must exist.
