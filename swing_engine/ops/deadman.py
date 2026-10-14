"""Dead-man alert for the nightly: a Telegram message when the morning's nightly has not finished by the time this
runs (scheduled by launchd at 08:30 on weekdays, deploy/launchd/com.swing.deadman.plist; only after the owner says
to install it). Silent on market holidays and when the nightly finished. Run by hand::

    uv run python -m swing_engine.ops.deadman --settings config/live.yaml
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from swing_engine.data.calendar import is_trading_day


def problem(report: Path, today: date) -> str | None:
    """Why today's nightly needs a look, or None (holiday, or a finished run)."""
    if not is_trading_day(today):
        return None
    if not report.exists():
        return f"The {today} nightly has not started: no run report at {report}."
    try:
        data = json.loads(report.read_text())
    except (OSError, json.JSONDecodeError) as e:
        return f"The {today} nightly's run report cannot be read ({type(e).__name__})."
    if not data.get("finished_at"):
        return f"The {today} nightly started at {data.get('started_at', '?')} and has not finished."
    return None


def main(argv: Sequence[str] | None = None) -> None:
    from swing_engine.core.config import load_settings
    from swing_engine.ops.nightly import run_file
    from swing_engine.ops.notify import deliver

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/live.yaml")
    ap.add_argument("--date", default=None, help="the session to check (default today)")
    args = ap.parse_args(argv)
    today = date.fromisoformat(args.date) if args.date else date.today()
    msg = problem(run_file(load_settings(args.settings), "nightly", today), today)
    if msg is None:
        print(f"nightly ok or not due for {today}")
        return
    why = deliver("Nightly missing", msg + " Check data/logs/nightly.err.log on the Mac.")
    print(msg, "(sent)" if why is None else f"(not sent: {why})")


if __name__ == "__main__":
    main()
