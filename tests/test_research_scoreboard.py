import pytest

from swing_engine.research import scoreboard as sc

ENGINE = """| strategy | window | trades | net R/trade | t | net Sharpe | haircut SR | DSR | max DD | hold days | top-7% P&L share | return |
|---|---|---|---|---|---|---|---|---|---|---|---|
| alpha_card | 2024 | 52 | -0.181 | -0.84 | -0.33 | -0.33 | 0.16 | 12.8% | 93 | -155% | -7.8% |

| strategy | window | excess / yr | IR | haircut IR | alpha / yr | alpha t | beta | exposure | net Sharpe | SPY Sharpe | turnover / yr |
|---|---|---|---|---|---|---|---|---|---|---|---|
| alpha_card | 2024 | -20.6% | -1.39 | -1.39 | -8.8% | -1.31 | 0.31 | 63% | -0.33 | 1.03 | 158% |

## Verdicts
- **alpha_card**: FAIL
"""
WEIGHTS = """## `book_card`: FAIL

| window | from | book | return/yr | deepest drop | worst month | months up | Sharpe | haircut SR | alpha/yr | alpha t | beta | turnover/yr | costs/yr |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B | 2024-10-07 | book | +27.0% | -18.8% | -12.5% | 80% | 1.12 | 0.5 | +7.1% | 0.73 | 1.19 | 246% | 0.72% |
| B | 2024-10-07 | SPY | +16.4% | -19.0% | -5.9% | 60% | 1.00 | | | | | |
| pooled | 2017-01-03 | book | +8.1% | -42.6% | -21.7% | 60% | 0.48 | 0.35 | -5.0% | -1.68 | 1.04 | 1052% | 3.28% |
"""


def test_engine_and_weights_tables_parse_into_one_row_per_card_window():
    e = sc.parse_engine(ENGINE, "x.md")[0]
    assert e["window"] == "2024-26" and e["alpha_t"] == pytest.approx(-1.31) and e["hold_days"] == 93.0
    assert e["exposure"] == pytest.approx(0.63) and e["turnover"] == pytest.approx(1.58) and e["max_dd"] == pytest.approx(0.128)
    w = sc.parse_weights(WEIGHTS, "y.md")
    assert [(r["card"], r["window"]) for r in w] == [("book_card", "2024-26"), ("book_card", "2017-26")]
    assert w[0]["excess_ann"] == pytest.approx(0.27 - 0.164) and w[0]["max_dd"] == pytest.approx(0.188)
    assert sc._verdicts(ENGINE) == {"alpha_card": "FAIL"}
