"""REST API handlers. Pure functions over DB — easy to test."""
from __future__ import annotations

import time

from .doctor import run_diagnostics
from .health import rank_nodes, verdict_for
from .presets import apply_preset, list_presets, recommend_preset
from .subscription import build_subscription
from .traffic import user_status


class API:
    def __init__(self, db, settings):
        self.db = db
        self.settings = settings
        self.managed_only = False

    # -- dashboard -------------------------------------------------------
    def dashboard(self) -> dict:
        nodes = self.db.list_nodes()
        users = self.db.list_users()
        health = self.db.all_latest_health()
        ranked = rank_nodes(nodes, health)
        traffic = self.db.traffic_summary()
        alerts = self.db.list_alerts(20)
        active_preset = self.db.get_setting("active_preset", "balanced")
        mode = self.db.get_setting("mode", self.settings.mode)
        return {
            "nodes": ranked,
            "users": [{**u, **user_status(u)} for u in users],
            "traffic": traffic,
            "alerts": alerts,
            "active_preset": active_preset,
            "mode": mode,
            "summary": {
                "total_nodes": len(nodes),
                "healthy_nodes": sum(1 for n in ranked if n["health_score"] >= 80),
                "total_users": len(users),
                "active_users": sum(1 for u in users if user_status(u)["status"] == "active"),
                "total_traffic_human": _human(traffic["total_bytes"]),
            },
        }

    # -- nodes -----------------------------------------------------------
    def create_node(self, body: dict) -> dict:
        return self.db.create_node(
            name=body.get("name", "node"),
            host=body.get("host", "127.0.0.1"),
            port=int(body.get("port", 443)),
            protocol=body.get("protocol", "vless"),
            transport=body.get("transport", "tcp"),
            security=body.get("security", "tls"),
            user_uuid=body.get("uuid", ""),
            remark=body.get("remark", ""),
            enabled=bool(body.get("enabled", True)),
        )

    def list_nodes(self) -> list[dict]:
        return rank_nodes(self.db.list_nodes(), self.db.all_latest_health())

    def update_node(self, nid: str, body: dict) -> dict | None:
        return self.db.update_node(nid, **body)

    def delete_node(self, nid: str) -> bool:
        return self.db.delete_node(nid)

    # -- users -----------------------------------------------------------
    def create_user(self, body: dict) -> dict:
        quota_gb = float(body.get("quota_gb", 0) or 0)
        days = float(body.get("days", 0) or 0)
        expires = time.time() + days * 86400 if days > 0 else 0
        return self.db.create_user(
            name=body.get("name", "user"),
            quota_bytes=int(quota_gb * 1024**3),
            expires_at=expires,
            enabled=bool(body.get("enabled", True)),
        )

    def list_users(self) -> list[dict]:
        return [{**u, **user_status(u)} for u in self.db.list_users()]

    def update_user(self, uid: str, body: dict) -> dict | None:
        kw = {}
        if "name" in body:
            kw["name"] = body["name"]
        if "enabled" in body:
            kw["enabled"] = 1 if body["enabled"] else 0
        if "quota_gb" in body:
            kw["quota_bytes"] = int(float(body["quota_gb"]) * 1024**3)
        if "days" in body:
            kw["expires_at"] = time.time() + float(body["days"]) * 86400 if float(body["days"]) > 0 else 0
        return self.db.update_user(uid, **kw)

    def delete_user(self, uid: str) -> bool:
        return self.db.delete_user(uid)

    # -- presets ---------------------------------------------------------
    def presets(self) -> list[dict]:
        mode = self.db.get_setting("mode", self.settings.mode)
        return list_presets(mode)

    def apply_preset(self, body: dict) -> dict:
        pid = body.get("preset", "balanced")
        result = apply_preset(pid, body.get("overrides"))
        self.db.set_setting("active_preset", pid)
        if "mode" in body:
            self.db.set_setting("mode", body["mode"])
        return {**result, "active_preset": pid}

    # -- doctor ----------------------------------------------------------
    def run_doctor(self, body: dict) -> dict:
        host = body.get("host", "127.0.0.1")
        port = int(body.get("port", 443))
        result = run_diagnostics(host, port, probes=int(body.get("probes", 5)),
                                 service_port=self.settings.port)
        result["recommended_preset"] = recommend_preset(result)
        # Persist health for matching node if exists
        for n in self.db.list_nodes():
            if n["host"] == host and int(n["port"]) == port:
                if n["security"] == "tls" and not result["tls_ok"]:
                    result["score"] = 0
                    result["verdict"] = "unhealthy"
                    result["summary"] = ("Node is unreachable; check the core service and firewall." if not result["reachable"]
                                         else "TLS verification failed; node excluded from subscriptions.")
                score = result["score"]
                self.db.record_health(n["id"], score, result["latency_ms"],
                                      result["loss_pct"], result["reachable"],
                                      result["summary"])
                break
        return result

    def check_all_nodes(self) -> dict:
        nodes = self.db.list_nodes()
        results = []
        for n in nodes:
            r = run_diagnostics(n["host"], int(n["port"]), probes=3,
                                service_port=self.settings.port)
            if n["security"] == "tls" and not r["tls_ok"]:
                r["score"] = 0
                r["verdict"] = "unhealthy"
                r["summary"] = ("Node is unreachable; check the core service and firewall." if not r["reachable"]
                                else "TLS verification failed; node excluded from subscriptions.")
            score = r["score"]
            self.db.record_health(n["id"], score, r["latency_ms"], r["loss_pct"],
                                  r["reachable"], r["summary"])
            results.append({"node_id": n["id"], "name": n["name"], **r})
        return {"checked": len(results), "results": results}

    # -- subscription ----------------------------------------------------
    def subscription(self, user_id: str, fmt: str = "base64", min_score: int | None = None) -> dict:
        user = self.db.get_user(user_id)
        if not user:
            raise KeyError("user not found")
        nodes = self.subscription_nodes()
        health = self.db.all_latest_health()
        return build_subscription(user, nodes, health, fmt=fmt,
                                  min_score=min_score if min_score is not None else self.settings.min_score)

    def subscription_nodes(self):
        nodes = self.db.list_nodes(enabled_only=True)
        if self.managed_only:
            node_id = self.db.get_setting("managed_core_node")
            return [node for node in nodes if node["id"] == node_id]
        return nodes

    def user_configs(self, user_id: str) -> dict:
        """Admin-only explanation and usable links, respecting subscription filters."""
        user = self.db.get_user(user_id)
        if not user:
            raise KeyError("user not found")
        sub = self.subscription(user_id, fmt="plain")
        nodes = self.subscription_nodes()
        checks = self.db.all_latest_health()
        if sub["meta"]["status"] != "active":
            reason = sub["meta"]["status"]
        elif not nodes:
            reason = "no_nodes"
        elif not any(n["id"] in checks for n in nodes):
            reason = "unchecked"
        elif not sub["links"]:
            reason = "no_healthy_nodes"
        else:
            reason = "ready"
        return {"links": sub["links"], "reason": reason,
                "healthy_nodes": len(sub["links"]), "total_nodes": len(nodes)}

    # -- traffic ---------------------------------------------------------
    def traffic_summary(self) -> dict:
        return self.db.traffic_summary()

    def node_health(self) -> list[dict]:
        nodes = self.db.list_nodes()
        health = self.db.all_latest_health()
        out = []
        for n in nodes:
            h = health.get(n["id"], {})
            score = int(h.get("score", 0))
            out.append({"node_id": n["id"], "name": n["name"], "host": n["host"],
                        "port": n["port"], "score": score, "verdict": verdict_for(score),
                        "latency_ms": h.get("latency_ms", 0), "loss_pct": h.get("loss_pct", 0),
                        "checked_at": h.get("checked_at", 0)})
        return out


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} PB"
