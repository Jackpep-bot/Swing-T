"""settings files can extend a base file so overrides never drift."""
from pathlib import Path

import pytest

from swing_engine.core.config import load_settings


def test_extends_layers_overrides_on_the_base(tmp_path: Path) -> None:
    (tmp_path / "base.yaml").write_text("data:\n  store_path: data/a.duckdb\n  history_years: 3\nrisk:\n  risk_per_trade_pct: 0.5\n")
    (tmp_path / "live.yaml").write_text("extends: base.yaml\ndata:\n  store_path: data/b.duckdb\n")
    s = load_settings.__wrapped__(tmp_path / "live.yaml")
    assert s.data.store_path == "data/b.duckdb" and s.data.history_years == 3 and s.risk.risk_per_trade_pct == 0.5


def test_missing_base_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "live.yaml").write_text("extends: nope.yaml\n")
    with pytest.raises(FileNotFoundError):
        load_settings.__wrapped__(tmp_path / "live.yaml")


def test_repo_live_yaml_matches_settings_except_paths() -> None:
    base, live = load_settings.__wrapped__(), load_settings.__wrapped__(Path(__file__).parents[1] / "config" / "live.yaml")
    assert live.data.store_path == "data/market.duckdb" and live.playbook == base.playbook
    assert live.strategies == base.strategies and live.risk == base.risk
