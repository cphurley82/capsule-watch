# Local Development Guide

This guide documents practical day-to-day development workflows for Capsule Watch.

## Prerequisites

- Ubuntu host with Python and `uv` installed
- Local clone at `/home/<user>/code/capsule-watch` (or equivalent)
- Optional: existing `systemd` install for runtime validation

## Command context

Unless noted otherwise, run all commands in this document from the repository root:

```bash
cd /home/<user>/code/capsule-watch
```

## 1. Prepare your environment

From the project root:

```bash
uv sync --extra dev
```

Run tests:

```bash
uv run pytest -q
```

## 2. Flow A: Example config, no sudo

Use this flow for fast local development without privileged commands.

Create a writable dev config based on the example:

```bash
mkdir -p .tmp
EXAMPLE_CONFIG="$PWD/.tmp/capsule-watch-example.local.yaml"
LOCAL_WEB_PORT=18080
cp config/config.example.yaml "$EXAMPLE_CONFIG"
sed -i 's|snapshot_file: .*|snapshot_file: /tmp/capsule-watch-status.json|' "$EXAMPLE_CONFIG"
sed -i 's|alerts_file: .*|alerts_file: /tmp/capsule-watch-alerts.json|' "$EXAMPLE_CONFIG"
sed -i "s|port: .*|port: ${LOCAL_WEB_PORT}|" "$EXAMPLE_CONFIG"
```

Run collectors:

```bash
uv run capsule-watch-collectors --config "$EXAMPLE_CONFIG" --output /tmp/capsule-watch-status.json
cat /tmp/capsule-watch-status.json | python3 -m json.tool
```

Run alerts:

```bash
uv run capsule-watch-alerts --config "$EXAMPLE_CONFIG"
cat /tmp/capsule-watch-alerts.json | python3 -m json.tool
```

Run the web app:

```bash
uv run capsule-watch-web --config "$EXAMPLE_CONFIG"
```

Open `http://127.0.0.1:18080/` (or use your `LOCAL_WEB_PORT` value).

Notes for this no-sudo flow:

- Backup/storage may be `unknown` if `time_machine_root` does not exist on your dev host.
- Drive health may warn about sudo requirements.
- This is expected for portable local iteration.

## 3. Flow B: System config, sudo as needed

Use this flow to validate behavior against your real host configuration.

Confirm the service account can read system config:

```bash
sudo -u capsule-watch test -r /etc/capsule-watch/config.yaml && echo "service config readable" || echo "service config NOT readable"
```

Run collectors as the `capsule-watch` service user:

```bash
OUTPUT_FILE="/tmp/capsule-watch-status.$(date +%s).json"
sudo -u capsule-watch -H ./.venv/bin/capsule-watch-collectors --config /etc/capsule-watch/config.yaml --output "$OUTPUT_FILE"
sudo cat "$OUTPUT_FILE" | python3 -m json.tool
```

Run alerts as the `capsule-watch` service user:

```bash
sudo -u capsule-watch -H ./.venv/bin/capsule-watch-alerts --config /etc/capsule-watch/config.yaml
sudo cat /var/lib/capsule-watch/alerts.json | python3 -m json.tool
```

Use the installed web service (recommended for this flow):

```bash
sudo systemctl restart capsule-watch-web.service
sudo systemctl is-active --quiet capsule-watch-web.service
curl --retry 5 --retry-delay 1 --retry-connrefused -sS http://127.0.0.1:8080/healthz
curl --retry 5 --retry-delay 1 --retry-connrefused -sS http://127.0.0.1:8080/api/status | python3 -m json.tool
```

If `is-active` fails, inspect startup errors:

```bash
systemctl status capsule-watch-web.service --no-pager -l
journalctl -u capsule-watch-web.service -n 80 --no-pager
```

## 4. Optional: fast systemd-backed iteration (symlink workflow)

Use this when you want to validate real service behavior without copying code into `/opt` after every change.
This workflow intentionally repoints `/opt/capsule-watch` to your working tree and is intended for local development hosts.

One-time setup:

```bash
REPO_ROOT="$(pwd -P)"
CODE_DIR="$(dirname "$REPO_ROOT")"
HOME_DIR="$HOME"

sudo systemctl stop capsule-watch-web.service capsule-watch-collector.timer capsule-watch-alert.timer
sudo rm -rf /opt/capsule-watch
sudo ln -s "$REPO_ROOT" /opt/capsule-watch

uv sync --extra dev --project "$REPO_ROOT"

sudo setfacl -m u:capsule-watch:rx "$HOME_DIR"
sudo setfacl -m u:capsule-watch:rx "$CODE_DIR"
sudo setfacl -R -m u:capsule-watch:rX "$REPO_ROOT"
sudo setfacl -d -m u:capsule-watch:rX "$REPO_ROOT"

sudo systemctl start capsule-watch-web.service capsule-watch-collector.timer capsule-watch-alert.timer
readlink -f /opt/capsule-watch
systemctl is-active capsule-watch-web.service capsule-watch-collector.timer capsule-watch-alert.timer
```

Iteration loop:

```bash
# after code edits
sudo systemctl restart capsule-watch-web.service
sudo systemctl start capsule-watch-collector.service
curl --retry 5 --retry-delay 1 --retry-connrefused -sS http://127.0.0.1:8080/healthz
curl --retry 5 --retry-delay 1 --retry-connrefused -sS http://127.0.0.1:8080/api/status | python3 -m json.tool
```

When dependencies change:

```bash
uv sync --extra dev
sudo systemctl restart capsule-watch-web.service
```

## 5. Recommended development rhythm

1. Write/update tests first.
2. Implement code.
3. Run `uv run pytest -q`.
4. Validate in the systemd-backed loop for real runtime behavior.
5. Update docs when behavior changes.

For workflow standards and commit gates, see [Development standards](development-standards.md).
