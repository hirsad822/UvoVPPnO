# PulseGrid — Architecture

## Overview
```
┌─────────────┐   HTTPS/HTTP    ┌──────────────────────────────┐
│  Browser    │ ──────────────► │  PulseGrid (Python stdlib)   │
│  Dashboard  │ ◄────────────── │  ThreadingHTTPServer         │
└─────────────┘                 │  ├─ API (REST/JSON)          │
                                │  ├─ Presets engine           │
                                │  ├─ Connection Doctor        │
                                │  ├─ Health scoring           │
                                │  ├─ Subscription builder     │
                                │  └─ Traffic accounting       │
                                └───────┬──────────────────────┘
                                        │
                                ┌───────▼───────┐   SQLite (WAL)
                                │  pulsegrid.db │
                                └───────────────┘
```

## Technology Choices
- **Backend:** Python 3.8+ **stdlib only** (`http.server`, `sqlite3`, `socket`, `ssl`,
  `concurrent.futures`). Zero `pip install` → fastest, most reliable one-line install.
- **Frontend:** Vanilla HTML/CSS/JS, no build step. Served by the backend.
- **Storage:** SQLite (single file, WAL mode). No external DB to provision.
- **Service:** systemd unit (`systemd/pulsegrid.service`). No Docker required.
- **Installer:** Bash (`install.sh`), idempotent, with `--update/--status/--uninstall`.

## Module Map (`pulsegrid/`)
| Module | Responsibility |
|---|---|
| `server.py` | HTTP routing, auth middleware, static file serving, JSON helpers |
| `api.py` | REST handlers: nodes, users, presets, doctor, subscription, traffic, dashboard |
| `config.py` | Settings loading (env + file), token, host/port, data dir |
| `db.py` | Schema + CRUD for nodes, users, health checks, traffic, alerts, settings |
| `presets.py` | Preset catalogue, apply/merge logic, validation |
| `doctor.py` | Probes: latency, packet loss, port, DNS, TLS, service health |
| `health.py` | Weighted 0–100 scoring + node ranking |
| `subscription.py` | Health-aware filtering/sorting + Base64/Plain/JSON output |
| `traffic.py` | Usage aggregation, quota checks, expiry logic |
| `__main__.py` | CLI entry (`python3 -m pulsegrid`) |

## Data Model (SQLite)
- `nodes(id, name, host, port, protocol, transport, security, uuid, remark, enabled, created_at)`
- `users(id, name, uuid, quota_bytes, used_bytes, expires_at, enabled, created_at)`
- `health_checks(id, node_id, score, latency_ms, loss_pct, reachable, checked_at, detail)`
- `traffic_events(id, user_id, node_id, up_bytes, down_bytes, ts)`
- `alerts(id, level, message, created_at, resolved_at)`
- `settings(key, value)` — active preset, token hash, mode (simple/expert)

## Health Scoring (0–100)
Weighted composite, computed from real probes:
- Latency 30% · Packet loss 25% · Reachability 20% · TLS 15% · Service uptime 10%

Thresholds: `≥80 Healthy` · `50–79 Degraded` · `<50 Unhealthy`.
Subscriptions include only `score ≥ min_score` (default 50), non-expired, quota-remaining nodes.

## API (REST/JSON, Bearer token except `/api/health` & `/api/subscription/*`)
- `GET  /api/health` — liveness
- `GET  /api/dashboard` — aggregated overview (nodes, users, traffic, alerts)
- `GET/POST /api/nodes`, `GET/PUT/DELETE /api/nodes/{id}`
- `GET/POST /api/users`, `GET/PUT/DELETE /api/users/{id}`
- `GET  /api/presets`, `POST /api/presets/apply`
- `POST /api/doctor/run` — full diagnostics (optionally `{"host":..., "port":...}`)
- `GET  /api/subscription/{user_id}?format=base64|plain|json`
- `GET  /api/traffic/summary`
- `GET  /api/health/nodes` — per-node latest scores

## Security
- Bearer token auth on all `/api/*` except health/subscription (subscription uses per-user UUID).
- Token stored in `~/.config/pulsegrid/token` (0600) or `PULSEGRID_TOKEN` env.
- Recommend reverse proxy + HTTPS in production.

## Deployment
`install.sh` → installs to `/opt/pulsegrid`, data in `/var/lib/pulsegrid`,
config in `/etc/pulsegrid`, systemd unit `pulsegrid.service`, port `8080`.
