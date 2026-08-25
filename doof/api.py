"""DOOF v0.3 API compatibility marker.

The v0.3 runtime is installed through ``doof.api_mount`` and ``doof.api_extra``.
This module remains the stable local HTTP API surface; the mount layer adds
updates/admin routes without replacing the core handler.
"""
from __future__ import annotations

# v0.3.0 / protocol 1.  Keep this module importable for existing callers.
DOOF_API_VERSION = "0.3.0"
DOOF_PROTOCOL = 1

from http.server import BaseHTTPRequestHandler


class Handler(BaseHTTPRequestHandler):
    """Minimal compatibility handler for environments that import api.Handler.

    The packaged application installs the full handler through api_mount before
    serving the GUI/API, so this fallback intentionally returns a useful health
    response rather than pretending unsupported routes exist.
    """

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[api] {fmt % args}")

    def do_GET(self) -> None:
        if self.path in ("/", "/api/health"):
            body = b'{"ok":true,"service":"doof","version":"0.3.0","protocol":1}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404, "not found")


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    from http.server import ThreadingHTTPServer

    try:
        from doof.api_mount import install
        install()
    except Exception as exc:
        print(f"[api] v0.3 mount: {exc}")

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"DOOF API v0.3.0 listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
