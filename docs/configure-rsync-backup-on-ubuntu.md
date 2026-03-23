# Add the rsync Backup Path on Ubuntu

This guide adds an rsync backup path to the Ubuntu server.

Use it if you want an rsync-based backup path with:

- direct file access from Linux
- normal-file restores with `rsync`, `cp`, and `find`
- ZFS snapshot history outside the Time Machine sparsebundle
- a cleaner base for later replication and disk rotation

You can use this guide in either of these ways:

- as an add-on after a basic Time Machine setup
- as the primary backup path on a server that does not use Time Machine

## Before you begin

This guide assumes:

- the backup pool and base datasets already exist from [Prepare a ZFS Backup Disk for Time Machine and rsync](disk-formatting-for-time-machine.md)
- `backupz/rsync` is mounted at `/backupz/rsync`
- `openssh-server` is installed and running, or you will install it as part of this guide

If you also want a Time Machine destination on the same server, complete [DIY Time Capsule: Ubuntu + Samba on ZFS](diy-time-capsule-setup.md) separately.

## 1. Install SSH server if needed

```bash
sudo apt update
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
sudo systemctl status ssh --no-pager --lines=0
```

## 2. Create the rsync backup account

Use a separate SSH identity for rsync writes. Do not reuse the Samba `timemachine` account.

```bash
sudo useradd -m -s /bin/bash rsync-backup 2>/dev/null || true
sudo passwd -l rsync-backup
sudo install -d -o rsync-backup -g rsync-backup -m 700 /home/rsync-backup/.ssh
```

The account remains SSH-key-only because it has no usable password.

## 3. Create the per-Mac ZFS dataset

Choose a stable machine name. Keep it lowercase and avoid spaces.

This name must match the `MAC_NAME` value you use later in the Mac-side backup script and in the restricted `sudoers` rule.

If you already created this dataset in the storage guide, skip the `zfs create` line and just verify the mountpoint and `current/` directory ownership.

```bash
MAC_NAME="macbook-air"

sudo zfs list backupz/rsync/"$MAC_NAME" >/dev/null 2>&1 || sudo zfs create \
  -o mountpoint="/backupz/rsync/$MAC_NAME" \
  -o snapdir=visible \
  backupz/rsync/"$MAC_NAME"

sudo install -d -o rsync-backup -g rsync-backup -m 0750 \
  "/backupz/rsync/$MAC_NAME/current"
```

Check it:

```bash
zfs list backupz/rsync/"$MAC_NAME"
findmnt "/backupz/rsync/$MAC_NAME"
ls -ld "/backupz/rsync/$MAC_NAME" "/backupz/rsync/$MAC_NAME/current"
```

## 4. Optional: allow normal users to browse backups read-only

Keep `rsync-backup` as the write identity, but grant read-only access through a separate group.

This is the cleanest model if you want an operator account to inspect `current/` and future snapshots without using `sudo`.

```bash
MAC_NAME="macbook-air"
OPERATOR_USER="your-ubuntu-username"

sudo groupadd --force backupreaders
sudo usermod -aG backupreaders "$OPERATOR_USER"

sudo setfacl -m g:backupreaders:rX \
  "/backupz/rsync/$MAC_NAME" \
  "/backupz/rsync/$MAC_NAME/current"

sudo find "/backupz/rsync/$MAC_NAME/current" -type d -exec \
  setfacl -m g:backupreaders:rX -m d:g:backupreaders:rX {} +

sudo find "/backupz/rsync/$MAC_NAME/current" -type f -exec \
  setfacl -m g:backupreaders:rX {} +
```

Notes:

- log out and back in after adding users to `backupreaders`
- a full reboot or a brand-new SSH login session is the simplest way to guarantee the new group is active
- create a fresh snapshot after this change so future snapshots preserve the new ACLs
- snapshots created before this ACL change may still require `sudo`

Quick check:

```bash
getent group backupreaders
getfacl -p "/backupz/rsync/$MAC_NAME/current" | sed -n '1,20p'
```

Then create one fresh snapshot after the ACL change:

```bash
sudo -u rsync-backup sudo /usr/local/sbin/capsule-rsync-post-backup "$MAC_NAME"
```

## 5. Install a root-owned post-backup snapshot helper

The clean v1 model is:

1. the Mac runs rsync into `current`
2. a successful run calls one restricted server-side helper
3. that helper creates a ZFS snapshot of the per-Mac dataset

Create the helper:

```bash
sudoedit /usr/local/sbin/capsule-rsync-post-backup
```

Use:

```bash
#!/usr/bin/env bash
set -euo pipefail

MAC_NAME="${1:?usage: capsule-rsync-post-backup <mac-name>}"
DATASET="backupz/rsync/$MAC_NAME"
STAMP="$(date +%Y-%m-%d-%H%M)"

/usr/sbin/zfs list -H -o name "$DATASET" >/dev/null
/usr/sbin/zfs snapshot "$DATASET@auto-$STAMP"
```

Make it executable:

```bash
sudo chmod 755 /usr/local/sbin/capsule-rsync-post-backup
```

Quick check:

```bash
ls -l /usr/local/sbin/capsule-rsync-post-backup
```

## 6. Allow `rsync-backup` to run only that helper with `sudo`

Edit a dedicated sudoers snippet:

```bash
sudo visudo -f /etc/sudoers.d/rsync-backup-snapshot
```

For a single Mac named `macbook-air`, use:

```sudoers
rsync-backup ALL=(root) NOPASSWD: /usr/local/sbin/capsule-rsync-post-backup macbook-air
```

If you add more Macs later, add one line per approved Mac name.

Quick check:

```bash
sudo -l -U rsync-backup
```

You should see the allowed `capsule-rsync-post-backup <mac-name>` command in the output.

## 7. Install the Mac SSH key

Because `rsync-backup` is password-locked, the first key install must go through a server admin account or a local `sudo` session on Ubuntu.

The Mac-side setup and key-install command are documented in [Set Up rsync Backups from macOS](rsync-backups-from-macos.md).

## 8. Smoke-test the rsync account

Once the key is installed, this should work from the Mac:

```bash
ssh -i "$HOME/.ssh/id_ed25519_capsule_backup" rsync-backup@<server-ip> "whoami && pwd"
```

Expected output includes:

```text
rsync-backup
/home/rsync-backup
```

## 9. What to do next

- For the Mac-side rsync job, use [Set Up rsync Backups from macOS](rsync-backups-from-macos.md).
- For restore validation, use [Verify and Restore rsync + ZFS Backups](verify-and-restore-rsync-backups.md).
- If you also want Apple-native Time Machine backups, add [DIY Time Capsule: Ubuntu + Samba on ZFS](diy-time-capsule-setup.md).
- For later replica disks and `zfs send` / `zfs receive`, use [ZFS Replication and Backup Rotation](zfs-replication-and-rotation.md).
