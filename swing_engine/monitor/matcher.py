"""Aho-Corasick symbol/alias/keyword matcher with the word-like-ticker guard.

Tickers are matched case-sensitively as whole words. A ticker that is also an English word (or <= 2 chars) only counts
when it appears as a cashtag ($ON), with an exchange qualifier ("NASDAQ: ON"), or with a company alias within
`ALIAS_PROXIMITY_CHARS` of the hit. Aliases and keywords are matched case-insensitively.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

import ahocorasick_rs as ac

from .constants import ALIAS_PROXIMITY_CHARS, EXCHANGE_QUALIFIERS, SHORT_TICKER_MAX_LEN, WORD_LIKE_TICKERS

_WORD_CHARS = re.compile(r"[A-Za-z0-9]")
_QUALIFIER_RE = re.compile(
    r"\b(" + "|".join(re.escape(q) for q in EXCHANGE_QUALIFIERS) + r")\s*[:\-]?\s*$", re.IGNORECASE
)


@dataclass
class MatchResult:
    symbols: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    guarded_out: list[str] = field(default_factory=list)  # word-like tickers seen but rejected by the guard

    def as_tuple(self) -> tuple[list[str], list[str]]:
        return self.symbols, self.keywords


def _is_boundary(text: str, start: int, end: int) -> bool:
    before = text[start - 1] if start > 0 else " "
    after = text[end] if end < len(text) else " "
    return not _WORD_CHARS.match(before) and not _WORD_CHARS.match(after)


class Matcher:
    def __init__(
        self,
        tickers: Iterable[str],
        aliases: Mapping[str, Iterable[str]] | None = None,
        keywords: Iterable[str] | None = None,
        word_like: Iterable[str] | None = None,
    ):
        self.tickers = sorted({t.upper().strip() for t in tickers if t and t.strip()})
        self.aliases: dict[str, list[str]] = {
            k.upper(): [a.lower().strip() for a in v if a and a.strip()] for k, v in (aliases or {}).items()
        }
        self.keywords = sorted({k.lower().strip() for k in (keywords or []) if k and k.strip()})
        base_word_like = set(WORD_LIKE_TICKERS) if word_like is None else {w.upper() for w in word_like}
        self.word_like = {t for t in self.tickers if t in base_word_like or len(t) <= SHORT_TICKER_MAX_LEN}
        self._ticker_ac = ac.AhoCorasick(self.tickers, matchkind=ac.MatchKind.LeftmostLongest) if self.tickers else None
        self._alias_patterns: list[str] = []
        self._alias_owner: list[tuple[str, str]] = []  # (kind, symbol-or-keyword)
        for sym, names in self.aliases.items():
            for n in names:
                self._alias_patterns.append(n)
                self._alias_owner.append(("alias", sym))
        for kw in self.keywords:
            self._alias_patterns.append(kw)
            self._alias_owner.append(("keyword", kw))
        self._alias_ac = (
            ac.AhoCorasick(self._alias_patterns, matchkind=ac.MatchKind.LeftmostLongest) if self._alias_patterns else None
        )

    # ---------------------------------------------------------------------------------------------------------
    def match(self, text: str) -> tuple[list[str], list[str]]:
        return self.match_detail(text).as_tuple()

    def match_detail(self, text: str) -> MatchResult:
        res = MatchResult()
        if not text:
            return res
        lowered = text.lower()
        alias_hits: dict[str, list[tuple[int, int]]] = {}
        keyword_hits: set[str] = set()
        if self._alias_ac is not None:
            for idx, start, end in self._alias_ac.find_matches_as_indexes(lowered):
                if not _is_boundary(lowered, start, end):
                    continue
                kind, owner = self._alias_owner[idx]
                if kind == "alias":
                    alias_hits.setdefault(owner, []).append((start, end))
                else:
                    keyword_hits.add(owner)
        symbols: set[str] = set(alias_hits)
        if self._ticker_ac is not None:
            for idx, start, end in self._ticker_ac.find_matches_as_indexes(text):
                sym = self.tickers[idx]
                if not self._ticker_boundary(text, start, end):
                    continue
                if sym in self.word_like and not self._guard_ok(text, sym, start, end, alias_hits.get(sym, [])):
                    res.guarded_out.append(sym)
                    continue
                symbols.add(sym)
        res.symbols = sorted(symbols)
        res.keywords = sorted(keyword_hits)
        res.guarded_out = sorted(set(res.guarded_out) - symbols)
        return res

    # ---------------------------------------------------------------------------------------------------------
    @staticmethod
    def _ticker_boundary(text: str, start: int, end: int) -> bool:
        before = text[start - 1] if start > 0 else " "
        if before == "$":
            return end >= len(text) or not _WORD_CHARS.match(text[end])
        return _is_boundary(text, start, end)

    def _guard_ok(self, text: str, sym: str, start: int, end: int, alias_spans: list[tuple[int, int]]) -> bool:
        if start > 0 and text[start - 1] == "$":
            return True
        prefix = text[max(0, start - 24) : start]
        if _QUALIFIER_RE.search(prefix.rstrip("( ")) or _QUALIFIER_RE.search(prefix):
            return True
        for a_start, a_end in alias_spans:
            if min(abs(a_start - end), abs(start - a_end)) <= ALIAS_PROXIMITY_CHARS:
                return True
        return False
