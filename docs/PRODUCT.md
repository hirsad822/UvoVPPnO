# PulseGrid — Product Concept

## Problem
Existing traffic/configuration panels expose raw forms: dozens of fields, repetitive screens,
and no guidance. Users copy-paste configs they don't understand, subscriptions include dead or
expired nodes, and when something breaks there is no built-in way to know *why*.

## Differentiation
PulseGrid inverts the UX: **automation first, forms second.**

| Pillar | How it works | User benefit |
|---|---|---|
| **Connection Doctor** | Probes latency, packet loss, port reachability, DNS, TLS, and service health; scores 0–100; recommends or applies a preset | "Why is it slow?" answered in one click, with a fix |
| **Smart Presets** | Curated profiles with sensible defaults; Simple Mode hides complexity | Working config in <60s without reading a manual |
| **Health-Aware Subscription** | Ranks nodes by live health score; filters expired / quota-exceeded / unhealthy | Clients always get the best node first |
| **Instant Actions** | Dashboard optimized for create-user → copy-link → done | Less clicking, less reading, more doing |

## Personas
- **Casual operator** — wants it to "just work". Simple Mode + presets + Doctor.
- **Power user** — wants full control. Expert Mode exposes transport/security/mux/routing.
- **Small team / reseller** — needs quota, expiry, and per-user subscriptions that self-clean.

## Design Principles
1. **One minute to first user.** Every primary flow ≤ 3 clicks.
2. **Explain in plain language.** "Node is healthy (score 92)" beats raw JSON.
3. **Automate the boring 90%.** Presets, ranking, filtering, and remediation are automatic.
4. **Zero-dependency install.** Python stdlib only → `curl | bash` just works, anywhere.
5. **Honest health.** Scores are computed from real probes, not hardcoded.

## Preset Catalogue
- **Balanced Daily** — safe defaults for everyday use (TCP + TLS, moderate mux).
- **Low Latency** — minimal overhead, aggressive sockopt, no mux delay.
- **Resilient Mode** — fallback-friendly, retry-tolerant, conservative timeouts.
- **Streaming Optimized** — throughput-oriented, larger buffers, parallel dial.
- **Max Privacy** — encrypted transport, minimal fingerprint surface, strict DNS.

## Success Metrics
- Time-to-first-user < 60s (measured in usability testing).
- Subscription dead-node rate → 0 (filtered by health/expiry/quota).
- Doctor mean-time-to-diagnosis < 10s.
