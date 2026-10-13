"""Local, read-only dashboard: one screen over the engine's own records (run files, DuckDB store, event log,
order ledger) plus the Alpaca paper account.

``python -m swing_engine.dashboard [--settings PATH] [--port 8765] [--demo] [--open]`` serves it on
127.0.0.1 only. Standard library HTTP server (``http.server.ThreadingHTTPServer``) and JSON; the page in
``static/`` draws it. The dashboard never places, replaces or cancels an order: the only writes it makes are an
alert rating (through ``monitor.rate.rate_alert``) and tripping the kill switch (``risk.killswitch.trip``);
clearing the kill switch stays a manual action. See ``docs/DASHBOARD.md``.
"""
from __future__ import annotations

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

__all__ = ["DEFAULT_HOST", "DEFAULT_PORT", "serve"]


def serve(settings_path: str | None = None, port: int = DEFAULT_PORT, demo: bool = False,
          open_browser: bool = False) -> None:
    """Run the dashboard until interrupted (entry point for a future ``swing dashboard`` command)."""
    from .server import serve as _serve

    _serve(settings_path=settings_path, port=port, demo=demo, open_browser=open_browser)
