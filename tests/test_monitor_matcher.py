from __future__ import annotations

from swing_engine.monitor.matcher import Matcher


def make():
    return Matcher(
        tickers=["AAPL", "ON", "IT", "NVDA", "A", "ACME"],
        aliases={"ON": ["ON Semiconductor", "onsemi"], "AAPL": ["Apple"], "ACME": ["Acme Corp"]},
        keywords=["FDA approval", "offering", "going concern"],
    )


def test_plain_ticker_and_keywords():
    syms, kws = make().match("NVDA rallies after the FDA approval headline; offering talk fades")
    assert syms == ["NVDA"] and kws == ["fda approval", "offering"]


def test_word_like_ticker_requires_guard():
    m = make()
    assert m.match("Turn ON the lights, IT works")[0] == []
    assert m.match("$ON breaks out")[0] == ["ON"]
    assert m.match("ON Semiconductor (NASDAQ: ON) rose 5%")[0] == ["ON"]
    assert m.match("Shares of onsemi jumped; ON closed higher")[0] == ["ON"]
    detail = m.match_detail("A new era: IT departments spend")
    assert detail.symbols == [] and set(detail.guarded_out) == {"A", "IT"}


def test_alias_must_be_within_proximity():
    m = make()
    far = "ON Semiconductor said " + "x " * 60 + "the switch was left ON overnight"
    assert m.match(far)[0] == ["ON"]  # alias hit alone maps to ON regardless of the ticker guard
    m2 = Matcher(tickers=["ON"], aliases={}, keywords=[])
    assert m2.match("the switch was left ON overnight")[0] == []


def test_boundaries_and_case():
    m = make()
    assert m.match("AAPLX is not AAPL; aapl lower-case is ignored")[0] == ["AAPL"]
    assert m.match("Apple announces results")[0] == ["AAPL"]  # alias, case-insensitive
    assert m.match("")[0] == []


def test_empty_matcher():
    m = Matcher(tickers=[], aliases={}, keywords=[])
    assert m.match("anything") == ([], [])
