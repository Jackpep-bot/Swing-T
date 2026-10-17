# Intraday lane, round 2: results

Graded per `docs/preregistration/2026-10-13-intraday-round2.md`. One run. Haircut over n_trials = 4103 (4099 logged before this group + 4). Costs 1 bp of traded notional per side. Returns are per unit of sleeve, equal weight over SPY, QQQ, IWM; no leverage, no compounding.

## Verdict

**Nothing passes.** No card meets the pre-registered rule.

| card | verdict | 1. mean daily net return A / B, bp (> 0) | 2. haircut Sharpe A / B (> 0) | 3. symbols with net return > 0 in B (>= 2) |
|---|---|---|---|---|
| `noise_area_momentum` | **FAIL** | +0.84 / -1.09 (no) | +0.00 / -0.46 (no) | 1 of 3 (no) |
| `first_half_hour_momentum` | **FAIL** | -2.44 / -2.02 (no) | -1.25 / -1.61 (no) | 0 of 3 (no) |

## Per card and window

Daily figures are the equal-weight card. `Sharpe at 0.1 bp` is the same run at the paper's cost, descriptive only. Alpha and beta are against SPY's close-to-close return.

| card | window | trades | hit ratio | gross bp / trade | net bp / trade | mean daily net bp | net return / yr | vol / yr | Sharpe | haircut Sharpe | max drawdown | alpha / yr | alpha t | beta | Sharpe at 0.1 bp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `noise_area_momentum` | A 2016-01..2023-12 | 5433 | 36.3% | +2.94 | +0.94 | +0.84 | +2.1% | 6.7% | +0.32 | +0.00 | 17.0% | +2.4% | +1.00 | -0.02 | +0.93 |
| `noise_area_momentum` | B 2024-01..2026-10 | 1834 | 36.1% | +0.76 | -1.24 | -1.09 | -2.7% | 6.0% | -0.46 | -0.46 | 12.4% | -3.4% | -0.94 | +0.03 | +0.21 |
| `first_half_hour_momentum` | A 2016-01..2023-12 | 5976 | 44.8% | -0.47 | -2.47 | -2.44 | -6.2% | 4.9% | -1.25 | -1.25 | 51.2% | -6.3% | -3.59 | +0.01 | -0.34 |
| `first_half_hour_momentum` | B 2024-01..2026-10 | 2066 | 45.2% | -0.04 | -2.04 | -2.02 | -5.1% | 3.2% | -1.61 | -1.61 | 16.4% | -5.2% | -2.75 | +0.01 | -0.19 |

## By symbol

Mean daily net return in bp of the symbol's own sleeve. Rule 3 reads window B.

| card | window | SPY | QQQ | IWM |
|---|---|---|---|---|
| `noise_area_momentum` | A 2016-01..2023-12 | +1.14 | +3.40 | -2.01 |
| `noise_area_momentum` | B 2024-01..2026-10 | -1.16 | +2.88 | -4.98 |
| `first_half_hour_momentum` | A 2016-01..2023-12 | -2.28 | -1.99 | -3.05 |
| `first_half_hour_momentum` | B 2024-01..2026-10 | -2.07 | -1.81 | -2.19 |

## By year and by direction

Descriptive only. Net bp per trade at the registered cost.

| card | year | trades | net bp / trade |
|---|---|---|---|
| `first_half_hour_momentum` | 2016 | 747 | -1.39 |
| `first_half_hour_momentum` | 2017 | 746 | -2.26 |
| `first_half_hour_momentum` | 2018 | 742 | -1.32 |
| `first_half_hour_momentum` | 2019 | 746 | -2.23 |
| `first_half_hour_momentum` | 2020 | 752 | +0.63 |
| `first_half_hour_momentum` | 2021 | 751 | -6.00 |
| `first_half_hour_momentum` | 2022 | 750 | -5.68 |
| `first_half_hour_momentum` | 2023 | 742 | -1.47 |
| `first_half_hour_momentum` | 2024 | 746 | -2.26 |
| `first_half_hour_momentum` | 2025 | 740 | -2.61 |
| `first_half_hour_momentum` | 2026 | 583 | -1.04 |
| `noise_area_momentum` | 2016 | 674 | -1.08 |
| `noise_area_momentum` | 2017 | 664 | -0.82 |
| `noise_area_momentum` | 2018 | 703 | +8.52 |
| `noise_area_momentum` | 2019 | 623 | -0.38 |
| `noise_area_momentum` | 2020 | 647 | -5.98 |
| `noise_area_momentum` | 2021 | 668 | +1.85 |
| `noise_area_momentum` | 2022 | 777 | +1.83 |
| `noise_area_momentum` | 2023 | 677 | +2.67 |
| `noise_area_momentum` | 2024 | 669 | -0.43 |
| `noise_area_momentum` | 2025 | 646 | -0.84 |
| `noise_area_momentum` | 2026 | 521 | -2.81 |

| card | direction | trades | net bp / trade |
|---|---|---|---|
| `first_half_hour_momentum` | long | 4399 | -2.79 |
| `first_half_hour_momentum` | short | 3646 | -1.84 |
| `noise_area_momentum` | long | 3739 | +0.69 |
| `noise_area_momentum` | short | 3530 | +0.06 |

## How the spec was read

Each point is a choice the spec left open, fixed in code before the run.

1. Minutes are counted from the session open in the NYSE calendar. A check at minute k reads the close of the last bar that started before k; the fill is the open of the bar that starts at k, or of the next bar that exists when that minute has no trade.
2. sigma for a check time is the plain mean of |P / Open - 1| over the 14 most recent earlier sessions of the same symbol that reached that check time and were not skipped. With fewer than 14 the target position is 0.
3. A skipped symbol-day (first regular bar after 09:31, or no previous session) trades nothing and adds nothing to sigma; its last close is still the next day's previous close.
4. VWAP uses (high + low + close) / 3 x volume of the regular bars that started before the check minute.
5. Card 1 holds a position only while the half-hourly check keeps it: +1 above max(UB, VWAP), -1 below min(LB, VWAP), flat otherwise. A flip is two trades at the same fill price.
6. Card 2 needs a full 390-minute session; r1 uses the close of the last bar before 10:00.
7. The session close fill is the close of the day's last regular bar.
8. Cost per trade = 2 x the per-side rate (entry and exit), in return units; a symbol's daily net return is the sum of its trades' side x (exit / entry - 1) minus their costs.
9. The card's daily return is the mean of the three symbols' daily net returns over every NYSE session of the window (0 for a symbol with no trade). Sharpe = mean / s.d. x sqrt(252); the haircut uses the window's length in calendar years.
10. Max drawdown is on the cumulative sum of daily returns (no compounding, as the returns are per unit sleeve).
11. Alpha and beta: OLS of the card's daily net return on SPY's close-to-close return from the regular-hours minutes, over the window's sessions.

## Notes (written after the run; nothing was re-run)

- `noise_area_momentum` reproduces the paper's size of edge before costs in window A (+2.9 bp a trade gross; the
  paper's $0.09 a share on SPY is 3 to 4 bp) and a Sharpe of 0.93 at the paper's 0.1 bp cost. At this engine's 1 bp a
  side the edge is +0.9 bp a trade and the haircut takes the Sharpe to zero.
- Window B is almost all after the paper's May 2024 publication: gross edge +0.8 bp a trade, negative after costs,
  Sharpe 0.21 even at the paper's cost. QQQ is positive in both windows, SPY and IWM are not in B; one symbol out of
  three is what chance looks like, and per-symbol rows cannot rescue a card.
- This run trades about 0.9 times a day per symbol; the paper reports 7,668 trades in about 4,300 sessions (1.8 a
  day). The registered reading checks stops only on the half hour. If the paper's improved version checks them
  every minute it would trade more often and pay more cost. That would be a new card and new trials, not a re-run.
- `first_half_hour_momentum` has no gross edge at all in 2016-2026 (-0.5 and -0.0 bp a trade): the 1993-2013 result
  did not carry into this sample.
