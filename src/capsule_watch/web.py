"""Web app for Capsule Watch."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from flask import Flask, jsonify, render_template_string

from capsule_watch.config import load_config
from capsule_watch.snapshot import read_snapshot


DASHBOARD_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Capsule Watch</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; }
      .status { display: inline-block; padding: 0.2rem 0.5rem; border-radius: 0.4rem; font-weight: 600; }
      .healthy { background: #def7e7; color: #136f3d; }
      .warning { background: #fff4ce; color: #8a6100; }
      .critical { background: #fde2e1; color: #8f1d1b; }
      .unknown { background: #eef0f2; color: #374151; }
      code { background: #f4f4f5; padding: 0.1rem 0.3rem; border-radius: 0.2rem; }
    </style>
  </head>
  <body>
    <h1>Capsule Watch</h1>
    <p>Generated at: <code>{{ snapshot.generated_at }}</code></p>
    <p>
      Overall status:
      <span class="status {{ snapshot.overall_status }}">{{ snapshot.overall_status }}</span>
    </p>
    <p><a href="/api/status">View raw status JSON</a></p>
  </body>
</html>
"""


def create_app(config_path: str | Path | None = None) -> Flask:
    effective_path = config_path or os.environ.get(
        "CAPSULE_WATCH_CONFIG", "/etc/capsule-watch/config.yaml"
    )
    config = load_config(effective_path)

    app = Flask(__name__)
    app.config["capsule_watch"] = config

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.get("/api/status")
    def api_status():
        snapshot = read_snapshot(config.paths.snapshot_file)
        return jsonify(snapshot)

    @app.get("/")
    def index():
        snapshot = read_snapshot(config.paths.snapshot_file)
        return render_template_string(DASHBOARD_TEMPLATE, snapshot=snapshot)

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Capsule Watch web app")
    parser.add_argument(
        "--config",
        default=os.environ.get("CAPSULE_WATCH_CONFIG", "/etc/capsule-watch/config.yaml"),
        help="Path to Capsule Watch YAML config",
    )
    args = parser.parse_args(argv)
    app = create_app(args.config)
    app_config = app.config["capsule_watch"]
    app.run(host=app_config.server.host, port=app_config.server.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
