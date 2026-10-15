"""``python -m swing_engine.dashboard [--settings PATH] [--port 8765] [--demo] [--open]``."""
from __future__ import annotations

import argparse
import sys

from . import DEFAULT_PORT, serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m swing_engine.dashboard",
        description="Local read-only dashboard on http://127.0.0.1:<port>/ (never places or cancels orders).",
    )
    parser.add_argument("--settings", default=None,
                        help="settings YAML (default config/settings.yaml; the paper setup uses config/live.yaml)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port on 127.0.0.1 (default {DEFAULT_PORT})")
    parser.add_argument("--demo", action="store_true", help="serve deterministic fake data (no keys, no files)")
    parser.add_argument("--open", dest="open_browser", action="store_true", help="open the default browser")
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 (any free port) and 65535")
    try:
        serve(settings_path=args.settings, port=args.port, demo=args.demo, open_browser=args.open_browser)
    except OSError as exc:
        print(f"could not start the dashboard on 127.0.0.1:{args.port}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
