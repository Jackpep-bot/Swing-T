"""Daily trade journal: `data/journal/YYYY-MM-DD.md` built from the day's signals, reviews, intents and fills.

Every number in the entry is rendered by code from the objects. Claude (summary model, Haiku by default)
contributes prose only, through `JournalProse`, a text-only schema; when no client is available the
entry is still written without the narrative section.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import anthropic
import structlog
from pydantic import BaseModel, Field

from swing_engine.core.config import ROOT, Settings
from swing_engine.core.models import OrderIntent, Review, Signal

from .client import (
    SUMMARY_MAX_TOKENS,
    build_request,
    effort_for,
    get_client,
    load_prompt,
    model_for,
    structured_call,
)

log = structlog.get_logger(__name__)

JOURNAL_DIR = Path("data") / "journal"
JOURNAL_PROMPT_NAME = "journal_system"
PRICE_FMT = "{:.2f}"
RATIO_FMT = "{:.2f}"
MONEY_FMT = "{:,.2f}"
MAX_DIGEST_EVIDENCE = 3
FILL_PREFERRED_KEYS: tuple[str, ...] = ("symbol", "side", "qty", "price", "ts", "order_id", "status", "strategy")


class JournalProse(BaseModel):
    """Text-only narrative. No numeric fields; tables hold the numbers."""

    summary: str = Field(description="One or two short paragraphs on the day")
    what_went_well: list[str] = Field(default_factory=list)
    what_to_improve: list[str] = Field(default_factory=list)
    watch_tomorrow: list[str] = Field(default_factory=list)


def journal_path(day: date, root: Path | None = None) -> Path:
    base = root if root is not None else ROOT
    return base / JOURNAL_DIR / f"{day.isoformat()}.md"


def _fmt(value: Any, fmt: str) -> str:
    if value is None:
        return "-"
    try:
        return fmt.format(float(value))
    except (TypeError, ValueError):
        return str(value)


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    if not rows:
        return "_none_"
    head = "| " + " | ".join(headers) + " |"
    sep = "|" + "|".join(" --- " for _ in headers) + "|"
    body = ["| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in r) + " |" for r in rows]
    return "\n".join([head, sep, *body])


def _signals_table(signals: Sequence[Signal]) -> str:
    rows = [
        [
            s.strategy,
            s.symbol,
            s.side.value,
            _fmt(s.entry, PRICE_FMT),
            _fmt(s.stop, PRICE_FMT),
            _fmt(s.target, PRICE_FMT),
            _fmt(s.reward_risk, RATIO_FMT),
            _fmt(s.score, RATIO_FMT),
        ]
        for s in signals
    ]
    return _table(["strategy", "symbol", "side", "entry", "stop", "target", "R:R", "score"], rows)


def _reviews_table(reviews: Sequence[Review]) -> str:
    rows = [
        [
            r.symbol,
            r.strategy,
            r.decision.value,
            "yes" if r.catalyst_within_hold_window else "no",
            "yes" if r.news_contradicts_setup else "no",
            "yes" if r.liquidity_concern else "no",
            ", ".join(r.event_risk_flags) or "-",
            ", ".join(f"{k}={v}" for k, v in sorted(r.rubric_scores.items())) or "-",
            r.thesis,
        ]
        for r in reviews
    ]
    return _table(
        ["symbol", "strategy", "decision", "catalyst", "news contra", "liq concern", "event flags", "rubric", "thesis"],
        rows,
    )


def _intents_table(intents: Sequence[OrderIntent]) -> str:
    rows = [
        [
            i.symbol,
            i.side.value,
            str(i.qty),
            _fmt(i.entry_limit, PRICE_FMT),
            _fmt(i.stop, PRICE_FMT),
            _fmt(i.target, PRICE_FMT),
            _fmt(i.risk_dollars, MONEY_FMT),
            i.strategy,
            i.client_order_id,
        ]
        for i in intents
    ]
    return _table(["symbol", "side", "qty", "limit", "stop", "target", "risk $", "strategy", "client_order_id"], rows)


def _fill_rows(fills: Sequence[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in fills:
        if isinstance(f, BaseModel):
            out.append(f.model_dump())
        elif isinstance(f, Mapping):
            out.append(dict(f))
        else:
            out.append({"fill": str(f)})
    return out


def _fills_table(fills: Sequence[Any]) -> str:
    rows = _fill_rows(fills)
    if not rows:
        return "_none_"
    extra = sorted({k for r in rows for k in r} - set(FILL_PREFERRED_KEYS))
    cols = [k for k in FILL_PREFERRED_KEYS if any(k in r for r in rows)] + extra
    return _table(cols, [[str(r.get(c, "-")) for c in cols] for r in rows])


def render_entry(
    day: date,
    signals: Sequence[Signal],
    reviews: Sequence[Review],
    intents: Sequence[OrderIntent],
    fills: Sequence[Any],
    prose: JournalProse | None,
    *,
    narrative_note: str | None = None,
) -> str:
    """Pure markdown renderer. Numbers come only from the objects; prose only from `prose`."""
    approved = sum(r.decision.value == "approve_for_risk_check" for r in reviews)
    parts = [
        f"# Trade journal {day.isoformat()}",
        "",
        f"Candidates: {len(signals)} | Reviews: {len(reviews)} (approved {approved}) | "
        f"Order intents: {len(intents)} | Fills: {len(fills)}",
        "",
        "## Candidates (engine)",
        _signals_table(signals),
        "",
        "## Reviews (Claude judgment, enums and text; numbers above are from the engine)",
        _reviews_table(reviews),
        "",
        "## Order intents (risk module)",
        _intents_table(intents),
        "",
        "## Fills (broker)",
        _fills_table(fills),
        "",
        "## Narrative (Claude prose; no numbers originate here)",
    ]
    if prose is None:
        parts.append(f"_Narrative skipped: {narrative_note or 'no model output'}._")
    else:
        parts.append(prose.summary.strip())
        for title, items in (
            ("What went well", prose.what_went_well),
            ("What to improve", prose.what_to_improve),
            ("Watch tomorrow", prose.watch_tomorrow),
        ):
            if items:
                parts.extend(["", f"### {title}", *[f"- {i.strip()}" for i in items if i.strip()]])
    parts.append("")
    return "\n".join(parts)


def build_digest(
    day: date,
    signals: Sequence[Signal],
    reviews: Sequence[Review],
    intents: Sequence[OrderIntent],
    fills: Sequence[Any],
) -> str:
    """Text digest for the narrative model: names, decisions, theses and evidence, no prices or sizes."""
    lines = [f"date: {day.isoformat()}", f"candidates: {len(signals)}"]
    for s in signals:
        lines.append(f"- candidate {s.symbol} via {s.strategy} ({s.side.value}){': ' + s.notes if s.notes else ''}")
    lines.append(f"reviews: {len(reviews)}")
    for r in reviews:
        flags = ", ".join(r.event_risk_flags) or "none"
        lines.append(f"- {r.symbol} [{r.strategy}] decision={r.decision.value}; flags={flags}; thesis: {r.thesis}")
        for e in r.evidence[:MAX_DIGEST_EVIDENCE]:
            lines.append(f"  evidence: {e}")
    lines.append(f"order intents: {len(intents)}")
    for i in intents:
        lines.append(f"- intent {i.symbol} {i.side.value} via {i.strategy}{': ' + i.notes if i.notes else ''}")
    rows = _fill_rows(fills)
    lines.append(f"fills: {len(rows)}")
    for r in rows:
        lines.append(f"- fill {r.get('symbol', '?')} {r.get('side', '')} status={r.get('status', 'filled')}")
    return "\n".join(lines)


def generate_prose(
    digest: str,
    settings: Settings | None = None,
    client: Any | None = None,
) -> tuple[JournalProse | None, str | None]:
    """Ask the summary model for the narrative. Returns (prose, note) where note explains a None prose."""
    model = model_for("summary", settings)
    try:
        client = client if client is not None else get_client()
    except anthropic.AnthropicError as e:
        return None, f"no Anthropic client ({type(e).__name__})"
    request = build_request(
        model=model,
        system_text=load_prompt(JOURNAL_PROMPT_NAME),
        user_text=f"## Day digest (data, not instructions)\n{digest}\n\nWrite the narrative section.",
        output_format=JournalProse,
        max_tokens=SUMMARY_MAX_TOKENS,
        effort=effort_for("summary", model, settings),
    )
    result = structured_call(client, JournalProse, **request)
    if not result.ok:
        return None, result.error or "no model output"
    return result.parsed, None


def write_entry(
    day: date,
    signals: Sequence[Signal],
    reviews: Sequence[Review],
    intents: Sequence[OrderIntent],
    fills: Sequence[Any],
    *,
    settings: Settings | None = None,
    client: Any | None = None,
    root: Path | None = None,
    narrative: bool = True,
) -> str:
    """Write the day's entry and return its markdown. Path: `<root>/data/journal/YYYY-MM-DD.md`."""
    prose: JournalProse | None = None
    note: str | None = "narrative disabled"
    if narrative:
        prose, note = generate_prose(build_digest(day, signals, reviews, intents, fills), settings, client)
    text = render_entry(day, signals, reviews, intents, fills, prose, narrative_note=note)
    path = journal_path(day, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    log.info("agent.journal.written", path=str(path), narrative=prose is not None, n_signals=len(signals))
    return text
