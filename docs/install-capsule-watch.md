# Install Capsule Watch

This guide assumes you have already completed the DIY Time Capsule setup and verified that Time Machine backups are working over Samba.

For CLI-first backup validation and restore testing (including recovery to a different Mac), see [Verify and restore Time Machine backups (CLI)](verify-and-restore-time-machine-backups.md).

This install path has been validated against a local Ubuntu 24.04 host and reflects the current repository layout (`config/`, `deploy/systemd/`, and Python CLI entry points).

## What this guide covers

After completing this guide, you should have:

- the Capsule Watch application code under `/opt/capsule-watch`
- a local configuration file at `/etc/capsule-watch/config.yaml`
- a dedicated `capsule-watch` service user
- a web service that starts on boot
- collector and alert timers managed by `systemd`

## Before you begin

Make sure your server already has:

- a working Samba Time Machine share
- `avahi-daemon` running if you rely on Bonjour discovery
- at least one successful backup from a Mac
- SSH or local terminal access to the Ubuntu host
- `sudo` access on the Ubuntu host

## Prerequisite tools

Start by installing and testing the base tools Capsule Watch depends on. On a minimal Ubuntu install, `wget` may be present when `curl` is not, and `python3` may be available without `pip`, so it is worth verifying the toolchain explicitly up front.

### Install the base packages

```bash
sudo apt update
sudo apt install -y git wget curl python3 smartmontools
```

On Ubuntu, installing `smartmontools` may also create or enable `smartmontools.service` and related `smartd` unit links. That is expected and separate from Capsule Watch's own services.

### Install `uv`

Download the installer with either `curl` or `wget`, then install `uv` to `/usr/local/bin` so it is available to both your admin user and the `capsule-watch` service account later.

With `curl`:

```bash
curl -LsSf https://astral.sh/uv/install.sh -o /tmp/install-uv.sh
sudo env UV_UNMANAGED_INSTALL=/usr/local/bin sh /tmp/install-uv.sh
```

With `wget`:

```bash
wget -qO /tmp/install-uv.sh https://astral.sh/uv/install.sh
sudo env UV_UNMANAGED_INSTALL=/usr/local/bin sh /tmp/install-uv.sh
```

Do not assume `python3 -m pip` is available on a fresh Ubuntu install. Use the official `uv` installer instead.

### Verify the toolchain

```bash
git --version
python3 --version
wget --version | head -n 1
curl --version | head -n 1
systemctl --version | head -n 1
visudo -V | head -n 1
smartctl --version | head -n 1
uv --version
```

At this stage, `smartctl --version` should work without `sudo`. Device-specific SMART queries come later and may require the dedicated `sudoers` configuration in this guide.

Tested on Ubuntu 24.04 with:

- `Python 3.12.3`
- `git 2.43.0`
- `GNU Wget 1.21.4`
- `curl 8.5.0`
- `systemd 255`
- `visudo 1.9.15p5`
- `smartctl 7.4`
- `uv 0.10.12`

Validated end-to-end on March 20, 2026.

## Verify monitoring tools and host access

Before installing Capsule Watch itself, verify that the host exposes the data sources the collectors will depend on.

### Verify the core monitoring commands

```bash
command -v smartctl tune2fs df uptime free systemctl
smartctl --scan
systemctl status smbd --no-pager --lines=0
systemctl status avahi-daemon --no-pager --lines=0
uptime
free -h
```

What this confirms:

- `smartctl --scan` can discover candidate storage devices
- `systemctl` can see the Samba and Avahi services Capsule Watch expects to monitor
- `uptime` and `free` provide the basic host telemetry used by the dashboard

### Verify the backup volume path

First identify the actual filesystem and mount point on the server:

```bash
lsblk -f
```

Then check the filesystem mounted at your Time Machine storage path:

```bash
df -hT /path/to/your/time-machine-root
```

Do not assume the path is `/srv/timecapsule`. Use the real mount point from your host.

If your backup volume is ext4, this command should show `Type` as `ext4`. That confirms the host can support the planned ext4 filesystem metadata checks.

Also verify the backup root contains sparsebundle directories:

```bash
ls -ld /path/to/your/time-machine-root
find /path/to/your/time-machine-root -maxdepth 1 -type d -name '*.sparsebundle'
```

If sparsebundles are present but backup recency later reports `No sparsebundle backups found`, verify service-user permissions in the Troubleshooting section.

A common fix is to grant the `capsule-watch` service account read/traverse access with ACLs:

```bash
sudo apt install -y acl
sudo setfacl -m u:capsule-watch:rx /path/to/your/time-machine-root
sudo setfacl -R -m u:capsule-watch:rX /path/to/your/time-machine-root/*.sparsebundle
```

Then re-run the path checks above before continuing.

### Verify privileged disk inspection commands

Some checks require elevated access to block devices even though the binaries themselves are installed correctly.

Without `sudo`, these commands may fail with `Permission denied`:

```bash
smartctl -H /dev/<disk>
tune2fs -l /dev/<filesystem>
```

Verify them with `sudo`:

```bash
sudo smartctl -H /dev/<disk>
sudo tune2fs -l /dev/<filesystem> | head -n 20
```

If these succeed, you have confirmed that the host can support SMART health checks and ext4 filesystem metadata checks. The later `sudoers` step in this guide narrows that access for the `capsule-watch` service account.

Expected results:

- `smartctl` should reach the device and report an overall health result such as `PASSED`
- `tune2fs` should print filesystem metadata like the volume name, UUID, mount path, and block size

Some drives may also print vendor-specific SMART warnings while still returning a usable health result. Treat those as signals to review, but not necessarily as proof the command path is broken.

## 1. Create the service user and directories

Create a dedicated system user and the runtime directories:

```bash
sudo useradd --system --home /opt/capsule-watch --shell /usr/sbin/nologin capsule-watch
sudo mkdir -p /opt/capsule-watch
sudo mkdir -p /etc/capsule-watch
sudo mkdir -p /var/lib/capsule-watch
sudo mkdir -p /var/log/capsule-watch
sudo chown -R capsule-watch:capsule-watch /opt/capsule-watch /var/lib/capsule-watch /var/log/capsule-watch
sudo chown root:capsule-watch /etc/capsule-watch
sudo chmod 755 /opt/capsule-watch /var/lib/capsule-watch /var/log/capsule-watch
sudo chmod 750 /etc/capsule-watch
```

Verify the user and directory layout:

```bash
getent passwd capsule-watch
ls -ld /opt/capsule-watch /etc/capsule-watch /var/lib/capsule-watch /var/log/capsule-watch
```

Expected shape:

- `capsule-watch` uses `/usr/sbin/nologin`
- `/opt/capsule-watch`, `/var/lib/capsule-watch`, and `/var/log/capsule-watch` are owned by `capsule-watch:capsule-watch`
- `/etc/capsule-watch` is owned by `root:capsule-watch` and is not world-readable

## 2. Clone the repository

Clone the project into the application directory:

```bash
sudo git clone https://github.com/<your-org-or-user>/capsule-watch.git /opt/capsule-watch
sudo chown -R capsule-watch:capsule-watch /opt/capsule-watch
```

Verify the clone as the `capsule-watch` user:

```bash
sudo -u capsule-watch -H git -C /opt/capsule-watch rev-parse --short HEAD
ls -la /opt/capsule-watch
```

If you are installing from your own fork or local mirror, replace the repository URL accordingly.

If you run `git -C /opt/capsule-watch ...` as your normal user after changing ownership to `capsule-watch`, Git may report `detected dubious ownership`. That is expected. Prefer running Git verification commands against this directory as the `capsule-watch` user.

## 3. Create the Python environment

Sync the project environment as the `capsule-watch` user:

```bash
sudo -u capsule-watch -H /usr/local/bin/uv sync --frozen --project /opt/capsule-watch
```

This command is based on the current scaffold, where the runtime model is:

- project metadata in `pyproject.toml`
- a committed `uv.lock`
- a project-local virtual environment managed by `uv`

At the current project stage, this step should create the virtual environment successfully when the repository includes `pyproject.toml` and `uv.lock`.

## 4. Create the configuration file

Start from the versioned example file in the repository:

```bash
sudo cp /opt/capsule-watch/config/config.example.yaml /etc/capsule-watch/config.yaml
sudoedit /etc/capsule-watch/config.yaml
```

Set at least the following values for your host:

- `paths.time_machine_root`
- `services.samba_unit` and `services.avahi_unit` if you use non-default unit names
- `alerts.email.*` if email delivery is enabled

Important: `paths.time_machine_root` should point to the directory that directly contains your `*.sparsebundle` folders. If it points one level too high or too low, backup recency will report `No sparsebundle backups found`.

Then lock down file permissions:

```bash
sudo chown root:capsule-watch /etc/capsule-watch/config.yaml
sudo chmod 640 /etc/capsule-watch/config.yaml
```

## 5. Grant limited privileged access

Capsule Watch should not run as `root`, and the web UI should not ask for a sudo password.

For commands that truly need elevated access, grant only narrowly scoped privileges. For example, create a `sudoers` drop-in:

```bash
sudo visudo -f /etc/sudoers.d/capsule-watch
```

Example contents:

```sudoers
capsule-watch ALL=(root) NOPASSWD: /usr/sbin/smartctl
capsule-watch ALL=(root) NOPASSWD: /usr/sbin/tune2fs
```

Keep this list as small as possible. The current collectors only elevate `smartctl` and `tune2fs`.

Capsule Watch collectors first attempt these commands directly and automatically retry with `sudo -n` only when they receive a permission-related failure. That means you should not need to run the whole app as `root`, and the service will not prompt for an interactive password.

Validate the `sudoers` file before continuing:

```bash
sudo visudo -cf /etc/sudoers.d/capsule-watch
```

Optional runtime check as the service user:

```bash
sudo -u capsule-watch -H sudo -n smartctl --scan
sudo -u capsule-watch -H sudo -n tune2fs -l /dev/<filesystem> | head -n 5
```

## 6. Install the web service

Install the versioned unit file from the repository:

```bash
sudo cp /opt/capsule-watch/deploy/systemd/capsule-watch-web.service /etc/systemd/system/capsule-watch-web.service
```

## 7. Install the collector service and timer

Install the collector unit and timer from the repository:

```bash
sudo cp /opt/capsule-watch/deploy/systemd/capsule-watch-collector.service /etc/systemd/system/capsule-watch-collector.service
sudo cp /opt/capsule-watch/deploy/systemd/capsule-watch-collector.timer /etc/systemd/system/capsule-watch-collector.timer
```

## 8. Install the alert service and timer

Install the alert unit and timer from the repository:

```bash
sudo cp /opt/capsule-watch/deploy/systemd/capsule-watch-alert.service /etc/systemd/system/capsule-watch-alert.service
sudo cp /opt/capsule-watch/deploy/systemd/capsule-watch-alert.timer /etc/systemd/system/capsule-watch-alert.timer
```

## 9. Enable services on boot

Reload `systemd`, enable the web service, and start the timers:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now capsule-watch-web.service
sudo systemctl enable --now capsule-watch-collector.timer
sudo systemctl enable --now capsule-watch-alert.timer
```

## 10. Verify the installation

Check service status:

```bash
systemctl status capsule-watch-web.service --no-pager -l
systemctl status capsule-watch-collector.timer --no-pager -l
systemctl status capsule-watch-alert.timer --no-pager -l
```

Check recent logs:

```bash
journalctl -u capsule-watch-web.service -n 50
journalctl -u capsule-watch-collector.service -n 50
journalctl -u capsule-watch-alert.service -n 50
```

If you are troubleshooting a fresh change, filter logs by time so older startup failures do not distract from current state:

```bash
journalctl -u capsule-watch-web.service --since "10 minutes ago" --no-pager
journalctl -u capsule-watch-collector.service --since "10 minutes ago" --no-pager
```

Force a collector run and check the resulting snapshot:

```bash
sudo systemctl start capsule-watch-collector.service
curl -sS http://127.0.0.1:8080/api/status | python3 -m json.tool
```

If the web service is running, open:

```text
http://<server-ip>:8080/
http://<server-ip>:8080/recovery
```

The main dashboard should show the latest saved snapshot rather than collecting live data during page loads.

The Recovery Assistant page should show discovered sparsebundle backups and copyable recovery commands for mounting and browsing backups from another Mac.

## 11. Email alerts (planned)

Email is the intended first notification channel, but SMTP delivery is not wired in yet.

Today, the alert service evaluates transitions and stores alert state in `paths.alerts_file`. Keep the `alerts.email` section configured so you are ready once notifier delivery lands.

## Troubleshooting

### `Permission denied: /etc/capsule-watch/config.yaml`

Make sure both the config directory and file allow group traverse/read for `capsule-watch`:

```bash
sudo chown root:capsule-watch /etc/capsule-watch
sudo chmod 750 /etc/capsule-watch
sudo chown root:capsule-watch /etc/capsule-watch/config.yaml
sudo chmod 640 /etc/capsule-watch/config.yaml
```

### Backup recency shows `No sparsebundle backups found`

1. Confirm `paths.time_machine_root` points directly to the directory containing `*.sparsebundle`.
2. Confirm the service account can enumerate it:

```bash
sudo -u capsule-watch -H ls -ld /path/to/your/time-machine-root
sudo -u capsule-watch -H find /path/to/your/time-machine-root -maxdepth 1 -type d -name '*.sparsebundle'
```

3. If needed, grant read/traverse access with ACLs:

```bash
sudo setfacl -m u:capsule-watch:rx /path/to/your/time-machine-root
sudo setfacl -R -m u:capsule-watch:rX /path/to/your/time-machine-root/*.sparsebundle
```

### SMART or filesystem checks stay in warning/unknown

Verify `sudoers` parsing and command access:

```bash
sudo visudo -cf /etc/sudoers.d/capsule-watch
sudo -u capsule-watch -H sudo -n smartctl --scan
sudo -u capsule-watch -H sudo -n tune2fs -l /dev/<filesystem> | head -n 5
```

### `uv` is not found under `sudo`

Use a full path to the binary:

```bash
sudo -u capsule-watch -H /usr/local/bin/uv sync --frozen --project /opt/capsule-watch
```

### Old errors still show in `journalctl` after a fix

Use time-filtered logs while validating current behavior:

```bash
journalctl -u capsule-watch-web.service --since "10 minutes ago" --no-pager
journalctl -u capsule-watch-collector.service --since "10 minutes ago" --no-pager
```
