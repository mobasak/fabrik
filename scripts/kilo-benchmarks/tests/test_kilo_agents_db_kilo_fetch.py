"""Behavior Contract for kilo_agents_db.fetch_kilo_models config-error path.

Phase B of plan-4. B1 config-error → alert + [], B2 happy-path preserved.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_kilo_config_invalid_triggers_alert(monkeypatch):
    """B1: `Configuration is invalid` in stderr → [] + apprise.send fired."""
    sent: list[tuple[str, str]] = []

    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv,
            returncode=0,
            stdout="",
            stderr=(
                "Error: Configuration is invalid at /home/x/.config/kilo/opencode.json\n"
                'Unrecognized keys: "subagent_model", "subagent_variant_overrides"\n'
            ),
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    import alerting.apprise as apprise_mod

    def fake_send(title, body):
        sent.append((title, body))
        return True

    monkeypatch.setattr(apprise_mod, "send", fake_send)

    import kilo_agents_db

    result = kilo_agents_db.fetch_kilo_models()
    assert result == []
    assert len(sent) == 1, f"expected 1 alert, got {len(sent)}: {sent}"
    assert "kilo-cli-config" in sent[0][0].lower()


def test_kilo_happy_path_returns_parsed_list(monkeypatch):
    """B2: valid stdout, no stderr error → parsed list, no alert."""

    stdout_text = (
        "kilo/foo\n"
        "{\n"
        '  "id": "anthropic/claude-fable-5",\n'
        '  "providerID": "kilo",\n'
        '  "name": "Anthropic: Claude Fable 5"\n'
        "}\n"
    )

    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, returncode=0, stdout=stdout_text, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    sent: list = []
    import alerting.apprise as apprise_mod

    monkeypatch.setattr(apprise_mod, "send", lambda title, body: sent.append((title, body)) or True)

    import kilo_agents_db

    result = kilo_agents_db.fetch_kilo_models()
    assert len(result) == 1
    assert result[0]["id"] == "anthropic/claude-fable-5"
    assert sent == [], f"unexpected alert on happy path: {sent}"
