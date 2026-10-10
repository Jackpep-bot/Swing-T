---
name: add-feed
description: Add a live feed adapter (RSS, REST poll, WebSocket) to the monitor with stable event ids, source timestamps, backoff, a staleness threshold and a recorded-fixture test.
---
## Read first
`docs/research-monitor.md` (vendor limits, ToS, alert policy); `swing_engine/core/interfaces.py` (Feed) and
`core/models.py` (Event); `swing_engine/monitor/adapters/_base.py` (`PollingFeed`, `ReconnectingFeed`, `stable_id`,
`now_utc`); `monitor/adapters/nasdaq_halts.py` (the simplest polling feed); `build_feeds` in `monitor/service.py`.

## Steps
1. Create `swing_engine/monitor/adapters/<name>.py` with `SOURCE = "<name>"` and `@register("feed", SOURCE)`.
   - Polling: subclass `PollingFeed` and implement `async _poll() -> list[Event]`. It already dedups ids, never polls
     faster than `interval_s`, honours `Retry-After` on 429/503, and waits `forbidden_retry_s` after a 403.
   - Streaming: subclass `WebSocketFeed` (or `ReconnectingFeed`) for a jittered-backoff reconnect loop; see
     `alpaca_news.py`.
   Keep parsing in pure functions (`parse_*`, `row_to_event`) so tests need no network.
2. Event fields:
   - `event_id = stable_id(SOURCE, <natural key>, <status>)`, the same on every poll.
   - `ts_source`: the publisher's timestamp, tz-aware. A filing uses its acceptance or filing time, never the
     transaction date.
   - `ts_received = now_utc()`, plus `kind`, `symbols` (upper case), `title` and `meta`.
3. Put the URL, cadence and any limits in `monitor/constants.py`. Add `STALENESS_THRESHOLD_S["<name>"]`, plus
   `STALENESS_WINDOW_ET` if the source is only live in some hours, so the watchdog judges it correctly.
4. `build_feeds` calls `cls()` for an unknown name. If the feed needs credentials or settings, add a branch there.
   Credentials come from `Secrets` (`.env`); never write keys from a Claude session.
5. Config: add the name to `monitor.feeds` in `config/settings.yaml` only if it is free and its ToS allows automated
   use. Otherwise leave it out and say why. Paid sources are proposals for Jack, not config.
6. Tests: record a real response into `tests/fixtures/monitor/<name>.<ext>`. Add tests to
   `tests/test_monitor_adapters.py`: parse, ids stable across two snapshots, only new or changed items emit, and
   `ts_source` correct. Add the name to the registry assertion near the top of that file.
   Run `uv run pytest -q tests/test_monitor_adapters.py tests/test_monitor_service.py`, then `uv run pytest -q` and
   `uv run ruff check .`.

Note: `swing monitor run --dry-run` replays the event file only and ignores `--feeds`, so it does not exercise a new
adapter. The fixture tests are the check.
