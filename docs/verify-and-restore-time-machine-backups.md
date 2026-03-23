# Verify and Restore Time Machine Backups

This guide covers two jobs:

- proving that your Time Machine backup path is really usable
- restoring files after a Mac has failed

It assumes you are using Time Machine over SMB.

## Command context

Unless explicitly marked as Ubuntu server commands, run commands in this guide on a Mac terminal.

- `Mac` means run on the Mac you are using for verification or recovery.
- `Ubuntu server` means run on the backup server host over SSH or local terminal.
- If you use `zsh`, avoid pasting comment lines into the shell unless you first run `setopt interactivecomments`.

## 1. Verify that Time Machine is still writing

Run this on the source Mac while it is still healthy.

Confirm that Time Machine is using the network destination:

`Mac`:

```bash
tmutil destinationinfo
tmutil status
mount | grep smbfs
```

Look for:

- `Kind : Network`
- the expected SMB share
- the expected network URL, such as `smb://<user>@<host>._smb._tcp.local./TimeCapsule`
- `Running = 0` after the backup completes

If you used your normal Samba username instead of a dedicated `timemachine` account during setup, that is fine. The checks in this guide work with either account.

It is normal for `tmutil destinationinfo` to show more than one destination. If the Mac also has local Time Machine history or other backup targets configured, focus on whether the expected `Network` destination is present.

It is also normal for `mount | grep smbfs` to return nothing when the network backup is idle. The SMB mount may appear only while a backup is actively running or while the share is in use.

If you want server-side proof that the network backup is being written, check sparsebundle band timestamps before and after a backup:

`Ubuntu server`:

```bash
find /backupz/timemachine -maxdepth 3 -type f -path '*/bands/*' -printf '%T@ %p\n' | sort -n | tail -n 5
```

Replace `/backupz/timemachine` if your mountpoint is different.

## 2. Restore from Time Machine on a different Mac

This flow proves all of the following:

- the Time Machine share is reachable
- the sparsebundle exists
- the backup can be mounted read-only
- files can be browsed and copied out

### 2.1 Find the share name

If the source Mac is still available:

`Mac (source Mac)`:

```bash
tmutil destinationinfo
```

Take the last path component from the network destination URL.

If the source Mac is unavailable, discover the share from the recovery Mac:

`Mac (different Mac)`:

```bash
SERVER_HOST="192.168.1.10"
SMB_USER="<samba-user>"
smbutil view "//$SMB_USER@$SERVER_HOST"
```

Set:

```bash
SHARE_NAME="TimeCapsule"
```

If needed, you can also list shares from the server:

`Ubuntu server`:

```bash
testparm -s 2>/dev/null | sed -n 's/^\[\(.*\)\]$/\1/p' | grep -Ev '^(global|printers|print\$)$'
```

### 2.2 Define variables and clean up old mounts

`Mac (different Mac)`:

```bash
cd ~
SERVER_HOST="192.168.1.10"
SMB_USER="<samba-user>"
SHARE_NAME="TimeCapsule"
BUNDLE_NAME="My-Source-Mac.sparsebundle"
```

Detach any older image mounts and unmount stale SMB mounts:

`Mac (different Mac)`:

```bash
hdiutil info | awk '/Backups of /{print $1}' | while read -r dev; do hdiutil detach -force "$dev"; done
for mp in $(mount | awk -v s="/$SHARE_NAME " '$0 ~ /smbfs/ && index($0,s){print $3}'); do diskutil unmount force "$mp"; done
```

### 2.3 Mount the SMB share

`Mac (different Mac)`:

```bash
SHARE_MOUNT="/Volumes/$SHARE_NAME"
sudo mkdir -p "$SHARE_MOUNT"
sudo chown "$USER":staff "$SHARE_MOUNT"
mount_smbfs "//$SMB_USER@$SERVER_HOST/$SHARE_NAME" "$SHARE_MOUNT"
find "$SHARE_MOUNT" -maxdepth 1 -type d -name '*.sparsebundle' -print
```

If more than one sparsebundle is listed, choose the right one and update `BUNDLE_NAME`.

Use the Samba username that the Time Machine share actually allows. For example, if your Samba share uses `valid users = chris`, set `SMB_USER="chris"` throughout this section.

`BUNDLE_NAME` must match the actual sparsebundle directory on the server, such as `My-MacBook-Air.sparsebundle`. If you are unsure, use the `find "$SHARE_MOUNT" ...` output from section **2.3** instead of guessing.

### 2.4 Attach the backup read-only

`Mac (different Mac)`:

```bash
SOURCE_BUNDLE="$SHARE_MOUNT/$BUNDLE_NAME"
test -d "$SOURCE_BUNDLE"
hdiutil attach -readonly "$SOURCE_BUNDLE"
```

Success should show a mounted `Backups of ...` volume.

If `hdiutil attach` fails with `Resource busy`, check for stale Samba sessions:

`Ubuntu server`:

```bash
sudo smbstatus
sudo systemctl restart smbd
```

Then remount the share and retry.

### 2.5 Browse the mounted backup

`Mac (different Mac)`:

```bash
BACKUP_VOLUME="/Volumes/Backups of ${BUNDLE_NAME%.sparsebundle}"
open "$BACKUP_VOLUME"
ls -la "$BACKUP_VOLUME" || sudo ls -la "$BACKUP_VOLUME"
find "$BACKUP_VOLUME" -maxdepth 2 -type d | head -n 40 || sudo find "$BACKUP_VOLUME" -maxdepth 2 -type d | head -n 40
```

If you can see snapshot directories such as `2026-03-20-161440.previous`, the backup is mounted and readable.

Because the mounted backup path contains spaces, always quote it. For example, use `ls -la "$BACKUP_VOLUME"` rather than `ls -la /Volumes/Backups of ...`.

### 2.6 Copy files out

`Mac (different Mac)`:

```bash
BACKUP_VOLUME="/Volumes/Backups of ${BUNDLE_NAME%.sparsebundle}"
SNAPSHOT_NAME="<snapshot-name>.previous"
SOURCE_VOLUME="<source-volume>"
SOURCE_REL_PATH="<path-inside-source-volume>"
SOURCE_PATH="$BACKUP_VOLUME/$SNAPSHOT_NAME/$SOURCE_VOLUME/$SOURCE_REL_PATH"
mkdir -p "$HOME/Recovered-from-TimeMachine"
rsync -avh "$SOURCE_PATH" "$HOME/Recovered-from-TimeMachine/"
```

If the copy succeeds, the Time Machine backup is usable for recovery.

`SOURCE_VOLUME` can vary by Mac and macOS install. Common examples include `Macintosh HD - Data`, but it may also be a host-specific name such as `macos15-2026-01 - Data`. Use `ls "$BACKUP_VOLUME/$SNAPSHOT_NAME"` to discover the correct value before copying.

## 3. Cleanly detach after verification

`Mac`:

```bash
BACKUP_VOLUME="/Volumes/Backups of ${BUNDLE_NAME%.sparsebundle}"
diskutil unmount "$BACKUP_VOLUME" 2>/dev/null || true
diskutil unmount "$SHARE_MOUNT" 2>/dev/null || true
```

## 4. Troubleshooting

### `.sparsebundle` looks like a directory

Expected. Sparsebundles are package directories.

### `hdiutil attach` fails with `No such file or directory`

If the sparsebundle path is correct and `Info.plist` is valid, check for a missing `token` file:

`Mac`:

```bash
test -e "$SOURCE_BUNDLE/token" && echo "token exists" || echo "token missing"
touch "$SOURCE_BUNDLE/token"
chmod 600 "$SOURCE_BUNDLE/token"
```

Then retry `hdiutil attach -readonly "$SOURCE_BUNDLE"`.
