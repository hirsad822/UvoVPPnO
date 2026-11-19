"""Configuration loading: env vars > config file > defaults.

Stdlib only. No external dependencies.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    host: str = "0.0.0.0"
    port: int = 8080
    token: str = ""
    data_dir: Path = field(default_factory=lambda: Path("/var/lib/pulsegrid"))
    config_dir: Path = field(default_factory=lambda: Path("/etc/pulsegrid"))
    web_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent / "web")
    db_path: Path = field(default_factory=lambda: Path("/var/lib/pulsegrid/pulsegrid.db"))
    mode: str = "simple"  # simple | expert
    dashboard_tls: bool = False
    min_score: int = 50

    @classmethod
    def from_env(cls, argv: dict | None = None) -> "Settings":
        argv = argv or {}
        s = cls()
        s.host = argv.get("host") or os.environ.get("PULSEGRID_HOST", s.host)
        s.port = int(argv.get("port") or os.environ.get("PULSEGRID_PORT", s.port))
        s.token = argv.get("token") or os.environ.get("PULSEGRID_TOKEN", "")
        s.mode = argv.get("mode") or os.environ.get("PULSEGRID_MODE", s.mode)
        s.dashboard_tls = os.environ.get("PULSEGRID_DASHBOARD_TLS", "0") == "1"
        if os.environ.get("PULSEGRID_DATA_DIR"):
            s.data_dir = Path(os.environ["PULSEGRID_DATA_DIR"])
            s.db_path = s.data_dir / "pulsegrid.db"
        if os.environ.get("PULSEGRID_CONFIG_DIR"):
            s.config_dir = Path(os.environ["PULSEGRID_CONFIG_DIR"])
        # Fall back to token file if no token provided
        if not s.token:
            for cand in (s.config_dir / "token", s.data_dir / "token", Path.home() / ".config" / "pulsegrid" / "token"):
                try:
                    if cand.is_file():
                        s.token = cand.read_text().strip()
                        break
                except OSError:
                    continue
        if not s.token:
            s.token = secrets.token_urlsafe(24)
        return s

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.config_dir):
            try:
                d.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
        # Persist generated token with restrictive perms (best effort)
        try:
            tf = self.config_dir / "token"
            if not tf.exists():
                tf.write_text(self.token + "\n")
                tf.chmod(0o600)
        except OSError:
            pass
