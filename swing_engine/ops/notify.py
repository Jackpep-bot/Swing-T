"""Telegram reports: the nightly summary, the weekly report on the week's last session, research rebuilds and a
delivery test. Reuses the monitor's `TelegramDeliverer` (HTML-escaped, rate-limited, retry on 429); plain text
built from run data only, no LLM call. A sender is any `(title, body) -> delivered` callable, so tests inject a
fake. Every public sender returns False / a reason instead of raising: a notification never fails its caller.
"""
from __future__ import annotations

import asyncio
import math
from collections.abc import Callable, Iterable, Mapping
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from swing_engine.core.config import Secrets, load_secrets

log = structlog.get_logger(__name__)

Sender = Callable[[str, str], bool]

#: room left under Telegram's 4096-char message limit for the title and HTML escaping
BODY_BUDGET = 3800
TOP_SHADOW = 3
TOP_LEADERBOARD = 5
DETAIL_CHARS = 80  # per failed step


def telegram_sender(secrets: Secrets) -> Sender | None:
    """A sender for TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID, or None when either is missing."""
    token, chat = secrets.telegram_bot_token, secrets.telegram_chat_id
    if not (token and chat):
        return None

    def send(title: str, body: str) -> bool:
        from swing_engine.core.models import Priority
        from swing_engine.monitor.delivery.telegram import TelegramDeliverer

        async def go() -> bool:
            bot = TelegramDeliverer(token, chat, rating_buttons=False)
            try:
                return await bot.send(title, body, Priority.P2)  # P2: a notifying (not silent) message
            finally:
                await bot.aclose()

        return asyncio.run(go())

    return send


def deliver(title: str, body: str, sender: Sender | None = None, secrets: Secrets | None = None) -> str | None:
    """Send one message; returns None when delivered, else why not (never raises)."""
    try:
        sender = sender or telegram_sender(secrets if secrets is not None else load_secrets())
        if sender is None:
            return "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set"
        return None if sender(title, body) else "telegram did not accept the message"
    except Exception as e:  # noqa: BLE001 - a notification must never fail its caller
        log.warning("notify.failed", error=f"{type(e).__name__}: {e}"[:200])
        return f"send failed: {type(e).__name__}"


def truncate(text: str, limit: int = BODY_BUDGET, note: str = "") -> str:
    if len(text) <= limit:
        return text
    tail = f"\n... (truncated{'; ' + note if note else ''})"
    return text[: limit - len(tail)].rsplit("\n", 1)[0] + tail


# ---- nightly --------------------------------------------------------------------------------------------------
def nightly_message(report: Any, shadow_top: Iterable[tuple[str, int, float]] = ()) -> tuple[str, str]:
    """(title, body) for a NightlyReport. `shadow_top` is (strategy, trades, net R per trade) graded today."""
    steps = [s for s in report.steps if s.name != "notify"]
    failed = [s for s in steps if str(s.status) == "fail"]
    skipped = [s.name for s in steps if str(s.status) == "skip"]
    title = f"Nightly {report.as_of}: {'OK' if not failed else f'{len(failed)} step(s) FAILED'}"
    regime = report.regime or {}
    state = regime.get("market_state") or {}
    lines = [f"regime: {regime.get('regime') or state.get('regime') or 'unknown'}"]
    allowed = regime.get("allowed")
    if allowed is not None:
        lines[0] += " | allowed: " + (", ".join(f"{k} x{float(v):g}" for k, v in allowed.items()) or "none")
    if not failed and not skipped:
        lines.append("steps: all ok")
    for s in failed:
        lines.append(f"FAIL {s.name}: {s.detail[:DETAIL_CHARS]}")
    if skipped:
        lines.append("skipped: " + ", ".join(skipped))
    execute = report.step("execute")
    if execute is not None and str(execute.status) == "ok":
        d = execute.data
        lines.append(f"paper orders: {int(d.get('submitted') or 0)} submitted; entries {_tally(d.get('entries'))}; "
                     f"exits {_tally(d.get('exits'))}")
    shadow = report.step("shadow")
    if shadow is not None and str(shadow.status) == "ok":
        lines.append(f"shadow: {shadow.data.get('recorded', 0)} recorded, {shadow.data.get('graded', 0)} graded")
    top = list(shadow_top)
    if top:
        lines.append("top shadow graded today (net R/trade): "
                     + ", ".join(f"{s} {r:+.2f}R ({n})" for s, n, r in top))
    journal = report.files.get("journal")
    if journal:
        lines.append(f"journal: {journal}")
    return title, truncate("\n".join(lines))


def _tally(d: Any) -> str:
    return ", ".join(f"{k} {v}" for k, v in (d or {}).items()) or "none"


def shadow_top_today(store: Any, day: date, n: int = TOP_SHADOW) -> list[tuple[str, int, float]]:
    """Strategies whose live shadow signals exited on `day` (at the weekly report's horizon), best net R first."""
    from swing_engine.agent.weekly import REPORT_HORIZON, _by_strategy
    from swing_engine.research.cards import executable
    from swing_engine.research.shadow import SHADOW_TABLE, horizon_column

    if not store.has_table(SHADOW_TABLE):
        return []
    live = executable(store.read_table(SHADOW_TABLE)).reset_index(drop=True)
    col = horizon_column("exit_date", REPORT_HORIZON)
    if live.empty or col not in live.columns:
        return []
    today = live.loc[pd.to_datetime(live[col]).dt.date == day]
    stats = _by_strategy(today, REPORT_HORIZON).sort_values("net_r", ascending=False).head(n)
    return [(str(k), int(r.n), float(r.net_r)) for k, r in stats.iterrows()]


def weekly_message(path: str | Path) -> tuple[str, str]:
    """The weekly markdown, compacted (no table rules, no blank runs) and cut to one message."""
    p = Path(path)
    out: list[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if set(line) <= set("|-: ") and line:  # markdown table separator
            continue
        if line or (out and out[-1]):
            out.append(line.lstrip("#").strip() if line.startswith("#") else line)
    return f"Weekly report {p.stem.removeprefix('weekly-')}", truncate("\n".join(out), note=f"full report: {p}")


# ---- research ------------------------------------------------------------------------------------------------
def research_message(survivors: Any, n_trials: int, top_rows: Any) -> tuple[str, str]:
    if isinstance(survivors, pd.DataFrame):
        names = sorted({f"{r.strategy}@{r.horizon}d" for r in survivors.itertuples()}) if not survivors.empty else []
    elif isinstance(survivors, int):
        names = [] if survivors == 0 else [f"{survivors}"]
    else:
        names = [str(s) for s in survivors or []]
    line = "survivors: none" if not names else f"survivors ({len(names)}): {', '.join(names)}"
    rows = top_rows.to_dict("records") if isinstance(top_rows, pd.DataFrame) else list(top_rows or [])
    lines = [line, f"trials: {n_trials}", f"top {min(TOP_LEADERBOARD, len(rows))} leaderboard rows:"]
    lines += [_row(r) for r in rows[:TOP_LEADERBOARD]]
    return "Research rebuild done", truncate("\n".join(lines))


def _row(r: Any) -> str:
    if not isinstance(r, Mapping):
        return str(r)
    head = f"{r.get('strategy', '?')}"
    if "horizon" in r:
        head += f" {r['horizon']}d"
    if "window" in r:
        head += f" [{r['window']}]"
    stats = [f"{k} {_num(r[k])}" for k in ("n", "net_r", "t", "haircut_sharpe") if k in r]
    return f"- {head}: {', '.join(stats)}" if stats else f"- {head}"


def _num(x: Any) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    if not math.isfinite(v):
        return "-"
    return f"{int(v)}" if v.is_integer() and abs(v) >= 1 else f"{v:+.3f}"


def notify_research_summary(
    survivors: Any, n_trials: int, top_rows: Any, *, sender: Sender | None = None, secrets: Secrets | None = None
) -> bool:
    """Telegram the result of a cards + leaderboard rebuild: the survivors line and the top 5 rows.

    `survivors`: research.leaderboard.survivors() frame, a count, or names; `top_rows`: leaderboard frame or row
    dicts (strategy, horizon, window, n, net_r, t, haircut_sharpe; missing keys are left out). Never raises;
    returns True when delivered (False also when Telegram is not configured).
    """
    try:
        title, body = research_message(survivors, n_trials, top_rows)
    except Exception as e:  # noqa: BLE001
        log.warning("notify.research_format_failed", error=f"{type(e).__name__}: {e}"[:200])
        return False
    why = deliver(title, body, sender, secrets)
    if why:
        log.info("notify.research_not_sent", reason=why)
    return why is None


TEST_TITLE = "swing-engine test"


def ping_message(now: str) -> tuple[str, str]:
    return TEST_TITLE, f"Telegram delivery works ({now}). Nightly and research reports will arrive here."
