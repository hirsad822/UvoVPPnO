"""Entry point: python3 -m pulsegrid [--host H] [--port P] [--token T] [--mode simple|expert]"""
from __future__ import annotations

import argparse

from .config import Settings
from .server import serve


def main() -> None:
    ap = argparse.ArgumentParser(prog="pulsegrid", description="PulseGrid Smart Traffic & Config Manager")
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--token", default=None)
    ap.add_argument("--mode", choices=["simple", "expert"], default=None)
    args = ap.parse_args()
    settings = Settings.from_env({"host": args.host, "port": args.port,
                                  "token": args.token, "mode": args.mode})
    serve(settings)


if __name__ == "__main__":
    main()
