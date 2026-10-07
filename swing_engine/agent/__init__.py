"""Claude layer: candidate review, daily journal and the strategy lab.

Hard rule: the model only returns enums and short text. Every schema sent to it is checked by
`client.assert_no_numeric_fields`; prices, sizes, stops and targets live on deterministic objects.
"""
from .client import get_async_client, get_client, model_for
from .journal import write_entry
from .review import review_candidates, review_candidates_async
from .strategy_lab import run as run_lab

__all__ = [
    "get_async_client",
    "get_client",
    "model_for",
    "review_candidates",
    "review_candidates_async",
    "run_lab",
    "write_entry",
]
