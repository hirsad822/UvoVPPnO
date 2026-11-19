"""Connection Doctor — real network diagnostics (stdlib only).

Tests: latency (TCP connect timing), packet loss (multi-probe success rate),
port reachability, DNS resolution, TLS handshake, and service health.
"""
from __future__ import annotations

import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor

from .health import score_health


def _tcp_probe(host: str, port: int, timeout: float = 3.0) -> tuple[bool, float]:
    """Return (reachable, latency_ms)."""
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, (time.perf_counter() - start) * 1000.0
    except OSError:
        return False, 0.0


def _dns_probe(host: str) -> tuple[bool, str]:
    try:
        ip = socket.gethostbyname(host)
        return True, ip
    except OSError as e:
        return False, str(e)


def _tls_probe(host: str, port: int, timeout: float = 3.0) -> tuple[bool, str]:
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                ver = ssock.version()
                return True, ver or "TLS"
    except Exception as e:  # noqa: BLE001 - diagnostic, report any failure
        return False, str(e)


def run_diagnostics(host: str, port: int = 443, probes: int = 5,
                    service_port: int | None = None) -> dict:
    """Run full diagnostics against host:port. Returns structured result."""
    findings: list[str] = []

    # DNS
    dns_ok, dns_detail = _dns_probe(host)
    findings.append(f"DNS {'OK' if dns_ok else 'FAILED'}: {host} -> {dns_detail}")

    # Reachability + latency (multi-probe for loss estimation)
    results: list[tuple[bool, float]] = []
    with ThreadPoolExecutor(max_workers=min(probes, 5)) as ex:
        futs = [ex.submit(_tcp_probe, host, port) for _ in range(probes)]
        for f in futs:
            try:
                results.append(f.result())
            except Exception:
                results.append((False, 0.0))

    successes = [r for ok, r in results if ok]
    reachable = len(successes) > 0
    latency_ms = round(sum(successes) / len(successes), 1) if successes else 0.0
    loss_pct = round((1 - len(successes) / probes) * 100, 1) if probes else 100.0

    if reachable:
        findings.append(f"Port {port} reachable, avg latency {latency_ms}ms over {probes} probes")
    else:
        findings.append(f"Port {port} UNREACHABLE after {probes} probes")

    # TLS (only if reachable)
    tls_ok, tls_detail = (False, "skipped (unreachable)")
    if reachable:
        tls_ok, tls_detail = _tls_probe(host, port)
        findings.append(f"TLS {'OK' if tls_ok else 'FAILED'}: {tls_detail}")

    # Service health (local check)
    service_ok = True
    if service_port is not None:
        service_ok, _ = _tcp_probe("127.0.0.1", service_port, timeout=1.0)
        findings.append(f"Local service port {service_port}: {'up' if service_ok else 'DOWN'}")

    score = score_health(latency_ms=latency_ms, loss_pct=loss_pct,
                         reachable=reachable, tls_ok=tls_ok,
                         service_ok=service_ok, dns_ok=dns_ok)
    verdict = "healthy" if score >= 80 else ("degraded" if score >= 50 else "unhealthy")

    # Human-readable summary + suggestion
    if not reachable:
        summary = "Node is unreachable. Check host/port and firewall, or try Resilient Mode."
    elif loss_pct >= 5:
        summary = f"High packet loss ({loss_pct}%). Resilient Mode recommended."
    elif latency_ms > 150:
        summary = f"High latency ({latency_ms}ms). Balanced or Low Latency preset recommended."
    elif score >= 80:
        summary = "Node is healthy and performing well."
    else:
        summary = "Node is degraded. Review findings and consider applying the recommended preset."

    return {
        "host": host, "port": port, "reachable": reachable,
        "latency_ms": latency_ms, "loss_pct": loss_pct,
        "dns_ok": dns_ok, "dns_detail": dns_detail,
        "tls_ok": tls_ok, "tls_detail": tls_detail,
        "service_ok": service_ok,
        "score": score, "verdict": verdict,
        "findings": findings, "summary": summary,
        "checked_at": time.time(),
    }
