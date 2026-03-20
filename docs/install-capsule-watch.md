# Install Capsule Watch

This guide assumes you have already completed the DIY Time Capsule setup and verified that Time Machine backups are working over Samba.

Capsule Watch is still in the planning stage at the time of writing, so this page documents the intended installation layout for the first release. Treat it as the target setup shape rather than a copy-paste-verified installer.

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
sudo chown root:root /etc/capsule-watch
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
- `/etc/capsule-watch` is owned by `root:root` and is not world-readable

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

Create `/etc/capsule-watch/config.yaml`:

```yaml
server:
  host: 0.0.0.0
  port: 8080

paths:
  time_machine_root: /path/to/your/time-machine-root
  snapshot_file: /var/lib/capsule-watch/status.json
  alerts_file: /var/lib/capsule-watch/alerts.json

services:
  samba_unit: smbd
  avahi_unit: avahi-daemon

thresholds:
  backup_warning_hours: 26
  backup_critical_hours: 48
  disk_warning_percent: 85
  disk_critical_percent: 95

alerts:
  email:
    enabled: false
    from: capsule-watch@example.com
    to:
      - you@example.com
    smtp_host: smtp.example.com
    smtp_port: 587
    username: smtp-user
    password: change-me
    starttls: true
```

Then lock down the file permissions:

```bash
sudo chown root:capsule-watch /etc/capsule-watch/config.yaml
sudo chmod 640 /etc/capsule-watch/config.yaml
```

This file shape is intentionally illustrative for now. The final config schema should be treated as authoritative once the application code exists.

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
capsule-watch ALL=(root) NOPASSWD: /usr/bin/systemctl status smbd
capsule-watch ALL=(root) NOPASSWD: /usr/bin/systemctl status avahi-daemon
```

Keep this list as small as possible. If the final implementation uses wrapper scripts instead of direct commands, prefer the wrapper-script approach.

## 6. Install the web service

Create `/etc/systemd/system/capsule-watch-web.service`:

```ini
[Unit]
Description=Capsule Watch web application
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=capsule-watch
Group=capsule-watch
WorkingDirectory=/opt/capsule-watch
Environment=CAPSULE_WATCH_CONFIG=/etc/capsule-watch/config.yaml
ExecStart=/opt/capsule-watch/.venv/bin/python -m capsule_watch.web
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 7. Install the collector service and timer

Create `/etc/systemd/system/capsule-watch-collector.service`:

```ini
[Unit]
Description=Capsule Watch collector run
After=network-online.target

[Service]
Type=oneshot
User=capsule-watch
Group=capsule-watch
WorkingDirectory=/opt/capsule-watch
Environment=CAPSULE_WATCH_CONFIG=/etc/capsule-watch/config.yaml
ExecStart=/opt/capsule-watch/.venv/bin/python -m capsule_watch.collectors
```

Create `/etc/systemd/system/capsule-watch-collector.timer`:

```ini
[Unit]
Description=Run Capsule Watch collectors on a schedule

[Timer]
OnBootSec=2m
OnUnitActiveSec=15m
Persistent=true
Unit=capsule-watch-collector.service

[Install]
WantedBy=timers.target
```

## 8. Install the alert service and timer

Create `/etc/systemd/system/capsule-watch-alert.service`:

```ini
[Unit]
Description=Capsule Watch alert evaluation
After=network-online.target

[Service]
Type=oneshot
User=capsule-watch
Group=capsule-watch
WorkingDirectory=/opt/capsule-watch
Environment=CAPSULE_WATCH_CONFIG=/etc/capsule-watch/config.yaml
ExecStart=/opt/capsule-watch/.venv/bin/python -m capsule_watch.alerts
```

Create `/etc/systemd/system/capsule-watch-alert.timer`:

```ini
[Unit]
Description=Run Capsule Watch alert evaluation on a schedule

[Timer]
OnBootSec=3m
OnUnitActiveSec=15m
Persistent=true
Unit=capsule-watch-alert.service

[Install]
WantedBy=timers.target
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
systemctl status capsule-watch-web.service
systemctl status capsule-watch-collector.timer
systemctl status capsule-watch-alert.timer
```

Check recent logs:

```bash
journalctl -u capsule-watch-web.service -n 50
journalctl -u capsule-watch-collector.service -n 50
journalctl -u capsule-watch-alert.service -n 50
```

If the web service is running, open:

```text
http://<server-ip>:8080/
```

You should expect the dashboard to show the latest saved snapshot rather than collecting live data during page loads.

## 11. Optional email alerts

Email is the intended MVP alert channel.

To enable it later:

1. Update the `alerts.email` section in `/etc/capsule-watch/config.yaml`.
2. Make sure your SMTP relay allows mail from the server.
3. Restart the web service and wait for the next alert evaluation run.

```bash
sudo systemctl restart capsule-watch-web.service
```

## Troubleshooting

### `uv` is not found under `sudo`

Use a full path to the binary, or preserve the correct `PATH` when running as `capsule-watch`.

### SMART checks fail

Confirm `smartmontools` is installed and verify the required `sudoers` entry exists.

### The dashboard loads but shows stale data

Check whether the collector timer is active and whether the collector service wrote `/var/lib/capsule-watch/status.json`.

### The app does not start on boot

Run:

```bash
sudo systemctl enable capsule-watch-web.service
sudo systemctl enable capsule-watch-collector.timer
sudo systemctl enable capsule-watch-alert.timer
```

Then reboot and verify the units again.
