"""Stage-1 deterministic rules. Each module registers one Rule via `@register("rule", name)`.

Rule contract (core.interfaces.Rule): `evaluate(event, ctx) -> (hit_name, priority) | None`, < 1 ms, no I/O.
`ctx` keys used: held (set), watchlist (set), now (UTC datetime), settings (MonitorConfig | None),
market_suppressed (bool), form4_history (dict), news_tagged (dict symbol -> UTC datetime).
Rules may annotate `event.meta` with what they parsed; they never change symbols or priority directly.
"""
