# Verify And Restore Time Machine Backups (CLI)

This guide is for two jobs:

- testing that network Time Machine backups are really readable
- recovering files from a backup after a Mac has failed

If you are actively recovering from a failed source Mac, start at section **2**.

## Command context

Unless explicitly marked as Ubuntu server commands, run commands in this guide on a Mac terminal.

- `Mac` means run on the Mac you are using for verification or recovery.
- `Ubuntu server` means run on the Time Machine server host over SSH or local terminal.
- If you are using `zsh`, avoid pasting comment lines into the shell unless you first run `setopt interactivecomments`.

## 1. Optional: verify that new backups are writing

Run this on the source Mac when it is still healthy.

Confirm Time Machine is using the network destination:

`Mac`:

```bash
tmutil destinationinfo
tmutil status
mount | grep smbfs
```

Look for a `Kind : Network` destination and confirm backup activity finishes with `Running = 0`.

If you want server-side proof that the network backup is being written, check sparsebundle band timestamps before and after a backup:

`Ubuntu server`:

```bash
find /srv/timecapsule -maxdepth 3 -type f -path '*/bands/*' -printf '%T@ %p\n' | sort -n | tail -n 5
```

Replace `/srv/timecapsule` with your real backup root if different.

## 2. Recovery flow: mount, browse, and copy files from a different Mac

Run this on a different Mac than the one that created the backup.

This flow proves all of the following:

- the Time Machine share is reachable
- the source Mac sparsebundle exists
- the backup can be mounted read-only
- files can be browsed and read
- files can be copied out

### 2.1 Find the share name

If the source Mac is still available, you can get the network destination from:

`Mac (source Mac)`:

```bash
tmutil destinationinfo
```

Look for the `Kind : Network` entry and take the last path component of its URL as the share name.

If the source Mac has crashed or is unavailable, discover the share from the recovery Mac:

`Mac (different Mac)`:

```bash
SERVER_HOST="192.168.1.10"
SMB_USER="backupuser"
smbutil view "//$SMB_USER@$SERVER_HOST"
```

Choose the Time Machine share from the list and set:

```bash
SHARE_NAME="timemachine"
```

If needed, you can also discover shares from the server:

`Ubuntu server`:

```bash
testparm -s 2>/dev/null | sed -n 's/^\[\(.*\)\]$/\1/p' | grep -Ev '^(global|printers|print\$)$'
```

### 2.2 Mount the SMB share

For terminal or SSH sessions, use `mount_smbfs`. This is more reliable than `open smb://...`.

`Mac (different Mac)`:

```bash
SERVER_HOST="192.168.1.10"
SMB_USER="backupuser"
MOUNT_POINT="$HOME/mnt/tm-share"
mkdir -p "$MOUNT_POINT"
mount_smbfs "//$SMB_USER@$SERVER_HOST/$SHARE_NAME" "$MOUNT_POINT"
mount | grep "$MOUNT_POINT"
```

When mounted this way, the network share appears at `"$MOUNT_POINT"`.

### 2.3 Find the source Mac sparsebundle

`Mac (different Mac)`:

```bash
find "$MOUNT_POINT" -maxdepth 1 -type d -name '*.sparsebundle' -print
SOURCE_BUNDLE="$(find "$MOUNT_POINT" -maxdepth 1 -type d -name '*.sparsebundle' | head -n 1)"
SOURCE_MAC_NAME="$(basename "$SOURCE_BUNDLE" .sparsebundle)"
echo "SOURCE_BUNDLE=$SOURCE_BUNDLE"
echo "SOURCE_MAC_NAME=$SOURCE_MAC_NAME"
```

If more than one sparsebundle is listed, choose the correct one and set `SOURCE_BUNDLE` manually.

### 2.4 Attach the backup read-only

`Mac (different Mac)`:

```bash
hdiutil attach -readonly "$SOURCE_BUNDLE"
```

Success looks like this pattern:

```text
/dev/disk2
/dev/disk3              EF57347C-0000-11AA-AA11-0030654
/dev/disk3s1            41504653-0000-11AA-AA11-0030654 /Volumes/Backups of My-Source-Mac
```

If `hdiutil attach` fails with `Resource busy`, the sparsebundle is usually locked by another Mac or stale SMB state. This recovery path often fixes it:

`Ubuntu server`:

```bash
sudo smbstatus
sudo systemctl restart smbd
```

`Mac (different Mac)`:

```bash
umount "$MOUNT_POINT" 2>/dev/null || true
mount_smbfs "//$SMB_USER@$SERVER_HOST/$SHARE_NAME" "$MOUNT_POINT"
hdiutil attach -readonly "$SOURCE_BUNDLE"
```

### 2.5 Find the mounted backup volume and latest snapshot

`Mac (different Mac)`:

```bash
ls -d "/Volumes/Backups of "* 2>/dev/null
MP="$(ls -d "/Volumes/Backups of "* 2>/dev/null | grep "$SOURCE_MAC_NAME" | head -n 1)"
echo "MP=$MP"
sudo tmutil listbackups -m "$MP"
SNAP="$(sudo tmutil listbackups -m "$MP" | tail -n 1)"
echo "SNAP=$SNAP"
```

### 2.6 Browse the backup contents

Start by identifying the source volume and user folders:

`Mac (different Mac)`:

```bash
sudo ls "$SNAP"
VOL="Macintosh HD - Data"
sudo ls "$SNAP/$VOL/Users"
SOURCE_USER_NAME="myuser"
sudo ls -la "$SNAP/$VOL/Users/$SOURCE_USER_NAME"
sudo find "$SNAP/$VOL/Users/$SOURCE_USER_NAME" -maxdepth 2 -type f | head -n 40
```

If `VOL="Macintosh HD - Data"` does not exist, choose a volume name from the `sudo ls "$SNAP"` output.

At this point you can spot-check files directly. For example:

`Mac (different Mac)`:

```bash
ls "$SNAP/$VOL/Users/$SOURCE_USER_NAME/Documents"
cat "$SNAP/$VOL/Users/$SOURCE_USER_NAME/Documents/example.txt"
```

If you can successfully run `ls` or `cat` on files inside the mounted backup, that is already strong proof that the backup data is readable.

### 2.7 Copy files out

For a simple recovery test, use `rsync` first. It is a good default because it preserves timestamps and is better suited to large or repeated copies than plain `cp`.

`Mac (different Mac)`:

```bash
SRC="$SNAP/$VOL/Users/$SOURCE_USER_NAME/Documents/example.txt"
mkdir -p "$HOME/Recovered-test"
rsync -a --progress "$SRC" "$HOME/Recovered-test/"
ls -l "$HOME/Recovered-test/$(basename "$SRC")"
```

If you prefer a Time Machine-aware restore command, use:

`Mac (different Mac)`:

```bash
SRC="$SNAP/$VOL/Users/$SOURCE_USER_NAME/Documents/example.txt"
mkdir -p "$HOME/Recovered-test"
DST="$HOME/Recovered-test/$(basename "$SRC")"
sudo tmutil restore "$SRC" "$DST"
ls -l "$DST"
```

If you only want the simplest possible direct copy, `cp "$SRC" "$HOME/Recovered-test/"` is still a fine fallback for a single file.

If any of these commands restore the file into `~/Recovered-test`, recovery from the network backup is working.

## 3. Cleanly detach after verification

`Mac`:

```bash
diskutil unmount "$MP" 2>/dev/null || true
umount "$MOUNT_POINT" 2>/dev/null || true
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

Then retry attach.

### `hdiutil attach` fails with `Resource busy`

Follow the recovery path in section **2.4**. In practice, restarting Samba on the server often clears stale sessions and resolves this.

### Mounted backup root shows `Operation not permitted`

This can happen with modern APFS Time Machine backup structure and macOS permissions.

If needed, grant Terminal or iTerm Full Disk Access in macOS Privacy settings and retry.

### Mounted share is empty or missing in `/Volumes`

If you mounted with `mount_smbfs`, use `"$MOUNT_POINT"` instead of looking under `/Volumes/<share-name>`.
