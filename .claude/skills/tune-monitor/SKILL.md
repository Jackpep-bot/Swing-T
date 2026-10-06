---
name: tune-monitor
description: Review the last N days of monitor alerts and user ratings, compute precision per rule and source, and propose threshold changes to settings.yaml.
---
1. `uv run swing monitor report --days 7` prints alerts per rule/source, duplicate rate, per-source latency, and useful/noise ratings.
2. Propose changes as a diff to `config/settings.yaml` and `monitor/rules/*.py` constants; never change a threshold without showing the before/after alert counts from a replay (`uv run swing monitor replay --days 7`).
3. Rules with zero acted-on P2+ alerts over 14 days get demoted to P1 (digest) by default.
