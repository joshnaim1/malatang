"""Serve the Malatang pipeline progress dashboard.

Reads ``results/metrics.jsonl`` and ``trajectories/iterN/`` from disk and exposes
them over a small local web UI. Poll-friendly for live iteration demos.

    python -m scripts.dashboard_server
    python -m scripts.dashboard_server --port 8765 --host 0.0.0.0
"""

from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from harness.config import REPO_ROOT
from harness.dashboard_runner import start_run
from harness.dashboard_state import get_dashboard_state

DASHBOARD_DIR = REPO_ROOT / "dashboard"
DEFAULT_PORT = 8765


class DashboardHandler(BaseHTTPRequestHandler):
    repo_root: Path = REPO_ROOT

    def log_message(self, format: str, *args: object) -> None:
        if self.path.startswith("/api/"):
            return
        super().log_message(format, *args)

    def _send_bytes(
        self,
        status: int,
        body: bytes,
        *,
        content_type: str,
        cache_control: str | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        if cache_control:
            self.send_header("Cache-Control", cache_control)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: object, *, status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self._send_bytes(
            status,
            body,
            content_type="application/json; charset=utf-8",
            cache_control="no-store",
        )

    def _safe_repo_path(self, relative: str) -> Path | None:
        candidate = (self.repo_root / relative).resolve()
        try:
            candidate.relative_to(self.repo_root.resolve())
        except ValueError:
            return None
        return candidate

    def _serve_file(self, path: Path) -> None:
        if not path.is_file():
            self._send_json({"error": "not found"}, status=404)
            return
        content_type, _ = mimetypes.guess_type(str(path))
        body = path.read_bytes()
        self._send_bytes(
            200,
            body,
            content_type=content_type or "application/octet-stream",
            cache_control="no-store" if path.suffix == ".json" else "public, max-age=30",
        )

    def _read_json_body(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON body: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def _handle_run(self) -> None:
        try:
            body = self._read_json_body()
            start_iteration = int(body.get("start_iteration", 0))
            iterations = int(body.get("iterations", 1))
            creator = str(body.get("creator", "live"))
            no_chart = bool(body.get("no_chart", True))
            fresh = bool(body.get("fresh", False))
            run_status = start_run(
                repo_root=self.repo_root,
                start_iteration=start_iteration,
                iterations=iterations,
                creator=creator,
                no_chart=no_chart,
                fresh=fresh,
            )
            self._send_json({"ok": True, "run_job": run_status})
        except (ValueError, TypeError) as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=400)
        except RuntimeError as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=409)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        route = unquote(parsed.path)
        if route == "/api/run":
            self._handle_run()
            return
        self._send_json({"error": "not found"}, status=404)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = unquote(parsed.path)

        if route == "/api/state":
            self._send_json(get_dashboard_state(self.repo_root))
            return

        if route.startswith("/results/"):
            rel = route.lstrip("/")
            path = self._safe_repo_path(rel)
            if path is None:
                self._send_json({"error": "forbidden"}, status=403)
                return
            self._serve_file(path)
            return

        if route in {"", "/"}:
            route = "/index.html"

        rel = route.lstrip("/")
        path = (DASHBOARD_DIR / rel).resolve()
        try:
            path.relative_to(DASHBOARD_DIR.resolve())
        except ValueError:
            self._send_json({"error": "forbidden"}, status=403)
            return

        if path.is_dir():
            path = path / "index.html"
        self._serve_file(path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Malatang pipeline dashboard server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="HTTP port")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Malatang dashboard: {url}")
    print("API: /api/state  /api/run  |  Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
