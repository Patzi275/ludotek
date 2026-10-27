"""HTTP layer: security checks, static files and routing to api.py."""
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import __version__, api, config
from .config import MAX_IMAGE, PORT, TOKEN, WEB_DIR
from .covers import read_cover
from .i18n import page_data, t

log = logging.getLogger(__name__)

# Fixed list of UI files: request paths never reach the file system directly.
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/fonts/host-grotesk.woff2": ("fonts/host-grotesk.woff2", "font/woff2"),
    "/fonts/instrument-sans.woff2": ("fonts/instrument-sans.woff2", "font/woff2"),
}


def _i18n_json():
    # Inlined in a <script type="application/json">: "</" must not close the tag.
    return json.dumps(page_data(), ensure_ascii=False).replace("</", "<\\/").encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8", cache="no-store"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        # Refused or failed requests only (a missing favicon is not worth a line).
        if code >= 400 and not (self.command == "GET" and code == 404):
            err = body.get("error") if isinstance(body, dict) else ""
            log.warning("%s %s -> %d %s", self.command, urlparse(self.path).path, code, err)
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(data)

    def _host_ok(self):
        # Blocks DNS rebinding: only our own address is accepted.
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return host in ("127.0.0.1", "localhost")

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": t("error.host_refused")})
        path = urlparse(self.path).path
        if path in STATIC:
            name, ctype = STATIC[path]
            data = (WEB_DIR / name).read_bytes()
            if name == "index.html":
                data = (data.replace(b"__TOKEN__", TOKEN.encode())
                        .replace(b"__VERSION__", __version__.encode())
                        .replace(b"__LANG__", config.LANGUAGE.encode())
                        .replace(b"__I18N__", _i18n_json()))
            return self._send(200, data, ctype)
        if path == "/api/library":
            return self._send(200, api.payload())
        if path.startswith("/covers/"):
            found = read_cover(path[len("/covers/"):])
            if found:
                return self._send(200, found[0], found[1], "max-age=31536000, immutable")
        self._send(404, {"error": t("error.not_found")})

    def do_POST(self):
        # The custom header forces a CORS preflight, which we never answer: other sites cannot POST.
        if not self._host_ok() or self.headers.get("X-Biblio-Token") != TOKEN:
            return self._send(403, {"error": t("error.refused")})
        req = self._read_body()
        if req is None:
            return self._send(413, {"error": t("error.file_too_big")})
        parts = urlparse(self.path).path.strip("/").split("/")
        if parts[:1] != ["api"] or len(parts) < 2:
            return self._send(404, {"error": t("error.not_found")})
        action = parts[1]
        iid = parts[2] if len(parts) > 2 else None

        if action == "quit":
            log.info(t("log.quit"))
            self._send(200, api.OK)
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        fn = api.ACTIONS.get(action)
        if fn is None:
            return self._send(404, {"error": t("error.unknown_action")})
        try:
            self._send(200, fn(iid, req))
        except api.ApiError as e:
            self._send(e.status, {"error": str(e)})

    def _read_body(self):
        """{"raw", "type", "json"} for the request, or None if it is too large."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length > MAX_IMAGE + 4096:
            return None
        raw = self.rfile.read(length) if length else b""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        body = {}
        if ctype == "application/json":
            try:
                body = json.loads(raw or b"{}")
            except ValueError:
                pass
        return {"raw": raw, "type": ctype, "json": body if isinstance(body, dict) else {}}


def make_server():
    # Localhost only, never 0.0.0.0. Falls back to a random port if ours is taken.
    for port in (PORT, 0):
        try:
            return ThreadingHTTPServer(("127.0.0.1", port), Handler)
        except OSError:
            continue
    raise SystemExit(t("error.no_port"))
