# Modelling Swing T on the "LIT Data Farm" video

Written 2026-10-13 from Jack's video (25 s TikTok by @keyzecom, caption "You can't make a trading bot with Claude").
Source checked: 25 frames at 1 fps, key frames cropped and upscaled; Swing T branch `claude/project-thread-jdz24e` at commit "STATUS: batch 3 running beside the re-run" (2026-10-10).

## Decisions for Jack (the build waits only on #1; the rest proceeds on the default)

1. **Add an intraday lane?** The video is an *intraday* engine (2-minute to 4-hour charts) on *futures*. Swing T is a *daily-bar swing* engine. Default: keep the swing engine and add an intraday lane beside it.
2. **Futures or ETF/crypto proxies?** Alpaca paper does not trade futures. Default: trade the same five markets through proxies Alpaca paper does support: MES→SPY, MNQ→QQQ, M2K→IWM, MGC→GLD, MBT→BTC/USD (Alpaca paper crypto). Real micro futures would need IBKR paper plus a paid CME data feed, which breaks the free-tier rule.
3. **Always-on host?** The video runs the bot on a cloud server ("the droplet trades, the farm watches"). The Mac sleeps on battery and has dropped long runs several times. Intraday trading cannot survive that. Default: Oracle Cloud Always Free VM (free, fits the rule; `deploy/systemd/` already exists). A paid $6/month droplet is simpler but breaks free-tier-only.
4. **The strategy style is unproven.** The engine trades ICT / "smart money concepts" (liquidity sweeps, order blocks, fair-value gaps). There is no peer-reviewed evidence these beat costs. Default: build it as pre-registered research cards under the same gates as everything else, with no exceptions.

## What the video shows

The video has no speech; the audio is a music track (loud, steady and rhythmic, with no speech gaps). Whisper could not be downloaded here to confirm. The only overlay text is the caption. Everything below is read from the screen.

**"LIT ∿ DATA FARM"**, a read-only web dashboard on localhost (`127.0.0.1`), header "read-only · the droplet trades, the farm watches". It has four tabs.

**Overview**
- Summary tiles: 98 days covered (about 2026-05 to 2026-08), 5 instruments (M2K Russell 2000 micro, MBT Bitcoin micro, MES S&P 500 micro, MGC Gold micro, MNQ Nasdaq-100 micro), 240,067 events extracted (across 25 kinds on a 2m to 4h ladder), 3,153 fires (full chain completed), 7,581 refusals (declined, with receipts), 3,125 outcomes (walked results, gross R), 4,452 ★ LIT chain fires, 98 daily studies (auto-written markdown).
- "The outcome book": the LIT chain (five steps) read beside an "m3 order-block book". The two routes are never added together.
- Coverage heatmap: instruments × days, coloured by number of events extracted. Clicking a cell opens that day's chart.
- "The tracked vocabulary": a written definition for every event kind, some carrying dated "operator rulings" (for example "operator ruling 2026-06-05"):
  - Liquidity: `pool_formed` (swing cluster resting above/below price: BSL/SSL, EQH/EQL), `pool_swept`, `sweep` (one event per physical pierce per timeframe; closed-back vs acceptance), `manip_leg` (displacement candle that takes liquidity, at least 1.5× the engine's factor), `manip_seq` (a run of candles that together take pools).
  - Structure: `mss` (market structure shift), `mss_failed`, `structure_break` (BOS/CHoCH, one event per physical break), HH/HL/LH/LL swings, `zigzag`.
  - Imbalance: `fvg_formed`, `fvg_inverted`, `ifvg_retest`.
  - Zones: order blocks `ob_confirmed`, `ob_mitigated`, `ob_invalidated`, `ob_expired`, `ob_consumed`.
  - Other: `session_open`, `rejection_2m` (the entry trigger), `inducement`.

**Chart**
- Candles per instrument and day, timeframe buttons 2m/5m/15m/30m/1h/4h, and a status line: "690 5m bars · 811 events · 7 entries · over his max-5 · sig 74889f8a". This shows a daily cap of 5 trades and a version hash stamped on the engine.
- Layer checkboxes with counts per timeframe: pools, sweeps, manipulation sequences/legs, inducements, ★★ THE TRADES (takeable), ○ setups SEEN (not taken), swing structure, structure breaks, MSS/failed, OB zones, FVG/inversions, session opens, 2m rejections. There are "declutter" and "everything" presets.
- An Inspector panel: clicking any drawn object shows its full event JSON (its "receipt").

**Studies**
- One auto-written study per day ("Farm study — 2026-05-29"), noting "R values are GROSS R-multiples (no fees, no sizing). engine_sig 74889f8a".
- Per instrument: a count of each event kind (for example M2K: 17 fires, 39 refusals, 22 MSS, 117 structure breaks).
- "★ LIT fires (16) — chain lineage": one line per trade showing the chain that produced it, for example `04:30Z M2K 15m m3_ob long — sweep non-structural → MSS@15m lvl 2932.8 disp 1.57 held → OB zone 2932.7–2936.4 → entry 2937.8 sl 2931.75 tp 2948.7 (rng 128%/95%)`.

**Events**: a raw event browser (the tab is not opened in the video).

### What the video does *not* show

It shows no P&L, equity curve, win rate, net returns or live orders. The only performance number is gross R with no fees and no sizing. **There is no return claim to test.** Swing T's daily-bar evidence cannot say anything about this intraday style. The intraday lane in P1 is what would test it.

## How Swing T compares

| Video feature | Swing T today | Gap |
|---|---|---|
| Executor separate from read-only observer | One Mac runs everything; dashboard reads the same stores | No always-on host; no executor/observer split |
| Every fire **and refusal** logged with receipts | Shadow ledger logs signals taken/not taken; autopilot records REFUSED with a reason string | Refusals are not a first-class, queryable event with the failed step and inputs |
| Engine version hash on every event | None found (`git_sha`/engine signature absent) | Add an engine signature (git sha + config hash) |
| Deterministic event vocabulary with written definitions | ~220 indicators (`features/extra.py`), levels, patterns | No market-structure event layer (sweeps, BOS/MSS, FVG, OB lifecycle) |
| Chart with toggleable layers + click-for-JSON | Charts tab (daily candles) | No signal/stop/target/level overlays, no inspector |
| Auto-written daily study | Nightly Telegram summary, weekly report | No per-day markdown study with chain lineage |
| Coverage heatmap | Doctor checks data health | No visual coverage grid |
| 2m–4h intraday on 5 markets | Daily bars only, US stocks | No intraday data, replay or execution |
| Daily trade cap, structured stop/target | Risk module has caps, stops, Turtle units | Fine; carry over to intraday |
| (not shown) net-of-cost grading, deflated Sharpe, survivorship-free replays, gates | **Swing T is ahead here** | Keep these; the video's farm grades gross only |

## Build plan, in priority order

Every item follows the standing rules: paper only, free data, point-in-time, no LLM numbers reaching an order, gates before paper.

### P0: farm features on the existing swing engine (no decision needed)
1. **Decision receipts.** Add an append-only `events` table that every run writes: `fire`, `refusal` (which gate/step failed, the inputs), `outcome`, each stamped with `engine_sig` = git sha + config hash. Backfill from the shadow ledger. This is the base the other items read from.
2. **Chart inspector.** The Charts tab gets layer toggles (signals taken/seen, entries, stops, targets, exits, `features/levels.py` support/resistance, regime shading) and a side panel showing the clicked object's receipt JSON.
3. **Daily auto-study.** The nightly job writes `docs/studies/YYYY-MM-DD.md`: counts per strategy, fires with their reasoning chain, refusals by reason, outcomes in gross **and net** R. Add a Studies tab and link the study from Telegram.
4. **Coverage heatmap + vocabulary page.** An Overview grid of symbols/strategies × days (bars present, events, fires), plus a generated page listing every strategy/feature with its definition and any dated operator rulings.

### P1: the intraday lane (needs decision #1, default yes)
5. **Intraday data.** Ingest Alpaca free historical minute bars for SPY, QQQ, IWM, GLD (2016→) and BTC/USD crypto bars. Resample to 2m/5m/15m/30m/1h/4h and store in `data/live/intraday.duckdb` with a session calendar. Before building, verify on the Mac how far back the free plan serves SIP minute bars. If it falls short, use the IEX feed and record the bias.
6. **Market-structure event extractor.** A deterministic, versioned module that emits the video's vocabulary per timeframe: zigzag swings, HH/HL/LH/LL, BOS/CHoCH/MSS (+failed), liquidity pools (EQH/EQL, prior day/session highs and lows), sweeps (closed-back vs acceptance), displacement legs, FVG formed/inverted/retest, order-block lifecycle, session opens. Each event is dated when it becomes *confirmable*, never when its pivot happened. It needs a no-look-ahead test like `tests/test_strategies_all.py` and a definitions doc.
7. **Pre-registered chain cards.** Write 2–3 cards *before* any replay, for example: sweep of a pool → MSS with displacement ≥ factor → retrace into the OB/FVG → lower-timeframe rejection entry, stop beyond the sweep extreme, target the opposing pool, max 5 trades/day, flat by the close (ETFs). Every chain that stops at a step logs a refusal naming the step.
8. **Intraday replay and grader.** Simulate bar by bar with next-bar fills, stop-before-target inside a bar, and modelled costs (ETF spread + slippage; Alpaca crypto taker fee). Report gross and net R, MFE/MAE and by-regime results. Add trials to the same trial log so deflated Sharpe counts them. Use two windows (2016–23, 2024–26) plus walk-forward.
9. **Intraday chart.** Add 2m–4h buttons and the event layers from item 6 to the Chart tab, with the inspector.

### P2: always-on execution (needs decision #3)
10. **Executor host.** Move the nightly and an intraday executor to an always-on host (default: Oracle Always Free VM using `deploy/systemd/`). The Mac becomes the research box and observer. Secrets live in the host's `.env`, never in git.
11. **Intraday paper executor.** Alpaca paper bracket orders for ETFs and crypto, a daily trade cap, a daily loss stop, a kill-switch file, flatten before the close, and a heartbeat to Telegram. It runs every strategy shadow-only, and only strategies that pass `docs/gates.md` trade on paper.
12. **Executor/observer split.** The executor writes events; the dashboard opens stores read-only, as in the video's "read-only" badge. Add a live-vs-replay drift check for the intraday lane.
13. **Telegram per-fire alerts** carrying the chain lineage line, plus the end-of-day study.

### P3: optional, each needs Jack's word
14. Real micro futures (IBKR paper + paid CME data).
15. LLM-written prose for the daily study. Allowed as text only: every number comes from code, and nothing it writes reaches an order. `agent.llm_enabled` stays false until Jack says otherwise.

## Expectations, plainly
- P0 gives Swing T the video's transparency (receipts, chart inspector, daily studies) without new data or risk.
- P1 is what actually tests whether a video-style intraday engine has an edge. Based on what Swing T has found so far (no daily strategy survives costs, and most apparent edge is market beta), expect most chain variants to fail net of costs. The gates decide, not the dashboard.
- The video itself is a research/observation tool. It does not show a profitable bot.
