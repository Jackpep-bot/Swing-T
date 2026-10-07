"""ops.doctor: offline checks run hermetically against a tmp tree; live checks are mocked with respx and a
fake Anthropic client. No test touches the network, and no secret value may ever appear in a detail."""

from __future__ import annotations

import importlib
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
import respx
import yaml

from swing_engine.core.config import Secrets, Settings
from swing_engine.ops import doctor
from swing_engine.ops.doctor import Check, CheckStatus, run_doctor
from tests.helpers_data import fixture_text

TODAY = date(2026, 10, 2)
SECRET_VALUES: dict[str, str] = {
    "massive_api_key": "massive-secret-key-0001",
    "eodhd_api_key": "eodhd-secret-key-0002",
    "alphavantage_api_key": "alphavantage-secret-0003",
    "alpaca_api_key": "PKALPACAKEYID0004",
    "alpaca_secret_key": "alpaca-secret-key-0005",
    "quiver_api_key": "quiver-secret-key-0006",
    "anthropic_api_key": "sk-ant-secret-0007",
    "telegram_bot_token": "123456789:telegram-secret-token-0008",
    "telegram_chat_id": "987654321",
    "pushover_user_key": "pushover-user-secret-0009",
    "pushover_app_token": "pushover-app-secret-0010",
}
CONTACT_AGENT = "swing-engine doctor@example.com"
TELEGRAM_BASE = f"{doctor.TELEGRAM_API}/bot{SECRET_VALUES['telegram_bot_token']}"
NASDAQ_RSS_PATTERN = r"https://www\.nasdaqtrader\.com/rss\.aspx.*"


# ----------------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------------
def make_settings(tmp_path: Path) -> tuple[Settings, Path]:
    raw = {
        "data": {"store_path": str(tmp_path / "data" / "swing.duckdb"), "bar_provider": "sample"},
        "risk": {
            "kill_switch_file": str(tmp_path / "state" / "KILL"),
            "limits_state_file": str(tmp_path / "state" / "limits.json"),
        },
        "strategies": {"rsi2_meanrev": {"enabled": True}},
    }
    path = tmp_path / "settings.yaml"
    path.write_text(yaml.safe_dump(raw))
    return Settings.model_validate(raw), path


def secrets_with(**overrides: Any) -> Secrets:
    return Secrets(_env_file=None, **{**SECRET_VALUES, "edgar_user_agent": CONTACT_AGENT, **overrides})


def no_secrets() -> Secrets:
    return Secrets(_env_file=None)


def run(tmp_path: Path, secrets: Secrets, live: bool, **kw: Any) -> dict[str, Check]:
    settings, settings_path = make_settings(tmp_path)
    checks = run_doctor(
        settings, secrets, live, settings_path=settings_path, env_path=tmp_path / ".env", today=TODAY, **kw
    )
    assert len({c.name for c in checks}) == len(checks), "check names must be unique"
    return {c.name: c for c in checks}


def assert_no_secret_leaks(checks: dict[str, Check]) -> None:
    text = " ".join(f"{c.name} {c.detail}" for c in checks.values())
    for value in SECRET_VALUES.values():
        assert value not in text, f"secret value leaked into doctor output: {value!r}"


class FakeAnthropic:
    """Stands in for `anthropic.Anthropic`: records the request, returns a response-shaped object or raises."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.error = error
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            model=kwargs["model"],
            stop_reason="max_tokens",
            usage=SimpleNamespace(input_tokens=8, output_tokens=1),
        )


def mock_vendors_ok() -> dict[str, respx.Route]:
    routes = {
        "massive": respx.get(doctor.MASSIVE_TICKERS_URL).mock(
            return_value=httpx.Response(
                200,
                json={"status": "OK", "results": [{"ticker": "AAPL"}], "count": 1},
                headers={"X-RateLimit-Limit": "5", "X-RateLimit-Remaining": "4"},
            )
        ),
        "alpaca_account": respx.get(f"{doctor.ALPACA_PAPER_URL}{doctor.ALPACA_ACCOUNT_PATH}").mock(
            return_value=httpx.Response(
                200, json={"status": "ACTIVE", "equity": "100000", "cash": "50000", "trading_blocked": False}
            )
        ),
        "alpaca_data": respx.get(doctor.ALPACA_DATA_LATEST_BAR_URL).mock(
            return_value=httpx.Response(
                200, json={"symbol": "SPY", "bar": {"t": "2026-10-02T19:59:00Z", "c": 570.12, "v": 1234}}
            )
        ),
        "alphavantage": respx.get(doctor.ALPHAVANTAGE_URL).mock(
            return_value=httpx.Response(200, text=fixture_text("alphavantage_earnings.csv"))
        ),
        "edgar": respx.get(doctor.EDGAR_CURRENT_URL).mock(
            return_value=httpx.Response(200, text=fixture_text("edgar_current_8k.atom"))
        ),
        "nasdaq": respx.get(url__regex=NASDAQ_RSS_PATTERN).mock(
            return_value=httpx.Response(200, text="<rss><channel><item>a</item><item>b</item></channel></rss>")
        ),
        "telegram_me": respx.get(f"{TELEGRAM_BASE}/getMe").mock(
            return_value=httpx.Response(200, json={"ok": True, "result": {"username": "swing_bot"}})
        ),
        "telegram_send": respx.post(f"{TELEGRAM_BASE}/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 77}})
        ),
        "pushover": respx.post(doctor.PUSHOVER_VALIDATE_URL).mock(
            return_value=httpx.Response(200, json={"status": 1, "devices": ["iphone"], "request": "r1"})
        ),
    }
    return routes


# ----------------------------------------------------------------------------------------------------------
# offline
# ----------------------------------------------------------------------------------------------------------
def test_offline_checks_without_keys(tmp_path: Path) -> None:
    c = run(tmp_path, no_secrets(), False)
    assert c["env_file"].status is CheckStatus.WARN and ".env.example" in c["env_file"].detail
    assert c["secret:MASSIVE_API_KEY"].status is CheckStatus.WARN and c["secret:MASSIVE_API_KEY"].detail == "missing"
    assert c["secret:ALPACA_PAPER"].status is CheckStatus.OK
    assert c["secret:EDGAR_USER_AGENT"].status is CheckStatus.WARN and "default" in c["secret:EDGAR_USER_AGENT"].detail
    assert c["settings_yaml"].status is CheckStatus.OK and "provider=sample" in c["settings_yaml"].detail
    assert c["store_path"].status is CheckStatus.OK and "not created yet" in c["store_path"].detail
    assert c["calendar"].status is CheckStatus.OK and "NYSE" in c["calendar"].detail and "2026-10-02" in c["calendar"].detail
    assert c["registry_plugins"].status is CheckStatus.OK and "strategy=" in c["registry_plugins"].detail
    assert c["kill_switch"].status is CheckStatus.OK and "clear" in c["kill_switch"].detail
    assert c["limits_state"].status is CheckStatus.SKIP
    assert c["python"].status is CheckStatus.OK and c["python"].detail.startswith("3.")
    assert c["package:pandas"].status is CheckStatus.OK
    assert c["package:lightgbm"].status in (CheckStatus.OK, CheckStatus.WARN)
    assert c["live"].status is CheckStatus.SKIP and "--live" in c["live"].detail
    assert not any(name.startswith("live:") for name in c)
    assert not any(check.status is CheckStatus.FAIL for check in c.values())


def test_present_secrets_report_set_and_never_print_values(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("MASSIVE_API_KEY=x\n")
    c = run(tmp_path, secrets_with(), False)
    assert c["env_file"].status is CheckStatus.OK
    for name in ("MASSIVE_API_KEY", "ALPACA_API_KEY", "ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN", "EDGAR_USER_AGENT"):
        assert c[f"secret:{name}"].status is CheckStatus.OK and c[f"secret:{name}"].detail == "set"
    assert_no_secret_leaks(c)


def test_live_keys_flag_is_a_warning(tmp_path: Path) -> None:
    c = run(tmp_path, secrets_with(alpaca_paper=False), False)
    assert c["secret:ALPACA_PAPER"].status is CheckStatus.WARN and "gates" in c["secret:ALPACA_PAPER"].detail


def test_kill_switch_tripped_and_limits_state(tmp_path: Path) -> None:
    kill = tmp_path / "state" / "KILL"
    kill.parent.mkdir(parents=True)
    kill.write_text("2026-10-01T20:00:00+00:00 manual stop\n")
    (tmp_path / "state" / "limits.json").write_text(
        json.dumps({"version": 1, "day": "2026-10-01", "peak_equity": 52000.0, "updated_at": "2026-10-01T21:00:00+00:00"})
    )
    c = run(tmp_path, no_secrets(), False)
    assert c["kill_switch"].status is CheckStatus.WARN
    assert "TRIPPED" in c["kill_switch"].detail and "manual stop" in c["kill_switch"].detail
    assert c["limits_state"].status is CheckStatus.OK and "peak_equity=52000.0" in c["limits_state"].detail


def test_unreadable_limits_state_fails_without_raising(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "limits.json").write_text("{not json")
    c = run(tmp_path, no_secrets(), False)
    assert c["limits_state"].status is CheckStatus.FAIL and "JSONDecodeError" in c["limits_state"].detail


def test_broken_settings_yaml_fails(tmp_path: Path) -> None:
    settings, settings_path = make_settings(tmp_path)
    settings_path.write_text("risk:\n  risk_per_trade_pct: not-a-number\n")
    checks = {c.name: c for c in run_doctor(settings, no_secrets(), False, settings_path=settings_path, env_path=tmp_path / ".env", today=TODAY)}
    assert checks["settings_yaml"].status is CheckStatus.FAIL and "ValidationError" in checks["settings_yaml"].detail


def test_missing_settings_yaml_is_a_warning(tmp_path: Path) -> None:
    settings, _ = make_settings(tmp_path)
    checks = {c.name: c for c in run_doctor(settings, no_secrets(), False, settings_path=tmp_path / "nope.yaml", env_path=tmp_path / ".env", today=TODAY)}
    assert checks["settings_yaml"].status is CheckStatus.WARN and "defaults" in checks["settings_yaml"].detail


def test_store_path_not_writable_fails(tmp_path: Path) -> None:
    blocker = tmp_path / "blocked"
    blocker.write_text("a file where the store directory should be")
    settings = Settings.model_validate({"data": {"store_path": str(blocker / "swing.duckdb")}})
    check = doctor._guarded("store_path", lambda: doctor.check_store_writable(settings), doctor.Redactor(no_secrets()))
    assert check.status is CheckStatus.FAIL and "Error" in check.detail


def test_optional_import_failure_is_a_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = importlib.import_module

    def fake_import(name: str, package: str | None = None) -> Any:
        if name == "lightgbm":
            raise OSError("dlopen(lib_lightgbm.dylib): Library not loaded: libomp.dylib")
        return real_import(name, package)

    monkeypatch.setattr(doctor.importlib, "import_module", fake_import)
    monkeypatch.setattr(doctor.metadata, "version", lambda name: "4.7.0")
    checks = {c.name: c for c in doctor.check_packages(("lightgbm", "pandas"))}
    assert checks["package:lightgbm"].status is CheckStatus.WARN
    assert "libomp" in checks["package:lightgbm"].detail and "OSError" in checks["package:lightgbm"].detail
    assert checks["package:pandas"].status is CheckStatus.OK and checks["package:pandas"].detail == "4.7.0"


def test_missing_package_is_a_warning() -> None:
    checks = doctor.check_packages(("definitely-not-installed-xyz",))
    assert checks[0].status is CheckStatus.WARN and checks[0].detail == "not installed"


# ----------------------------------------------------------------------------------------------------------
# live
# ----------------------------------------------------------------------------------------------------------
@respx.mock
def test_live_checks_all_ok(tmp_path: Path) -> None:
    routes = mock_vendors_ok()
    fake = FakeAnthropic()
    c = run(tmp_path, secrets_with(), True, anthropic_client=fake)

    assert c["live:massive"].status is CheckStatus.OK
    assert "results=1" in c["live:massive"].detail and "ratelimit-limit=5" in c["live:massive"].detail.lower()
    assert routes["massive"].calls[0].request.headers["Authorization"] == f"Bearer {SECRET_VALUES['massive_api_key']}"
    assert routes["massive"].calls[0].request.url.params["limit"] == "1"

    assert c["live:alpaca_account"].status is CheckStatus.OK
    assert "paper" in c["live:alpaca_account"].detail and "equity=100000" in c["live:alpaca_account"].detail
    assert routes["alpaca_account"].calls[0].request.headers["APCA-API-KEY-ID"] == SECRET_VALUES["alpaca_api_key"]

    assert c["live:alpaca_data"].status is CheckStatus.OK and "570.12" in c["live:alpaca_data"].detail
    assert c["live:alphavantage"].status is CheckStatus.OK and "symbol,name,reportDate" in c["live:alphavantage"].detail
    assert routes["alphavantage"].calls[0].request.url.params["function"] == "EARNINGS_CALENDAR"

    assert c["live:edgar"].status is CheckStatus.OK and "entries" in c["live:edgar"].detail
    edgar_request = routes["edgar"].calls[0].request
    assert edgar_request.headers["User-Agent"] == CONTACT_AGENT and edgar_request.url.params["output"] == "atom"

    assert c["live:nasdaq_halts"].status is CheckStatus.OK and "2 halt items" in c["live:nasdaq_halts"].detail

    assert c["live:anthropic"].status is CheckStatus.OK and "claude-haiku-4-5" in c["live:anthropic"].detail
    assert fake.calls == [
        {"model": "claude-haiku-4-5", "max_tokens": 1, "messages": [{"role": "user", "content": "ping"}]}
    ]

    assert c["live:telegram"].status is CheckStatus.OK and "@swing_bot" in c["live:telegram"].detail
    assert "--send-test" in c["live:telegram"].detail and routes["telegram_send"].call_count == 0

    assert c["live:pushover"].status is CheckStatus.OK and "iphone" in c["live:pushover"].detail
    assert_no_secret_leaks(c)


@respx.mock
def test_send_test_posts_one_message_to_the_chat(tmp_path: Path) -> None:
    routes = mock_vendors_ok()
    c = run(tmp_path, secrets_with(), True, send_test=True, anthropic_client=FakeAnthropic())
    assert c["live:telegram"].status is CheckStatus.OK and "message_id=77" in c["live:telegram"].detail
    assert routes["telegram_send"].call_count == 1
    body = json.loads(routes["telegram_send"].calls[0].request.read())
    assert body["chat_id"] == SECRET_VALUES["telegram_chat_id"] and body["text"] == doctor.TELEGRAM_TEST_TEXT
    assert_no_secret_leaks(c)


@respx.mock
def test_telegram_without_chat_id_warns_and_never_sends(tmp_path: Path) -> None:
    routes = mock_vendors_ok()
    c = run(tmp_path, secrets_with(telegram_chat_id=None), True, send_test=True, anthropic_client=FakeAnthropic())
    assert c["live:telegram"].status is CheckStatus.WARN and "TELEGRAM_CHAT_ID" in c["live:telegram"].detail
    assert routes["telegram_send"].call_count == 0


@respx.mock
def test_live_failures_are_isolated_and_redacted(tmp_path: Path) -> None:
    import anthropic

    respx.get(doctor.MASSIVE_TICKERS_URL).mock(return_value=httpx.Response(401, json={"status": "ERROR"}))
    respx.get(f"{doctor.ALPACA_PAPER_URL}{doctor.ALPACA_ACCOUNT_PATH}").mock(side_effect=httpx.ReadTimeout("slow"))
    respx.get(doctor.ALPACA_DATA_LATEST_BAR_URL).mock(return_value=httpx.Response(500, text="upstream exploded"))
    respx.get(doctor.ALPHAVANTAGE_URL).mock(
        return_value=httpx.Response(200, json={"Note": "Thank you for using Alpha Vantage! Our standard API rate limit is 25 requests per day."})
    )
    respx.get(doctor.EDGAR_CURRENT_URL).mock(return_value=httpx.Response(403, text="Request Rate Threshold Exceeded"))
    respx.get(url__regex=NASDAQ_RSS_PATTERN).mock(side_effect=httpx.ConnectError("name resolution failed"))
    respx.get(f"{TELEGRAM_BASE}/getMe").mock(
        side_effect=httpx.ConnectError(f"failed to connect to {TELEGRAM_BASE}/getMe")
    )
    respx.post(doctor.PUSHOVER_VALIDATE_URL).mock(
        return_value=httpx.Response(400, json={"status": 0, "errors": ["user identifier is invalid"]})
    )
    auth_error = anthropic.AuthenticationError(
        "invalid x-api-key",
        response=httpx.Response(401, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")),
        body=None,
    )
    c = run(tmp_path, secrets_with(), True, anthropic_client=FakeAnthropic(error=auth_error))

    assert c["live:massive"].status is CheckStatus.FAIL and "401" in c["live:massive"].detail
    assert c["live:alpaca_account"].status is CheckStatus.FAIL and "timed out after 10 s" in c["live:alpaca_account"].detail
    assert c["live:alpaca_data"].status is CheckStatus.FAIL and "HTTP 500" in c["live:alpaca_data"].detail
    assert c["live:alphavantage"].status is CheckStatus.WARN and "JSON" in c["live:alphavantage"].detail
    assert c["live:edgar"].status is CheckStatus.FAIL and "EDGAR_USER_AGENT" in c["live:edgar"].detail
    assert c["live:nasdaq_halts"].status is CheckStatus.FAIL and "ConnectError" in c["live:nasdaq_halts"].detail
    assert c["live:anthropic"].status is CheckStatus.FAIL and "401" in c["live:anthropic"].detail
    assert c["live:telegram"].status is CheckStatus.FAIL and "***" in c["live:telegram"].detail
    assert c["live:pushover"].status is CheckStatus.FAIL and "user identifier is invalid" in c["live:pushover"].detail
    assert_no_secret_leaks(c)


@respx.mock
def test_generic_exception_in_a_live_check_is_a_fail_not_a_crash(tmp_path: Path) -> None:
    mock_vendors_ok()
    c = run(tmp_path, secrets_with(), True, anthropic_client=FakeAnthropic(error=RuntimeError("boom sk-ant-secret-0007")))
    assert c["live:anthropic"].status is CheckStatus.FAIL
    assert c["live:anthropic"].detail.startswith("RuntimeError: boom") and "***" in c["live:anthropic"].detail
    assert c["live:massive"].status is CheckStatus.OK  # the other checks still ran


@respx.mock
def test_live_without_keys_skips_vendors_and_still_probes_public_feeds(tmp_path: Path) -> None:
    respx.get(doctor.EDGAR_CURRENT_URL).mock(return_value=httpx.Response(200, text=fixture_text("edgar_current_8k.atom")))
    nasdaq = respx.get(url__regex=NASDAQ_RSS_PATTERN).mock(return_value=httpx.Response(200, text="<rss><item/></rss>"))
    c = run(tmp_path, no_secrets(), True)
    for name, hint in (
        ("live:massive", "MASSIVE_API_KEY"),
        ("live:alpaca_account", "ALPACA_API_KEY"),
        ("live:alpaca_data", "ALPACA_API_KEY"),
        ("live:alphavantage", "ALPHAVANTAGE_API_KEY"),
        ("live:anthropic", "ANTHROPIC_API_KEY"),
        ("live:telegram", "TELEGRAM_BOT_TOKEN"),
        ("live:pushover", "PUSHOVER_USER_KEY"),
    ):
        assert c[name].status is CheckStatus.SKIP and hint in c[name].detail, name
    assert nasdaq.call_count == 1 and c["live:nasdaq_halts"].status is CheckStatus.OK
    assert c["live:edgar"].status is CheckStatus.WARN and "default" in c["live:edgar"].detail  # placeholder User-Agent


@respx.mock
def test_edgar_user_agent_without_contact_fails_before_any_request(tmp_path: Path) -> None:
    edgar = respx.get(doctor.EDGAR_CURRENT_URL).mock(return_value=httpx.Response(200, text="<feed/>"))
    respx.get(url__regex=NASDAQ_RSS_PATTERN).mock(return_value=httpx.Response(200, text="<rss/>"))
    c = run(tmp_path, secrets_with(edgar_user_agent="no-contact-here"), True, anthropic_client=FakeAnthropic())
    assert c["live:edgar"].status is CheckStatus.FAIL and "contact email" in c["live:edgar"].detail
    assert edgar.call_count == 0


@respx.mock
def test_live_alpaca_live_mode_hits_live_host_and_warns(tmp_path: Path) -> None:
    mock_vendors_ok()
    live_route = respx.get(f"{doctor.ALPACA_LIVE_URL}{doctor.ALPACA_ACCOUNT_PATH}").mock(
        return_value=httpx.Response(200, json={"status": "ACTIVE", "equity": "1"})
    )
    c = run(tmp_path, secrets_with(alpaca_paper=False), True, anthropic_client=FakeAnthropic())
    assert live_route.call_count == 1
    assert c["live:alpaca_account"].status is CheckStatus.WARN and "LIVE" in c["live:alpaca_account"].detail


def test_redactor_blanks_values_and_query_credentials() -> None:
    redact = doctor.Redactor(secrets_with())
    text = f"GET https://x.test/?apikey={SECRET_VALUES['alphavantage_api_key']} token {SECRET_VALUES['telegram_bot_token']} short"
    out = redact(text)
    assert "***" in out
    for value in SECRET_VALUES.values():
        assert value not in out
