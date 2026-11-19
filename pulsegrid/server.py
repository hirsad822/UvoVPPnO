"""HTTP server: routing, auth, static files. Stdlib ThreadingHTTPServer."""
from __future__ import annotations

import json
import hmac
import ssl
import mimetypes
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .api import API
from .config import Settings
from .db import DB


class App:
    def __init__(self, settings: Settings):
        settings.ensure_dirs()
        self.settings = settings
        self.db = DB(settings.db_path)
        self.api = API(self.db, settings)

    def check_auth(self, headers) -> bool:
        auth = headers.get("Authorization", "")
        return hmac.compare_digest(auth.encode(), f"Bearer {self.settings.token}".encode())


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "PulseGrid/1.0"

        # -- helpers -----------------------------------------------------
        def _json(self, obj, status=200, extra_headers=None):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            if extra_headers:
                for k, v in extra_headers.items():
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0) or 0)
            if not length:
                return {}
            try:
                return json.loads(self.rfile.read(length).decode() or "{}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                return {}

        def _serve_static(self, path: str):
            web = app.settings.web_dir
            rel = path.lstrip("/") or "index.html"
            target = (web / rel).resolve()
            if not target.is_relative_to(web.resolve()) or not target.is_file():
                self._json({"error": "not found"}, 404)
                return
            ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):  # quieter logs
            pass

        # -- routing -----------------------------------------------------
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            qs = urllib.parse.parse_qs(parsed.query)

            if path == "/api/health":
                return self._json({"status": "ok", "version": "1.0.0"})

            if path.startswith("/api/subscription/"):
                uid = path.split("/")[-1]
                fmt = (qs.get("format", ["base64"])[0]).lower()
                if fmt not in ("base64", "plain", "json"):
                    fmt = "base64"
                user = app.db.get_user(uid)
                if not user or not hmac.compare_digest(uid, user["uuid"]):
                    return self._json({"error": "user not found"}, 404)
                try:
                    sub = app.api.subscription(uid, fmt=fmt)
                except KeyError:
                    return self._json({"error": "user not found"}, 404)
                if fmt == "json":
                    return self._json(sub, extra_headers=sub["headers"])
                body = sub["payload"].encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                for k, v in sub["headers"].items():
                    self.send_header(k, v)
                self.end_headers()
                return self.wfile.write(body)

            if path.startswith("/api/"):
                if not app.check_auth(self.headers):
                    return self._json({"error": "unauthorized"}, 401)
                if path == "/api/dashboard":
                    return self._json(app.api.dashboard())
                if path == "/api/nodes":
                    return self._json(app.api.list_nodes())
                if path == "/api/users":
                    return self._json(app.api.list_users())
                if path == "/api/presets":
                    return self._json(app.api.presets())
                if path == "/api/traffic/summary":
                    return self._json(app.api.traffic_summary())
                if path == "/api/health/nodes":
                    return self._json(app.api.node_health())
                return self._json({"error": "not found"}, 404)

            return self._serve_static(path)

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            if not app.check_auth(self.headers):
                return self._json({"error": "unauthorized"}, 401)
            body = self._body()
            if path == "/api/nodes":
                return self._json(app.api.create_node(body), 201)
            if path == "/api/users":
                return self._json(app.api.create_user(body), 201)
            if path == "/api/presets/apply":
                try:
                    return self._json(app.api.apply_preset(body))
                except ValueError as e:
                    return self._json({"error": str(e)}, 400)
            if path == "/api/doctor/run":
                return self._json(app.api.run_doctor(body))
            if path == "/api/doctor/check-all":
                return self._json(app.api.check_all_nodes())
            return self._json({"error": "not found"}, 404)

        def do_PUT(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            if not app.check_auth(self.headers):
                return self._json({"error": "unauthorized"}, 401)
            body = self._body()
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[0] == "api" and parts[1] == "nodes":
                r = app.api.update_node(parts[2], body)
                return self._json(r or {"error": "not found"}, 200 if r else 404)
            if len(parts) == 3 and parts[0] == "api" and parts[1] == "users":
                r = app.api.update_user(parts[2], body)
                return self._json(r or {"error": "not found"}, 200 if r else 404)
            return self._json({"error": "not found"}, 404)

        def do_DELETE(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            if not app.check_auth(self.headers):
                return self._json({"error": "unauthorized"}, 401)
            parts = path.strip("/").split("/")
            if len(parts) == 3 and parts[0] == "api" and parts[1] == "nodes":
                ok = app.api.delete_node(parts[2])
                return self._json({"deleted": ok}, 200 if ok else 404)
            if len(parts) == 3 and parts[0] == "api" and parts[1] == "users":
                ok = app.api.delete_user(parts[2])
                return self._json({"deleted": ok}, 200 if ok else 404)
            return self._json({"error": "not found"}, 404)

    return Handler


def serve(settings: Settings) -> None:
    app = App(settings)
    from .core import CoreSupervisor
    core = CoreSupervisor(settings)
    handler = make_handler(app)
    httpd = ThreadingHTTPServer((settings.host, settings.port), handler)
    scheme = "http"
    if settings.dashboard_tls:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(str(settings.config_dir / "tls-current/fullchain.pem"),
                                str(settings.config_dir / "tls-current/privkey.pem"))
        httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
        scheme = "https"
    core.start()
    print(f"PulseGrid listening on {scheme}://{settings.host}:{settings.port}")
    print(f"Dashboard: {scheme}://{settings.host}:{settings.port}/  (token required)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        httpd.server_close()
        core.stop()
        app.db.close()
