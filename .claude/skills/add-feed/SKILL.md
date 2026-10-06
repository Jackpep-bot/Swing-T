---
name: add-feed
description: Add a new live feed adapter (RSS, WebSocket, REST poll, social) to the monitor with dedup, replay and a staleness watchdog.
---
1. Read `swing_engine/core/interfaces.py` (Feed, Event) and `monitor/adapters/nasdaq_halts.py` as the simplest example.
2. Create `monitor/adapters/<name>.py` with `@register("feed", "<name>")`; produce `Event` with a stable `event_id`, `ts_source`, `ts_received`, `symbols`.
3. Respect the source's rate limit and ToS (see `docs/research-monitor.md`); add backoff on 429/403.
4. Add the feed name to `monitor.feeds` in `config/settings.yaml` (disabled by default if paid or ToS-sensitive).
5. Add a parser test with a recorded fixture under `tests/fixtures/<name>/`.
