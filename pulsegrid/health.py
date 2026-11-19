"""Health scoring & node ranking (0–100 weighted composite)."""
from __future__ import annotations


def score_health(latency_ms: float = 0, loss_pct: float = 0, reachable: bool = True,
                 tls_ok: bool = True, service_ok: bool = True, dns_ok: bool = True) -> int:
    """Compute weighted health score.

    Weights: latency 30% · loss 25% · reachability 20% · TLS 15% · service 10%.
    """
    if not reachable:
        return 0
    # Latency component (0-30): <50ms=30, 50-100=24, 100-150=18, 150-250=10, >250=4
    if latency_ms <= 0:
        lat = 0
    elif latency_ms < 50:
        lat = 30
    elif latency_ms < 100:
        lat = 24
    elif latency_ms < 150:
        lat = 18
    elif latency_ms < 250:
        lat = 10
    else:
        lat = 4
    # Loss component (0-25)
    if loss_pct <= 0:
        loss = 25
    elif loss_pct < 2:
        loss = 20
    elif loss_pct < 5:
        loss = 14
    elif loss_pct < 10:
        loss = 8
    else:
        loss = 3
    reach = 20 if reachable else 0
    tls = 15 if tls_ok else 0
    svc = 10 if service_ok else 0
    dns_bonus = 0  # DNS failure already hurts reachability; keep weight neutral
    score = lat + loss + reach + tls + svc + dns_bonus
    return max(0, min(100, int(round(score))))


def verdict_for(score: int) -> str:
    if score >= 80:
        return "healthy"
    if score >= 50:
        return "degraded"
    return "unhealthy"


def rank_nodes(nodes: list[dict], health_map: dict[str, dict]) -> list[dict]:
    """Attach score/verdict to nodes and sort best-first."""
    ranked = []
    for n in nodes:
        h = health_map.get(n["id"], {})
        score = int(h.get("score", 0))
        ranked.append({**n, "health_score": score, "verdict": verdict_for(score),
                       "latency_ms": h.get("latency_ms", 0), "loss_pct": h.get("loss_pct", 0),
                       "health_detail": h.get("detail", ""), "checked_at": h.get("checked_at", 0)})
    ranked.sort(key=lambda x: x["health_score"], reverse=True)
    return ranked
