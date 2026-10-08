"""Review regression for connors_pctb: the pctb_col trial's column is attached to the panel the exit reads."""
from __future__ import annotations

import pytest

from swing_engine.core import registry
from swing_engine.features.extra import required_extras


@pytest.mark.parametrize("col", ["bb_pctb_20", "bb_pctb_5"])
def test_pctb_col_is_a_required_extra(col):
    s = registry.get("strategy", "connors_pctb")({"pctb_col": col})
    assert required_extras([s]) == [col]
