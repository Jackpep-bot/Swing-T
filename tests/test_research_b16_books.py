import numpy as np
import pandas as pd
import pytest

from swing_engine.research import b16_books as b16


def test_blend_is_standardised_and_missing_gp_is_neutral():
    names = [f"s{i}" for i in range(50)]
    m = pd.Series(np.linspace(-2, 2, 50), index=names)
    gp = pd.Series(np.linspace(2, -2, 50), index=names)  # exactly opposite: blend flat except where gp is missing
    gp.iloc[-1] = np.nan
    z = b16.blend(m, gp)
    assert z.mean() == pytest.approx(0.0, abs=1e-9) and z.std() == pytest.approx(1.0)
    assert z.idxmax() == "s49"  # top momentum, no gross profit: g = 0, so it keeps its momentum half
    assert z.notna().all()
