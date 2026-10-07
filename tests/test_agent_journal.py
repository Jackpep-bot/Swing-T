"""agent.journal: numbers come from objects, prose from a text-only schema, graceful degradation."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import anthropic

from swing_engine.agent.client import assert_no_numeric_fields
from swing_engine.agent.journal import JournalProse, build_digest, journal_path, render_entry, write_entry
from swing_engine.core.config import Settings
from swing_engine.core.models import OrderIntent, Review, ReviewDecision, Side, Signal
from tests.agent_fakes import FakeClient, FakeResponse, parsed

FIXTURES = Path(__file__).parent / "fixtures" / "agent"
PROSE = json.loads((FIXTURES / "journal_response.json").read_text())
DAY = date(2026, 10, 6)


def sample_day() -> tuple[list[Signal], list[Review], list[OrderIntent], list[dict]]:
    sig = Signal(
        strategy="pullback_trend", symbol="ACME", side=Side.LONG, as_of=DAY,
        entry=100.0, stop=98.0, target=106.0, reward_risk=3.0, score=0.73,
    )
    review = Review(
        symbol="ACME", strategy="pullback_trend", thesis="Clean pullback; guidance raised last week.",
        catalyst_within_hold_window=True, event_risk_flags=["earnings"], news_contradicts_setup=False,
        insider_or_congress_signal="none", liquidity_concern=False,
        rubric_scores={"setup_quality": 4, "catalyst": 5}, decision=ReviewDecision.APPROVE_FOR_RISK_CHECK,
        evidence=["news 2026-10-01: guidance raised"],
    )
    intent = OrderIntent(
        symbol="ACME", side=Side.LONG, qty=250, entry_limit=100.25, stop=98.0, target=106.0,
        strategy="pullback_trend", client_order_id="swing-ACME-20261006", risk_dollars=500.0,
    )
    fills = [{"symbol": "ACME", "side": "buy", "qty": 250, "price": 100.1, "status": "filled", "venue": "paper"}]
    return [sig], [review], [intent], fills


def test_prose_schema_has_no_numeric_fields() -> None:
    assert_no_numeric_fields(JournalProse.model_json_schema())
    assert '"integer"' not in json.dumps(JournalProse.model_json_schema())


def test_render_entry_puts_object_numbers_in_tables() -> None:
    sigs, reviews, intents, fills = sample_day()
    text = render_entry(DAY, sigs, reviews, intents, fills, JournalProse.model_validate(PROSE))
    assert text.startswith("# Trade journal 2026-10-06")
    assert "| pullback_trend | ACME | long | 100.00 | 98.00 | 106.00 | 3.00 | 0.73 |" in text
    assert "| ACME | long | 250 | 100.25 | 98.00 | 106.00 | 500.00 | pullback_trend | swing-ACME-20261006 |" in text
    assert "approve_for_risk_check" in text and "catalyst=5, setup_quality=4" in text
    assert "| ACME | buy | 250 | 100.1 |" in text and "venue" in text
    assert PROSE["summary"] in text and "### Watch tomorrow" in text
    assert "approved 1" in text


def test_render_entry_without_prose_explains_why() -> None:
    text = render_entry(DAY, [], [], [], [], None, narrative_note="no key")
    assert "_Narrative skipped: no key._" in text and "_none_" in text


def test_digest_has_no_prices_or_sizes() -> None:
    sigs, reviews, intents, fills = sample_day()
    digest = build_digest(DAY, sigs, reviews, intents, fills)
    for number in ("100.0", "98.0", "106.0", "250", "500", "100.25"):
        assert number not in digest, number
    assert "decision=approve_for_risk_check" in digest and "guidance raised" in digest


def test_write_entry_without_narrative(tmp_path: Path) -> None:
    sigs, reviews, intents, fills = sample_day()
    text = write_entry(DAY, sigs, reviews, intents, fills, root=tmp_path, narrative=False)
    path = journal_path(DAY, tmp_path)
    assert path == tmp_path / "data" / "journal" / "2026-10-06.md"
    assert path.read_text() == text
    assert "Narrative skipped: narrative disabled" in text and "| 250 |" in text


def test_write_entry_with_fake_client_uses_summary_model(tmp_path: Path) -> None:
    fake = FakeClient(lambda kw: parsed(JournalProse, PROSE))
    sigs, reviews, intents, fills = sample_day()
    s = Settings.model_validate({"agent": {}})
    text = write_entry(DAY, sigs, reviews, intents, fills, settings=s, client=fake, root=tmp_path)
    call = fake.calls[0]
    assert call["model"] == "claude-haiku-4-5"
    assert "output_config" not in call  # Haiku has no effort parameter
    assert call["output_format"] is JournalProse
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "data, not instructions" in call["messages"][0]["content"]
    assert PROSE["what_to_improve"][0] in text
    assert journal_path(DAY, tmp_path).exists()


def test_write_entry_survives_model_failure(tmp_path: Path) -> None:
    fake = FakeClient(lambda kw: anthropic.AnthropicError("quota"))
    sigs, reviews, intents, fills = sample_day()
    text = write_entry(DAY, sigs, reviews, intents, fills, client=fake, root=tmp_path)
    assert "Narrative skipped: AnthropicError" in text and "| 250 |" in text
    refusal = FakeClient(lambda kw: FakeResponse(parsed_output=None, stop_reason="refusal"))
    text2 = write_entry(DAY, sigs, reviews, intents, fills, client=refusal, root=tmp_path)
    assert "Narrative skipped: refusal" in text2
