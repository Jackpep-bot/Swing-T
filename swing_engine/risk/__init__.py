"""Risk layer: deterministic sizing, portfolio limits and the kill switch. No LLM output enters here."""
from swing_engine.risk.killswitch import is_tripped, reset, trip
from swing_engine.risk.limits import LimitState
from swing_engine.risk.sizing import size_signal, size_signal_detail

__all__ = ["LimitState", "is_tripped", "reset", "size_signal", "size_signal_detail", "trip"]
