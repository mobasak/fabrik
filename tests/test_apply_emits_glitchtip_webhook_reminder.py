"""Phase 7 (deploy-readiness-gaps): apply-time GlitchTip webhook reminder.

GlitchTip exposes no API to register a webhook recipient (probed 2026-06-29 —
/rules/, /alert-rules/, /alerts/ all 404), so `fabrik apply` can't automate it.
For any spec whose watchdog ingests `error_webhook`, it must instead print a
clear operator-manual reminder. These tests pin the pure reminder builder the
apply summary calls — see `cli.py` reconcile-all loop + `glitchtip.py`.
"""

from __future__ import annotations

from types import SimpleNamespace

from fabrik.drivers.glitchtip import webhook_registration_reminder


def _spec(sources: list[str], sid: str = "demo-svc") -> SimpleNamespace:
    return SimpleNamespace(id=sid, watchdog=SimpleNamespace(trigger_sources=sources))


def test_reminder_logged_when_error_webhook_enabled(monkeypatch):
    # Force defaults so the asserted URL is deterministic regardless of host env.
    monkeypatch.delenv("GLITCHTIP_ORG_SLUG", raising=False)
    monkeypatch.delenv("GLITCHTIP_URL", raising=False)
    rem = webhook_registration_reminder(_spec(["health", "error_webhook"]))
    assert rem is not None
    assert "ACTION REQUIRED: register GlitchTip webhook" in rem
    # canonical UI URL (org default 'ocoron', driver base) + the :8889 recipient
    assert "https://errors.vps1.ocoron.com/ocoron/demo-svc/" in rem
    assert "http://demo-svc-watchdog:8889/" in rem
    assert "recipient type: webhook" in rem


def test_no_reminder_when_error_webhook_disabled():
    assert webhook_registration_reminder(_spec(["emitter", "health"])) is None
    assert webhook_registration_reminder(_spec([])) is None
    # a spec with no watchdog block at all must not raise
    assert webhook_registration_reminder(SimpleNamespace(id="x", watchdog=None)) is None


def test_total_and_exact_match_on_malformed_trigger_sources():
    # This public helper runs inside `fabrik apply`'s reconcile loop, so it must
    # be TOTAL (never raise) and EXACT (membership, not substring). The Spec
    # model rejects scalar trigger_sources, but a duck-typed caller could pass
    # garbage — none of it may fire or crash.
    # 1) a STRING that merely contains the token as a substring must NOT fire
    assert webhook_registration_reminder(_spec("health,error_webhook_DISABLED")) is None
    assert webhook_registration_reminder(_spec("error_webhook")) is None  # str, not list
    # 2) non-iterable / None trigger_sources must return None, not raise
    assert webhook_registration_reminder(_spec(5)) is None
    assert webhook_registration_reminder(_spec(None)) is None
    # 3) a spec carrying error_webhook but no .id must return None, not raise
    assert (
        webhook_registration_reminder(
            SimpleNamespace(watchdog=SimpleNamespace(trigger_sources=["error_webhook"]))
        )
        is None
    )


def test_apply_helper_emits_for_error_webhook_spec(capsys, monkeypatch):
    # `fabrik apply` (the single deploy entry point) must surface the reminder
    # on a COMPLETE deploy — not only `reconcile-all`. The helper load_spec's
    # the just-deployed spec; monkeypatch it to a fake error_webhook spec.
    from fabrik import cli

    monkeypatch.delenv("GLITCHTIP_ORG_SLUG", raising=False)
    monkeypatch.delenv("GLITCHTIP_URL", raising=False)
    monkeypatch.setattr(cli, "load_spec", lambda p: _spec(["error_webhook"], sid="cal-api"))
    cli._emit_glitchtip_webhook_reminder("ignored.yaml")
    out = capsys.readouterr().out
    assert "ACTION REQUIRED: register GlitchTip webhook for cal-api" in out
    assert "http://cal-api-watchdog:8889/" in out


def test_apply_helper_silent_for_non_error_webhook(capsys, monkeypatch):
    from fabrik import cli

    monkeypatch.setattr(cli, "load_spec", lambda p: _spec(["health"]))
    cli._emit_glitchtip_webhook_reminder("ignored.yaml")
    assert capsys.readouterr().out == ""


def test_apply_helper_never_raises_on_bad_spec(capsys):
    # A reminder must never break a deploy that already COMPLETEd — a load
    # failure (e.g. missing/garbled spec) is swallowed silently.
    from fabrik import cli

    cli._emit_glitchtip_webhook_reminder("/nonexistent/does-not-exist.yaml")  # must not raise
    assert capsys.readouterr().out == ""


def test_fabrik_apply_command_emits_reminder_on_complete(tmp_path, monkeypatch):
    # End-to-end: invoke the real `fabrik apply` Command with the orchestrator
    # mocked to a COMPLETE deploy; the reminder MUST appear in its output (this
    # is the path the operator/hub-AI actually deploys through — the original
    # bug was that only reconcile-all emitted it).
    from click.testing import CliRunner

    from fabrik import cli
    from fabrik.orchestrator import DeploymentState

    class _Ctx:
        state = DeploymentState.COMPLETE
        deployed_url = "https://cal.example.com"
        spec = {"domain": "cal.example.com"}
        error = None

    class _Orch:
        def __init__(self, *a, **k):
            pass

        def deploy(self, *a, **k):
            return _Ctx()

    monkeypatch.setattr(cli, "DeploymentOrchestrator", _Orch)
    monkeypatch.setattr(cli, "_post_deploy_sync", lambda: None)
    monkeypatch.setattr(cli, "load_spec", lambda p: _spec(["error_webhook"], sid="cal-api"))
    monkeypatch.delenv("GLITCHTIP_ORG_SLUG", raising=False)
    monkeypatch.delenv("GLITCHTIP_URL", raising=False)

    spec_file = tmp_path / "s.yaml"
    spec_file.write_text("id: cal-api\n")  # only needs to satisfy click's exists=True
    result = CliRunner().invoke(cli.apply, [str(spec_file), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "ACTION REQUIRED: register GlitchTip webhook for cal-api" in result.output


def test_reminder_honours_org_and_base_overrides(monkeypatch):
    monkeypatch.setenv("GLITCHTIP_ORG_SLUG", "acme")
    monkeypatch.setenv("GLITCHTIP_URL", "https://gt.example.com/")
    rem = webhook_registration_reminder(_spec(["error_webhook"], sid="billing-api"))
    assert rem is not None
    assert "https://gt.example.com/acme/billing-api/" in rem
    assert "http://billing-api-watchdog:8889/" in rem
