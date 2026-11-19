"""SQLite storage layer. Stdlib only."""
from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 443,
    protocol TEXT NOT NULL DEFAULT 'vless',
    transport TEXT NOT NULL DEFAULT 'tcp',
    security TEXT NOT NULL DEFAULT 'tls',
    uuid TEXT NOT NULL DEFAULT '',
    remark TEXT DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    uuid TEXT NOT NULL UNIQUE,
    quota_bytes INTEGER NOT NULL DEFAULT 0,
    used_bytes INTEGER NOT NULL DEFAULT 0,
    expires_at REAL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS health_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    latency_ms REAL DEFAULT 0,
    loss_pct REAL DEFAULT 0,
    reachable INTEGER DEFAULT 0,
    checked_at REAL NOT NULL,
    detail TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS traffic_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT DEFAULT '',
    node_id TEXT DEFAULT '',
    up_bytes INTEGER DEFAULT 0,
    down_bytes INTEGER DEFAULT 0,
    ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT DEFAULT 'info',
    message TEXT DEFAULT '',
    created_at REAL NOT NULL,
    resolved_at REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_health_node ON health_checks(node_id, checked_at);
CREATE INDEX IF NOT EXISTS idx_traffic_ts ON traffic_events(ts);
"""


class DB:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    # -- helpers ---------------------------------------------------------
    def _now(self) -> float:
        return time.time()

    # -- settings --------------------------------------------------------
    def get_setting(self, key: str, default: str = "") -> str:
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    # -- nodes -----------------------------------------------------------
    def create_node(self, name, host, port=443, protocol="vless", transport="tcp",
                    security="tls", user_uuid="", remark="", enabled=True) -> dict:
        nid = uuid.uuid4().hex[:12]
        now = self._now()
        self.conn.execute(
            "INSERT INTO nodes(id,name,host,port,protocol,transport,security,uuid,remark,enabled,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (nid, name, host, int(port), protocol, transport, security, user_uuid, remark, 1 if enabled else 0, now),
        )
        self.conn.commit()
        return self.get_node(nid)

    def get_node(self, nid: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM nodes WHERE id=?", (nid,)).fetchone()
        return dict(row) if row else None

    def list_nodes(self, enabled_only: bool = False) -> list[dict]:
        q = "SELECT * FROM nodes" + (" WHERE enabled=1" if enabled_only else "") + " ORDER BY created_at"
        return [dict(r) for r in self.conn.execute(q).fetchall()]

    def update_node(self, nid: str, **kw) -> dict | None:
        allowed = {"name", "host", "port", "protocol", "transport", "security", "uuid", "remark", "enabled"}
        kw = {k: v for k, v in kw.items() if k in allowed}
        if not kw:
            return self.get_node(nid)
        sets = ", ".join(f"{k}=?" for k in kw)
        self.conn.execute(f"UPDATE nodes SET {sets} WHERE id=?", (*kw.values(), nid))
        self.conn.commit()
        return self.get_node(nid)

    def delete_node(self, nid: str) -> bool:
        cur = self.conn.execute("DELETE FROM nodes WHERE id=?", (nid,))
        self.conn.commit()
        return cur.rowcount > 0

    # -- users -----------------------------------------------------------
    def create_user(self, name, quota_bytes=0, expires_at=0, enabled=True) -> dict:
        uid = uuid.uuid4().hex[:12]
        u = str(uuid.uuid4())
        now = self._now()
        self.conn.execute(
            "INSERT INTO users(id,name,uuid,quota_bytes,used_bytes,expires_at,enabled,created_at)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (uid, name, u, int(quota_bytes), 0, float(expires_at), 1 if enabled else 0, now),
        )
        self.conn.commit()
        return self.get_user(uid)

    def get_user(self, uid: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM users WHERE id=? OR uuid=?", (uid, uid)).fetchone()
        return dict(row) if row else None

    def list_users(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()]

    def update_user(self, uid: str, **kw) -> dict | None:
        allowed = {"name", "quota_bytes", "used_bytes", "expires_at", "enabled"}
        kw = {k: v for k, v in kw.items() if k in allowed}
        if not kw:
            return self.get_user(uid)
        sets = ", ".join(f"{k}=?" for k in kw)
        self.conn.execute(f"UPDATE users SET {sets} WHERE id=?", (*kw.values(), uid))
        self.conn.commit()
        return self.get_user(uid)

    def delete_user(self, uid: str) -> bool:
        cur = self.conn.execute("DELETE FROM users WHERE id=?", (uid,))
        self.conn.commit()
        return cur.rowcount > 0

    def add_usage(self, uid: str, up: int = 0, down: int = 0) -> None:
        self.conn.execute(
            "UPDATE users SET used_bytes = used_bytes + ? WHERE id=?", (int(up) + int(down), uid)
        )
        self.conn.execute(
            "INSERT INTO traffic_events(user_id,node_id,up_bytes,down_bytes,ts) VALUES(?,?,?,?,?)",
            (uid, "", int(up), int(down), self._now()),
        )
        self.conn.commit()

    # -- health ----------------------------------------------------------
    def record_health(self, node_id: str, score: int, latency_ms: float, loss_pct: float,
                      reachable: bool, detail: str = "") -> dict:
        now = self._now()
        self.conn.execute(
            "INSERT INTO health_checks(node_id,score,latency_ms,loss_pct,reachable,checked_at,detail)"
            " VALUES(?,?,?,?,?,?,?)",
            (node_id, int(score), float(latency_ms), float(loss_pct), 1 if reachable else 0, now, detail),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM health_checks WHERE node_id=? ORDER BY checked_at DESC LIMIT 1", (node_id,)).fetchone()
        return dict(row) if row else {}

    def latest_health(self, node_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM health_checks WHERE node_id=? ORDER BY checked_at DESC LIMIT 1", (node_id,)
        ).fetchone()
        return dict(row) if row else None

    def all_latest_health(self) -> dict[str, dict]:
        rows = self.conn.execute(
            "SELECT * FROM health_checks WHERE id IN (SELECT MAX(id) FROM health_checks GROUP BY node_id)"
        ).fetchall()
        return {r["node_id"]: dict(r) for r in rows}

    # -- traffic / alerts ------------------------------------------------
    def traffic_summary(self) -> dict:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(up_bytes),0) AS up, COALESCE(SUM(down_bytes),0) AS down, COUNT(*) AS events"
            " FROM traffic_events"
        ).fetchone()
        users = self.conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        nodes = self.conn.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()["c"]
        return {"up_bytes": int(row["up"]), "down_bytes": int(row["down"]),
                "total_bytes": int(row["up"]) + int(row["down"]), "events": int(row["events"]),
                "users": int(users), "nodes": int(nodes)}

    def add_alert(self, level: str, message: str) -> dict:
        now = self._now()
        self.conn.execute("INSERT INTO alerts(level,message,created_at) VALUES(?,?,?)", (level, message, now))
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else {}

    def list_alerts(self, limit: int = 50) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
