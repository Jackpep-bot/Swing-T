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


def test_realized_gains_split_short_and_long_term():
    from datetime import date

    import pandas as pd
    import pytest

    from swing_engine.ops import shadow_books as sb

    days = [date(2024, 1, 2), date(2024, 6, 3), date(2025, 6, 2)]
    opens = pd.DataFrame({"A": [10.0, 20.0, 40.0], "B": [10.0, 10.0, 10.0]}, index=days)
    plan = {days[0]: pd.Series({"A": 1.0}), days[1]: pd.Series({"A": 0.5, "B": 0.5}), days[2]: pd.Series({"B": 1.0})}
    g = sb.realized_gains(plan, opens, opens)
    # day 1: $1 buys 0.1 A at 10, worth $2; half sold (0.05 A, +0.5 short-term); day 2: rest sold +1.5 long-term
    assert g["short_term"] == pytest.approx(0.5) and g["long_term"] == pytest.approx(1.5)
    assert g["unrealized"] == pytest.approx(0.0)
    assert g["tax"] == pytest.approx(0.5 * sb.TAX_SHORT_TERM + 1.5 * sb.TAX_LONG_TERM)
