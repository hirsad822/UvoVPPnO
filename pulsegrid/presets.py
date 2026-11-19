"""Smart preset engine.

Curated profiles with sensible defaults. Simple Mode hides complexity;
Expert Mode exposes transport/security/mux/routing/sockopt tweaks.
"""
from __future__ import annotations

import copy

PRESETS: dict[str, dict] = {
    "balanced": {
        "id": "balanced",
        "name": "Balanced Daily",
        "description": "Safe defaults for everyday use. Good balance of speed and stability.",
        "tagline": "Recommended for most people",
        "config": {
            "protocol": "vless",
            "transport": "tcp",
            "security": "tls",
            "mux": {"enabled": True, "concurrency": 8},
            "sockopt": {"tcpKeepAliveIdle": 100, "tcpNoDelay": True},
            "routing": {"strategy": "balanced"},
            "timeouts": {"connect": 5, "read": 30},
        },
    },
    "low_latency": {
        "id": "low_latency",
        "name": "Low Latency",
        "description": "Minimal overhead for gaming, calls, and interactive apps.",
        "tagline": "Best for gaming & calls",
        "config": {
            "protocol": "vless",
            "transport": "tcp",
            "security": "tls",
            "mux": {"enabled": False, "concurrency": 1},
            "sockopt": {"tcpKeepAliveIdle": 30, "tcpNoDelay": True, "tcpFastOpen": True},
            "routing": {"strategy": "lowest-latency"},
            "timeouts": {"connect": 3, "read": 15},
        },
    },
    "resilient": {
        "id": "resilient",
        "name": "Resilient Mode",
        "description": "Fallback-friendly and retry-tolerant for unstable networks.",
        "tagline": "Best for unstable networks",
        "config": {
            "protocol": "vless",
            "transport": "ws",
            "security": "tls",
            "mux": {"enabled": True, "concurrency": 4},
            "sockopt": {"tcpKeepAliveIdle": 60, "tcpNoDelay": False},
            "routing": {"strategy": "fallback", "retries": 3},
            "timeouts": {"connect": 10, "read": 60},
        },
    },
    "streaming": {
        "id": "streaming",
        "name": "Streaming Optimized",
        "description": "Throughput-oriented for video and large downloads.",
        "tagline": "Best for video & downloads",
        "config": {
            "protocol": "vless",
            "transport": "tcp",
            "security": "tls",
            "mux": {"enabled": True, "concurrency": 16},
            "sockopt": {"tcpKeepAliveIdle": 100, "tcpNoDelay": True, "bufferSize": 262144},
            "routing": {"strategy": "throughput", "parallelDial": 4},
            "timeouts": {"connect": 5, "read": 45},
        },
    },
    "privacy": {
        "id": "privacy",
        "name": "Max Privacy",
        "description": "Encrypted transport with minimal fingerprint surface.",
        "tagline": "Best for privacy",
        "config": {
            "protocol": "vless",
            "transport": "ws",
            "security": "reality",
            "mux": {"enabled": True, "concurrency": 4},
            "sockopt": {"tcpKeepAliveIdle": 100, "tcpNoDelay": True},
            "routing": {"strategy": "privacy", "dns": "encrypted"},
            "timeouts": {"connect": 5, "read": 30},
        },
    },
}

# Expert-only keys hidden in Simple Mode
EXPERT_KEYS = ("mux", "sockopt", "routing", "timeouts")


def list_presets(mode: str = "simple") -> list[dict]:
    """Return preset catalogue. In simple mode, expert keys are stripped."""
    out = []
    for pid, p in PRESETS.items():
        cfg = copy.deepcopy(p["config"])
        if mode != "expert":
            for k in EXPERT_KEYS:
                cfg.pop(k, None)
        out.append({"id": pid, "name": p["name"], "description": p["description"],
                    "tagline": p["tagline"], "config": cfg})
    return out


def get_preset(pid: str) -> dict | None:
    p = PRESETS.get(pid)
    return copy.deepcopy(p) if p else None


def apply_preset(pid: str, overrides: dict | None = None) -> dict:
    """Return merged config for preset + optional expert overrides."""
    p = get_preset(pid)
    if not p:
        raise ValueError(f"Unknown preset: {pid}")
    cfg = copy.deepcopy(p["config"])
    if overrides:
        for k, v in overrides.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    return {"preset": pid, "name": p["name"], "config": cfg}


def recommend_preset(doctor_result: dict) -> str:
    """Recommend a preset based on Doctor findings."""
    score = doctor_result.get("score", 50)
    latency = doctor_result.get("latency_ms", 0)
    loss = doctor_result.get("loss_pct", 0)
    if not doctor_result.get("reachable", True):
        return "resilient"
    if loss >= 5 or score < 50:
        return "resilient"
    if latency and latency < 50 and loss < 1:
        return "low_latency"
    if latency and latency > 150:
        return "balanced"
    return "balanced"
