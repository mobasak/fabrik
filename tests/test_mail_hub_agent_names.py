"""scripts/mail.py — a builder `agents_up.sh add` spawns is a hub addressee by its own name (W-677578ef).

agents_spawn.py names a builder `<role>-<suffix>` (role `builder` by default, chartered under
docs/reference/agents/); mail.py admitted only beats and `<beat>-<N>`, so the merge reply to builder-tmpfix
was refused and its record stranded. Hermetic: the hub root is a tmp FABRIK_OPT_ROOT carrying the charters."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_MAIL_PY = Path(__file__).resolve().parent.parent / "scripts" / "mail.py"
spec = importlib.util.spec_from_file_location("fabrik_mail_hub_names", _MAIL_PY)
mail = importlib.util.module_from_spec(spec)
sys.modules["fabrik_mail_hub_names"] = mail
spec.loader.exec_module(mail)

MARKER = "# Agent charter"


def _env(tmp_path, monkeypatch, charters: dict[str, str]):
    mail_root, opt_root = tmp_path / "mail", tmp_path / "opt"
    mail_root.mkdir()
    agents = opt_root / "fabrik" / "docs" / "reference" / "agents"
    agents.mkdir(parents=True)
    for role, first in charters.items():
        (agents / f"{role}.md").write_text(first + "\nbody\n", encoding="utf-8")
    hook = opt_root / "alpha" / ".claude" / "hooks" / "mail_notify.py"
    hook.parent.mkdir(parents=True)
    hook.write_text("# hook\n", encoding="utf-8")
    monkeypatch.setenv("FABRIK_MAIL_ROOT", str(mail_root))
    monkeypatch.setenv("FABRIK_OPT_ROOT", str(opt_root))


def _agent(path: Path) -> str | None:
    return mail._parse(path.read_text(encoding="utf-8")).get("agent")


def test_a_spawned_builder_is_addressed_and_routed_by_its_name(tmp_path, monkeypatch):
    _env(tmp_path, monkeypatch, {"builder": f"{MARKER} — builder"})
    for name in ("builder-tmpfix", "builder-tmp-fix", "builder-1"):
        assert (
            _agent(mail.send(to="fabrik", kind="finding", body=name, frm="alpha", to_agent=name))
            == name
        )
    mid = mail.send(to="fabrik", kind="finding", body="b", frm="alpha", broadcast=True).stem
    mail.route(mid, "builder-tmpfix", repo="fabrik")
    assert mail._parse(mail.read_msg(mid, "fabrik")).get("agent") == "builder-tmpfix"


@pytest.mark.parametrize(
    "charters",
    [{}, {"builder": "# Agent charter-obsolete"}, {"builder": "# Builder notes"}],
    ids=["no-charter", "marker-with-suffix", "no-marker"],
)
def test_the_same_name_is_refused_without_a_marked_charter(tmp_path, monkeypatch, charters):
    _env(tmp_path, monkeypatch, charters)
    with pytest.raises(mail.MailRefusedError, match="unknown hub beat"):
        mail.send(to="fabrik", kind="finding", body="x", frm="alpha", to_agent="builder-tmpfix")
    mid = mail.send(to="fabrik", kind="finding", body="b", frm="alpha", broadcast=True).stem
    with pytest.raises(mail.MailRefusedError, match="unknown hub beat"):
        mail.route(mid, "builder-tmpfix", repo="fabrik")


def test_names_outside_the_spawner_grammar_stay_refused(tmp_path, monkeypatch):
    _env(
        tmp_path,
        monkeypatch,
        {
            r: f"{MARKER} — {r}"
            for r in ("builder", "infra", "infra-2", "coordinator", "lead-coordinator")
        },
    )
    for name in (
        "builder",  # a role, not a builder
        "builder-",  # empty suffix
        "builder-x-",  # ends in a dash
        "-builder-x",
        "Builder-x",
        "builder-" + "x" * 30,  # 38 chars, over the 32-char name grammar
        "builder-coordinator",  # a coordinator NAME (agents_spawn.py preflight)
        "coordinator-x",  # a coordinator ROLE
        "lead-coordinator-x",
        "infra-x",  # beats keep D-1130's <beat>-<N>
        "infra-2-x",  # a <beat>-<N> role
        "devops-2",  # no charter
    ):
        assert not mail.is_hub_agent(name), name
        with pytest.raises(mail.MailRefusedError, match="unknown hub beat"):
            mail.send(to="fabrik", kind="finding", body=name, frm="alpha", to_agent=name)
    for name in ("infra", "infra-2", "coordinator", "kaizen-12"):  # D-1130's shapes are unchanged
        assert mail.is_hub_agent(name), name


def test_a_reply_reaches_the_spawned_builder_that_asked(tmp_path, monkeypatch):
    """The merge-request path: merge_request.py replies `--re <request>`; the answer must reach the
    builder that sent the request, not the request's addressee."""
    _env(tmp_path, monkeypatch, {"builder": f"{MARKER} — builder"})
    monkeypatch.setattr(mail, "_caller_agent", lambda: "builder-tmpfix")
    parent = mail.send(to="fabrik", kind="request", body="mr", frm="fabrik", to_agent="coordinator")
    monkeypatch.setattr(mail, "_caller_agent", lambda: "coordinator")
    reply = mail.send(to="fabrik", kind="reply", body="merged", frm="fabrik", re=parent.stem)
    assert _agent(reply) == "builder-tmpfix"
