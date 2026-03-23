# Set Up rsync Backups from macOS

This guide configures a Mac to send an rsync backup stream to the Ubuntu server over SSH.

It assumes the Ubuntu server already has:

- the ZFS layout from [Prepare a ZFS Backup Disk for Time Machine and rsync](disk-formatting-for-time-machine.md)
- the rsync server-side setup from [Add the rsync Backup Path on Ubuntu](configure-rsync-backup-on-ubuntu.md)

This guide intentionally starts with a conservative allowlist of high-value directories rather than trying to mirror the entire Mac.

## What this backup is for

Use this backup path for:

- direct file access from Linux
- restore without Apple Time Machine tooling
- ZFS snapshot history outside the sparsebundle

Do not treat it as a full system image.

## 1. Install a modern rsync on the Mac

The built-in macOS `rsync` is old. Use Homebrew's current build instead:

```bash
brew install rsync
RSYNC_BIN="$(brew --prefix rsync)/bin/rsync"
"$RSYNC_BIN" --version
```

All automation below uses the Homebrew binary explicitly.

## 2. Create a dedicated SSH key for backup traffic

```bash
ssh-keygen -t ed25519 -f "$HOME/.ssh/id_ed25519_capsule_backup" -C "rsync-backup@$(scutil --get ComputerName)"
```

For unattended `launchd` runs, the simplest option is to leave this backup key without a passphrase. If you protect it with a passphrase, background runs will need additional SSH agent or Keychain setup.

Install the public key on the server from an Ubuntu shell:

```bash
sudo install -d -o rsync-backup -g rsync-backup -m 700 /home/rsync-backup/.ssh
sudo vim /home/rsync-backup/.ssh/authorized_keys
```

Paste the Mac's public key from `~/.ssh/id_ed25519_capsule_backup.pub` into `authorized_keys` as a single line, then save and exit.

Fix ownership and permissions:

```bash
sudo chown rsync-backup:rsync-backup /home/rsync-backup/.ssh/authorized_keys
sudo chmod 600 /home/rsync-backup/.ssh/authorized_keys
```

Test the login:

```bash
SERVER_HOST="<server-ip-or-hostname>"
KEY_FILE="$HOME/.ssh/id_ed25519_capsule_backup"
ssh -i "$KEY_FILE" rsync-backup@"$SERVER_HOST" "whoami && pwd"
```

## 3. Choose what to back up

Start with a broad allowlist of absolute paths plus a separate exclude file for noisy or sensitive data.

Create a sources file:

```bash
mkdir -p "$HOME/.config/capsule-backup" "$HOME/bin"
cat > "$HOME/.config/capsule-backup/rsync-sources.txt" <<'EOF'
# One path per line, absolute and starting with /.
/Users
/Applications
EOF
```

Create an exclude file:

```bash
cat > "$HOME/.config/capsule-backup/rsync-excludes.txt" <<'EOF'
# One exclude pattern per line, using absolute source paths.
/Users/*/Library/Caches/**
/Users/*/Library/Logs/**
/Users/*/.Trash
/Users/*/.Trash/**
/Users/*/.cache/**
/Users/*/.zsh_sessions/**
/Users/*/Library/Accounts/**
/Users/*/Library/AppleMediaServices/**
/Users/*/Library/Application Support/AddressBook/**
/Users/*/Library/Application Support/CallHistoryDB/**
/Users/*/Library/Application Support/CallHistoryTransactions/**
/Users/*/Library/Application Support/CloudDocs/**
/Users/*/Library/Application Support/DifferentialPrivacy/**
/Users/*/Library/Application Support/FaceTime/**
/Users/*/Library/Application Support/FileProvider/**
/Users/*/Library/Application Support/Knowledge/**
/Users/*/Library/Application Support/MobileSync/**
/Users/*/Library/Application Support/com.apple.TCC/**
/Users/*/Library/Application Support/com.apple.avfoundation/Frecents/**
/Users/*/Library/Application Support/com.apple.sharedfilelist/**
/Users/*/Library/Application Support/Claude/vm_bundles/**
/Users/*/Library/Assistant/SiriVocabulary/**
/Users/*/Library/Autosave Information/**
/Users/*/Library/Biome/**
/Users/*/Library/Calendars/**
/Users/*/Library/ContainerManager/**
/Users/*/Library/Containers/com.apple.*
/Users/*/Library/Containers/com.apple.*/**
/Users/*/Library/Cookies/**
/Users/*/Library/CoreFollowUp/**
/Users/*/Library/Daemon Containers/**
/Users/*/Library/DoNotDisturb/**
/Users/*/Library/DuetExpertCenter/**
/Users/*/Library/Group Containers/com.apple.*
/Users/*/Library/Group Containers/com.apple.*/**
/Users/*/Library/Group Containers/group.com.apple.*
/Users/*/Library/Group Containers/group.com.apple.*/**
/Users/*/Library/HomeKit/**
/Users/*/Library/IdentityServices/**
/Users/*/Library/IntelligencePlatform/**
/Users/*/Library/Mail/**
/Users/*/Library/Messages/**
/Users/*/Library/Metadata/CoreSpotlight/**
/Users/*/Library/Metadata/com.apple.IntelligentSuggestions/**
/Users/*/Library/PersonalizationPortrait/**
/Users/*/Library/Safari/**
/Users/*/Library/Sharing/**
/Users/*/Library/Shortcuts/**
/Users/*/Library/StatusKit/**
/Users/*/Library/Suggestions/**
/Users/*/Library/Trial/**
/Users/*/Library/Weather/**
/Users/*/Library/com.apple.aiml.instrumentation/**
/Users/*/Library/com.apple.bluetooth.services.cloud/CachedRecords/SoundProfileAsset/**
/Users/*/Library/Preferences/com.apple.AddressBook.plist
/Users/*/Library/Preferences/com.apple.homed.plist
/Users/*/.docker/**
/Users/*/.colima/**
/Users/*/.local/share/containers/**
/Users/*/.ssh/id_*
/Users/*/.gnupg/**
EOF
```

Keep the sources file broad and the exclude file opinionated.

Good candidates:

- `/Users`
- `/Applications`
- selected external-drive paths such as `/Volumes/MediaDrive/Projects`
- narrower user-data paths such as `/Users/your-macos-username/Documents` if you do not want the whole `/Users` tree

Good default excludes:

- user caches and logs
- trash directories
- Apple-private `Library` databases and app-state trees that commonly trigger `Operation not permitted`
- File Provider tombstones and similar sync metadata
- VM or container disk images
- private SSH and GPG keys
- app-specific transient bundles that can grow rapidly

Be careful with broad excludes under `Library`. Some application data in `Library/Application Support` is valuable and should be kept.

The script below rewrites these absolute exclude patterns per source before each rsync run, so you can keep the exclude file easy to read.

If an exclude ends in `/**`, the script should also exclude the parent directory itself. Without that extra parent-dir exclude, rsync can still descend into protected macOS paths and emit `Operation not permitted` during automated runs.

The backup keeps the same path shape under the server-side `current/` tree. For example, `/Users/chris/Documents` becomes `/backupz/rsync/<mac-name>/current/Users/chris/Documents`.

Using `/Users` is the simplest broad option, but many people later narrow it to a smaller allowlist once they better understand what they do and do not want to retain.

## 4. Create the backup script

Create `~/bin/backup-to-capsule-rsync.zsh`:

```bash
cat > "$HOME/bin/backup-to-capsule-rsync.zsh" <<'EOF'
#!/bin/zsh
set -euo pipefail

umask 077
PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin"

SERVER_HOST="<server-ip-or-hostname>"
REMOTE_USER="rsync-backup"
MAC_NAME="macbook-air"
KEY_FILE="$HOME/.ssh/id_ed25519_capsule_backup"

if [[ -x /opt/homebrew/bin/brew ]]; then
  BREW_BIN="/opt/homebrew/bin/brew"
elif [[ -x /usr/local/bin/brew ]]; then
  BREW_BIN="/usr/local/bin/brew"
else
  echo "Homebrew not found in /opt/homebrew/bin or /usr/local/bin" >&2
  exit 1
fi

RSYNC_BIN="$("$BREW_BIN" --prefix rsync)/bin/rsync"
SSH_BIN="/usr/bin/ssh"
CONFIG_DIR="$HOME/.config/capsule-backup"
STATE_DIR="$HOME/.local/state/capsule-backup"
SOURCES_FILE="$CONFIG_DIR/rsync-sources.txt"
EXCLUDES_FILE="$CONFIG_DIR/rsync-excludes.txt"
REMOTE_ROOT="/backupz/rsync/$MAC_NAME/current"
STATUS_FILE="$STATE_DIR/status.txt"
LAST_SUCCESS_FILE="$STATE_DIR/last-success.txt"
LAST_FAILURE_FILE="$STATE_DIR/last-failure.txt"
LOCK_DIR="$STATE_DIR/run.lock"
START_TIME="$(date '+%Y-%m-%d %H:%M:%S %Z')"
LOCK_OWNED=0
FORCE_RUN=0
STATUS_FINALIZED=0

while (( $# > 0 )); do
  case "$1" in
    --force)
      FORCE_RUN=1
      shift
      ;;
    *)
      echo "Usage: $0 [--force]" >&2
      exit 2
      ;;
  esac
done

mkdir -p "$STATE_DIR"

write_status() {
  local run_state="$1"
  local exit_code="$2"
  local end_time="$3"
  local note="${4:-}"

  cat > "$STATUS_FILE" <<EOF_STATUS
status=$run_state
exit_code=$exit_code
start_time=$START_TIME
end_time=$end_time
server_host=$SERVER_HOST
mac_name=$MAC_NAME
note=$note
EOF_STATUS
}

finalize_status() {
  local run_state="$1"
  local exit_code="$2"
  local stamp

  stamp="$(date '+%Y-%m-%d %H:%M:%S %Z')"
  write_status "$run_state" "$exit_code" "$stamp"

  if [[ "$run_state" == "success" ]]; then
    printf '%s\n' "$stamp" > "$LAST_SUCCESS_FILE"
  else
    printf '%s\n' "$stamp" > "$LAST_FAILURE_FILE"
  fi
}

record_skip() {
  local note="$1"
  local stamp

  stamp="$(date '+%Y-%m-%d %H:%M:%S %Z')"
  write_status "skipped" "0" "$stamp" "$note"
  STATUS_FINALIZED=1
}

cleanup() {
  local exit_code=$?

  if [[ "$LOCK_OWNED" -eq 1 ]]; then
    rm -rf "$LOCK_DIR"
  fi

  if [[ "${STATUS_FINALIZED:-0}" -eq 0 ]]; then
    finalize_status "failed" "$exit_code" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  if [[ -f "$LOCK_DIR/pid" ]]; then
    existing_pid="$(<"$LOCK_DIR/pid")"
    if kill -0 "$existing_pid" 2>/dev/null; then
      echo "Another backup run is already in progress with pid $existing_pid"
      record_skip "already_running"
      exit 0
    fi
  fi

  rm -rf "$LOCK_DIR"
  mkdir "$LOCK_DIR"
fi

printf '%s\n' "$$" > "$LOCK_DIR/pid"
LOCK_OWNED=1
write_status "running" "0" "-"

for required_path in "$KEY_FILE" "$SOURCES_FILE" "$EXCLUDES_FILE"; do
  [[ -r "$required_path" ]] || { echo "Missing required file: $required_path" >&2; exit 1; }
done

[[ -x "$RSYNC_BIN" ]] || { echo "rsync binary not found: $RSYNC_BIN" >&2; exit 1; }

SSH_OPTS=(
  -i "$KEY_FILE"
  -o BatchMode=yes
  -o ConnectTimeout=10
  -o ServerAliveInterval=30
  -o ServerAliveCountMax=3
)

echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] Starting capsule rsync backup"
echo "Server: $SERVER_HOST"
echo "Mac dataset: $MAC_NAME"

today_stamp="$(date '+%Y-%m-%d')"
if [[ "$FORCE_RUN" -eq 0 && -r "$LAST_SUCCESS_FILE" ]]; then
  last_success="$(<"$LAST_SUCCESS_FILE")"
  if [[ "$last_success" == "$today_stamp"* ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] Backup already completed today; skipping"
    record_skip "already_completed_today"
    exit 0
  fi
fi

"$SSH_BIN" "${SSH_OPTS[@]}" "$REMOTE_USER@$SERVER_HOST" "true"

if [[ -t 1 ]]; then
  RSYNC_INFO="progress2,stats2"
else
  RSYNC_INFO="stats2"
fi

backup_status=0

while IFS= read -r src; do
  [[ -z "$src" || "$src" == \#* ]] && continue
  [[ "$src" == /* ]] || { echo "Path must be absolute: $src" >&2; backup_status=1; continue; }

  if [[ ! -e "$src" ]]; then
    echo "Missing path: $src" >&2
    backup_status=1
    continue
  fi

  remote_rel="${src#/}"
  exclude_tmp="$(mktemp "${TMPDIR:-/tmp}/capsule-rsync-exclude.XXXXXX")"

  while IFS= read -r raw_exclude; do
    [[ -z "$raw_exclude" || "$raw_exclude" == \#* ]] && continue
    [[ "$raw_exclude" == "$src" || "$raw_exclude" == "$src/"* ]] || continue
    mapped_exclude="${raw_exclude#$src}"
    printf '%s\n' "$mapped_exclude" >> "$exclude_tmp"

    # Also exclude the parent directory so rsync does not descend into
    # protected macOS paths before the recursive pattern takes effect.
    if [[ "$mapped_exclude" == */\*\* ]]; then
      printf '%s\n' "${mapped_exclude%/\*\*}" >> "$exclude_tmp"
    fi
  done < "$EXCLUDES_FILE"

  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] Starting rsync for: $src"

  if [[ -d "$src" ]]; then
    "$RSYNC_BIN" \
      --archive \
      --human-readable \
      --info="$RSYNC_INFO" \
      --partial \
      --protect-args \
      --delete \
      --delete-excluded \
      --mkpath \
      --exclude-from="$exclude_tmp" \
      -e "$SSH_BIN ${SSH_OPTS[*]}" \
      "$src/" \
      "$REMOTE_USER@$SERVER_HOST:$REMOTE_ROOT/$remote_rel/" || backup_status=1
  else
    "$RSYNC_BIN" \
      --archive \
      --human-readable \
      --info="$RSYNC_INFO" \
      --partial \
      --protect-args \
      --mkpath \
      --exclude-from="$exclude_tmp" \
      -e "$SSH_BIN ${SSH_OPTS[*]}" \
      "$src" \
      "$REMOTE_USER@$SERVER_HOST:$REMOTE_ROOT/$remote_rel" || backup_status=1
  fi

  rm -f "$exclude_tmp"
done < "$SOURCES_FILE"

if (( backup_status != 0 )); then
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] Backup finished with rsync errors"
  finalize_status "failed" "$backup_status"
  STATUS_FINALIZED=1
  exit "$backup_status"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] Creating snapshot for: $MAC_NAME"
"$SSH_BIN" "${SSH_OPTS[@]}" "$REMOTE_USER@$SERVER_HOST" \
  "sudo /usr/local/sbin/capsule-rsync-post-backup '$MAC_NAME'"

echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] Backup completed successfully"
finalize_status "success" "0"
STATUS_FINALIZED=1
EOF
chmod 700 "$HOME/bin/backup-to-capsule-rsync.zsh"
```

Set `SERVER_HOST` and `MAC_NAME` to match the server and per-Mac ZFS dataset you created on Ubuntu.

`MAC_NAME` must exactly match the dataset name and the allowed `sudoers` entry on the Ubuntu server.

Use a normalized lowercase name such as `macbook-air` or `office-mac-mini`. Avoid spaces and punctuation.

This script does the following:

1. syncs each approved path into `current/...` using the same path shape it has on the Mac
2. fails if any listed source is missing or any rsync run fails
3. skips paths matched by the exclude file
4. removes excluded files from `current/...` on later runs if they were copied earlier
5. takes a ZFS snapshot only after the whole run succeeds
6. writes a simple local status record so you can check the last successful or failed run later
7. avoids overlapping runs by using a lock directory under `~/.local/state/capsule-backup`
8. under the laptop-friendly schedule, skips quickly if a successful backup already happened today unless you pass `--force`

## 5. Run the first backup manually

Before the first run, give the app that launches the script the macOS privacy permissions it needs.

Typical setup:

- If you run the script from Terminal, enable Full Disk Access for `Terminal`.
- If you run it from VS Code's integrated terminal, enable Full Disk Access for `Visual Studio Code`.
- If you run it from iTerm, enable Full Disk Access for `iTerm`.
- In `Privacy & Security -> Files and Folders`, approve access prompts for locations such as Desktop, Documents, Downloads, removable volumes, and network volumes if your chosen sources need them.

Open `System Settings -> Privacy & Security -> Full Disk Access` and enable the launcher app before the first long run.

Even with Full Disk Access, do not assume literally every macOS-managed path will behave well. Keep using the exclude file for noisy or privacy-protected locations that are not worth fighting.

If the run ends with `rsync error ... (code 23)` and many `Operation not permitted` lines, the usual fixes are:

- confirm Full Disk Access is enabled for the launcher app you are actually using
- restart that launcher app after changing macOS privacy settings
- confirm the live script includes the current exclude rewrite logic from step 4
- extend the exclude file for the Apple-managed `Library` paths that are still denied

Then run:

```bash
"$HOME/bin/backup-to-capsule-rsync.zsh"
```

If you need to bypass the once-per-day guard and run the backup again manually on the same day, use:

```bash
"$HOME/bin/backup-to-capsule-rsync.zsh" --force
```

Use `--force` from the same terminal app that already has the needed macOS privacy permissions. A same-day forced rerun launched from a different shell context can still hit `Operation not permitted` even when the normal operator workflow is healthy.

After it finishes, verify from the server:

`Ubuntu server`:

```bash
MAC_NAME="macbook-air"
find "/backupz/rsync/$MAC_NAME/current" -maxdepth 3 | head -n 40
zfs list -t snapshot -o name,creation -s creation backupz/rsync/"$MAC_NAME"
```

The first command should show normal files. The second should show a new `auto-...` snapshot.

If you did not configure `backupreaders` on Ubuntu, rerun the inspection command with `sudo`.

## 6. Automate it with `launchd`

`launchd` tends to surface automation bugs faster than an interactive shell because it starts with a smaller environment and does not benefit from your terminal app's context.

The example below is laptop-friendly: `launchd` checks once per hour, and the script exits quickly if a successful backup already happened today.

Create a per-user LaunchAgent:

```bash
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$HOME/Library/LaunchAgents/local.capsule-backup.rsync.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>local.capsule-backup.rsync</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>/Users/REPLACE_ME/bin/backup-to-capsule-rsync.zsh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/REPLACE_ME</string>
  <key>ProcessType</key>
  <string>Background</string>
  <key>RunAtLoad</key>
  <true/>
  <key>StartInterval</key>
  <integer>3600</integer>
  <key>StandardOutPath</key>
  <string>/Users/REPLACE_ME/Library/Logs/capsule-backup-rsync.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/REPLACE_ME/Library/Logs/capsule-backup-rsync.log</string>
</dict>
</plist>
EOF
```

Replace `REPLACE_ME` with your macOS username before loading it:

```bash
plutil -lint "$HOME/Library/LaunchAgents/local.capsule-backup.rsync.plist"
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/local.capsule-backup.rsync.plist" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/local.capsule-backup.rsync.plist"
launchctl kickstart -k "gui/$(id -u)/local.capsule-backup.rsync"
```

Check status:

```bash
launchctl print "gui/$(id -u)/local.capsule-backup.rsync"
tail -n 50 "$HOME/Library/Logs/capsule-backup-rsync.log"
sed -n '1,80p' "$HOME/.local/state/capsule-backup/status.txt"
```

Expected result:

- `launchctl print` eventually shows `last exit code = 0`
- the log either shows a real backup run ending with `Backup completed successfully` or a fast skip with `Backup already completed today; skipping`
- the status file shows either `status=success` or `status=skipped`
- Ubuntu shows a fresh `auto-...` snapshot for the per-Mac dataset when the run actually performs a backup instead of skipping

For hourly checks, the common healthy pattern is:

- the first successful run of the day creates the fresh Ubuntu snapshot
- later hourly runs that same day exit quickly with `status=skipped` and `note=already_completed_today`

If you want to run the real backup path again on the same day instead of the skip path, run the script manually with `--force` from your normal terminal app first, then re-check Ubuntu for the fresh snapshot.

If the forced run still shows many `Operation not permitted` lines for paths that are already in the exclude file, pause and inspect the generated exclude handling before assuming the problem is only Full Disk Access.

## 7. Mac-side files

These are the main files and paths involved on the Mac side after setup:

| Path | Purpose |
| --- | --- |
| `$HOME/.ssh/id_ed25519_capsule_backup` | Private SSH key used by the backup script to connect to `rsync-backup` on Ubuntu. |
| `$HOME/.ssh/id_ed25519_capsule_backup.pub` | Public key you install into `/home/rsync-backup/.ssh/authorized_keys` on Ubuntu. |
| `$HOME/.config/capsule-backup/rsync-sources.txt` | Allowlist of source paths to back up. |
| `$HOME/.config/capsule-backup/rsync-excludes.txt` | Exclude patterns filtered per source before each rsync run. |
| `$HOME/bin/backup-to-capsule-rsync.zsh` | Main Mac-side backup script for manual and automated runs. |
| `$HOME/Library/LaunchAgents/local.capsule-backup.rsync.plist` | Per-user LaunchAgent that schedules the background backup job. |
| `$HOME/Library/Logs/capsule-backup-rsync.log` | Combined stdout/stderr log from `launchd` runs. |
| `$HOME/.local/state/capsule-backup/status.txt` | Latest run status summary written by the script. |
| `$HOME/.local/state/capsule-backup/last-success.txt` | Timestamp of the most recent successful run. |
| `$HOME/.local/state/capsule-backup/last-failure.txt` | Timestamp of the most recent failed run. |
| `$HOME/.local/state/capsule-backup/run.lock` | Transient lock directory used to prevent overlapping runs. |

Typical inspection commands:

```bash
sed -n '1,80p' "$HOME/.local/state/capsule-backup/status.txt"
tail -n 50 "$HOME/Library/Logs/capsule-backup-rsync.log"
launchctl print "gui/$(id -u)/local.capsule-backup.rsync"
```

## 8. Restore data later

Use [Verify and Restore rsync + ZFS Backups](verify-and-restore-rsync-backups.md) for:

- latest-state restore from `current`
- historical restore from `/.zfs/snapshot/...`
- replacement-Mac copy-back

## 9. Notes and limitations

- This workflow is intentionally conservative. It backs up selected user data, not the whole system.
- If a backup relies on macOS-specific metadata, package directories, or protected locations, test that data set explicitly before you trust it.
- If you later need multiple Macs, create one ZFS dataset per Mac and one LaunchAgent per Mac or profile.
