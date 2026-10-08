"""research.cards: card Empirical sections from the replay shadow ledger and replay trades."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from swing_engine.research import cards


def shadow_rows() -> pd.DataFrame:
    rows = []
    for as_of, regime, r in [
        (date(2025, 3, 3), "choppy", 1.0), (date(2025, 3, 4), "choppy", -1.0), (date(2025, 6, 2), "healthy_uptrend", 2.0),
        (date(2019, 5, 1), "healthy_uptrend", -0.5),
    ]:
        row = {"strategy": "demo", "as_of": as_of, "regime": regime, "taken": False}
        for h in (5, 10, 20):
            row |= {f"hit_{h}d": "time_exit", f"result_r_{h}d": r, f"mfe_r_{h}d": max(r, 0.0), f"mae_r_{h}d": min(r, 0.0)}
        rows.append(row)
    rows.append({"strategy": "other", "as_of": date(2025, 3, 3), "regime": "choppy", "taken": False,
                 **{f"{c}_{h}d": v for h in (5, 10, 20) for c, v in
                    (("hit", "stop_hit"), ("result_r", -1.0), ("mfe_r", 0.0), ("mae_r", -1.0))}})
    return pd.DataFrame(rows)


def trades() -> pd.DataFrame:
    return pd.DataFrame([{"strategy": "demo", "signal_date": "2025-03-03", "r_multiple": 1.5, "pnl": 300.0,
                          "bars_held": 4}])


def test_render_splits_windows_and_regimes() -> None:
    text = cards.render_section("demo", shadow_rows(), trades(), generated=date(2026, 10, 8), n_strategies=127)
    short, long_ = text.split("### 2017-01-01")
    assert "| choppy | 2 | 0 | 50% | +0.00 |" in short and "| **all** | 3 | 0 | 67% | +0.67 |" in short
    assert "1 trades, win 100%, avg +1.50R" in short and "About 127 strategies" in text
    assert "| **all** | 1 | 0 | 0% | -0.50 |" in long_ and "no trades taken" in long_
    assert "other" not in text


def test_replace_section_keeps_the_rest_of_the_card(tmp_path: Path) -> None:
    card = "# Demo\n\n## Rules\nx\n\n## Empirical (replay)\n_Pending._\n\n## Sources\n- a\n"
    out = cards.replace_section(card, "## Empirical (replay)\nNEW\n")
    assert out == "# Demo\n\n## Rules\nx\n\n## Empirical (replay)\nNEW\n\n## Sources\n- a\n"
    assert cards.replace_section("# Demo\n", "## Empirical (replay)\nNEW\n").endswith("\n\n## Empirical (replay)\nNEW\n")
    (tmp_path / "demo.md").write_text(card)
    assert cards.write_cards(shadow_rows(), trades(), ["demo", "missing"], tmp_path) == ["demo"]
    again = cards.write_cards(shadow_rows(), trades(), ["demo"], tmp_path)  # idempotent: one section, rest intact
    text = (tmp_path / "demo.md").read_text()
    assert again == ["demo"] and text.count("## Empirical (replay)") == 1 and text.endswith("## Sources\n- a\n")
