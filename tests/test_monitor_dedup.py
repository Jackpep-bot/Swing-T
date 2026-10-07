from __future__ import annotations

from datetime import timedelta

from swing_engine.monitor.dedup import Deduper, hamming, normalize_title, simhash
from tests.monitor_helpers import T0, make_event


def test_normalize_strips_noise_prefix_and_case():
    assert normalize_title("UPDATE 2: Acme & Co Beats Q3!") == "acme and co beats q3"
    assert normalize_title("BREAKING - Acme beats") == "acme beats"


def test_simhash_near_duplicates_are_close():
    a = simhash(normalize_title("Acme Reports Record Q3 Revenue Of $90B, Beats Estimates"))
    b = simhash(normalize_title("UPDATE: Acme reports record Q3 revenue of $90B beats estimates"))
    c = simhash(normalize_title("Acme announces new CFO after surprise resignation"))
    assert hamming(a, b) <= 3
    assert hamming(a, c) > 3


def test_provider_id_then_simhash_within_window():
    d = Deduper(window_min=30)
    e1 = make_event("p1", symbols=["ACME"], title="Acme Reports Record Q3 Revenue Of $90B, Beats Estimates")
    e2 = make_event("p2", source="edgar", symbols=["ACME"], title="Acme reports record Q3 revenue of $90B beats estimates")
    e3 = make_event("p3", symbols=["ACME"], title="Acme announces new CFO after surprise resignation")
    assert d.check(e1) is None
    assert d.check(e1).startswith("duplicate_id")
    assert d.check(e2).startswith("near_duplicate:p1")
    assert d.check(e3) is None
    assert d.is_duplicate(e3)


def test_same_title_different_ticker_is_not_a_duplicate():
    d = Deduper()
    assert d.check(make_event("a", symbols=["AAA"], title="Prices $20M Registered Direct Offering")) is None
    assert d.check(make_event("b", symbols=["BBB"], title="Prices $20M Registered Direct Offering")) is None


def test_reprint_tagged_with_a_different_symbol_set_is_a_duplicate():
    d = Deduper()
    title = "Acme Corp to acquire Zeta Inc in $2 billion all-cash deal"
    assert d.check(make_event("a", symbols=["ACME", "ZETA"], title=title)) is None
    assert d.check(make_event("b", source="edgar", symbols=["ZETA"], title=title)).startswith("near_duplicate:a")
    assert d.check(make_event("c", symbols=["OTHR"], title=title)) is None  # unrelated name, same boilerplate
    assert d.check(make_event("u1", symbols=[], title="Fed holds rates steady")) is None
    assert d.check(make_event("u2", symbols=[], title="UPDATE: Fed holds rates steady")).startswith("near_duplicate:u1")


def test_window_expiry():
    d = Deduper(window_min=30)
    e1 = make_event("p1", symbols=["ACME"], title="Acme beats estimates and raises guidance")
    assert d.check(e1) is None
    later = make_event("p9", symbols=["ACME"], title="Acme beats estimates and raises guidance", received=T0 + timedelta(minutes=31))
    assert d.check(later) is None
    assert len(d) == 1
