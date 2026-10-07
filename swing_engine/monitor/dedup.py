"""Two-stage dedup: exact provider id, then SimHash of the normalized title compared against every recent event
whose symbol set intersects (or, for untagged events, every recent untagged event) within a window.

Cross-source reprints (Benzinga vs. PR wire vs. EDGAR title) get collapsed even when the feeds tag a different
primary ticker (a merger tagged [ACME, ZETA] by one and [ZETA] by the other); genuinely different headlines on
the same ticker survive because the hamming threshold is tight, and the same boilerplate on two unrelated names
is not a duplicate because their symbol sets do not intersect.
"""
from __future__ import annotations

import hashlib
import re
from collections import OrderedDict
from datetime import datetime, timedelta

from swing_engine.core.models import Event

from .constants import DEDUP_WINDOW_MIN, SIMHASH_BITS, SIMHASH_MAX_HAMMING, SIMHASH_SHINGLE

_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
_WS = re.compile(r"\s+")
_NOISE_PREFIX = re.compile(
    r"^(update(d)?\s*\d*\s*[:\-]\s*|breaking\s*[:\-]\s*|exclusive\s*[:\-]\s*|press release\s*[:\-]\s*)", re.I
)


def normalize_title(title: str) -> str:
    t = _NOISE_PREFIX.sub("", title.strip())
    t = t.lower().replace("&", " and ")
    t = _NON_ALNUM.sub(" ", t)
    return _WS.sub(" ", t).strip()


def _shingles(text: str, k: int = SIMHASH_SHINGLE) -> list[str]:
    toks = text.split()
    if len(toks) <= k:
        return [" ".join(toks)] if toks else []
    return [" ".join(toks[i : i + k]) for i in range(len(toks) - k + 1)]


def simhash(text: str, bits: int = SIMHASH_BITS) -> int:
    v = [0] * bits
    for sh in _shingles(text):
        h = int.from_bytes(hashlib.blake2b(sh.encode(), digest_size=bits // 8).digest(), "big")
        for i in range(bits):
            v[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i in range(bits):
        if v[i] > 0:
            out |= 1 << i
    return out


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


class Deduper:
    """In-memory dedup state. `check(event)` returns None when the event is new, else a reason string."""

    def __init__(self, window_min: int = DEDUP_WINDOW_MIN, max_hamming: int = SIMHASH_MAX_HAMMING):
        self.window = timedelta(minutes=window_min)
        self.max_hamming = max_hamming
        self._ids: OrderedDict[str, datetime] = OrderedDict()
        # event_id -> (title hash, ts, symbol set); matched against events whose symbols intersect
        self._hashes: OrderedDict[str, tuple[int, datetime, frozenset[str]]] = OrderedDict()

    @staticmethod
    def fingerprint(event: Event) -> tuple[frozenset[str], int]:
        symbols = frozenset(s.upper() for s in event.symbols if s)
        return symbols, simhash(normalize_title(event.title))

    def check(self, event: Event) -> str | None:
        now = event.ts_received
        self._prune(now)
        if event.event_id in self._ids:
            return f"duplicate_id:{event.event_id}"
        symbols, h = self.fingerprint(event)
        if event.title.strip():
            for eid, (h2, _ts, symbols2) in self._hashes.items():
                related = bool(symbols & symbols2) if (symbols or symbols2) else True
                if related and hamming(h, h2) <= self.max_hamming:
                    return f"near_duplicate:{eid}"
        self._ids[event.event_id] = now
        self._hashes[event.event_id] = (h, now, symbols)
        return None

    def is_duplicate(self, event: Event) -> bool:
        return self.check(event) is not None

    def _prune(self, now: datetime) -> None:
        cutoff = now - self.window
        for store in (self._ids, self._hashes):
            while store:
                k, v = next(iter(store.items()))
                ts = v if isinstance(v, datetime) else v[1]
                if ts < cutoff:
                    store.popitem(last=False)
                else:
                    break

    def __len__(self) -> int:
        return len(self._ids)
