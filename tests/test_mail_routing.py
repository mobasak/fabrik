"""Mail routing — the ownership map, the matcher, the trail and send (plan
docs/development/plans/2026-10-13-plan-1-mail-routing.md, Phase A; spec
docs/superpowers/specs/2026-10-13-mail-routing-design.md § The delta D1-D3, D7).

Every test runs against a scratch hub tree under ``FABRIK_OPT_ROOT`` and a scratch store
under ``FABRIK_MAIL_ROOT`` — no test reads the live map or touches the live mailboxes.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_MAIL_PY = _REPO / "scripts" / "mail.py"
_CHECK = _REPO / "scripts" / "enforcement" / "check_beat_owners.py"

spec = importlib.util.spec_from_file_location("fabrik_mail_routing", _MAIL_PY)
mail = importlib.util.module_from_spec(spec)
sys.modules["fabrik_mail_routing"] = mail
spec.loader.exec_module(mail)

HUB_FILES = (
    "scripts/mail.py",
    "scripts/sysadmin/dispatch_headroom.py",
    "scripts/review_loop_ledger.py",
    "templates/scaffold/app.py",
    "templates/governance/CLAUDE.md",
    "CLAUDE.md",
    "docs/reference/unowned.md",
)

RULES = [
    {
        "paths": ["scripts/**", "CLAUDE.md"],
        "topics": ["merge request"],
        "owner": "infra",
        "source": "D-815 (1)",
    },
    {"paths": ["templates/**"], "topics": ["redeploy"], "owner": "fleet", "source": "fleet.md:13"},
    {"paths": ["templates/governance/**"], "owner": "infra", "source": "D-815 (5)"},
    {
        "paths": ["scripts/review_loop_ledger.py"],
        "topics": ["benchmark"],
        "owner": "intel",
        "source": "D-815 (3)",
    },
]


def _write_map(opt: Path, rules=None, switches=None, version: int = 3) -> Path:
    path = opt / "fabrik" / ".fabrik" / "beat-owners.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": version,
        "switches": {"auto_address": False, "fabrik_lib_address": False, **(switches or {})},
        "rules": RULES if rules is None else rules,
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture()
def env(tmp_path, monkeypatch):
    mail_root = tmp_path / "mail"
    opt = tmp_path / "opt"
    mail_root.mkdir()
    for rel in HUB_FILES:
        f = opt / "fabrik" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"# hub {rel}\n", encoding="utf-8")
    hook = opt / "alpha" / ".claude" / "hooks" / "mail_notify.py"
    hook.parent.mkdir(parents=True)
    hook.write_text("# hook\n", encoding="utf-8")
    monkeypatch.setenv("FABRIK_MAIL_ROOT", str(mail_root))
    monkeypatch.setenv("FABRIK_OPT_ROOT", str(opt))
    monkeypatch.delenv("CLAUDE_AGENT", raising=False)
    monkeypatch.setattr(mail, "_current_repo", lambda: "fabrik")
    monkeypatch.setattr(mail, "_caller_agent", lambda: "infra")
    monkeypatch.setattr(mail, "_sender_role", lambda: "")
    _write_map(opt)
    return {"mail_root": mail_root, "opt": opt}


def _header(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    end = text.find("\n---", 4)
    return text[4:end].splitlines()


def _lines(path: Path, key: str) -> list[str]:
    return [ln for ln in _header(path) if ln.startswith(f"{key}:")]


# --- A1 (V1) — the routing trail ------------------------------------------------------------


def test_route_appends_a_trail_line_per_reroute(env):
    p = mail.send(to="fabrik", kind="finding", body="hello", frm="alpha", to_agent="fleet")
    mid = p.stem
    mail.route(mid, "intel", repo="fabrik", reason="it is the review loop")
    mail.route(mid, "kaizen", repo="fabrik")
    trail = _lines(p, "routed")
    assert len(trail) == 2
    assert trail[0].endswith("· infra · fleet → intel · it is the review loop")
    assert trail[1].endswith("· infra · intel → kaizen · (no reason)")
    assert mail._parse(p.read_text(encoding="utf-8"))["agent"] == "kaizen"
    assert mail._routed_lines(p.read_text(encoding="utf-8")) == trail


def test_route_reason_is_sanitised_to_one_line(env):
    p = mail.send(to="fabrik", kind="finding", body="hello", frm="alpha", to_agent="fleet")
    mail.route(p.stem, "intel", repo="fabrik", reason="a\nagent: x\u2028b · c\x1d" + "z" * 400)
    trail = _lines(p, "routed")
    assert len(trail) == 1
    assert not any(ln.startswith("agent: x") for ln in _header(p))
    reason = trail[0].split(" · ", 4)[-1]
    assert "·" not in reason and len(reason) <= 200
    assert reason.startswith("a agent: x b c")
    assert mail._parse(p.read_text(encoding="utf-8"))["agent"] == "intel"


# --- A2 (V3) — owner_of ---------------------------------------------------------------------


def test_last_matching_rule_wins_with_its_reason(env):
    r = mail.owner_of("see `templates/governance/CLAUDE.md`")
    assert (r.owner, r.owners) == ("infra", ["infra"])
    assert r.reason == "templates/governance/CLAUDE.md → D-815 (5)"
    assert r.map_version == "3"
    assert mail.owner_of("at scripts/review_loop_ledger.py:12").owner == "intel"
    assert mail.owner_of("`templates/scaffold/app.py`").owner == "fleet"


def test_two_owners_give_none_with_both(env):
    r = mail.owner_of("`scripts/mail.py` and `templates/scaffold/app.py:3-9`")
    assert r.owner is None
    assert r.owners == ["fleet", "infra"]


def test_dirs_missing_and_unowned_files_are_ignored(env):
    r = mail.owner_of("`scripts/sysadmin` `scripts/nope.py` `docs/reference/unowned.md` `mail.py`")
    assert (r.owner, r.owners, r.map_version) == (None, [], "3")


def test_star_stops_at_a_slash(env):
    _write_map(env["opt"], rules=[{"paths": ["scripts/*.py"], "owner": "infra", "source": "s"}])
    assert mail.owner_of("`scripts/sysadmin/dispatch_headroom.py`").owner is None
    assert mail.owner_of("`scripts/mail.py`").owner == "infra"
    assert mail._glob_re("scripts/**").fullmatch("scripts/a/b/c.py")
    assert not mail._glob_re("scripts/*.py").fullmatch("scripts/a/b.py")


def test_subject_topic_is_an_advisory_owner(env):
    r = mail.owner_of("Subject: please redeploy crm\n\nno paths here")
    assert r.owner == "fleet"
    assert r.reason.startswith("topic")
    assert mail.owner_of("Subject: nothing\n\nredeploy is in the body only").owner is None


def test_no_citation_and_bad_maps(env):
    assert mail.owner_of("plain words").owner is None
    path = env["opt"] / "fabrik" / ".fabrik" / "beat-owners.json"
    path.write_text("{not json", encoding="utf-8")
    assert mail.owner_of("`scripts/mail.py`") == mail.Routing(None, [], "", "")
    path.unlink()
    assert mail.owner_of("`scripts/mail.py`").map_version == ""


def test_absolute_hub_token_counts_for_every_sender(env):
    tok = f"{env['opt']}/fabrik/scripts/review_loop_ledger.py:4"
    assert mail.owner_of(f"at {tok}").owner == "intel"
    assert mail.owner_of(f"at {tok}", from_repo="alpha").owner == "intel"


def test_project_sender_own_files_are_not_hub_owned(env):
    proj = env["opt"] / "alpha"
    (proj / "CLAUDE.md").write_text("# alpha's own\n", encoding="utf-8")
    (proj / "scripts").mkdir()
    (proj / "scripts" / "mail.py").write_bytes(
        (env["opt"] / "fabrik" / "scripts" / "mail.py").read_bytes()
    )
    assert mail.owner_of("`CLAUDE.md`", from_repo="alpha").owner is None
    assert mail.owner_of("`scripts/mail.py`", from_repo="alpha").owner == "infra"  # synced copy
    assert mail.owner_of("`scripts/review_loop_ledger.py`", from_repo="alpha").owner == "intel"


def test_path_traversal_never_escapes_the_hub(env):
    (env["opt"] / "secret.py").write_text("x", encoding="utf-8")
    _write_map(env["opt"], rules=[{"paths": ["**"], "owner": "infra", "source": "s"}])
    assert mail.owner_of("`../secret.py`").owners == []


# --- A3 (V4) — automatic address, --to-agent map, fail-open ------------------------------------


def test_auto_address_off_refuses_as_today(env):
    with pytest.raises(mail.MailRefusedError, match="unaddressed hub-bound"):
        mail.send(to="fabrik", kind="finding", body="`scripts/mail.py`", frm="alpha")


def test_auto_address_on_addresses_paths_owner(env, capsys):
    _write_map(env["opt"], switches={"auto_address": True})
    p = mail.send(to="fabrik", kind="finding", body="`scripts/review_loop_ledger.py`", frm="alpha")
    fm = mail._parse(p.read_text(encoding="utf-8"))
    assert fm["agent"] == "intel"
    assert _lines(p, "routed")[0].split(" · ", 1)[1].startswith("map · - → intel · ownership map (")
    assert "addressed to intel by the ownership map" in capsys.readouterr().err
    for body in ("Subject: redeploy it\n\nx", "`scripts/mail.py` `templates/scaffold/app.py`"):
        with pytest.raises(mail.MailRefusedError, match="unaddressed hub-bound"):
            mail.send(to="fabrik", kind="finding", body=body, frm="alpha")


def test_no_map_refuses_and_writes_no_header(env):
    (env["opt"] / "fabrik" / ".fabrik" / "beat-owners.json").unlink()
    with pytest.raises(mail.MailRefusedError, match="unaddressed hub-bound"):
        mail.send(to="fabrik", kind="finding", body="`scripts/mail.py`", frm="alpha")
    p = mail.send(
        to="fabrik", kind="finding", body="`scripts/mail.py`", frm="alpha", to_agent="fleet"
    )
    assert not _lines(p, "map-owner") and not _lines(p, "routed")


def test_thread_reply_is_never_auto_addressed(env):
    _write_map(env["opt"], switches={"auto_address": True})
    parent = mail.send(to="fabrik", kind="finding", body="x", frm="alpha", broadcast=True, ack="no")
    p = mail.send(to="fabrik", kind="reply", body="`scripts/mail.py`", frm="alpha", re=parent.stem)
    assert "agent" not in mail._parse(p.read_text(encoding="utf-8"))
    assert not _lines(p, "routed")


def test_to_agent_map_addresses_with_the_switch_off(env):
    p = mail.send(
        to="fabrik", kind="finding", body="`scripts/mail.py`", frm="alpha", to_agent="map"
    )
    assert mail._parse(p.read_text(encoding="utf-8"))["agent"] == "infra"
    assert " · map · map → infra · ownership map (" in _lines(p, "routed")[0]
    for body in (
        "Subject: redeploy\n\nx",
        "`scripts/mail.py` `templates/scaffold/app.py`",
        "nothing",
    ):
        with pytest.raises(mail.MailRefusedError, match="--to-agent map"):
            mail.send(to="fabrik", kind="finding", body=body, frm="alpha", to_agent="map")


def test_to_agent_map_is_hub_only(env):
    with pytest.raises(mail.MailRefusedError, match="hub-mailbox name"):
        mail.send(
            to="fabrik-lib", kind="finding", body="`scripts/mail.py`", frm="alpha", to_agent="map"
        )


def test_a_raising_matcher_leaves_send_as_today(env, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("matcher fault")

    monkeypatch.setattr(mail, "owner_of", boom)
    _write_map(env["opt"], switches={"auto_address": True})
    with pytest.raises(mail.MailRefusedError, match="unaddressed hub-bound"):
        mail.send(to="fabrik", kind="finding", body="`scripts/mail.py`", frm="alpha")
    p = mail.send(
        to="fabrik", kind="finding", body="`scripts/mail.py`", frm="alpha", to_agent="fleet"
    )
    assert not _lines(p, "map-owner")
    with pytest.raises(mail.MailRefusedError, match="--to-agent map"):
        mail.send(
            to="fabrik", kind="finding", body="`scripts/mail.py`", frm="alpha", to_agent="map"
        )


def test_lane_from_name_is_not_the_sender_repo(env, monkeypatch):
    proj = env["opt"] / "alpha"
    (proj / "CLAUDE.md").write_text("# alpha's own\n", encoding="utf-8")
    monkeypatch.setattr(mail, "_current_repo", lambda: "alpha")
    p = mail.send(to="fabrik", kind="finding", body="`CLAUDE.md`", frm="wef1", to_agent="fleet")
    assert _lines(p, "map-owner")[0].startswith("map-owner: unmapped · v3")


# --- A4 (V4) — the advisory and the header ------------------------------------------------------


def test_explicit_mismatch_advises_inherited_does_not(env, capsys):
    p1 = mail.send(
        to="fabrik", kind="finding", body="`scripts/mail.py`", frm="alpha", to_agent="intel"
    )
    err = capsys.readouterr().err
    assert (
        "advisory: the ownership map names infra (scripts/mail.py → D-815 (1)); delivered to intel"
        in err
    )
    parent = mail.send(to="fabrik", kind="finding", body="q", frm="fabrik", to_agent="intel")
    capsys.readouterr()
    p2 = mail.send(
        to="fabrik", kind="reply", body="`scripts/mail.py`", frm="fabrik", re=parent.stem
    )
    assert "advisory" not in capsys.readouterr().err
    for p in (p1, p2):
        assert mail._parse(p.read_text(encoding="utf-8"))["agent"] == "intel"
        assert _lines(p, "map-owner") == ["map-owner: infra · v3 · scripts/mail.py → D-815 (1)"]


def test_header_shapes_mixed_and_unmapped(env):
    p = mail.send(
        to="fabrik",
        kind="finding",
        body="`scripts/mail.py` `templates/scaffold/app.py`",
        frm="alpha",
        to_agent="fleet",
    )
    assert _lines(p, "map-owner")[0].startswith("map-owner: mixed:fleet,infra · v3")
    p = mail.send(to="fabrik", kind="finding", body="none", frm="alpha", to_agent="fleet")
    assert _lines(p, "map-owner") == ["map-owner: unmapped · v3"]


# --- A5 (V2) — the validator --------------------------------------------------------------------


def _git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)


def _check(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_CHECK), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_validator_green_on_a_good_map_and_reports_unowned(env):
    hub = env["opt"] / "fabrik"
    _git_repo(hub)
    r = _check(hub)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "unowned: 2 of 8 tracked" in r.stdout


@pytest.mark.parametrize(
    ("rules", "switches", "needle"),
    [
        ([{"paths": ["scripts/**"], "owner": "devops", "source": "s"}], None, "unknown owner"),
        ([{"paths": ["scripts/**"], "owner": "infra"}], None, "missing source"),
        ([{"paths": ["scripts/[x"], "owner": "infra", "source": "s"}], None, "malformed pattern"),
        ([{"paths": ["nothing/**"], "owner": "infra", "source": "s"}], None, "dead pattern"),
        (
            [
                {"paths": ["templates/governance/**"], "owner": "infra", "source": "s"},
                {"paths": ["templates/**"], "owner": "fleet", "source": "s"},
            ],
            None,
            "shadowed",
        ),
        (None, {"auto_adress": True}, "unknown switch"),
    ],
)
def test_validator_refuses_each_defect(env, rules, switches, needle):
    hub = env["opt"] / "fabrik"
    _write_map(env["opt"], rules=rules, switches=switches)
    _git_repo(hub)
    r = _check(hub)
    assert r.returncode == 1, r.stdout + r.stderr
    assert needle in r.stdout


def test_validator_self_skips_without_a_map(tmp_path):
    _git_repo(tmp_path)
    r = _check(tmp_path)
    assert r.returncode == 0 and "no .fabrik/beat-owners.json" in r.stdout


# --- A6 (V9) — the fabrik-lib leg ---------------------------------------------------------------


def _lib(env) -> Path:
    lib = env["opt"] / "fabrik-lib"
    for mod in ("rag", "ocr", "payments", "doc-crawl"):
        (lib / mod).mkdir(parents=True)
        (lib / mod / "README.md").write_text("x", encoding="utf-8")
    owners = {
        "fabrik-lib-dev1": ["rag", "doc-crawl"],
        "fabrik-lib-dev2": ["payments"],
        "fabrik-lib-sentinel": ["ocr"],
    }
    (lib / ".fabrik").mkdir()
    (lib / ".fabrik" / "module-owners.json").write_text(
        json.dumps({"owners": owners}), encoding="utf-8"
    )
    return lib


def test_fabrik_lib_leg_only_with_the_switch_and_one_owner(env):
    _lib(env)
    single = "the `rag/rag/store.py:12` module is slow"
    p = mail.send(to="fabrik-lib", kind="finding", body=single, frm="alpha")
    assert "agent" not in mail._parse(p.read_text(encoding="utf-8"))
    _write_map(env["opt"], switches={"fabrik_lib_address": True})
    p = mail.send(to="fabrik-lib", kind="finding", body=single, frm="alpha")
    assert mail._parse(p.read_text(encoding="utf-8"))["agent"] == "fabrik-lib-dev1"
    assert " · map · - → fabrik-lib-dev1 · " in _lines(p, "routed")[0]
    p = mail.send(
        to="fabrik-lib",
        kind="finding",
        body=f"`{env['opt']}/fabrik-lib/ocr/README.md` and `rag/README.md`",
        frm="alpha",
    )
    assert "agent" not in mail._parse(p.read_text(encoding="utf-8"))
    p = mail.send(to="fabrik-lib", kind="finding", body="nothing named", frm="alpha")
    assert "agent" not in mail._parse(p.read_text(encoding="utf-8"))
    p = mail.send(
        to="fabrik-lib", kind="finding", body=single, frm="alpha", to_agent="fabrik-lib-sentinel"
    )
    assert mail._parse(p.read_text(encoding="utf-8"))["agent"] == "fabrik-lib-sentinel"
    assert not _lines(p, "routed")


def test_fabrik_lib_leg_never_addresses_a_reply_or_a_broadcast(env):
    """W-c687ce60: the hub leg spares a thread reply and a broadcast; the fabrik-lib leg did
    not, so a reply in a dev2 thread citing a dev1 module was re-addressed to dev1."""
    _lib(env)
    _write_map(env["opt"], switches={"fabrik_lib_address": True})
    body = "the `doc-crawl` module is slow"
    control = mail.send(to="fabrik-lib", kind="finding", body=body, frm="alpha")
    assert mail._parse(control.read_text(encoding="utf-8")).get("agent") == "fabrik-lib-dev1"
    p = mail.send(
        to="fabrik-lib", kind="reply", body=body, frm="alpha", re="01M4ZZZZZZZZZZZZZZZZZZZZZZ"
    )
    assert "agent" not in mail._parse(p.read_text(encoding="utf-8")), "a thread reply"
    p = mail.send(to="fabrik-lib", kind="finding", body=body, frm="alpha", broadcast=True, ack="no")
    assert "agent" not in mail._parse(p.read_text(encoding="utf-8")), "a broadcast"


def test_a_single_word_module_routes_only_as_a_path(env):
    """W-c687ce60: `account`, `storage` and `rag` are ordinary words — a bare backticked one is
    no evidence the mail is about that module. A path is; so is a hyphenated module name."""
    _lib(env)
    _write_map(env["opt"], switches={"fabrik_lib_address": True})

    def agent_of(body):
        p = mail.send(to="fabrik-lib", kind="finding", body=body, frm="alpha")
        return mail._parse(p.read_text(encoding="utf-8")).get("agent")

    assert agent_of("the `rag` cache is cold") is None, "a bare single word"
    assert agent_of("see `rag/rag/store.py:12`") == "fabrik-lib-dev1", "a relative module path"
    assert agent_of("the `doc-crawl` module") == "fabrik-lib-dev1", "a hyphenated module name"
    assert agent_of("the `doc-crawl/` dir") == "fabrik-lib-dev1", "a trailing slash"
    assert agent_of("`rag/` is slow") is None, "a single word with a slash is no path"
    assert agent_of("`rag`, `payments` and `ocr` are words here") is None


def test_fabrik_lib_leg_spares_threads_senders_and_their_own_folders(env, monkeypatch):
    """W-c687ce60 critiques: a threaded finding, the module's own author, the sender's own
    `rag/` folder and a `..` climb never address; a bare word naming a second owner unaddresses."""
    _lib(env)
    _write_map(env["opt"], switches={"fabrik_lib_address": True})

    def agent_of(body, frm="alpha", **kw):
        p = mail.send(to="fabrik-lib", kind="finding", body=body, frm=frm, **kw)
        return mail._parse(p.read_text(encoding="utf-8")).get("agent")

    path = "see `rag/rag/store.py:12`"
    assert agent_of(path) == "fabrik-lib-dev1", "control"
    assert agent_of(path, re="01M4ZZZZZZZZZZZZZZZZZZZZZZ") is None, "a threaded finding"
    assert agent_of("see `rag/../payments/x.py`") is None, "a `..` climb"
    assert agent_of("`rag/x.py` but the `payments` side too") is None, "a bare second owner"
    (env["opt"] / "beta" / "rag").mkdir(parents=True)
    (env["opt"] / "beta" / "payments").write_text("a file, not a folder", encoding="utf-8")
    with monkeypatch.context() as m:
        m.setattr(mail, "_current_repo", lambda: "beta")
        assert agent_of("see `payments/x.py`", frm="beta") == "fabrik-lib-dev2", "a file"
    with monkeypatch.context() as m:
        m.setattr(mail, "_current_repo", lambda: "beta")
        assert agent_of(path, frm="beta") is None, "the sender's own rag/ folder"
    assert agent_of(path) == "fabrik-lib-dev1", "control, after the sender-repo patch"
    monkeypatch.setattr(mail, "_sender_role", lambda: "fabrik-lib-dev1")
    assert agent_of(path) is None, "never the sender itself"


# --- review round 1 (Phase A scoped review) — each test is red on its defect ----------------------


@pytest.mark.parametrize(
    "bad_rule",
    [
        {
            "paths": "scripts/**",
            "owner": "infra",
            "source": "s",
        },  # a bare string iterates as characters
        {"paths": ["scripts/**"], "topics": "mesh", "owner": "infra", "source": "s"},
        {"paths": [5], "owner": "infra", "source": "s"},
        {"paths": ["scripts/**"], "topics": [""], "owner": "infra", "source": "s"},
    ],
)
def test_a_malformed_rule_makes_the_whole_map_invalid(env, bad_rule):
    _write_map(env["opt"], rules=[*RULES, bad_rule])
    assert mail.owner_of("Subject: a thing\n\n`scripts/mail.py`") == mail.Routing(None, [], "", "")
    p = mail.send(
        to="fabrik", kind="finding", body="`scripts/mail.py`", frm="alpha", to_agent="fleet"
    )
    assert not _lines(p, "map-owner")


def test_a_boolean_version_is_not_a_version(env):
    path = _write_map(env["opt"])
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = True
    path.write_text(json.dumps(data), encoding="utf-8")
    assert mail.owner_of("`scripts/mail.py`").map_version == ""


def test_a_deeply_nested_map_never_fails_a_send(env):
    path = env["opt"] / "fabrik" / ".fabrik" / "beat-owners.json"
    path.write_text("[" * 200000 + "]" * 200000, encoding="utf-8")
    p = mail.send(
        to="fabrik", kind="finding", body="`scripts/mail.py`", frm="alpha", to_agent="fleet"
    )
    assert p.is_file() and not _lines(p, "map-owner")


def test_dot_and_double_slash_tokens_match_the_specific_rule(env):
    for tok in (
        "scripts/./review_loop_ledger.py",
        "scripts//review_loop_ledger.py",
        "./scripts/review_loop_ledger.py",
    ):
        r = mail.owner_of(f"`{tok}`")
        assert (r.owner, r.reason) == ("intel", "scripts/review_loop_ledger.py → D-815 (3)"), tok


def test_glob_segment_class_and_anchor_semantics(env):
    assert not mail._pattern_matches("scripts/**.py", "scripts/a/b.py")
    assert mail._pattern_matches("scripts/**.py", "scripts/b.py")
    assert mail._pattern_matches("[!a]x.py", "bx.py") and not mail._pattern_matches(
        "[!a]x.py", "ax.py"
    )
    assert mail._pattern_matches("/scripts/mail.py", "scripts/mail.py")
    assert mail._pattern_matches("**/mail.py", "scripts/mail.py")
    assert mail._pattern_matches("scripts/**/x.py", "scripts/x.py")


def test_a_noop_route_writes_nothing(env):
    p = mail.send(to="fabrik", kind="finding", body="hello", frm="alpha", to_agent="intel")
    before = p.read_bytes()
    mail.route(p.stem, "intel", repo="fabrik", reason="same")
    assert p.read_bytes() == before
    mail.route(p.stem, "", repo="fabrik")
    mail.route(p.stem, "", repo="fabrik")
    assert len(_lines(p, "routed")) == 1


def test_an_unsafe_fabrik_lib_owner_key_is_never_written(env):
    lib = _lib(env)
    bad = {
        "owners": {"dev1\nack: no": ["rag"], "dev\u20282": ["ocr"], "fabrik-lib-dev2": ["payments"]}
    }
    (lib / ".fabrik" / "module-owners.json").write_text(json.dumps(bad), encoding="utf-8")
    _write_map(env["opt"], switches={"fabrik_lib_address": True})
    for body in ("`rag/x.py`", "`ocr/x.py`"):  # paths: a bare word no longer routes
        p = mail.send(to="fabrik-lib", kind="request", body=body, frm="alpha", ack="required")
        fm = mail._parse(p.read_text(encoding="utf-8"))
        assert "agent" not in fm and fm["ack"] == "required"
    p = mail.send(to="fabrik-lib", kind="request", body="`payments/x.py`", frm="alpha")
    assert mail._parse(p.read_text(encoding="utf-8"))["agent"] == "fabrik-lib-dev2"


@pytest.mark.parametrize(
    ("rules", "needle"),
    [
        ([{"paths": "scripts/**", "owner": "infra", "source": "s"}], "malformed paths"),
        (
            [{"paths": ["scripts/**"], "topics": "mesh", "owner": "infra", "source": "s"}],
            "malformed topics",
        ),
        (
            [{"paths": ["scripts/**"], "owner": ["infra"], "source": "s"}],
            "owner must be one beat name",
        ),
        (["not a rule"], "not an object"),
    ],
)
def test_validator_refuses_malformed_shapes(env, rules, needle):
    hub = env["opt"] / "fabrik"
    _write_map(env["opt"], rules=rules)
    _git_repo(hub)
    r = _check(hub)
    assert r.returncode == 1 and needle in r.stdout, r.stdout


def test_validator_without_git_is_a_defect(env, monkeypatch):
    hub = env["opt"] / "fabrik"
    _git_repo(hub)
    r = subprocess.run(
        [sys.executable, str(_CHECK), "--root", str(hub)],
        capture_output=True,
        text=True,
        timeout=60,
        env={"PATH": str(env["opt"])},
    )
    assert r.returncode == 1 and "git ls-files failed" in r.stdout, r.stdout + r.stderr


def test_one_send_reads_the_map_once(env, monkeypatch):
    _write_map(env["opt"], switches={"auto_address": True})
    calls = []
    real = mail._load_map
    monkeypatch.setattr(mail, "_load_map", lambda: calls.append(1) or real())
    p = mail.send(to="fabrik", kind="finding", body="`scripts/review_loop_ledger.py`", frm="alpha")
    assert mail._parse(p.read_text(encoding="utf-8"))["agent"] == "intel"
    assert len(calls) == 1


def test_a_root_only_pattern_is_not_a_catch_all(env):
    assert not mail._pattern_matches("/", "scripts/mail.py")
    assert mail._pattern_matches("/**", "scripts/mail.py")  # an explicit catch-all stays one


@pytest.mark.parametrize(
    ("pattern", "needle"),
    [
        ("/", "malformed pattern"),
        ("", "malformed pattern"),
        ("**", "catch-all owner"),
        ("/**", "catch-all owner"),
        ("*", "catch-all owner"),
        ("**/*", "catch-all owner"),
        ("**/**", "catch-all owner"),
    ],
)
def test_validator_refuses_a_catch_all_or_empty_pattern(env, pattern, needle):
    hub = env["opt"] / "fabrik"
    _write_map(env["opt"], rules=[{"paths": [pattern], "owner": "infra", "source": "s"}])
    _git_repo(hub)
    r = _check(hub)
    assert r.returncode == 1 and needle in r.stdout, r.stdout


def test_validator_refuses_a_catch_all_split_across_patterns_but_not_a_complete_map(env):
    hub = env["opt"] / "fabrik"
    _write_map(env["opt"], rules=[{"paths": ["/*", "*/**"], "owner": "infra", "source": "s"}])
    _git_repo(hub)
    r = _check(hub)
    assert r.returncode == 1 and "catch-all owner" in r.stdout, r.stdout
    _write_map(
        env["opt"],
        rules=[
            {"paths": ["/*"], "owner": "infra", "source": "s"},
            {"paths": ["*/**"], "owner": "fleet", "source": "s"},
        ],
    )
    r = _check(hub)
    assert r.returncode == 0 and "unowned: 0 of" in r.stdout, r.stdout


def test_validator_refuses_one_owner_split_across_rules(env):
    hub = env["opt"] / "fabrik"
    _write_map(
        env["opt"],
        rules=[
            {"paths": ["/*"], "owner": "infra", "source": "s"},
            {"paths": ["*/**"], "owner": "infra", "source": "s"},
        ],
    )
    _git_repo(hub)
    r = _check(hub)
    assert r.returncode == 1 and "catch-all owner 'infra'" in r.stdout, r.stdout


def test_a_conflicted_path_is_counted_once(env):
    hub = env["opt"] / "fabrik"
    _write_map(env["opt"], rules=[{"paths": ["**"], "owner": "infra", "source": "s"}])
    _git_repo(hub)
    blob = subprocess.run(
        ["git", "-C", str(hub), "hash-object", "-w", str(hub / "CLAUDE.md")],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    stages = "".join(f"100644 {blob} {n}\tCLAUDE.md\n" for n in (1, 2, 3))
    subprocess.run(["git", "-C", str(hub), "rm", "-q", "--cached", "CLAUDE.md"], check=True)
    subprocess.run(
        ["git", "-C", str(hub), "update-index", "--index-info"], input=stages, text=True, check=True
    )
    r = _check(hub)
    assert r.returncode == 1 and "catch-all owner 'infra'" in r.stdout, r.stdout
    assert "of 8 tracked" in r.stdout, r.stdout


def test_validator_survives_a_non_utf8_filename(env):
    hub = env["opt"] / "fabrik"
    with open(str(hub).encode() + b"/caf\xe9.txt", "wb") as fh:
        fh.write(b"x")
    _git_repo(hub)
    r = _check(hub)
    assert "Traceback" not in r.stderr, r.stderr
    assert "map OK" in r.stdout or "defect" in r.stdout, r.stdout


# --- Phase B — read, claim, report (spec D4, D5) ---------------------------------------------


def _hub_msg(
    env,
    mid: str,
    *,
    agent="",
    owner_line="",
    sub="inbox",
    ts="2026-10-13T00:00:00+00:00",
    kind="finding",
    re_="",
    from_agent="",
    extra=(),
):
    d = env["mail_root"] / "fabrik" / sub
    d.mkdir(parents=True, exist_ok=True)
    lines = [
        f"id: {mid}",
        "from: alpha",
        "to: fabrik",
        f"ts: {ts}",
        f"re: {re_}",
        f"kind: {kind}",
        "ack: required",
        "hops: 0",
    ]
    if agent:
        lines.append(f"agent: {agent}")
    if from_agent:
        lines.append(f"from-agent: {from_agent}")
    lines += list(extra)
    if owner_line:
        lines.append(f"map-owner: {owner_line}")
    p = d / f"{mid}.md"
    p.write_text("---\n" + "\n".join(lines) + "\n---\nSubject: x\n", encoding="utf-8")
    return p


_IDS = [
    "01M4TA00000000000000000001",
    "01M4TA00000000000000000002",
    "01M4TA00000000000000000003",
    "01M4TA00000000000000000004",
    "01M4TA00000000000000000005",
]


def test_list_marks_the_map_owner_from_the_header(env):
    _hub_msg(env, _IDS[0], agent="infra", owner_line="infra · v1 · scripts/mail.py → s")
    _hub_msg(env, _IDS[1], agent="intel", owner_line="infra · v1 · scripts/mail.py → s")
    _hub_msg(env, _IDS[2], agent="fleet", owner_line="mixed:fleet,infra · v1")
    _hub_msg(env, _IDS[3], agent="fleet", owner_line="unmapped · v1")
    _hub_msg(env, _IDS[4], agent="fleet")
    notes = {fm["id"]: fm["map_note"] for fm in mail.list_msgs("fabrik")}
    assert [notes[i] for i in _IDS] == [
        "",
        "→ map: infra",
        "→ mixed: fleet,infra",
        "→ unmapped",
        "",
    ]
    infra = {fm["id"]: fm.get("map_match", False) for fm in mail.list_msgs("fabrik", agent="infra")}
    assert infra == {_IDS[0]: False, _IDS[1]: True}


def test_a_forged_map_owner_header_shows_nothing(env):
    _hub_msg(env, _IDS[0], agent="intel", owner_line="infra-ops · v1")
    _hub_msg(env, _IDS[1], agent="intel", owner_line="mixed:infra,devops · v1")
    assert [fm["map_note"] for fm in mail.list_msgs("fabrik")] == ["", ""]


def test_cli_list_prints_the_note_and_the_map_mark(env, capsys):
    _hub_msg(env, _IDS[1], agent="intel", owner_line="infra · v1 · scripts/mail.py → s")
    assert mail.main(["list", "--repo", "fabrik", "--agent", "infra"]) == 0
    out = capsys.readouterr().out
    assert "@intel → map: infra (map)" in out


def test_claim_by_a_non_owner_advises_and_still_claims(env, capsys, monkeypatch):
    p = _hub_msg(env, _IDS[1], agent="intel", owner_line="infra · v1 · scripts/mail.py → s")
    before = p.read_bytes()
    monkeypatch.setattr(mail, "_caller_agent", lambda: "intel")
    real_rename = mail.os.rename

    def lose(src, dst):
        raise FileNotFoundError("a peer claimed it first")

    monkeypatch.setattr(mail.os, "rename", lose)
    with pytest.raises(FileNotFoundError):
        mail.claim(_IDS[1], "fabrik")
    assert "advisory" not in capsys.readouterr().err  # a loser never says it claimed
    monkeypatch.setattr(mail.os, "rename", real_rename)
    dst = mail.claim(_IDS[1], "fabrik")
    assert "advisory: the ownership map names infra" in capsys.readouterr().err
    assert dst.read_bytes() == before
    p2 = _hub_msg(env, _IDS[2], agent="intel", owner_line="intel · v1 · x → s")
    mail.claim(_IDS[2], "fabrik")
    assert "advisory" not in capsys.readouterr().err
    assert not p2.exists()


def _route_line(frm: str, to: str, by: str = "kaizen") -> str:
    return f"routed: 2026-10-13T01:00:00+00:00 · {by} · {frm} → {to} · r"


def test_route_report_counts_with_numerators_and_denominators(env):
    import datetime as _dt

    now = _dt.datetime.now(_dt.UTC)
    ts = (now - _dt.timedelta(hours=3)).isoformat()
    old = (now - _dt.timedelta(days=400)).isoformat()
    first = (now - _dt.timedelta(hours=2)).isoformat()
    later = (now - _dt.timedelta(hours=1)).isoformat()
    m0, m1, m2, m3, m4 = _IDS
    m5 = "01M4TA00000000000000000006"
    # m0: addressed intel, map infra, re-routed to infra; first answer from infra
    _hub_msg(
        env,
        m0,
        agent="infra",
        owner_line="infra · v1 · a → s",
        sub="archive",
        ts=ts,
        extra=[_route_line("intel", "infra")],
    )
    # m1: addressed fleet, map infra, kept; first answer from fleet (a project mailbox),
    # a later answer with no readable ts from infra is skipped
    _hub_msg(env, m1, agent="fleet", owner_line="infra · v1 · a → s", ts=ts)
    # m2: agrees with the map; its send-time map line is not a receiver re-route
    _hub_msg(
        env,
        m2,
        agent="intel",
        owner_line="intel · v1 · a → s",
        ts=ts,
        extra=["routed: 2026-10-13T00:00:00+00:00 · map · map → intel · ownership map (a)"],
    )
    # m3: addressed kaizen, map infra, moved to infra then away to fleet: judged by the LAST move
    _hub_msg(
        env,
        m3,
        agent="fleet",
        owner_line="infra · v1 · a → s",
        ts=ts,
        extra=[_route_line("kaizen", "infra"), _route_line("infra", "fleet")],
    )
    # m4: sent unaddressed, then given a first address by a receiver — that is the first
    # addressee, not a re-route; map infra, so it differed and was kept
    _hub_msg(
        env,
        m4,
        agent="fleet",
        owner_line="infra · v1 · a → s",
        ts=ts,
        extra=[_route_line("-", "fleet")],
    )
    # m6: still unaddressed: no sender address to measure
    _hub_msg(env, "01M4TA00000000000000000007", owner_line="infra · v1 · a → s", ts=ts)
    # m5: older than --days
    _hub_msg(env, m5, agent="intel", owner_line="infra · v1 · a → s", ts=old)
    # a dotfile copy of m1 is not a message
    arch = env["mail_root"] / "fabrik" / "archive"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / f".{m1}.md").write_text(
        (env["mail_root"] / "fabrik" / "inbox" / f"{m1}.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _hub_msg(
        env,
        "01M4TA00000000000000000009",
        kind="reply",
        re_=m0,
        from_agent="infra",
        sub="archive",
        ts=first,
    )
    proj = env["mail_root"] / "alpha" / "inbox"
    proj.mkdir(parents=True)
    for rid, who, when in (("A", "fleet", first), ("B", "infra", "garbage"), ("C", "intel", later)):
        (proj / f"01M4TA000000000000000000R{rid}.md").write_text(
            f"---\nid: 01M4TA000000000000000000R{rid}\nfrom: fabrik\nto: alpha\nts: {when}\n"
            f"re: {m1}\nkind: reply\nack: no\nhops: 1\nfrom-agent: {who}\n---\nok\n",
            encoding="utf-8",
        )
    text = "\n".join(mail.route_report(days=30))
    assert "hub mail, last 30 days: 6 (replies excluded), 5 addressed" in text, text
    assert "map differed from the first addressee: 4 of 5" in text
    assert "re-routed to the map owner: 1 of 4" in text
    assert "re-routed elsewhere: 1 of 4" in text
    assert "kept: 2 of 4" in text
    assert "first reply from the map owner: 1 of 2" in text
    assert "first reply from the first addressee: 1 of 2" in text
    assert "re-routed by a receiver (addressed hub mail): 2 of 5" in text


def test_list_agent_marks_unaddressed_map_mail_and_hides_repeated_mixed(env):
    _hub_msg(env, _IDS[0], owner_line="infra · v1 · a → s")
    _hub_msg(env, _IDS[1], agent="intel", owner_line="mixed:infra,infra · v1")
    rows = {fm["id"]: fm for fm in mail.list_msgs("fabrik", agent="infra")}
    assert rows[_IDS[0]].get("map_match") is True
    assert _IDS[1] not in rows
    assert {fm["id"]: fm["map_note"] for fm in mail.list_msgs("fabrik")}[_IDS[1]] == ""


def test_route_by_a_caller_named_map_is_still_a_receiver_move(env, monkeypatch):
    p = mail.send(to="fabrik", kind="finding", body="hello", frm="alpha", to_agent="fleet")
    monkeypatch.setattr(mail, "_caller_agent", lambda: "map")
    mail.route(p.stem, "intel", repo="fabrik")
    assert " · agent-map · fleet → intel · " in _lines(p, "routed")[0]


def test_route_report_first_answer_is_any_from_agent(env):
    import datetime as _dt

    now = _dt.datetime.now(_dt.UTC)
    _hub_msg(env, _IDS[0], agent="fleet", owner_line="infra · v1 · a → s", ts=now.isoformat())
    for rid, who, hrs in (("A", "wa1", 1), ("B", "infra", 2)):
        _hub_msg(
            env,
            f"01M4TA000000000000000000R{rid}",
            kind="reply",
            re_=_IDS[0],
            from_agent=who,
            sub="archive",
            ts=(now + _dt.timedelta(hours=hrs)).isoformat(),
        )
    text = "\n".join(mail.route_report(days=30))
    assert "first reply from the map owner: 0 of 1" in text, text


def test_route_report_with_no_mail_root_is_all_zero(env, monkeypatch):
    monkeypatch.setenv("FABRIK_MAIL_ROOT", str(env["mail_root"] / "nowhere"))
    assert (
        mail.route_report(days=30)[0] == "hub mail, last 30 days: 0 (replies excluded), 0 addressed"
    )


def test_route_report_ignores_a_topic_owner(env):
    import datetime as _dt

    ts = _dt.datetime.now(_dt.UTC).isoformat()
    _hub_msg(env, _IDS[0], agent="infra", owner_line='fleet · v1 · topic "redeploy"', ts=ts)
    _hub_msg(env, _IDS[1], agent="intel", owner_line="infra · v1 · a → s", ts=ts)
    text = "\n".join(mail.route_report(days=30))
    assert "map differed from the first addressee: 1 of 1" in text, text


def test_a_path_named_topic_is_still_a_path_owner(env):
    (env["opt"] / "fabrik" / "topics.md").write_text("x", encoding="utf-8")
    _write_map(env["opt"], rules=[{"paths": ["topics.md"], "owner": "fleet", "source": "s"}])
    r = mail.owner_of("`topics.md`")
    assert (r.owner, r.reason) == ("fleet", "topics.md → s")
    p = mail.send(to="fabrik", kind="finding", body="`topics.md`", frm="alpha", to_agent="map")
    assert mail._parse(p.read_text(encoding="utf-8"))["agent"] == "fleet"


def test_a_send_with_no_map_reads_the_map_once(env, monkeypatch):
    (env["opt"] / "fabrik" / ".fabrik" / "beat-owners.json").unlink()
    calls = []
    real = mail._load_map
    monkeypatch.setattr(mail, "_load_map", lambda: calls.append(1) or real())
    mail.send(to="fabrik", kind="finding", body="`scripts/mail.py`", frm="alpha", to_agent="fleet")
    assert len(calls) == 1


def test_route_never_resurrects_a_message_claimed_mid_route(env, monkeypatch):
    p = mail.send(to="fabrik", kind="finding", body="hello", frm="alpha", to_agent="fleet")
    archive = env["mail_root"] / "fabrik" / "archive"
    real_write = Path.write_text

    def claim_during_write(self, *a, **k):
        out = real_write(self, *a, **k)
        if ".routing." in self.name and p.exists():
            archive.mkdir(parents=True, exist_ok=True)
            p.rename(archive / p.name)  # a concurrent claim wins here
        return out

    monkeypatch.setattr(Path, "write_text", claim_during_write)
    with pytest.raises(mail.MailRefusedError, match="claimed while it was being routed"):
        mail.route(p.stem, "intel", repo="fabrik")
    monkeypatch.undo()
    assert not p.exists() and (archive / p.name).exists()
    assert not list((env["mail_root"] / "fabrik" / "inbox").glob("*.routing.*"))
