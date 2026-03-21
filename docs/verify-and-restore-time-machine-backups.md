# Verify and Restore Time Machine Backups

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

### 2.2 Define the recovery variables and clean up old mounts

This validated flow uses a normal `/Volumes/<share-name>` mount on the recovery Mac.

`Mac (different Mac)`:

```bash
cd ~
SERVER_HOST="192.168.1.10"
SMB_USER="backupuser"
SHARE_NAME="timemachine"
BUNDLE_NAME="My-Source-Mac.sparsebundle"
```

Before remounting, detach any older backup image mounts and unmount any stale SMB mount for the same share:

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

That final `find` command should list the sparsebundle you intend to inspect.

If more than one sparsebundle is listed, choose the right one and set `BUNDLE_NAME` manually before continuing.

### 2.4 Attach the backup read-only

`Mac (different Mac)`:

```bash
SOURCE_BUNDLE="$SHARE_MOUNT/$BUNDLE_NAME"
test -d "$SOURCE_BUNDLE"
hdiutil attach -readonly "$SOURCE_BUNDLE"
```

Success looks like this pattern:

```text
/dev/disk4
/dev/disk5              EF57347C-0000-11AA-AA11-0030654
/dev/disk5s1            41504653-0000-11AA-AA11-0030654 /Volumes/Backups of My-Source-Mac
```

If `hdiutil attach` fails with `Resource busy`, the sparsebundle is usually locked by another Mac or stale Samba session state.

Try this on the server:

`Ubuntu server`:

```bash
sudo smbstatus
sudo systemctl restart smbd
```

Then on the recovery Mac, remount the SMB share from section **2.3** and retry `hdiutil attach -readonly "$SOURCE_BUNDLE"`.

### 2.5 Browse the mounted backup

`Mac (different Mac)`:

```bash
BACKUP_VOLUME="/Volumes/Backups of ${BUNDLE_NAME%.sparsebundle}"
open "$BACKUP_VOLUME"
ls -la "$BACKUP_VOLUME" || sudo ls -la "$BACKUP_VOLUME"
find "$BACKUP_VOLUME" -maxdepth 2 -type d | head -n 40 || sudo find "$BACKUP_VOLUME" -maxdepth 2 -type d | head -n 40
```

If you can list the backup root and see snapshot directories such as `2026-03-20-161440.previous`, the backup is mounted and readable.

If you see `Operation not permitted`, give Terminal or iTerm Full Disk Access in macOS Privacy settings and retry.

### 2.6 Drill down to the file you want

From the snapshot list, choose the snapshot and source volume you want:

`Mac (different Mac)`:

```bash
cd "$BACKUP_VOLUME"
ls
```

Example:

```bash
SNAPSHOT_NAME="2026-03-20-161440.previous"
SOURCE_VOLUME="Macintosh HD - Data"
cd "$BACKUP_VOLUME/$SNAPSHOT_NAME/$SOURCE_VOLUME"
ls
```

At this point you can browse normally with `cd`, `ls`, `find`, `cat`, or `open`.

### 2.7 Copy files out

Use `rsync` as the default recovery tool. It is a good fit for both single files and large directory trees.

`Mac (different Mac)`:

```bash
BACKUP_VOLUME="/Volumes/Backups of ${BUNDLE_NAME%.sparsebundle}"
SNAPSHOT_NAME="<snapshot-name>.previous"
SOURCE_VOLUME="<source-volume>"
SOURCE_REL_PATH="<path-inside-source-volume>"
SOURCE_PATH="$BACKUP_VOLUME/$SNAPSHOT_NAME/$SOURCE_VOLUME/$SOURCE_REL_PATH"
echo "$SOURCE_PATH"
mkdir -p "$HOME/Recovered-from-TimeMachine"
rsync -avh "$SOURCE_PATH" "$HOME/Recovered-from-TimeMachine/"
```

For example, if you want to recover a directory from `Users/alex/Pictures/photo-library`:

```bash
BACKUP_VOLUME="/Volumes/Backups of ${BUNDLE_NAME%.sparsebundle}"
SNAPSHOT_NAME="2026-03-20-161440.previous"
SOURCE_VOLUME="Macintosh HD - Data"
SOURCE_REL_PATH="Users/alex/Pictures/photo-library"
SOURCE_PATH="$BACKUP_VOLUME/$SNAPSHOT_NAME/$SOURCE_VOLUME/$SOURCE_REL_PATH"
mkdir -p "$HOME/Recovered-from-TimeMachine"
rsync -avh "$SOURCE_PATH" "$HOME/Recovered-from-TimeMachine/"
```

If `rsync` copies the file or directory into `~/Recovered-from-TimeMachine`, recovery from the network backup is working.

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

Then retry attach.

### `hdiutil attach` fails with `Resource busy`

Follow the recovery path in section **2.4**. In practice, restarting Samba on the server often clears stale sessions and resolves this.

### Mounted backup root shows `Operation not permitted`

This can happen with modern APFS Time Machine backup structure and macOS permissions.

If needed, grant Terminal or iTerm Full Disk Access in macOS Privacy settings and retry.

### Mounted share is empty or missing in `/Volumes`

If you mounted with `mount_smbfs`, make sure you are looking at the actual mount path you used, such as `"/Volumes/$SHARE_NAME"`.
