# PulseGrid — Smart Traffic & Configuration Manager

> **Set up a working proxy node or user in under a minute. No 50-page manual. No raw-form fatigue.**

PulseGrid is a distinctive, high-appeal traffic & configuration management system built around
**smart automation, self-diagnostics, and effortless one-command installation** — instead of
exposing overwhelming raw forms and repetitive panel screens.

![Status](https://img.shields.io/badge/status-production%20ready-brightgreen)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Deps](https://img.shields.io/badge/dependencies-zero%20(stdlib%20only)-orange)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## ✨ What Makes PulseGrid Different

| Generic Panels | PulseGrid |
|---|---|
| Raw forms, 50 fields, guesswork | **Smart Presets** — one click applies a curated profile |
| "It doesn't work" with no clues | **Connection Doctor** — tests latency, loss, ports, TLS & service health, then suggests/applies a fix |
| Static subscription dumps dead nodes | **Health-Aware Subscription** — only healthy, low-latency, non-expired nodes, ranked by live score |
| Dashboard = tables | **Instant Actions** — create a user/node in <60s, copy subscription, see quota & expiry in plain language |
| Expert-only UX | **Simple Mode by default**, Expert Mode when you want full control |

### Standout Features

1. **🩺 Smart Route & Connection Doctor** — built-in diagnostics that test latency, packet loss,
   port reachability, DNS, TLS handshake, and core/service health. Returns a 0–100 health score
   with human-readable findings and **one-click "Apply recommended preset"** remediation.

2. **⚡ One-Click Smart Presets + Simple Mode** — curated profiles:
   *Balanced Daily*, *Low Latency*, *Resilient Mode*, *Streaming Optimized*, *Max Privacy*.
   Simple Mode hides everything else. Expert Mode reveals transport, security, mux, routing & sockopt tweaks.

3. **🔗 Health-Aware Dynamic Subscription** — subscription links that prioritize healthy,
   low-latency, non-expired nodes and show clear quota & expiry info. Formats: Base64, Plain, JSON
   (Clash / Sing-box / V2RayNG friendly).

4. **📊 Clean Modern Dashboard & Instant Actions** — fast overview of nodes, users, traffic usage,
   and alerts. Designed for speed: add user → copy link → done.

---

## 🚀 One-Line Installation

```bash
curl -fsSL https://raw.githubusercontent.com/hirsad822/UvoVPPnO/main/install.sh | sudo bash
```

Or clone and run locally:

```bash
git clone https://github.com/hirsad822/UvoVPPnO.git && cd UvoVPPnO
sudo bash install.sh
```

The installer detects OS/arch (Debian/Ubuntu `x86_64` / `arm64`, RHEL, Alpine), checks root,
installs only `python3` (zero pip dependencies — stdlib only), creates a systemd service,
prints firewall hints, runs a health check, and shows access details + status commands.
Re-running is safe (idempotent).

### After Install

```
✅ PulseGrid installed successfully!

   Dashboard : http://<your-server-ip>:8080
   Token     : <shown once — save it>
   Service   : systemctl status pulsegrid
   Logs      : journalctl -u pulsegrid -f
```

Open the dashboard, paste the token, pick a preset, add a user — done.

---

## 🧭 Quick Start (60 seconds)

1. Open `http://<server>:8080` → enter token.
2. Click **Connection Doctor → Run Diagnostics** (optional but recommended).
3. Pick a preset (e.g. **Balanced Daily**) → **Apply**.
4. **Users → Add User** → copy the subscription link.
5. Import the link into your client (V2RayNG / Streisand / Clash / Sing-box).

---

## 📁 Repository Layout

```
.
├── install.sh                  # One-line installer (install / --update / --status / --uninstall)
├── README.md                   # This file
├── docs/
│   ├── PRODUCT.md              # Product concept & differentiation
│   ├── ARCHITECTURE.md         # System design, data model, API
│   └── TROUBLESHOOTING.md      # Usage & troubleshooting commands
├── pulsegrid/                  # Core backend (Python stdlib only — zero pip deps)
│   ├── __init__.py
│   ├── __main__.py             # Entry point: python3 -m pulsegrid
│   ├── server.py               # Threading HTTP server + routing + static files
│   ├── config.py               # Settings, token, paths
│   ├── db.py                   # SQLite storage layer
│   ├── presets.py              # Smart preset engine
│   ├── doctor.py               # Connection Doctor diagnostics
│   ├── health.py               # Health scoring & ranking
│   ├── subscription.py         # Health-aware subscription builder
│   ├── traffic.py              # Traffic accounting & quota
│   └── api.py                  # REST API handlers
├── web/                        # Dashboard frontend (no build step)
│   ├── index.html
│   ├── app.js
│   └── style.css
├── systemd/
│   └── pulsegrid.service       # systemd unit
├── scripts/
│   └── verify.sh               # Post-install verification
└── tests/                      # Unit + API tests (stdlib unittest)
    ├── test_presets.py
    ├── test_doctor.py
    ├── test_health.py
    ├── test_subscription.py
    └── test_api.py
```

---

## 🔧 Management Commands

```bash
# Service
systemctl status pulsegrid
systemctl restart pulsegrid
journalctl -u pulsegrid -f

# Installer subcommands
sudo bash install.sh --status     # show install + health status
sudo bash install.sh --update     # update to latest code (keeps data & token)
sudo bash install.sh --uninstall  # remove service & files (keeps data unless --purge)
sudo bash install.sh --help

# Local dev (no install needed)
python3 -m pulsegrid --host 0.0.0.0 --port 8080 --token dev-token
python3 -m unittest discover -s tests -v
bash scripts/verify.sh
```

---

## 🔒 Security & Compliance

- Token-based admin auth (Bearer). Change the token after install.
- Bind to `127.0.0.1` behind a reverse proxy (nginx/Caddy) with HTTPS in production.
- All network configurations must respect applicable laws and regulations in your jurisdiction.
- PulseGrid manages *your own* infrastructure; you are responsible for lawful use.

---

## 📄 Documentation

- [Product Concept](docs/PRODUCT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## 📜 License

MIT — see `LICENSE` if present, otherwise treat as MIT for this template.
