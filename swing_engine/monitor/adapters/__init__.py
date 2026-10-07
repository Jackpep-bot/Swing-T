"""Feed adapters register with `@register("feed", name)`. Each yields normalized core.models.Event objects.

Parsing is split into pure `parse_*` functions (tested on fixtures) and thin async loops with reconnect/backoff.
"""
