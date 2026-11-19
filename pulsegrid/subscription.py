"""Health-aware dynamic subscription builder.

Prioritizes healthy, low-latency, non-expired nodes; filters quota-exceeded
users; emits Base64 / Plain / JSON formats with quota & expiry info.
"""
from __future__ import annotations

import base64
import json
import time
import urllib.parse

from .health import rank_nodes
from .traffic import is_expired, quota_exceeded, user_status


def _node_link(node: dict, user_uuid: str) -> str:
    """Build a vless:// style link (generic, client-friendly)."""
    name = urllib.parse.quote(node.get("remark") or node.get("name") or node["id"])
    host = node.get("host", "")
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = int(node.get("port", 443))
    proto = node.get("protocol", "vless")
    transport = node.get("transport", "tcp")
    security = node.get("security", "tls")
    uuid = user_uuid or node.get("uuid", "")
    params = {"type": transport, "security": security}
    if security == "tls":
        params["sni"] = node.get("host", "")
    return f"{proto}://{uuid}@{host}:{port}?{urllib.parse.urlencode(params)}#{name}"


def build_subscription(user: dict, nodes: list[dict], health_map: dict[str, dict],
                       fmt: str = "base64", min_score: int = 50,
                       now: float | None = None) -> dict:
    """Build a health-filtered, health-ranked subscription for a user.

    Returns dict with links, meta (quota/expiry), and the encoded payload.
    """
    now = now or time.time()
    status = user_status(user, now)
    expired = is_expired(user, now)
    exceeded = quota_exceeded(user)

    ranked = rank_nodes([n for n in nodes if n.get("enabled", 1)], health_map)
    # Filter: healthy enough, not expired users get nothing (explicit empty)
    healthy = [n for n in ranked if n["health_score"] >= min_score]
    links = [_node_link(n, user.get("uuid", "")) for n in healthy]

    meta = {
        "user": user.get("name", ""),
        "status": status["status"],
        "quota_remaining_human": status["quota_remaining_human"],
        "days_left": status["days_left"],
        "healthy_nodes": len(healthy),
        "total_nodes": len(ranked),
        "min_score": min_score,
        "generated_at": now,
    }

    if expired or exceeded or status["status"] == "disabled":
        payload = ""
        links = []
        meta["note"] = "Subscription empty: account disabled, expired or quota exceeded."
    elif fmt == "json":
        payload = json.dumps({"meta": meta, "nodes": [
            {"name": n.get("name"), "host": n.get("host"), "port": n.get("port"),
             "protocol": n.get("protocol"), "transport": n.get("transport"),
             "security": n.get("security"), "health_score": n["health_score"],
             "verdict": n["verdict"], "link": _node_link(n, user.get("uuid", ""))}
            for n in healthy], "links": links}, indent=2, ensure_ascii=False)
    elif fmt == "plain":
        payload = "\n".join(links)
    else:  # base64 (default, most clients)
        payload = base64.b64encode("\n".join(links).encode()).decode()

    return {"format": fmt, "payload": payload, "links": links, "meta": meta,
            "headers": {
                "X-Quota-Remaining": status["quota_remaining_human"],
                "X-Expiry-Days": str(status["days_left"]) if status["days_left"] is not None else "never",
                "X-Healthy-Nodes": str(len(healthy)),
            }}
