from datetime import date

import pandas as pd
import pytest

from swing_engine.data.calendar import trading_days
from swing_engine.data.store import Store
from swing_engine.ops import shadow_books as sb


def test_needed_days_start_with_the_book_in_force():
    assert sb.needed_days(date(2026, 10, 14)) == [date(2026, 9, 21)]
    assert sb.needed_days(date(2027, 3, 31))[0] == date(2026, 9, 21) and len(sb.needed_days(date(2027, 3, 31))) == 2


def test_forward_record_beside_spy_and_the_summary(tmp_path):
    days = trading_days("2026-10-13", "2026-10-21")
    rows = [{"symbol": s, "ts": pd.Timestamp(d, tz="America/New_York"), "open": px, "high": px, "low": px, "close": px,
             "volume": 1e6} for d in days for s, px in (("SPY", 500.0 + days.index(d)), ("AAA", 10.0))]
    state = {"book": sb.BOOK, "start": "2026-10-14", "orders": {"2026-09-21": {"AAA": 1.0}}, "record": None}
    with Store() as store:
        store.write_bars(pd.DataFrame(rows))
        rec = sb.record(store, state, date(2026, 10, 21))
    assert rec["book_return"] == pytest.approx(-10.0 / 1e4) and rec["names"] == 1  # flat AAA, bought once at 10 bp
    assert rec["spy_return"] == pytest.approx((500.0 + days.index(date(2026, 10, 21))) / 501.0 - 1.0)
    sb.save(sb.book_path(tmp_path), {**state, "record": rec})
    lines = sb.summary_lines(tmp_path)
    assert lines[0] == "## Shadow books (no orders)" and "SPY +" in lines[3]
    assert sb.summary_lines(tmp_path / "nothing") == []
