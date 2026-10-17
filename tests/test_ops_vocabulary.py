from swing_engine.ops import vocabulary as v


def test_read_card_and_rulings(tmp_path):
    card = tmp_path / "x.md"
    card.write_text("---\nslug: x\nname: X setup\nstatus: shadow_only  # note\n---\n\n# X\n\n## One-line summary\nBuy the\nthing.\n\n## Next\n")
    got = v.read_card(card)
    assert got["name"] == "X setup" and got["status"] == "shadow_only" and got["summary"] == "Buy the thing."
    r = tmp_path / "r.md"
    r.write_text("# t\n- 2026-10-13 x: not enabled\n- 2026-10-08 *: paper only\nnoise\n")
    assert v.read_rulings(r) == {"x": [("2026-10-13", "not enabled")], "*": [("2026-10-08", "paper only")]}


def test_render_lists_every_strategy():
    text = v.render()
    assert all(f"{e['slug']}" in text for e in v.entries())
