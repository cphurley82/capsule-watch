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

You will also need:

- `sudo` access on the Ubuntu host
- Git installed
- Python 3.12 available
- `uv` installed for Python environment management

## 1. Install base packages

Install the packages Capsule Watch is expected to rely on:

```bash
sudo apt update
sudo apt install -y git curl python3 smartmontools
```

If `uv` is not already installed, install it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Open a new shell after installing `uv`, or make sure `~/.local/bin` is on your `PATH`.

## 2. Create the service user and directories

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

## 3. Clone the repository

Clone the project into the application directory:

```bash
sudo git clone https://github.com/<your-org-or-user>/capsule-watch.git /opt/capsule-watch
sudo chown -R capsule-watch:capsule-watch /opt/capsule-watch
```

If you are installing from your own fork or local mirror, replace the repository URL accordingly.

## 4. Create the Python environment

Sync the project environment as the `capsule-watch` user:

```bash
sudo -u capsule-watch -H env PATH="$HOME/.local/bin:$PATH" uv sync --frozen --project /opt/capsule-watch
```

The exact command may change slightly once the app scaffold is committed, but the intended model is:

- project metadata in `pyproject.toml`
- a committed `uv.lock`
- a project-local virtual environment managed by `uv`

## 5. Create the configuration file

Create `/etc/capsule-watch/config.yaml`:

```yaml
server:
  host: 0.0.0.0
  port: 8080

paths:
  time_machine_root: /srv/timecapsule
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

## 6. Grant limited privileged access

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

## 7. Install the web service

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

## 8. Install the collector service and timer

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

## 9. Install the alert service and timer

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

## 10. Enable services on boot

Reload `systemd`, enable the web service, and start the timers:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now capsule-watch-web.service
sudo systemctl enable --now capsule-watch-collector.timer
sudo systemctl enable --now capsule-watch-alert.timer
```

## 11. Verify the installation

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

## 12. Optional email alerts

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
