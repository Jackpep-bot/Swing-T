"""Review regressions for strategies/canslim.py (and the other EDGAR-fed strategies sharing the same gap)."""
import pytest

from swing_engine.data import fundamentals
from swing_engine.strategies import canslim, pead_sue, revenue_surprise

NOTE = "No engine panel builder joins edgar_panel_features yet"


@pytest.mark.parametrize("mod", [canslim, pead_sue, revenue_surprise])
def test_docstring_states_strategy_is_dead_until_edgar_is_joined(mod):
    # `sue` / `rev_surprise` only exist if a panel builder joins edgar_panel_features; until data.fundamentals.join_edgar
    # lands (and is wired into replay / cli / nightly) the docstring must say the strategy is silent, then drop the note.
    doc = " ".join((mod.__doc__ or "").split())
    if hasattr(fundamentals, "join_edgar"):
        assert NOTE not in doc
    else:
        assert NOTE in doc
