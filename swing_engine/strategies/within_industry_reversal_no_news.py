"""Within-industry reversal of no-news losers (Da, Liu & Schaumburg 2014; Savor 2012):
docs/proposals/swing-methods-2026-10/batch6/within_industry_reversal_no_news.md.

Universe on a session: the 1,000 largest names by `mcap_pit` among the rows passed in (the replay's screened
universe) that have a two-digit SIC (`sic2`, data.b6.join_b6), a 21-session return and 252 daily returns. Industries
with fewer than 5 such members are skipped. Score = (the name's 21-session return minus the equal-weight mean
21-session return of the OTHER members of its industry) / (the sample standard deviation of its last 252 daily
returns x sqrt(21)). No score when the last 21 sessions hold an earnings reaction session (`days_since_earnings`)
or a news day: `news_flag_1d` = 1, or, on a session the news table does not cover, an 8-K reaction session
(`news_8k_flag_1d`). Names dropped for news or earnings still count in their industry's mean. Book rules and the
hold-zone deviation: `_b6.MonthEndLoserBook` (buy the 50 lowest scores at month end, keep the lowest 100,
catastrophe stop 20%).

Known gap registered with the card: `sic2` is EDGAR's current code, applied to the whole history (data.sic).
Replay-only: silent without `mcap_pit`, `sic2`, `days_since_earnings` or the two news columns.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.registry import register

from . import _b5 as b5
from . import _catalog1 as c1
from ._b6 import SINCE_EARNINGS, MonthEndLoserBook
from ._base import SYMBOL

NAME = "within_industry_reversal_no_news"
SIC2 = "sic2"  # data.b6.join_b6
NEWS, NEWS_8K = "news_flag_1d", "news_8k_flag_1d"  # data.news.join_news, data.filings.join_filings
NEEDS = (b5.MCAP, SIC2, SINCE_EARNINGS, NEWS, NEWS_8K)
WARMUP_CALENDAR_DAYS = 420  # 253 bars (~370 days), with a margin


@register("strategy", NAME)
class WithinIndustryReversalNoNews(MonthEndLoserBook):
    name = NAME
    description = "Month end: buy the 50 large caps that lagged their SIC2 industry most with no earnings or news."
    default_params: dict[str, Any] = {
        "universe_top": 1000,  # card: the 1,000 largest by mcap_pit
        "min_industry_members": 5,  # card: industries with fewer than 5 universe members are skipped
        "form_sessions": 21,  # card: 21-session return; also the news and earnings window
        "vol_sessions": 252,  # card: the stock's 252-session daily return standard deviation
        **MonthEndLoserBook.BOOK_PARAMS,
    }
    warmup_calendar_days = WARMUP_CALENDAR_DAYS

    def scores(self, panel: pd.DataFrame, as_of: date, rows: pd.DataFrame) -> pd.Series:
        out = pd.Series(np.nan, index=rows.index)
        if any(c not in panel.columns for c in NEEDS):
            return out
        p = self.params
        form, vol_n = int(p["form_sessions"]), int(p["vol_sessions"])
        member = (b5.mcap_rank(rows) <= int(p["universe_top"])) & rows[SIC2].notna()
        view = c1.view(self, panel, as_of, ["close", NEWS, NEWS_8K])
        ret, vol, quiet = out.copy(), out.copy(), pd.Series(False, index=rows.index)
        for idx in rows.index[member.fillna(False)]:
            w = view.window(str(rows.at[idx, SYMBOL]), ["close", NEWS, NEWS_8K])
            close = w["close"][-(vol_n + 1):]
            if len(close) <= vol_n or not np.isfinite(close).all():
                continue
            daily = close[1:] / close[:-1] - 1.0
            ret[idx], vol[idx] = close[-1] / close[-(form + 1)] - 1.0, float(np.std(daily, ddof=1))
            news, filed = w[NEWS][-form:], w[NEWS_8K][-form:]
            quiet[idx] = not bool(((news == 1.0) | (np.isnan(news) & (filed == 1.0))).any())
        ind = rows[SIC2].where(ret.notna())
        n, total = ret.groupby(ind).transform("count"), ret.groupby(ind).transform("sum")
        peers = ((total - ret) / (n - 1)).where(n >= int(p["min_industry_members"]))
        score = (ret - peers) / (vol.where(vol > 0) * math.sqrt(form))
        return score.where(quiet & ~(rows[SINCE_EARNINGS] < form))
