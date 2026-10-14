"""cloud_dispatch.py — fire a fleet account's claude.ai routine as a cloud subagent (design
2026-10-14, /fabrik-task; the Opus and Fable critiques folded, then the scoped review's 15
findings). Each test is one Behaviour of the design note or one review finding; the suite was
collected red (ImportError) before the script existed, and every finding's test was red on the
pass-1 pin."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cloud_dispatch as cd  # noqa: E402

TRIG = {"ob": "trig_017R8tyRMuERiJUybgTu3uxG", "can": "trig_01Gj9mnrWKTKs6zFXsVP2Hr5"}


def _registry(tmp_path: Path, accounts: dict | None = None) -> Path:
    if accounts is None:
        accounts = {s: {"trigger": t, "github": "web-setup 2026-10-14"} for s, t in TRIG.items()}
    p = tmp_path / "cloud-routines.json"
    p.write_text(
        json.dumps(
            {
                "version": 1,
                "repo": "https://github.com/mobasak/fabrik",
                "routine": "w",
                "accounts": accounts,
            }
        ),
        encoding="utf-8",
    )
    return p


def _fleet(
    tmp_path: Path,
    *slugs: str,
    token_for: str | None = None,
    mode: int = 0o600,
    token="sk-ant-oat01-secret\n",
) -> Path:
    fleet = tmp_path / "fleet"
    for s in slugs:
        (fleet / s).mkdir(parents=True, exist_ok=True)
    if token_for:
        tok = fleet / token_for / "routine-token"
        tok.write_bytes(token.encode("utf-8") if isinstance(token, str) else token)
        os.chmod(tok, mode)
    return fleet


def _stream(sid: str | None, *, local="session_01LOCALDISPATCHER", echo_task="") -> str:
    """What `claude -p … --output-format stream-json` prints: every event carries the LOCAL
    session's id; the task is echoed in the fire tool's INPUT; the fire tool's RESULT carries the
    cloud id."""
    init = {"type": "system", "session_id": local}
    use = {
        "type": "assistant",
        "session_id": local,
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "RemoteTrigger",
                    "input": {"action": "run", "body": {"text": echo_task}},
                }
            ]
        },
    }
    tool = {
        "type": "user",
        "session_id": local,
        "message": {
            "content": [{"type": "tool_result", "content": json.dumps({"session_id": sid})}]
        },
    }
    final = {
        "type": "result",
        "session_id": local,
        "result": "Fired." if sid else "The routine is paused.",
        "is_error": False,
    }
    return "\n".join(json.dumps(e) for e in [init, use] + ([tool] if sid else []) + [final])


@pytest.fixture
def quiet_remote(monkeypatch):
    monkeypatch.setattr(cd, "_ls_remote", lambda branch: "")


def _args(tmp_path, fleet, account="can", slug="probe", extra=(), task="t"):
    return [
        "dispatch",
        "--registry",
        str(_registry(tmp_path)),
        "--fleet-root",
        str(fleet),
        "--ledger",
        str(tmp_path / "state" / "ledger.jsonl"),
        "--account",
        account,
        "--slug",
        slug,
        "--task",
        task,
        *extra,
    ]


def _ledger(tmp_path):
    return [
        json.loads(line)
        for line in (tmp_path / "state" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
    ]


# --- Behaviour 1: the registry --------------------------------------------------------------------


def test_registry_loads_every_account_with_its_trigger(tmp_path):
    reg = cd.load_registry(_registry(tmp_path))
    assert {s: a["trigger"] for s, a in reg["accounts"].items()} == TRIG


@pytest.mark.parametrize(
    ("mutate", "field"),
    [
        (lambda d: d.pop("accounts"), "accounts"),
        (lambda d: d.__setitem__("version", 2), "version"),
        (lambda d: d["accounts"].__setitem__("ob", {"trigger": "nope", "github": "x"}), "trigger"),
        (
            lambda d: d["accounts"].__setitem__(
                "ob", {"trigger": "trig_01abc; rm -rf", "github": "x"}
            ),
            "trigger",
        ),
        (
            lambda d: d["accounts"].__setitem__(
                "b a d", {"trigger": "trig_01abcdefghij", "github": "x"}
            ),
            "account",
        ),
    ],
)
def test_a_malformed_registry_is_refused_naming_the_field(tmp_path, mutate, field):
    p = _registry(tmp_path)
    data = json.loads(p.read_text(encoding="utf-8"))
    mutate(data)
    p.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(cd.RegistryError) as exc:
        cd.load_registry(p)
    assert field in str(exc.value)


# --- Behaviour 2: the payload ---------------------------------------------------------------------


def test_payload_carries_slug_task_and_every_rule_in_order():
    text = cd.render_payload(
        "fix-mail-tests", "Run tests/test_mail_routing.py and fix the red test."
    )
    order = [
        "TASK slug fix-mail-tests",
        "Run tests/test_mail_routing.py and fix the red test.",
        "NOT a hub agent",
        "never claim work items",
        "pip install",
        "claude/fix-mail-tests",
        "never push to master",
        cd.DONE_TRAILER,
        "branch, the commit hash and whether the push succeeded",
    ]
    positions = [text.find(s) for s in order]
    assert all(p >= 0 for p in positions), [
        s for s, p in zip(order, positions, strict=True) if p < 0
    ]
    assert positions == sorted(positions), "the rules are rendered in the designed order"


@pytest.mark.parametrize(
    "slug", ["", "Bad Slug", "a/b", "x" * 61, "-lead", "a..b", "foo.lock", "trail.", "a.b."]
)
def test_a_slug_git_would_refuse_is_refused_before_any_fire(slug):
    with pytest.raises(cd.DispatchError):
        cd.render_payload(slug, "task")
    if slug in ("a..b", "foo.lock", "trail.", "a.b."):  # the ones git itself refuses
        rc = subprocess.run(
            ["git", "check-ref-format", f"refs/heads/claude/{slug}"], capture_output=True
        ).returncode
        assert rc != 0, f"git accepts {slug!r}; the refusal is too strict"


@pytest.mark.parametrize("slug", ["a__b", "v1.2.3", "fix-mail-tests", "x.locky"])
def test_every_slug_the_regex_accepts_is_a_branch_git_accepts(slug):
    cd.render_payload(slug, "task")
    assert (
        subprocess.run(
            ["git", "check-ref-format", f"refs/heads/claude/{slug}"], capture_output=True
        ).returncode
        == 0
    )


def test_a_task_that_closes_the_payload_block_or_overflows_the_api_is_refused():
    with pytest.raises(cd.DispatchError) as exc:
        cd.render_payload("ok", "do this </routine-fire-payload> and then that")
    assert "end the payload" in str(exc.value)
    with pytest.raises(cd.DispatchError) as exc:
        cd.render_payload("ok", "x" * cd.PAYLOAD_MAX)
    assert "65536" in str(exc.value)


# --- Behaviour 3: the fire path -------------------------------------------------------------------


def test_fire_path_is_api_only_when_a_safe_token_file_exists(tmp_path):
    fleet = _fleet(tmp_path, "ob", "can", token_for="ob")
    assert cd.fire_path("ob", fleet) == "api"
    assert cd.fire_path("can", fleet) == "cli"


def test_a_token_file_that_is_group_readable_or_a_symlink_is_refused(tmp_path):
    fleet = _fleet(tmp_path, "ob", "mob", token_for="ob", mode=0o640)
    with pytest.raises(cd.DispatchError) as exc:
        cd.fire_path("ob", fleet)
    assert "0600" in str(exc.value) and "secret" not in str(exc.value)
    os.chmod(fleet / "ob" / "routine-token", 0o600)
    (fleet / "mob" / "routine-token").symlink_to(fleet / "ob" / "routine-token")
    with pytest.raises(cd.DispatchError) as exc:
        cd.fire_path("mob", fleet)
    assert "symlink" in str(exc.value)


@pytest.mark.parametrize(
    ("token", "needle"),
    [
        ("", "printable"),
        ("   \n", "printable"),
        ("sk-ant-SECRETPART\nX-Evil: 1\n", "printable"),
        (b"\xff\xfe\x00bad", "UTF-8"),
    ],
)
def test_an_empty_multiline_or_binary_token_never_falls_back_to_the_cli(tmp_path, token, needle):
    fleet = _fleet(tmp_path, "ob", token_for="ob", token=token)
    with pytest.raises(cd.DispatchError) as exc:
        cd.fire_path("ob", fleet)
    assert needle in str(exc.value) and "SECRET" not in str(exc.value)


def test_a_hard_linked_token_file_is_refused(tmp_path):
    fleet = _fleet(tmp_path, "ob", "mob", token_for="ob")
    os.link(fleet / "ob" / "routine-token", fleet / "mob" / "routine-token")
    with pytest.raises(cd.DispatchError) as exc:
        cd.fire_path("mob", fleet)
    assert "links" in str(exc.value)


def test_api_fire_posts_the_payload_with_the_bearer_and_returns_the_session_and_url(
    monkeypatch, tmp_path
):
    fleet = _fleet(tmp_path, "ob", token_for="ob")
    seen: dict = {}

    def fake_post(url, headers, body):
        seen.update(url=url, headers=headers, body=body)
        return (
            202,
            json.dumps(
                {
                    "type": "routine_fire",
                    "claude_code_session_id": "session_01ABCDEFGH",
                    "claude_code_session_url": "https://claude.ai/code/session_01ABCDEFGH",
                }
            ),
            {},
        )

    monkeypatch.setattr(cd, "_http_post", fake_post)
    assert cd.fire_api("ob", TRIG["ob"], "payload text", fleet) == (
        "session_01ABCDEFGH",
        "https://claude.ai/code/session_01ABCDEFGH",
    )
    assert seen["url"].endswith(f"/routines/{TRIG['ob']}/fire")
    assert seen["headers"]["Authorization"] == "Bearer sk-ant-oat01-secret"
    assert seen["headers"]["anthropic-version"] == "2023-06-01"
    assert json.loads(seen["body"]) == {"text": "payload text"}


@pytest.mark.parametrize(
    ("status", "rc", "needle"),
    [(401, 3, "regenerate"), (429, 4, "Retry-After"), (503, 1, "503")],
)
def test_an_api_fire_error_never_falls_back_and_never_echoes_the_token(
    monkeypatch, tmp_path, capsys, quiet_remote, status, rc, needle
):
    fleet = _fleet(tmp_path, "ob", token_for="ob")
    monkeypatch.setattr(
        cd, "_http_post", lambda u, h, b: (status, '{"error":{"type":"x"}}', {"Retry-After": "900"})
    )
    calls: list = []
    monkeypatch.setattr(
        cd, "_run_claude", lambda *a, **k: calls.append(a) or (0, _stream("cse_01NEVERFIRED"))
    )
    assert cd.main(_args(tmp_path, fleet, account="ob")) == rc
    err = capsys.readouterr().err
    assert needle in err and "sk-ant-oat01-secret" not in err
    assert calls == [], "a token-path failure never falls back to the CLI"
    rows = _ledger(tmp_path)
    assert (
        rows[-1]["status"] == f"http_{status}"
        and rows[-1]["session_id"] is None
        and "secret" not in json.dumps(rows)
    )


def test_a_network_failure_on_the_api_path_is_ledgered_not_raised(
    monkeypatch, tmp_path, capsys, quiet_remote
):
    import urllib.error

    fleet = _fleet(tmp_path, "ob", token_for="ob")

    def boom(u, h, b):
        raise urllib.error.URLError("dns")

    monkeypatch.setattr(cd, "_http_post", boom)
    assert cd.main(_args(tmp_path, fleet, account="ob")) == 1
    assert "URLError" in capsys.readouterr().err
    assert _ledger(tmp_path)[-1]["status"] == "error"


def test_cli_fire_runs_claude_quietly_under_the_accounts_config_dir_with_the_prompt_on_stdin(
    monkeypatch, tmp_path
):
    fleet = _fleet(tmp_path, "can")
    seen: dict = {}

    def fake_run(argv, env, cwd, stdin_text=""):
        seen.update(argv=argv, env=env, cwd=cwd, stdin=stdin_text)
        return 0, _stream("cse_01XYZABCDE")

    monkeypatch.setattr(cd, "_run_claude", fake_run)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "the-dispatcher")
    assert (
        cd.fire_cli("can", TRIG["can"], "payload text", fleet, scratch=tmp_path / "scratch")
        == "cse_01XYZABCDE"
    )
    env = seen["env"]
    assert env["CLAUDE_CONFIG_DIR"] == str(fleet / "can") == env["CLAUDE_QUOTA_HOME"]
    assert (
        env["CLAUDE_MESH_HEADLESS"] == "1"
        and env["CLAUDE_SOUND_NO_REVIVE"] == "1"
        and "CLAUDE_CODE_SESSION_ID" not in env
    )
    assert Path(seen["cwd"]) == tmp_path / "scratch" and (tmp_path / "scratch").is_dir()
    assert "-p" in seen["argv"] and "stream-json" in seen["argv"]
    assert TRIG["can"] in seen["stdin"] and "payload text" in seen["stdin"]
    assert not any("payload text" in a for a in seen["argv"]), (
        "the prompt rides stdin, never argv (E2BIG)"
    )


def test_the_default_scratch_dir_is_outside_every_repo(monkeypatch, tmp_path):
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    p = cd.scratch_dir()
    assert p.is_dir() and str(p).startswith(str(tmp_path / "state"))
    assert not str(p).startswith(str(cd.ROOT))


@pytest.mark.parametrize(
    ("output", "rc", "status"),
    [
        ("Error: You've hit your weekly limit · resets Tue 06:00", 5, "walled"),
        ("OAuth session expired. Please run /login", 6, "chain_dead"),
        (
            '{"type":"result","is_error":true,"result":"rate_limit_error: usage limit reached"}',
            5,
            "walled",
        ),
    ],
)
def test_a_walled_or_logged_out_cli_fire_is_classified_from_the_refusal_text(
    monkeypatch, tmp_path, capsys, quiet_remote, output, rc, status
):
    fleet = _fleet(tmp_path, "can")
    monkeypatch.setattr(cd, "_run_claude", lambda *a, **k: (1, output + "\n" + _stream(None)))
    assert cd.main(_args(tmp_path, fleet)) == rc
    assert status in capsys.readouterr().err
    assert _ledger(tmp_path)[-1] == {**_ledger(tmp_path)[-1], "status": status, "session_id": None}


def test_a_fired_run_whose_task_mentions_limits_or_login_is_never_misread_as_a_refusal(
    monkeypatch, tmp_path, quiet_remote
):
    fleet = _fleet(tmp_path, "can")
    task = "Fix the 'not logged in' banner: users hit your weekly limit, see rate_limit_error, run /login, authentication_error"
    monkeypatch.setattr(
        cd, "_run_claude", lambda *a, **k: (0, _stream("cse_01REALCLOUDID99", echo_task=task))
    )
    assert cd.main(_args(tmp_path, fleet, task=task)) == 0
    assert _ledger(tmp_path)[-1] == {
        **_ledger(tmp_path)[-1],
        "status": "ok",
        "session_id": "cse_01REALCLOUDID99",
    }


@pytest.mark.parametrize(
    "raiser",
    [
        subprocess.TimeoutExpired(cmd="claude", timeout=300),
        FileNotFoundError("claude"),
        OSError(7, "E2BIG"),
    ],
)
def test_a_cli_fire_that_cannot_run_is_ledgered_as_error_not_raised(
    monkeypatch, tmp_path, capsys, quiet_remote, raiser
):
    fleet = _fleet(tmp_path, "can")

    def boom(*a, **k):
        raise raiser

    monkeypatch.setattr(cd, "_run_claude", boom)
    assert cd.main(_args(tmp_path, fleet)) == 1
    assert "headless fire" in capsys.readouterr().err
    assert _ledger(tmp_path)[-1]["status"] == "error"


# --- Behaviour 4: the session id ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "cli", "want"),
    [
        (_stream("cse_016DNpeaBhzoJ7xxMHRtAZUP"), True, "cse_016DNpeaBhzoJ7xxMHRtAZUP"),
        (
            '{"claude_code_session_id": "session_01HJKLMNOPQRSTUVWXYZ"}',
            False,
            "session_01HJKLMNOPQRSTUVWXYZ",
        ),
        (_stream(None), True, None),
        (_stream("session_01CLOUDBUTSESSIONSHAPED"), True, None),
        (_stream(None, echo_task="continue cse_01OLDRUNABCDEF from before"), True, None),
        (
            _stream("cse_01NEWRUNABCDEF", echo_task="continue cse_01OLDRUNABCDEF"),
            True,
            "cse_01NEWRUNABCDEF",
        ),
        ('{"type":"result","result":"Routine fired. Session cse_01PROSEONLYXX"}', True, None),
        ("cse_ (empty)", True, None),
    ],
)
def test_the_session_id_comes_only_from_a_tool_result_or_the_api_body(text, cli, want):
    assert cd.parse_session_id(text, cli=cli) == want


def test_a_nested_tool_result_with_json_text_blocks_still_parses():
    tool = {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({"ok": True, "session_id": "cse_01NESTEDOKAYXX"}),
                        }
                    ],
                }
            ]
        },
    }
    assert cd.parse_session_id(json.dumps(tool), cli=True) == "cse_01NESTEDOKAYXX"


def test_a_fire_without_a_session_id_exits_1_and_records_the_attempt_as_unparsed(
    monkeypatch, tmp_path, capsys, quiet_remote
):
    fleet = _fleet(tmp_path, "can")
    monkeypatch.setattr(cd, "_run_claude", lambda *a, **k: (0, _stream(None)))
    assert cd.main(_args(tmp_path, fleet)) == 1
    assert "routine is paused" in capsys.readouterr().err
    rows = _ledger(tmp_path)
    assert rows == [
        {**rows[0], "status": "unparsed", "session_id": None, "account": "can", "slug": "probe"}
    ]


# --- Behaviour 5: --pick --------------------------------------------------------------------------


def _status(*rows):
    out = []
    for slug, weekly, parked, expires_in_days, *rest in rows:
        source, age = (rest + ["live", None])[:2] if rest else ("live", None)
        out.append(
            {
                "email": f"{slug}@ocoron.com",
                "slugs": [slug],
                "parked": parked,
                "source": source,
                "age_s": age,
                "seven_day": None
                if weekly is None
                else {"utilization": weekly, "resets_at_epoch": 0},
                "refresh_expires_epoch": None
                if expires_in_days is None
                else 1_000_000.0 + expires_in_days * 86400,
            }
        )
    return {"accounts": out, "active": "ob"}


def _reg(*slugs):
    return {"accounts": {s: {} for s in slugs}}


def _rows(**counts):
    return [{"account": s, "ts": 999_000.0} for s, n in counts.items() for _ in range(n)]


def test_pick_prefers_a_token_account_then_the_fewest_dispatches_this_week(tmp_path):
    fleet = _fleet(tmp_path, "ob", "can", "mob", token_for="mob")
    status = _status(("ob", 14.0, False, 30), ("can", 100.0, False, 30), ("mob", 99.0, False, 30))
    slug, reason = cd.pick_account(
        _reg("ob", "can", "mob"), status, _rows(mob=5, can=1), fleet, now=1_000_000.0
    )
    assert slug == "mob" and "token" in reason
    os.remove(fleet / "mob" / "routine-token")
    slug, reason = cd.pick_account(
        _reg("ob", "can", "mob"), status, _rows(mob=5, can=1), fleet, now=1_000_000.0
    )
    assert slug == "ob" and "0 dispatch" in reason  # fewest this week wins over weekly %


def test_pick_skips_parked_stale_expired_and_expiring_rows_and_breaks_ties_by_weekly(tmp_path):
    fleet = _fleet(tmp_path, "ob", "can", "mob", "sarp", "x", "y", "z")
    status = _status(
        ("ob", 14.0, False, 30),
        ("can", 100.0, False, 0.5),
        ("mob", 99.0, False, 30),
        ("sarp", 95.0, True, 3),
        ("x", 50.0, False, -1),
        ("y", 100.0, False, 30, "cache", 234_458.0),
        ("z", 100.0, False, 30, "cache", None),
    )
    slug, reason = cd.pick_account(
        _reg("ob", "can", "mob", "sarp", "x", "y", "z"), status, [], fleet, now=1_000_000.0
    )
    assert slug == "mob", (
        reason
    )  # can expires within a day, sarp parked, x expired, y stale, z unknown age, mob hotter than ob
    assert "99" in reason


def test_pick_never_takes_a_parked_account_even_with_a_token_or_fewer_dispatches(tmp_path):
    fleet = _fleet(tmp_path, "ob", "sarp", token_for="sarp")
    status = _status(("ob", 14.0, False, 30), ("sarp", 99.0, True, 30))
    slug, _ = cd.pick_account(_reg("ob", "sarp"), status, _rows(ob=3), fleet, now=1_000_000.0)
    assert slug == "ob"  # sarp has a token, fewer dispatches and a hotter week, and is parked


def test_pick_fails_closed_when_no_account_qualifies(tmp_path, monkeypatch, capsys, quiet_remote):
    fleet = _fleet(tmp_path, "ob")
    with pytest.raises(cd.DispatchError) as exc:
        cd.pick_account(_reg("ob"), _status(("can", 100.0, False, 30)), [], fleet, now=1_000_000.0)
    assert "no_account" in str(exc.value) and "--account" in str(exc.value)
    with pytest.raises(cd.DispatchError):
        cd.pick_account(_reg("ob"), None, [], fleet, now=1_000_000.0)
    assert (
        cd.pick_account(_reg("ob"), _status(("ob", None, False, 30)), [], fleet, now=1_000_000.0)[0]
        == "ob"
    )
    monkeypatch.setattr(cd, "fleet_status", lambda: None)
    args = _args(tmp_path, fleet)
    args[args.index("--account")] = "--pick"
    del args[args.index("can")]
    assert cd.main(args) == 3
    assert "pass --account" in capsys.readouterr().err


def test_pick_survives_malformed_status_and_ledger_rows(tmp_path):
    fleet = _fleet(tmp_path, "ob")
    status = _status(("ob", 14.0, False, 30))
    status["accounts"][0]["refresh_expires_epoch"] = "never"
    status["accounts"].append(7)
    with pytest.raises(cd.DispatchError):  # "never" is not a live chain
        cd.pick_account(
            _reg("ob"), status, [7, {"account": "ob", "ts": "soon"}], fleet, now=1_000_000.0
        )
    status["accounts"][0]["refresh_expires_epoch"] = 1_000_000.0 + 30 * 86400
    assert (
        cd.pick_account(
            _reg("ob"), status, [7, {"account": "ob", "ts": "soon"}], fleet, now=1_000_000.0
        )[0]
        == "ob"
    )


# --- Behaviour 6: wait + the branch guard ---------------------------------------------------------


def test_dispatch_refuses_an_existing_branch_unless_force_new_and_records_the_pre_fire_sha(
    monkeypatch, tmp_path, capsys
):
    fleet = _fleet(tmp_path, "can")
    monkeypatch.setattr(cd, "_ls_remote", lambda branch: "abc123\trefs/heads/claude/probe\n")
    monkeypatch.setattr(cd, "_run_claude", lambda *a, **k: (0, _stream("cse_01XYZABCDE")))
    assert cd.main(_args(tmp_path, fleet)) == 1
    assert (
        "claude/probe" in capsys.readouterr().err
        and not (tmp_path / "state" / "ledger.jsonl").exists()
    )
    assert cd.main(_args(tmp_path, fleet, extra=("--force-new",))) == 0
    assert _ledger(tmp_path)[-1]["pre_fire_sha"] == "abc123"


def test_the_done_trailer_must_be_a_real_trailer_not_a_quoted_one():
    assert cd.has_done_trailer(f"done\n\n{cd.DONE_TRAILER} cse_01X\n")
    assert cd.has_done_trailer(f"done\n\nAgent-Role: subagent\n{cd.DONE_TRAILER} unknown\n")
    assert not cd.has_done_trailer(f"wip: TODO add the {cd.DONE_TRAILER} trailer later\n")
    assert not cd.has_done_trailer("plain\n")


def test_wait_returns_only_a_newer_tip_whose_commit_carries_the_trailer_and_2_on_timeout(
    monkeypatch,
):
    shas = iter(
        [
            "",
            "aaa1111\trefs/heads/claude/probe\n",
            "bbb2222\trefs/heads/claude/probe\n",
            "ccc3333\trefs/heads/claude/probe\n",
        ]
    )
    monkeypatch.setattr(cd, "_ls_remote", lambda branch: next(shas))
    msgs = {
        "aaa1111": f"done\n\n{cd.DONE_TRAILER} cse_01OLD\n",
        "bbb2222": "wip\n",
        "ccc3333": f"done\n\n{cd.DONE_TRAILER} cse_01X\n",
    }
    seen: list = []
    monkeypatch.setattr(cd, "_tip_message", lambda branch, sha: seen.append(sha) or msgs[sha])
    monkeypatch.setattr(cd.time, "sleep", lambda s: None)
    clock = iter(range(0, 10_000, 10))
    monkeypatch.setattr(cd.time, "monotonic", lambda: next(clock))
    assert cd.wait_for_branch("probe", timeout=100, interval=1, since="aaa1111") == "ccc3333"
    assert "aaa1111" not in seen, "the pre-fire sha is never even read"
    monkeypatch.setattr(cd, "_ls_remote", lambda branch: "")
    assert cd.wait_for_branch("probe", timeout=20, interval=1) is None
    assert (
        cd.main(
            [
                "wait",
                "--slug",
                "probe",
                "--timeout",
                "0",
                "--interval",
                "0",
                "--ledger",
                "/nonexistent",
            ]
        )
        == 2
    )


def test_wait_reads_the_pre_fire_sha_from_the_ledger_and_clamps_the_interval(monkeypatch, tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    cd.append_ledger(ledger, {"slug": "probe", "pre_fire_sha": "aaa1111", "ts": 1})
    monkeypatch.setattr(cd, "_ls_remote", lambda branch: "aaa1111\trefs/heads/claude/probe\n")
    monkeypatch.setattr(cd, "_tip_message", lambda branch, sha: f"done\n\n{cd.DONE_TRAILER} x\n")
    slept: list = []
    monkeypatch.setattr(cd.time, "sleep", lambda s: slept.append(s))
    clock = iter([0, 0, 5, 5, 100, 100])
    monkeypatch.setattr(cd.time, "monotonic", lambda: next(clock))
    assert (
        cd.main(
            [
                "wait",
                "--slug",
                "probe",
                "--timeout",
                "10",
                "--interval",
                "0",
                "--ledger",
                str(ledger),
            ]
        )
        == 2
    )
    assert slept and min(slept) >= 1.0


def test_tip_message_fetches_into_a_private_ref_and_reads_at_the_given_sha(monkeypatch):
    calls: list = []
    monkeypatch.setattr(cd, "_git", lambda *a, **k: calls.append(a) or "msg\n")
    assert cd._tip_message("claude/probe", "deadbeef") == "msg\n"
    assert (
        calls[0][:3] == ("fetch", "-q", "origin")
        and "refs/cloud-dispatch/claude/probe" in calls[0][3]
        and "FETCH_HEAD" not in " ".join(calls[0])
    )
    assert calls[1] == ("log", "-1", "--format=%B", "deadbeef")


# --- Behaviour 7: the ledger and the CLI ----------------------------------------------------------


def test_every_fire_attempt_appends_one_json_line(monkeypatch, tmp_path, capsys, quiet_remote):
    fleet = _fleet(tmp_path, "can")
    monkeypatch.setattr(cd, "_run_claude", lambda *a, **k: (0, _stream("cse_01XYZABCDE")))
    args = _args(tmp_path, fleet)
    assert cd.main(args) == 0 and cd.main(args + ["--force-new"]) == 0
    rows = _ledger(tmp_path)
    assert len(rows) == 2
    assert rows[0] == {
        **rows[0],
        "account": "can",
        "trigger": TRIG["can"],
        "session_id": "cse_01XYZABCDE",
        "slug": "probe",
        "branch": "claude/probe",
        "via": "cli",
        "status": "ok",
    }
    assert len(rows[0]["task_sha256"]) == 16
    assert (
        json.loads(capsys.readouterr().out.strip().splitlines()[-1])["session_id"]
        == "cse_01XYZABCDE"
    )
    ledger = tmp_path / "state" / "ledger.jsonl"
    assert (
        cd.main(
            [
                "list",
                "--registry",
                str(_registry(tmp_path)),
                "--fleet-root",
                str(fleet),
                "--ledger",
                str(ledger),
                "--no-status",
            ]
        )
        == 0
    )
    assert "cse_01XYZABCDE" in capsys.readouterr().out


def test_a_task_file_is_read_and_digested(monkeypatch, tmp_path, quiet_remote):
    fleet = _fleet(tmp_path, "can")
    f = tmp_path / "brief.md"
    f.write_text("do the thing\n", encoding="utf-8")
    monkeypatch.setattr(cd, "_run_claude", lambda *a, **k: (0, _stream("cse_01XYZABCDE")))
    args = _args(tmp_path, fleet)
    args[args.index("--task")] = "--task-file"
    args[args.index("t")] = str(f)
    assert cd.main(args) == 0
    import hashlib

    assert (
        _ledger(tmp_path)[-1]["task_sha256"] == hashlib.sha256(b"do the thing\n").hexdigest()[:16]
    )


def test_shared_options_work_before_or_after_the_verb(tmp_path, capsys):
    reg = _registry(tmp_path)
    fleet = _fleet(tmp_path, "ob", "can")
    before = [
        "--registry",
        str(reg),
        "--fleet-root",
        str(fleet),
        "--ledger",
        str(tmp_path / "l.jsonl"),
        "list",
        "--no-status",
    ]
    after = [
        "list",
        "--no-status",
        "--registry",
        str(reg),
        "--fleet-root",
        str(fleet),
        "--ledger",
        str(tmp_path / "l.jsonl"),
    ]
    assert cd.main(before) == 0
    out_before = capsys.readouterr().out
    assert cd.main(after) == 0
    assert out_before == capsys.readouterr().out and str(reg) in out_before


def test_the_log_verb_reads_the_run_headlessly_under_the_accounts_config(
    monkeypatch, tmp_path, capsys
):
    fleet = _fleet(tmp_path, "can")
    monkeypatch.setenv("ROTATE_STATE_DIR", str(tmp_path / "state"))
    seen: dict = {}

    def fake_run(argv, env, cwd, stdin_text=""):
        seen.update(argv=argv, env=env, cwd=cwd, stdin=stdin_text)
        return 0, json.dumps({"result": "env[info]: Allocating sandbox …"})

    monkeypatch.setattr(cd, "_run_claude", fake_run)
    assert (
        cd.main(
            [
                "log",
                "--registry",
                str(_registry(tmp_path)),
                "--fleet-root",
                str(fleet),
                "--account",
                "can",
                "--session",
                "cse_01ABCDEFGH",
            ]
        )
        == 0
    )
    assert "Allocating sandbox" in capsys.readouterr().out
    assert (
        seen["env"]["CLAUDE_CONFIG_DIR"] == str(fleet / "can") and "cse_01ABCDEFGH" in seen["stdin"]
    )
    assert (
        cd.main(
            [
                "log",
                "--registry",
                str(_registry(tmp_path)),
                "--fleet-root",
                str(fleet),
                "--account",
                "can",
                "--session",
                "nope",
            ]
        )
        == 1
    )


# --- closing-pass own-fix findings ------------------------------------------------------------


def test_a_fifo_at_the_token_path_is_refused_at_once_not_blocked_on(tmp_path):
    fleet = _fleet(tmp_path, "ob")
    os.mkfifo(fleet / "ob" / "routine-token", 0o600)
    with pytest.raises(cd.DispatchError) as exc:
        cd.fire_path("ob", fleet)  # a blocking open would hang here forever
    assert "regular file" in str(exc.value)


def test_the_done_trailer_counts_when_it_is_the_last_line_even_without_a_blank_line_before_it():
    assert cd.has_done_trailer(f"subject\n{cd.DONE_TRAILER} cse_01X\n")
    assert cd.has_done_trailer(f"subject\n\nbody\n{cd.DONE_TRAILER} unknown")
    assert not cd.has_done_trailer(f"{cd.DONE_TRAILER} first, then more work\nreal last line\n")


def test_an_abbreviated_since_still_names_the_pre_fire_commit(monkeypatch, capsys):
    monkeypatch.setattr(
        cd,
        "_ls_remote",
        lambda branch: "9cb2693dfeedfacefeedfacefeedfacefeedface\trefs/heads/claude/probe\n",
    )
    monkeypatch.setattr(cd, "_tip_message", lambda branch, sha: f"done\n\n{cd.DONE_TRAILER} x\n")
    monkeypatch.setattr(cd.time, "sleep", lambda s: None)
    clock = iter([0, 0, 100, 100, 200, 200])
    monkeypatch.setattr(cd.time, "monotonic", lambda: next(clock))
    assert cd.wait_for_branch("probe", timeout=10, interval=1, since="9cb2693dfeed") is None
    assert (
        cd.wait_for_branch("probe", timeout=10, interval=1, since="0000000")
        == "9cb2693dfeedfacefeedfacefeedfacefeedface"
    )
    assert cd.main(["wait", "--slug", "probe", "--since", "not-a-sha", "--timeout", "0"]) == 1
    assert "hex" in capsys.readouterr().err


def test_an_http_client_exception_on_the_api_path_is_ledgered(monkeypatch, tmp_path, quiet_remote):
    import http.client

    fleet = _fleet(tmp_path, "ob", token_for="ob")

    def boom(u, h, b):
        raise http.client.IncompleteRead(b"")

    monkeypatch.setattr(cd, "_http_post", boom)
    assert cd.main(_args(tmp_path, fleet, account="ob")) == 1
    assert _ledger(tmp_path)[-1]["status"] == "error"
