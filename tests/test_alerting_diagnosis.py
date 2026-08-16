"""Alerting delivery diagnosis — the 2026-08-16 "every alert silently failed" fix.

WHAT BROKE: `/opt/fabrik/.env` splits the Telegram credential. `TELEGRAM_BOT_TOKEN`
holds only the SECRET half (`AAHw…`, no colon); the usable token is `<bot_id>:<secret>`
and lives in `TELEGRAM_FULL_BOT_TOKEN`. `libs/alerting/telegram.py` posted to
`/bot<secret>/sendMessage`, which Telegram answers with HTTP 404 `Not Found` — a
status that reads like a dead endpoint, not a malformed credential. The SSH→Apprise
primary was independently down (remote curl exit 6: `apprise` does not resolve on the
VPS). Both legs failed, and the module logged one line naming neither method nor
cause. Every alert the box raises routes through here.

These tests pin the two things that let it hide: token RESOLUTION, and the fact that
a total failure now reports each method and why.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "libs"))

import alerting  # noqa: E402

# Importing the submodules binds them as attributes of the package, which is what
# `monkeypatch.setattr(alerting.apprise, …)` needs. `attempt_delivery` resolves them
# through `sys.modules`, so it sees the same objects the tests patch.
from alerting import apprise, telegram  # noqa: E402, F401
from alerting._attempt import DeliveryAttempt  # noqa: E402

TELEGRAM_VARS = (
    "TELEGRAM_FULL_BOT_TOKEN",
    "TELEGRAM_BOT_ID",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """The module autoloads `.env` at import, so a real credential would leak in."""
    for var in TELEGRAM_VARS:
        monkeypatch.delenv(var, raising=False)


# ── Token resolution: the actual root cause ─────────────────────────────────────


def test_secret_half_alone_is_refused_not_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    """A colon-less TELEGRAM_BOT_TOKEN must resolve to NOTHING.

    This is the exact live configuration. Sending it produced a 404 that cost the
    operator an unknown number of missed alerts; refusing it names the missing var.
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "AAHwSecretHalfOnlyNoColonHere")
    token, source = telegram.resolve_bot_token()
    assert token == ""
    assert "secret half" in source
    assert "TELEGRAM_BOT_ID" in source


def test_split_credential_is_composed(monkeypatch: pytest.MonkeyPatch) -> None:
    """`TELEGRAM_BOT_ID` + secret half compose into a usable `id:secret`."""
    monkeypatch.setenv("TELEGRAM_BOT_ID", "8751000")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "AAHwSecret")
    token, source = telegram.resolve_bot_token()
    assert token == "8751000:AAHwSecret"
    assert "composed" in source


def test_full_token_wins_over_the_halves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_FULL_BOT_TOKEN", "111:full")
    monkeypatch.setenv("TELEGRAM_BOT_ID", "222")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "other")
    token, source = telegram.resolve_bot_token()
    assert token == "111:full"
    assert source == "TELEGRAM_FULL_BOT_TOKEN"


def test_complete_colon_shaped_bot_token_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Projects that store the whole token in TELEGRAM_BOT_TOKEN must keep working."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "333:complete")
    token, source = telegram.resolve_bot_token()
    assert token == "333:complete"
    assert "already complete" in source


def test_bot_id_without_secret_names_the_real_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Half-configured must not report as "nothing is set" — that misdirects the fix."""
    monkeypatch.setenv("TELEGRAM_BOT_ID", "8751000")
    token, source = telegram.resolve_bot_token()
    assert token == ""
    assert "TELEGRAM_BOT_TOKEN is empty" in source


def test_a_token_shaped_string_is_redacted_from_the_report() -> None:
    """The diagnosis surface must never become a credential-disclosure surface."""
    leaky = DeliveryAttempt(
        "telegram-direct",
        False,
        "URLError contacting https://api.telegram.org/bot8751000:AAHwabcdefghijklmnopqrstuvwxyz012345/sendMessage",
    )
    rendered = leaky.render()
    assert "AAHwabcdefghijklmnopqrstuvwxyz012345" not in rendered
    assert "<redacted-token>" in rendered


def test_a_critical_escalation_is_not_swallowed_by_an_earlier_info_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dedup keys on (severity, title). A title-only key hid exactly this escalation."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")  # enable the module
    monkeypatch.setattr("time.time", lambda: 1000.0)
    alerting._last_sent.clear()
    sent: list[str] = []
    monkeypatch.setattr(
        alerting,
        "attempt_delivery",
        lambda t, b: (sent.append(t), [DeliveryAttempt("telegram-direct", True, "ok")])[1],
    )

    assert alerting.send_alert("quota", "80%", severity="info") is True
    # Same title, same instant, escalated severity — must NOT be suppressed.
    assert alerting.send_alert("quota", "95%", severity="critical") is True
    # A genuine repeat at the SAME severity still is.
    assert alerting.send_alert("quota", "96%", severity="critical") is False
    assert len(sent) == 2


def test_unconfigured_reports_which_vars_are_missing() -> None:
    token, source = telegram.resolve_bot_token()
    assert token == ""
    assert "TELEGRAM_FULL_BOT_TOKEN" in source


def test_dotenv_curates_all_three_telegram_keys() -> None:
    """Composing needs every half loaded — loading only the secret is what broke it."""
    from alerting._dotenv import DOTENV_KEYS

    for var in ("TELEGRAM_FULL_BOT_TOKEN", "TELEGRAM_BOT_ID", "TELEGRAM_BOT_TOKEN"):
        assert var in DOTENV_KEYS, f"{var} must be autoloaded or the token cannot resolve"


# ── The diagnosis surface ───────────────────────────────────────────────────────


def test_unconfigured_telegram_attempt_explains_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    attempt = telegram.try_send("t", "b")
    assert attempt.ok is False
    assert attempt.method == "telegram-direct"
    assert "no usable bot token" in attempt.detail


def test_missing_chat_id_is_named_specifically(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_FULL_BOT_TOKEN", "111:full")
    attempt = telegram.try_send("t", "b")
    assert attempt.ok is False
    assert "TELEGRAM_CHAT_ID" in attempt.detail


def test_failure_log_names_every_method_and_cause(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The regression test for the one-line `Alert FAILED` that hid two breakages."""
    monkeypatch.setattr(
        alerting,
        "attempt_delivery",
        lambda title, body: [
            DeliveryAttempt("ssh-apprise", False, "remote curl exit 6 — host unresolvable"),
            DeliveryAttempt("telegram-direct", False, "HTTP 404: bot token rejected"),
        ],
    )
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "x")  # enable the module
    alerting._last_sent.clear()

    with caplog.at_level("WARNING"):
        assert alerting.send_alert("quota drain", "80% used") is False

    logged = caplog.text
    assert "ssh-apprise" in logged, "the failure log must name the primary method"
    assert "telegram-direct" in logged, "the failure log must name the fallback method"
    assert "curl exit 6" in logged, "the failure log must carry each method's CAUSE"
    assert "404" in logged
    assert "--selftest" in logged, "the log must point at the command that proves the path"


def test_delivery_stops_at_the_first_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fire-and-forget, not fan-out: a working primary must not also page Telegram."""
    monkeypatch.setattr(
        alerting.apprise, "try_send", lambda t, b: DeliveryAttempt("ssh-apprise", True, "ok")
    )

    def _boom(title: str, body: str) -> DeliveryAttempt:  # pragma: no cover
        raise AssertionError("fallback must not run after the primary succeeded")

    monkeypatch.setattr(alerting.telegram, "try_send", _boom)
    attempts = alerting.attempt_delivery("t", "b")
    assert len(attempts) == 1
    assert attempts[0].ok


def test_a_broken_leg_becomes_a_failed_attempt_not_an_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A delivery layer that raises also loses the alert it was raising about."""

    def _explode(title: str, body: str) -> DeliveryAttempt:
        raise RuntimeError("ssh binary vanished")

    monkeypatch.setattr(alerting.apprise, "try_send", _explode)
    monkeypatch.setattr(
        alerting.telegram, "try_send", lambda t, b: DeliveryAttempt("telegram-direct", False, "no")
    )
    attempts = alerting.attempt_delivery("t", "b")
    assert len(attempts) == 2
    assert attempts[0].ok is False
    assert "ssh binary vanished" in attempts[0].detail


# ── The selftest an operator/cron can run ───────────────────────────────────────


def test_selftest_dry_run_fails_when_unconfigured() -> None:
    code, lines = alerting.selftest_report(dry_run=True)
    assert code == 1
    assert any("UNRESOLVED" in line for line in lines)


def test_selftest_dry_run_passes_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_FULL_BOT_TOKEN", "111:full")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    code, lines = alerting.selftest_report(dry_run=True)
    assert code == 0
    assert any(line.startswith("PASS") for line in lines)


def test_selftest_reports_nonzero_when_no_method_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A selftest that cannot fail would be the very bug this change is fixing."""
    monkeypatch.setenv("TELEGRAM_FULL_BOT_TOKEN", "111:full")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setattr(
        alerting,
        "attempt_delivery",
        lambda t, b: [DeliveryAttempt("ssh-apprise", False, "unreachable")],
    )
    code, lines = alerting.selftest_report()
    assert code == 1
    assert any(line.startswith("FAIL") for line in lines)


def test_cli_writes_the_report_and_returns_the_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`__main__` owns the only stdout write — the library itself stays print-free."""
    monkeypatch.setenv("TELEGRAM_FULL_BOT_TOKEN", "111:full")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    assert alerting._main(["--selftest", "--dry-run"]) == 0
    assert "alerting selftest" in capsys.readouterr().out


def test_library_contains_no_print_calls() -> None:
    """Regression guard for the gate's Print/Console.log ban, which covers `libs/`."""
    pkg = Path(alerting.__file__).parent
    for module in pkg.glob("*.py"):
        if module.name == "__main__.py":
            continue
        assert "print(" not in module.read_text(encoding="utf-8"), (
            f"{module.name} writes to stdout — libs/ must stay embeddable"
        )


def test_alerting_package_is_runnable_with_dash_m() -> None:
    """`python -m alerting --selftest` must exist — a package needs __main__.py."""
    assert (Path(alerting.__file__).parent / "__main__.py").is_file()
