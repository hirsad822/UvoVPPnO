"""Traffic accounting, quota & expiry helpers."""
from __future__ import annotations

import time


def is_expired(user: dict, now: float | None = None) -> bool:
    now = now or time.time()
    exp = float(user.get("expires_at") or 0)
    return exp > 0 and now > exp


def quota_exceeded(user: dict) -> bool:
    quota = int(user.get("quota_bytes") or 0)
    if quota <= 0:
        return False  # 0 = unlimited
    return int(user.get("used_bytes") or 0) >= quota


def quota_remaining(user: dict) -> int:
    quota = int(user.get("quota_bytes") or 0)
    if quota <= 0:
        return -1  # unlimited
    return max(0, quota - int(user.get("used_bytes") or 0))


def format_bytes(n: int) -> str:
    if n < 0:
        return "unlimited"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} PB"


def user_status(user: dict, now: float | None = None) -> dict:
    now = now or time.time()
    expired = is_expired(user, now)
    exceeded = quota_exceeded(user)
    remaining = quota_remaining(user)
    exp = float(user.get("expires_at") or 0)
    days_left = max(0, int((exp - now) / 86400)) if exp > 0 else None
    if expired:
        status = "expired"
    elif exceeded:
        status = "quota_exceeded"
    elif not user.get("enabled", 1):
        status = "disabled"
    else:
        status = "active"
    return {
        "status": status,
        "expired": expired,
        "quota_exceeded": exceeded,
        "quota_remaining_bytes": remaining,
        "quota_remaining_human": format_bytes(remaining),
        "days_left": days_left,
        "used_human": format_bytes(int(user.get("used_bytes") or 0)),
        "quota_human": format_bytes(int(user.get("quota_bytes") or 0)) if int(user.get("quota_bytes") or 0) > 0 else "unlimited",
    }
