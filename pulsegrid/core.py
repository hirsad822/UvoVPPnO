"""Optional local Xray supervisor. Runs as the same unprivileged user as PulseGrid.

The managed transport is VLESS over TCP with TLS; see the deployment guide.
"""
import json
import logging
import os
import socket
import ssl
import time
import subprocess
import threading
from pathlib import Path

from .db import DB
from .traffic import user_status
from .tls import validate_certificate

log = logging.getLogger(__name__)


def xray_config(users, port, cert_path, key_path):
    clients = [{"id": u["uuid"], "email": u["id"]} for u in users
               if user_status(u)["status"] == "active"]
    return {"log": {"loglevel": "warning"},
            "inbounds": [{"listen": "0.0.0.0", "port": port, "protocol": "vless",
                          "settings": {"clients": clients, "decryption": "none"},
                          "streamSettings": {"network": "tcp", "security": "tls",
                                             "tlsSettings": {"certificates": [{"certificateFile": str(cert_path), "keyFile": str(key_path)}]}}}],
            "outbounds": [{"protocol": "freedom"}]}


class CoreSupervisor:
    def __init__(self, settings):
        self.settings = settings
        self.binary = Path(os.environ.get("PULSEGRID_XRAY_BIN", "/opt/pulsegrid-core/xray"))
        self.host = os.environ.get("PULSEGRID_PUBLIC_HOST", "").strip()
        self.port = int(os.environ.get("PULSEGRID_CORE_PORT", "10000"))
        self.cert_path = settings.config_dir / "tls-current" / "fullchain.pem"
        self.key_path = settings.config_dir / "tls-current" / "privkey.pem"
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.lock = threading.RLock()
        self.process = None
        self.thread = None
        self.last_config = None
        self.last_cert_digest = None

    def start(self):
        # Never publish stale managed subscriptions while the core is starting.
        db = DB(self.settings.db_path)
        try:
            node_id = db.get_setting("managed_core_node")
            node = db.get_node(node_id) if node_id else None
            if node and node["enabled"]:
                db.update_node(node_id, enabled=0)
                db.set_setting("managed_core_tls_disabled", "1")
        finally:
            db.close()
        if not self.host or not self.binary.is_file():
            log.warning("Xray disabled: configure PULSEGRID_PUBLIC_HOST and install the core")
            return
        self.thread = threading.Thread(target=self.run, daemon=True, name="xray-supervisor")
        self.thread.start()

    def run(self):
        db = DB(self.settings.db_path)
        try:
            while not self.stop_event.is_set():
                self.wake_event.clear()
                try:
                    self.reconcile(db)
                except Exception:
                    with self.lock:
                        self._stop_process()
                        self.last_config = None
                    node_id = db.get_setting("managed_core_node")
                    if node_id and db.get_node(node_id) and db.get_node(node_id)["enabled"]:
                        db.update_node(node_id, enabled=0)
                        db.set_setting("managed_core_tls_disabled", "1")
                    log.exception("Xray reconciliation failed; managed node disabled")
                # Record only local readiness, never claim public reachability.
                node_id = db.get_setting("managed_core_node")
                node = db.get_node(node_id) if node_id else None
                if node and node["enabled"]:
                    ready = self.wait_ready(timeout=1)
                    last = db.latest_health(node_id)
                    score = 80 if ready else 0
                    if not last or last["score"] != score or time.time() - last["checked_at"] >= 60:
                        detail = ("Verified local Xray TLS; external reachability not tested" if ready
                                  else "Local Xray TLS is not ready")
                        db.record_health(node_id, score, 0, 0 if ready else 100, ready, detail)
                self.wake_event.wait(5)
        finally:
            self._stop_process()
            db.close()

    def _stop_process(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.process = None

    def reconcile(self, db):
        with self.lock:
            self._reconcile(db)

    def _reconcile(self, db):
        node_id = db.get_setting("managed_core_node")
        node = db.get_node(node_id) if node_id else None
        try:
            digest = validate_certificate(self.host, self.cert_path, self.key_path)
        except Exception:
            # Do not keep serving an old, insecure or expired configuration.
            self._stop_process()
            self.last_config = None
            if node and node["enabled"]:
                db.update_node(node["id"], enabled=0)
                db.set_setting("managed_core_tls_disabled", "1")
            raise

        config = json.dumps(xray_config(db.list_users(), self.port, self.cert_path, self.key_path), sort_keys=True)
        if config != self.last_config or digest != self.last_cert_digest or self.process is None or self.process.poll() is not None:
            path = self.settings.data_dir / "xray.json"
            temp = path.with_suffix(".tmp")
            temp.write_text(config)
            temp.chmod(0o600)
            os.replace(temp, path)
            subprocess.run([str(self.binary), "run", "-test", "-config", str(path)], check=True,
                           timeout=15, stdout=subprocess.DEVNULL)
            self._stop_process()
            self.process = subprocess.Popen([str(self.binary), "run", "-config", str(path)])
            self.last_config = config
            self.last_cert_digest = digest
            log.info("Xray started with TLS and updated client list")

        if not node:
            node = db.create_node("Local Xray", self.host, self.port, security="tls")
            db.set_setting("managed_core_node", node["id"])
        elif (node["host"], node["port"], node["security"], node["transport"], node["protocol"]) != (self.host, self.port, "tls", "tcp", "vless"):
            db.update_node(node["id"], host=self.host, port=self.port, security="tls", transport="tcp", protocol="vless")
            # A check for the old insecure endpoint cannot certify the new one.
            db.record_health(node["id"], 0, 0, 100, False, "TLS configuration changed; check again")
        if db.get_setting("managed_core_tls_disabled") == "1":
            db.update_node(node["id"], enabled=1)
            db.set_setting("managed_core_tls_disabled", "0")
            db.record_health(node["id"], 0, 0, 100, False, "TLS restored; check again")
        # Health checks remain explicit: run Doctor/check-all before subscribing.

    def request_sync(self):
        self.wake_event.set()

    def wait_ready(self, user_uuid=None, timeout=15):
        """Check the running process has loaded the user and verified local TLS.

        This is a local readiness check, not a test of external reachability.
        """
        if not self.thread or not self.thread.is_alive():
            return False
        deadline = time.monotonic() + timeout
        while not self.stop_event.is_set():
            with self.lock:
                if self.process is not None and self.process.poll() is None and self.last_config:
                    config = json.loads(self.last_config)
                    clients = config["inbounds"][0]["settings"]["clients"]
                    if user_uuid is None or any(c["id"] == user_uuid for c in clients):
                        try:
                            with socket.create_connection(("127.0.0.1", self.port), timeout=1) as sock:
                                with ssl.create_default_context().wrap_socket(sock, server_hostname=self.host):
                                    if self.process.poll() is None:
                                        return True
                        except (OSError, ssl.SSLError):
                            pass
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            self.stop_event.wait(min(0.2, remaining))
        return False

    def stop(self):
        self.stop_event.set()
        self.wake_event.set()
        if self.thread:
            self.thread.join(timeout=25)
