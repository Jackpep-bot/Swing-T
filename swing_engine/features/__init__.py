"""Feature engineering: indicators, cross-sectional features, levels, patterns, regime and the RVOL profile.

Entry point: :func:`swing_engine.features.panel.build_panel`. Every column is defined in
``docs/feature-contract.md`` and computed per symbol with only past data.
"""

from __future__ import annotations

from .panel import FEATURE_COLUMNS, build_panel

__all__ = ["FEATURE_COLUMNS", "build_panel"]
