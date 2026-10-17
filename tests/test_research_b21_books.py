from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.research import b21_books as b21


def test_exclusion_buffer_keeps_unscored_names_and_caps():
    names = [f"s{i}" for i in range(300)]
    s1 = pd.Series(np.linspace(1.0, -1.0, 300), index=names)  # s299 lowest surprise
    s1["s0"] = np.nan  # unscored: stays in the book
    s2 = s1.copy()
    s2["s299"] = s1["s180"]  # rises to rank ~120 from the bottom: still excluded (within the lowest 130)
    s2["s250"] = s1["s10"]  # far above: returns
    mcap = pd.Series(1.0, index=names)
    mcap["s0"] = 1000.0
    u = {date(2017, 4, 3): pd.DataFrame({"mcap_pit": mcap, "surprise": s1}),
         date(2017, 6, 1): pd.DataFrame({"mcap_pit": mcap, "surprise": s2})}
    book, gone, share = b21.plan(u, date(2016, 1, 4))
    b1, b2 = book[date(2017, 4, 3)], book[date(2017, 6, 1)]
    assert "s0" in b1.index and "s299" not in b1.index and len(b1) == 200
    assert "s299" not in b2.index and "s250" in b2.index
    assert b1.sum() == pytest.approx(1.0) and b1["s0"] == pytest.approx(0.10)
    assert len(gone[date(2017, 4, 3)]) == 100 and 0 < share[date(2017, 4, 3)] < 1
