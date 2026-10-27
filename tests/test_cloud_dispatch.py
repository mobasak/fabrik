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


def _status(*rows, states=None, drain_band=85.0):
    """Raw rows plus claude_rotate's `picture` view (state + weekly_pct per account), the part
    pick_account reads for the weekly wall (W-87078932). A state defaults to `eligible`, or
    `weekly-exhausted` at 100%; `states={slug: state}` overrides it."""
    out = []
    pic = []
    for slug, weekly, parked, expires_in_days, *rest in rows:
        source, age = (rest + ["live", None])[:2] if rest else ("live", None)
        state = (states or {}).get(slug) or (
            "weekly-exhausted" if weekly is not None and weekly >= 100 else "eligible"
        )
        pic.append({"slugs": [slug], "state": state, "weekly_pct": weekly})
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
    return {
        "accounts": out,
        "active": "ob",
        "picture": {"accounts": pic, "thresholds": {"trip": 99.0, "drain_band": drain_band}},
    }


def _reg(*slugs):
    return {"accounts": {s: {} for s in slugs}}


def _rows(**counts):
    return [{"account": s, "ts": 999_000.0} for s, n in counts.items() for _ in range(n)]


def test_pick_prefers_a_token_account_then_the_coolest_week(tmp_path):
    fleet = _fleet(tmp_path, "ob", "can", "mob", token_for="mob")
    status = _status(("ob", 14.0, False, 30), ("can", 100.0, False, 30), ("mob", 50.0, False, 30))
    slug, reason = cd.pick_account(
        _reg("ob", "can", "mob"), status, _rows(mob=5, can=1), fleet, now=1_000_000.0
    )
    assert slug == "mob" and "token" in reason
    os.remove(fleet / "mob" / "routine-token")
    slug, reason = cd.pick_account(
        _reg("ob", "can", "mob"), status, _rows(mob=5, can=1), fleet, now=1_000_000.0
    )
    assert slug == "ob" and "0 dispatch" in reason and "weekly 14%" in reason


def test_pick_skips_parked_stale_expired_and_expiring_rows(tmp_path):
    fleet = _fleet(tmp_path, "ob", "can", "mob", "sarp", "x", "y", "z")
    status = _status(  # every skipped row is COOLER than the two that qualify
        ("ob", 80.0, False, 30),
        ("can", 10.0, False, 0.5),
        ("mob", 60.0, False, 30),
        ("sarp", 5.0, True, 3),
        ("x", 3.0, False, -1),
        ("y", 2.0, False, 30, "cache", 234_458.0),
        ("z", 1.0, False, 30, "cache", None),
    )
    slug, reason = cd.pick_account(
        _reg("ob", "can", "mob", "sarp", "x", "y", "z"), status, [], fleet, now=1_000_000.0
    )
    assert slug == "mob", (
        reason
    )  # can expires within a day, sarp parked, x expired, y stale, z unknown age, mob cooler than ob
    assert "60" in reason


def test_pick_never_takes_a_parked_account_even_with_a_token_or_fewer_dispatches(tmp_path):
    fleet = _fleet(tmp_path, "ob", "sarp", token_for="sarp")
    status = _status(("ob", 14.0, False, 30), ("sarp", 5.0, True, 30))
    slug, _ = cd.pick_account(_reg("ob", "sarp"), status, _rows(ob=3), fleet, now=1_000_000.0)
    assert slug == "ob"  # sarp has a token, fewer dispatches and a cooler week, and is parked


def test_pick_fails_closed_when_no_account_qualifies(tmp_path, monkeypatch, capsys, quiet_remote):
    fleet = _fleet(tmp_path, "ob")
    with pytest.raises(cd.DispatchError) as exc:
        cd.pick_account(_reg("ob"), _status(("can", 100.0, False, 30)), [], fleet, now=1_000_000.0)
    assert "no_account" in str(exc.value) and "--account" in str(exc.value)
    with pytest.raises(cd.DispatchError):
        cd.pick_account(_reg("ob"), None, [], fleet, now=1_000_000.0)
    with pytest.raises(cd.DispatchError) as exc:  # no readable weekly figure: never picked blind
        cd.pick_account(_reg("ob"), _status(("ob", None, False, 30)), [], fleet, now=1_000_000.0)
    assert "ob no weekly reading" in str(exc.value)
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


_WALLED_STATES = (
    "cap-walled",
    "weekly-unreadable",
    "weekly-exhausted",
    "session-exhausted",
    "over-threshold",
    "unavailable",
    "something-new",
)


@pytest.mark.parametrize("allow_plan", [False, True])
@pytest.mark.parametrize("state", _WALLED_STATES)
def test_pick_takes_only_eligible_or_active_accounts_in_both_modes(tmp_path, state, allow_plan):
    """W-87078932: the rotation tick's own verdict decides; every other state is out, even when
    it is the coolest account with a token and no dispatches (mob at 100% won both modes live)."""
    fleet = _fleet(tmp_path, "ob", "mob", token_for="mob")
    tok = fleet / "ob" / "routine-token"
    tok.write_text("sk-ant-oat01-secret\n", encoding="utf-8")
    os.chmod(tok, 0o600)
    status = _status(("ob", 60.0, False, 30), ("mob", 5.0, False, 30), states={"mob": state})
    slug, _ = cd.pick_account(
        _reg("ob", "mob"), status, _rows(ob=9), fleet, now=1_000_000.0, allow_plan=allow_plan
    )
    assert slug == "ob"
    status = _status(("ob", 60.0, False, 30), ("mob", 5.0, False, 30), states={"mob": "active"})
    assert (
        cd.pick_account(
            _reg("ob", "mob"), status, _rows(ob=9), fleet, now=1_000_000.0, allow_plan=allow_plan
        )[0]
        == "mob"
    )


def test_pick_skips_an_account_at_or_over_the_weekly_ceiling(tmp_path):
    fleet = _fleet(tmp_path, "ob", "mob", token_for="mob")
    tok = fleet / "ob" / "routine-token"
    tok.write_text("sk-ant-oat01-secret\n", encoding="utf-8")
    os.chmod(tok, 0o600)
    reg = _reg("ob", "mob")
    # the default ceiling is the picture's drain band, at its edge exactly
    status = _status(("ob", 84.9, False, 30), ("mob", 85.0, False, 30))
    assert cd.pick_account(reg, status, [], fleet, now=1_000_000.0)[0] == "ob"
    # a published band of 90 admits an 86% account that the default 85 would skip
    status = _status(("ob", 86.0, False, 30), ("mob", 95.0, False, 30), drain_band=90.0)
    assert cd.pick_account(reg, status, [], fleet, now=1_000_000.0)[0] == "ob"
    status = _status(("ob", 50.0, False, 30), ("mob", 40.0, False, 30))
    assert cd.pick_account(reg, status, [], fleet, now=1_000_000.0, max_weekly=45.0)[0] == "mob"
    with pytest.raises(cd.DispatchError) as exc:
        cd.pick_account(reg, status, [], fleet, now=1_000_000.0, max_weekly=40.0)
    assert "mob weekly 40% >= ceiling 40%" in str(exc.value)
    status = _status(("ob", 50.0, False, 30), ("mob", 40.0, False, 30))
    status["picture"]["accounts"][1]["weekly_pct"] = "40"  # not a number: no reading
    assert cd.pick_account(reg, status, [], fleet, now=1_000_000.0)[0] == "ob"
    del status["picture"]["thresholds"]  # no band published: the documented 85
    status["picture"]["accounts"][0]["weekly_pct"] = 85.0
    with pytest.raises(cd.DispatchError) as exc:
        cd.pick_account(reg, status, [], fleet, now=1_000_000.0)
    assert "ob weekly 85% >= ceiling 85%" in str(exc.value)


def test_pick_ranks_the_coolest_week_above_the_dispatch_count(tmp_path):
    fleet = _fleet(tmp_path, "ob", "mob", token_for="mob")
    tok = fleet / "ob" / "routine-token"
    tok.write_text("sk-ant-oat01-secret\n", encoding="utf-8")
    os.chmod(tok, 0o600)
    status = _status(("ob", 70.0, False, 30), ("mob", 20.0, False, 30))
    for allow_plan in (False, True):
        slug, why = cd.pick_account(
            _reg("ob", "mob"),
            status,
            _rows(mob=12),
            fleet,
            now=1_000_000.0,
            allow_plan=allow_plan,
        )
        assert slug == "mob" and "12 dispatch(es)" in why and "weekly 20%" in why


def test_pick_refuses_without_a_picture_and_names_each_skip(tmp_path):
    fleet = _fleet(tmp_path, "ob", "mob", "can", token_for="mob")
    reg = _reg("ob", "mob", "can")
    status = _status(("ob", 10.0, False, 30), ("mob", 10.0, False, 30))
    del status["picture"]
    with pytest.raises(cd.DispatchError) as exc:
        cd.pick_account(reg, status, [], fleet, now=1_000_000.0)
    assert str(exc.value).startswith("no_account: no fleet status picture")
    assert "--account" in str(exc.value)
    status = _status(
        ("ob", 10.0, False, 30), ("mob", 100.0, False, 30), states={"ob": "cap-walled"}
    )
    with pytest.raises(cd.DispatchError) as exc:
        cd.pick_account(reg, status, [], fleet, now=1_000_000.0)
    msg = str(exc.value)
    assert msg.startswith("no_account:") and "--account" in msg
    assert (
        "ob cap-walled" in msg and "mob weekly-exhausted" in msg and "can no weekly reading" in msg
    )


def test_a_live_status_snapshot_picks_the_only_account_with_room(tmp_path):
    """The 2026-10-27 15:30 picture, as claude_rotate wrote it: three walled accounts and the
    active one at 33%. The old order took mob (100%) in both modes."""
    fleet = _fleet(tmp_path, "ob", "ozgurbasak", "can", "mob", token_for="ob")
    for s in ("ozgurbasak", "can", "mob"):
        tok = fleet / s / "routine-token"
        tok.write_text("sk-ant-oat01-secret\n", encoding="utf-8")
        os.chmod(tok, 0o600)
    status = _status(
        ("can", 99.0, False, 30),
        ("mob", 100.0, False, 30),
        ("ob", 100.0, False, 30),
        ("ozgurbasak", 33.0, False, 30),
        states={"can": "cap-walled", "ozgurbasak": "active"},
    )
    reg = _reg("ob", "ozgurbasak", "can", "mob")
    rows = _rows(ozgurbasak=12, mob=9, ob=1)
    for allow_plan in (False, True):
        assert (
            cd.pick_account(reg, status, rows, fleet, now=1_000_000.0, allow_plan=allow_plan)[0]
            == "ozgurbasak"
        )
    with pytest.raises(cd.DispatchError) as exc:
        cd.pick_account(reg, status, rows, fleet, now=1_000_000.0, max_weekly=30.0)
    assert "ozgurbasak weekly 33% >= ceiling 30%" in str(exc.value)


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


# --- credit guard (design 2026-10-14 evening, Opus + Fable folds): cost rows, pause rows, expiry


def _events(cost=0.3226484, plan_7d=0.26, plan_5h=0.05, overage=False, finished=True):
    rl = {
        "event_type": "rate_limit_event",
        "payload": {
            "rate_limit_info": {
                "isUsingOverage": overage,
                "overageDisabledReason": "out_of_credits",
                "unifiedWindows": {
                    "five_hour": {"utilization": plan_5h},
                    "seven_day": {"utilization": plan_7d},
                },
            }
        },
    }
    res = {
        "event_type": "result",
        "payload": {
            "total_cost_usd": cost,
            "usage": {"input_tokens": 66, "output_tokens": 545, "cache_read_input_tokens": 265564},
        },
    }
    # newest-first, as the endpoint pages
    return {"data": ([res] if finished else []) + [rl, rl], "resume_cursor": None}


def _creds(fleet: Path, slug: str, token="sk-ant-oat01-ACCESS", mode=0o600, expires_in_s=3600.0):
    import time as _t

    p = fleet / slug / ".credentials.json"
    p.write_text(
        json.dumps(
            {
                "claudeAiOauth": {
                    "accessToken": token,
                    "expiresAt": int((_t.time() + expires_in_s) * 1000),
                }
            }
        ),
        encoding="utf-8",
    )
    os.chmod(p, mode)
    return p


def _guard_registry(tmp_path, claimed=250, expires="2026-11-04", margin=None):
    accounts = {
        s: {"trigger": t, "github": "x", "credit": {"claimed_usd": claimed, "expires": expires}}
        for s, t in TRIG.items()
    }
    data = {"version": 1, "repo": "r", "routine": "w", "accounts": accounts}
    if margin is not None:
        data["credit_margin_usd"] = margin
    p = tmp_path / "cloud-routines.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _g(tmp_path, fleet, reg, *more):
    return [
        "--registry",
        str(reg),
        "--fleet-root",
        str(fleet),
        "--ledger",
        str(tmp_path / "state" / "ledger.jsonl"),
        *more,
    ]


def test_settle_run_reads_the_newest_result_and_rate_limit_events():
    row = cd.settle_run(_events()["data"])
    assert row == {
        **row,
        "cost_usd": 0.3226484,
        "input_tokens": 66,
        "output_tokens": 545,
        "cache_read_tokens": 265564,
        "plan_5h": 0.05,
        "plan_7d": 0.26,
        "using_overage": False,
        "finished": True,
    }
    assert row["rate_limit_info"]["overageDisabledReason"] == "out_of_credits", (
        "the raw block is kept verbatim"
    )
    unfinished = cd.settle_run(_events(finished=False)["data"])
    assert unfinished["cost_usd"] is None and unfinished["finished"] is False
    two = cd.settle_run(
        [
            {"event_type": "result", "payload": {"total_cost_usd": 2.0}},
            {"event_type": "result", "payload": {"total_cost_usd": 1.0}},
        ]
    )
    assert two["cost_usd"] == 2.0, "the newest (first) cumulative result wins; never a sum"


def test_the_access_token_is_read_from_a_0600_credentials_file_with_its_expiry(tmp_path):
    fleet = _fleet(tmp_path, "ob")
    _creds(fleet, "ob", expires_in_s=100)
    tok, fresh = cd.read_access_token("ob", fleet)
    assert tok == "sk-ant-oat01-ACCESS" and fresh is True
    _creds(fleet, "ob", expires_in_s=-100)
    assert cd.read_access_token("ob", fleet)[1] is False
    os.chmod(fleet / "ob" / ".credentials.json", 0o644)
    with pytest.raises(cd.DispatchError) as exc:
        cd.read_access_token("ob", fleet)
    assert "0600" in str(exc.value) and "ACCESS" not in str(exc.value)
    assert cd.read_access_token("can", _fleet(tmp_path, "can")) == (None, False)


def test_fetch_run_events_refreshes_an_expired_token_by_the_in_place_probe_only(
    monkeypatch, tmp_path
):
    fleet = _fleet(tmp_path, "ob")
    _creds(fleet, "ob", expires_in_s=-10)
    probes: list = []

    def fake_probe(cfg, scratch):
        probes.append(cfg)
        _creds(fleet, "ob", token="sk-ant-oat01-FRESH", expires_in_s=3600)
        return True

    monkeypatch.setattr(cd, "_refresh_probe", fake_probe)
    seen: dict = {}
    monkeypatch.setattr(
        cd, "_http_get", lambda u, h: seen.update(url=u, headers=h) or (200, json.dumps(_events()))
    )
    evs, refreshed = cd.fetch_run_events("ob", "cse_01ABCDEFGH", fleet)
    assert len(evs) == 3 and refreshed is True and probes == [fleet / "ob"]
    assert seen["url"].endswith("/v1/code/sessions/cse_01ABCDEFGH/events?limit=200")
    assert seen["headers"]["Authorization"] == "Bearer sk-ant-oat01-FRESH"
    # a fresh token never probes; a 401 never retries, never probes, never names the token
    probes.clear()
    monkeypatch.setattr(cd, "_http_get", lambda u, h: (401, "expired"))
    with pytest.raises(cd.DispatchError) as exc:
        cd.fetch_run_events("ob", "cse_01ABCDEFGH", fleet)
    assert "401" in str(exc.value) and "FRESH" not in str(exc.value) and probes == []
    with pytest.raises(cd.DispatchError):
        cd.fetch_run_events("ob", "session_01NOTCSE", fleet)


def test_spent_counts_the_latest_settle_per_fired_run_and_unsettled_runs_at_the_margin():
    now = 1_000_000.0
    rows = [
        {
            "account": "ob",
            "slug": "a",
            "session_id": "cse_01A",
            "status": "ok",
            "ts": now - 3 * 86400,
        },
        {
            "kind": "settle",
            "account": "ob",
            "session_id": "cse_01A",
            "cost_usd": None,
            "ts": now - 3 * 86400,
        },
        {
            "kind": "settle",
            "account": "ob",
            "session_id": "cse_01A",
            "cost_usd": 1.5,
            "ts": now - 2 * 86400,
        },  # re-settled: latest wins
        {
            "account": "ob",
            "slug": "b",
            "session_id": "cse_01B",
            "status": "ok",
            "ts": now - 2 * 86400,
        },  # never settled → margin
        {
            "account": "ob",
            "slug": "c",
            "session_id": "cse_01C",
            "status": "ok",
            "ts": now - 3600,
        },  # never settled → margin from dispatch
        {
            "account": "ob",
            "slug": "d",
            "session_id": None,
            "status": "http_503",
            "ts": now - 3 * 86400,
        },  # never reached
        {"account": "mob", "slug": "e", "session_id": "cse_01E", "status": "ok", "ts": now - 3600},
        {
            "kind": "settle",
            "account": "mob",
            "session_id": "cse_01E",
            "cost_usd": 4.0,
            "ts": now - 1800,
        },
    ]
    assert cd.spent_usd(rows, "ob", margin=10) == 21.5
    assert cd.spent_usd(rows, "mob", margin=10) == 4.0
    assert cd.spent_usd(rows, "can", margin=10) == 0.0
    assert cd.unsettled(rows, "ob") == ["b", "c"]


def test_margin_is_proportional_with_a_floor_and_a_calibrated_balance_is_honoured(tmp_path, capsys):
    reg = json.loads(_guard_registry(tmp_path, claimed=250).read_text())
    assert cd.margin_of(reg, "ob") == 25.0
    reg = json.loads(_guard_registry(tmp_path, claimed=50).read_text())
    assert cd.margin_of(reg, "ob") == 10.0
    reg = json.loads(_guard_registry(tmp_path, margin=3).read_text())
    assert cd.margin_of(reg, "ob") == 3.0
    reg_path = _guard_registry(tmp_path, claimed=250)
    reg = json.loads(reg_path.read_text())
    ledger = tmp_path / "ledger.jsonl"
    cd.append_ledger(
        ledger,
        {"account": "ob", "slug": "a", "session_id": "cse_01A", "status": "ok", "ts": 1_000.0},
    )
    cd.append_ledger(
        ledger,
        {
            "kind": "settle",
            "account": "ob",
            "session_id": "cse_01A",
            "cost_usd": 30.0,
            "ts": 1_000.0,
        },
    )
    assert (
        cd.main(
            [
                "calibrate",
                "ob",
                "--balance",
                "200",
                "--registry",
                str(reg_path),
                "--ledger",
                str(ledger),
            ]
        )
        == 0
    )
    assert "left 200.00" in capsys.readouterr().out
    cal = cd.read_ledger(ledger)[-1]
    assert cal == {**cal, "kind": "calibrate", "account": "ob", "balance_usd": 200.0}
    cd.append_ledger(
        ledger,
        {
            "account": "ob",
            "slug": "b",
            "session_id": "cse_01B",
            "status": "ok",
            "ts": cal["ts"] + 10,
        },
    )
    cd.append_ledger(
        ledger,
        {
            "kind": "settle",
            "account": "ob",
            "session_id": "cse_01B",
            "cost_usd": 5.0,
            "ts": cal["ts"] + 20,
        },
    )
    cd.append_ledger(
        ledger,
        {
            "account": "ob",
            "slug": "p",
            "session_id": "cse_01P",
            "status": "ok",
            "ts": cal["ts"] + 30,
            "plan_usage": True,
        },
    )
    cd.append_ledger(
        ledger,
        {
            "kind": "settle",
            "account": "ob",
            "session_id": "cse_01P",
            "cost_usd": 9.0,
            "ts": cal["ts"] + 40,
        },
    )
    rows = cd.read_ledger(ledger)
    assert cd.credit_left(reg, "ob", rows) == 250.0 - 50.0 - 5.0, (
        "the row fired before the calibration is inside the balance; a plan_usage row never counts"
    )
    assert (
        cd.main(
            [
                "calibrate",
                "nope",
                "--balance",
                "1",
                "--registry",
                str(reg_path),
                "--ledger",
                str(ledger),
            ]
        )
        == 1
    )


@pytest.mark.parametrize(
    ("spent", "settle", "want"),
    [
        (224.0, {"using_overage": False}, None),
        (225.0, {"using_overage": False}, "spent"),
        (1.0, {"using_overage": True}, "overage"),
        (1.0, {"using_overage": None}, None),
    ],
)
def test_decide_pause_fires_on_spend_and_overage_only(spent, settle, want):
    reason = cd.decide_pause("can", spent=spent, claimed=250, margin=25.0, settle=settle)
    assert (reason is None) == (want is None)
    if want:
        assert want in reason


def test_plan_rise_is_advisory_never_a_pause():
    note = cd.plan_rise_note({"plan_7d": 0.27}, {"plan_7d": 0.26}, account="can", active_slug="ob")
    assert note and "0.260" in note and "0.270" in note
    assert (
        cd.plan_rise_note({"plan_7d": 0.27}, {"plan_7d": 0.26}, account="ob", active_slug="ob")
        is None
    )
    assert (
        cd.plan_rise_note({"plan_7d": 0.27}, {"plan_7d": 0.26}, account="can", active_slug=None)
        is None
    )
    assert (
        cd.plan_rise_note({"plan_7d": 0.10}, {"plan_7d": 0.26}, account="can", active_slug="ob")
        is None
    )
    assert cd.plan_rise_note({"plan_7d": 0.27}, None, account="can", active_slug="ob") is None


def test_pause_state_lives_in_the_ledger_and_the_latest_row_wins(tmp_path, capsys):
    ledger = tmp_path / "ledger.jsonl"
    reg = _guard_registry(tmp_path)
    assert (
        cd.main(
            [
                "pause",
                "can",
                "--reason",
                "credit exhausted",
                "--registry",
                str(reg),
                "--ledger",
                str(ledger),
            ]
        )
        == 0
    )
    rows = cd.read_ledger(ledger)
    assert rows[-1] == {**rows[-1], "kind": "pause", "account": "can", "reason": "credit exhausted"}
    assert cd.paused_of(rows, "can")["reason"] == "credit exhausted"
    assert cd.paused_of(rows, "ob") is None
    assert json.loads(reg.read_text(encoding="utf-8"))["accounts"]["can"].get("paused") is None, (
        "the registry is never written"
    )
    assert cd.main(["unpause", "can", "--registry", str(reg), "--ledger", str(ledger)]) == 0
    assert cd.paused_of(cd.read_ledger(ledger), "can") is None
    assert (
        cd.main(["pause", "nope", "--reason", "x", "--registry", str(reg), "--ledger", str(ledger)])
        == 1
    )


def test_dispatch_and_pick_refuse_a_paused_account(monkeypatch, tmp_path, capsys, quiet_remote):
    reg = _guard_registry(tmp_path)
    fleet = _fleet(tmp_path, "ob", "can", token_for="ob")
    ledger = tmp_path / "state" / "ledger.jsonl"
    cd.append_ledger(
        ledger, {"kind": "pause", "account": "can", "reason": "credit exhausted", "ts": 1.0}
    )
    monkeypatch.setattr(cd, "_run_claude", lambda *a, **k: (0, _stream("cse_01XYZABCDE")))
    monkeypatch.setattr(
        cd,
        "_http_post",
        lambda u, h, b: (200, '{"claude_code_session_id": "cse_01XYZABCDE"}', {}),
    )
    monkeypatch.setattr(
        cd, "fleet_status", lambda: _status(("ob", 50.0, False, 30), ("can", 14.0, False, 30))
    )
    assert (
        cd.main(
            [
                "dispatch",
                "--slug",
                "p",
                "--account",
                "can",
                "--task",
                "t",
                *_g(tmp_path, fleet, reg),
            ]
        )
        == 7
    )
    assert "paused" in capsys.readouterr().err
    # can would WIN the pick on every other key (token path too, cooler weekly): the pause removes it
    tok = fleet / "can" / "routine-token"
    tok.write_text("sk-ant-oat01-secret\n", encoding="utf-8")
    os.chmod(tok, 0o600)
    rc = cd.main(["dispatch", "--slug", "p2", "--pick", "--task", "t", *_g(tmp_path, fleet, reg)])
    assert (
        rc == 0 and json.loads(capsys.readouterr().out.strip().splitlines()[-1])["account"] == "ob"
    )
    rows = cd.read_ledger(ledger)
    registry = json.loads(reg.read_text(encoding="utf-8"))
    status = _status(("ob", 50.0, False, 30), ("can", 14.0, False, 30))
    assert cd.pick_account(registry, status, rows, fleet, now=1_000_000.0)[0] == "ob"
    assert (
        cd.pick_account(registry, status, rows, fleet, now=1_000_000.0, allow_plan=True)[0] == "can"
    ), "the flag ignores the pause; the coolest weekly reading wins in both modes"
    # an expired account is out of the pick the same way (6 h before 00:00 UTC of its date)
    registry["accounts"]["ob"]["credit"]["expires"] = "2026-11-04"
    registry["accounts"]["can"]["credit"]["expires"] = "2026-12-01"
    at_wall = cd.expiry_epoch("2026-11-04") - cd.EXPIRY_GUARD_S
    cd.append_ledger(ledger, {"kind": "unpause", "account": "can", "ts": 2.0})
    rows = cd.read_ledger(ledger)
    # ob is the COOLER account, so only its expiry can hand the pick to can
    status = _status(("ob", 14.0, False, 30, "live", 0), ("can", 50.0, False, 30, "live", 0))
    assert cd.pick_account(registry, status, rows, fleet, now=at_wall)[0] == "can"
    assert cd.pick_account(registry, status, rows, fleet, now=at_wall - 1)[0] == "ob"


def test_expiry_is_utc_midnight_minus_the_guard_and_plan_usage_needs_the_flag(
    monkeypatch, tmp_path, capsys, quiet_remote
):
    import calendar

    fleet = _fleet(tmp_path, "can")
    monkeypatch.setattr(cd, "_run_claude", lambda *a, **k: (0, _stream("cse_01XYZABCDE")))
    expires = calendar.timegm((2026, 11, 4, 0, 0, 0))
    assert cd.expiry_epoch("2026-11-04") == expires
    reg = _guard_registry(tmp_path, expires="2026-11-04")
    base = ["dispatch", "--slug", "p", "--account", "can", "--task", "t", *_g(tmp_path, fleet, reg)]
    monkeypatch.setattr(cd.time, "time", lambda: expires - cd.EXPIRY_GUARD_S - 1)
    assert cd.main(base) == 0
    monkeypatch.setattr(cd.time, "time", lambda: expires - cd.EXPIRY_GUARD_S)
    assert cd.main(base + ["--force-new"]) == 7
    assert "expired" in capsys.readouterr().err
    cd.append_ledger(
        tmp_path / "state" / "ledger.jsonl",
        {"kind": "pause", "account": "can", "reason": "r", "ts": 1.0},
    )
    assert cd.main(base + ["--force-new"]) == 7
    assert cd.main(base + ["--force-new", "--allow-plan-usage"]) == 0, (
        "the flag bypasses expiry AND pause"
    )
    out = capsys.readouterr()
    assert "plan usage" in out.err.lower()
    row = json.loads(out.out.strip().splitlines()[-1])
    assert row["plan_usage"] is True and row["status"] == "ok"
    assert cd.EXPIRY_GUARD_S == 6 * 3600


def test_settle_verb_writes_the_cost_row_pauses_on_spend_and_is_idempotent(
    monkeypatch, tmp_path, capsys
):
    reg = _guard_registry(tmp_path, claimed=1.0, margin=0.5)
    fleet = _fleet(tmp_path, "ob", "can")
    _creds(fleet, "can")
    ledger = tmp_path / "state" / "ledger.jsonl"
    cd.append_ledger(
        ledger,
        {
            "account": "can",
            "slug": "job1",
            "session_id": "cse_01ABCDEFGH",
            "status": "ok",
            "ts": 1.0,
        },
    )
    monkeypatch.setattr(cd, "_http_get", lambda u, h: (200, json.dumps(_events(cost=0.6))))
    monkeypatch.setattr(cd, "active_slug", lambda: "ob")
    assert cd.main(["settle", "--slug", "job1", *_g(tmp_path, fleet, reg)]) == 0
    rows = cd.read_ledger(ledger)
    assert rows[-2] == {
        **rows[-2],
        "kind": "settle",
        "account": "can",
        "slug": "job1",
        "session_id": "cse_01ABCDEFGH",
        "cost_usd": 0.6,
        "spent_usd_total": 0.6,
    }
    assert rows[-1]["kind"] == "pause" and rows[-1]["reason"].startswith("spent")
    out = capsys.readouterr()
    assert "0.60" in out.out and "left" in out.out and "PAUSED" in out.err
    assert cd.main(["settle", "--slug", "job1", *_g(tmp_path, fleet, reg)]) == 0
    assert cd.spent_usd(cd.read_ledger(ledger), "can", margin=0.5) == 0.6, (
        "settling twice never double-counts"
    )
    assert sum(r.get("kind") == "pause" for r in cd.read_ledger(ledger)) == 1, (
        "an already-paused account is not re-paused"
    )


def test_an_unreadable_run_is_settle_pending_and_charged_at_the_margin(
    monkeypatch, tmp_path, capsys
):
    reg = _guard_registry(tmp_path)
    fleet = _fleet(tmp_path, "can")
    ledger = tmp_path / "state" / "ledger.jsonl"
    cd.append_ledger(
        ledger,
        {
            "account": "can",
            "slug": "job1",
            "session_id": "cse_01ABCDEFGH",
            "status": "ok",
            "ts": 1_000_000.0,
        },
    )
    probes: list = []
    monkeypatch.setattr(
        cd, "_refresh_probe", lambda cfg, scratch: probes.append(cfg) or False
    )  # the wall
    monkeypatch.setattr(cd.time, "time", lambda: 1_000_000.0 + 3600)
    _creds(fleet, "can", expires_in_s=-10)  # written against the patched clock
    assert cd.main(["settle", "--slug", "job1", *_g(tmp_path, fleet, reg)]) == 0
    rows = cd.read_ledger(ledger)
    assert rows[-1] == {**rows[-1], "kind": "settle", "status": "settle_pending", "cost_usd": None}
    assert rows[-2] == {**rows[-2], "kind": "token_refresh", "account": "can", "ok": False}
    out = capsys.readouterr()
    assert "pending" in out.out and "/login" in out.err
    assert cd.spent_usd(rows, "can", margin=25.0) == 25.0, (
        "unreadable → provisional at the margin, from dispatch"
    )
    # a second settle within 8 h never probes again (one plan turn per account per 8 h)
    assert cd.main(["settle", "--slug", "job1", *_g(tmp_path, fleet, reg)]) == 0
    assert len(probes) == 1
    # settle --all retries pending rows and, once readable, replaces the provisional charge
    _creds(fleet, "can", expires_in_s=3600)
    monkeypatch.setattr(cd, "_http_get", lambda u, h: (200, json.dumps(_events(cost=0.4))))
    assert cd.main(["settle", "--all", *_g(tmp_path, fleet, reg)]) == 0
    assert cd.spent_usd(cd.read_ledger(ledger), "can", margin=25.0) == 0.4
    assert cd.unsettled(cd.read_ledger(ledger), "can") == []


def test_wait_settles_automatically_on_success(monkeypatch, tmp_path, capsys):
    reg = _guard_registry(tmp_path)
    fleet = _fleet(tmp_path, "can")
    _creds(fleet, "can")
    ledger = tmp_path / "state" / "ledger.jsonl"
    cd.append_ledger(
        ledger,
        {
            "account": "can",
            "slug": "job1",
            "session_id": "cse_01ABCDEFGH",
            "status": "ok",
            "ts": 1.0,
            "pre_fire_sha": None,
        },
    )
    monkeypatch.setattr(cd, "_ls_remote", lambda branch: "aaa1111\trefs/heads/claude/job1\n")
    monkeypatch.setattr(cd, "_tip_message", lambda branch, sha: f"done\n\n{cd.DONE_TRAILER} x\n")
    monkeypatch.setattr(cd, "_http_get", lambda u, h: (200, json.dumps(_events(cost=0.42))))
    monkeypatch.setattr(cd, "active_slug", lambda: "ob")
    assert cd.main(["wait", "--slug", "job1", "--timeout", "0", *_g(tmp_path, fleet, reg)]) == 0
    out = capsys.readouterr()
    assert out.out.strip() == "aaa1111", "stdout is the tip sha alone — callers parse it"
    assert "0.42" in out.err
    assert any(r.get("kind") == "settle" for r in cd.read_ledger(ledger))


def test_list_shows_spent_left_and_the_pause_state_and_names_the_ledger(tmp_path, capsys):
    reg = _guard_registry(tmp_path)
    fleet = _fleet(tmp_path, "ob", "can")
    ledger = tmp_path / "ledger.jsonl"
    cd.append_ledger(ledger, {"account": "ob", "session_id": "cse_01A", "status": "ok", "ts": 1.0})
    cd.append_ledger(
        ledger,
        {"kind": "settle", "account": "ob", "session_id": "cse_01A", "cost_usd": 12.5, "ts": 1.0},
    )
    cd.append_ledger(
        ledger, {"kind": "pause", "account": "can", "reason": "credit exhausted", "ts": 2.0}
    )
    assert (
        cd.main(
            [
                "list",
                "--no-status",
                "--registry",
                str(reg),
                "--fleet-root",
                str(fleet),
                "--ledger",
                str(ledger),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert (
        "spent 12.50" in out
        and "left 237.50" in out
        and "PAUSED" in out
        and "credit exhausted" in out
    )
    assert str(ledger) in out


# --- the scoped review's round-1 findings (S-1 … S-6), each red on the pass-1 pin ------------------


def test_settle_decides_the_pause_from_rows_read_under_the_ledger_lock(
    monkeypatch, tmp_path, capsys
):
    """S-1: two settles of the same account racing — the second must see the first's cost."""
    reg = _guard_registry(tmp_path, claimed=250, margin=25)
    fleet = _fleet(tmp_path, "can")
    _creds(fleet, "can")
    ledger = tmp_path / "state" / "ledger.jsonl"
    for sid in ("cse_01AAAAAAAA", "cse_01BBBBBBBB"):
        cd.append_ledger(
            ledger,
            {
                "account": "can",
                "slug": sid[-4:].lower(),
                "session_id": sid,
                "status": "ok",
                "ts": 1.0,
            },
        )
    monkeypatch.setattr(cd, "_http_get", lambda u, h: (200, json.dumps(_events(cost=120.0))))
    monkeypatch.setattr(cd, "active_slug", lambda: "ob")
    real_txn = cd.LedgerTxn
    seen: list = []

    class Spy(real_txn):  # the rows a settle decides from are the rows under its own lock
        def __enter__(self):
            txn = super().__enter__()
            seen.append(len(txn.rows))
            return txn

    monkeypatch.setattr(cd, "LedgerTxn", Spy)
    assert cd.main(["settle", "--all", *_g(tmp_path, fleet, reg)]) == 0
    rows = cd.read_ledger(ledger)
    assert [r["kind"] for r in rows if "kind" in r] == ["settle", "settle", "pause"]
    assert rows[-2]["spent_usd_total"] == 240.0 and rows[-1]["reason"].startswith("spent 240.00")
    assert seen[-1] >= 3, "the second settle read the first settle's row under the lock"
    # the lock is real: a writer holding it blocks the transaction until released
    import fcntl as _f
    import threading

    order: list = []

    def late():
        with real_txn(ledger):
            order.append("txn")

    with open(ledger, "a", encoding="utf-8") as fh:
        _f.flock(fh, _f.LOCK_EX)
        th = threading.Thread(target=late)
        th.start()
        th.join(0.3)
        order.append("release")
        _f.flock(fh, _f.LOCK_UN)
    th.join(5)
    assert order == ["release", "txn"]


def test_pick_counts_dispatch_rows_only_never_guard_rows(tmp_path):
    """S-2: five settle rows on `a` are not five dispatches."""
    reg = json.loads(_guard_registry(tmp_path).read_text())
    fleet = _fleet(tmp_path, "ob", "can", token_for="ob")
    tok = fleet / "can" / "routine-token"
    tok.write_text("sk-ant-oat01-secret\n", encoding="utf-8")
    os.chmod(tok, 0o600)
    now = 1_000_000.0
    rows = [
        {"account": "can", "slug": "x", "session_id": "cse_01X", "status": "ok", "ts": now - 60}
    ]
    rows += [
        {"kind": k, "account": "ob", "session_id": "cse_01Y", "ts": now - 60}
        for k in ("settle", "settle", "pause", "unpause", "calibrate", "token_refresh")
    ]
    status = _status(("ob", 10.0, False, 30), ("can", 10.0, False, 30))
    slug, why = cd.pick_account(reg, status, rows, fleet, now=now)
    assert slug == "ob" and "0 dispatch(es)" in why


def test_a_fired_row_without_ts_still_counts_after_a_calibration():
    """S-3: a malformed (ts-less) row is never read as 'before the calibration'."""
    rows = [
        {"kind": "calibrate", "account": "ob", "balance_usd": 250.0, "ts": 100.0},
        {"account": "ob", "slug": "a", "session_id": "cse_01A", "status": "ok"},
        {
            "kind": "settle",
            "account": "ob",
            "session_id": "cse_01A",
            "cost_usd": 200.0,
            "ts": 200.0,
        },
    ]
    assert cd.spent_usd(rows, "ob", margin=25, claimed=250) == 200.0


def test_a_settle_row_of_another_account_never_settles_this_accounts_session():
    """S-4: settle rows are scoped by account."""
    rows = [
        {"account": "victim", "slug": "v", "session_id": "cse_01SHARED", "status": "ok", "ts": 1.0},
        {
            "kind": "settle",
            "account": "other",
            "session_id": "cse_01SHARED",
            "cost_usd": 0.0,
            "ts": 2.0,
        },
    ]
    assert cd.spent_usd(rows, "victim", margin=25) == 25.0
    assert cd.unsettled(rows, "victim") == ["v"]


@pytest.mark.parametrize(
    ("credit", "field"),
    [
        ({"claimed_usd": 250, "expires": "not-a-date"}, "credit.expires"),
        ({"claimed_usd": -1, "expires": "2026-11-04"}, "credit.claimed_usd"),
        ({"claimed_usd": "lots", "expires": "2026-11-04"}, "credit.claimed_usd"),
    ],
)
def test_a_malformed_credit_block_is_refused_at_load_for_every_verb(tmp_path, credit, field):
    """S-5: one bad date is a registry error naming the field, not a fleet-wide pick abort."""
    p = _guard_registry(tmp_path)
    data = json.loads(p.read_text(encoding="utf-8"))
    data["accounts"]["can"]["credit"] = credit
    p.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(cd.RegistryError) as exc:
        cd.load_registry(p)
    assert field in str(exc.value) and "can" in str(exc.value)
    data["accounts"]["can"]["credit"] = {"claimed_usd": 250, "expires": "2026-11-04"}
    data["credit_margin_usd"] = "free"
    p.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(cd.RegistryError) as exc:
        cd.load_registry(p)
    assert "credit_margin_usd" in str(exc.value)


def test_the_automatic_sweep_backs_off_a_refused_token_for_eight_hours(
    monkeypatch, tmp_path, capsys
):
    """S-6: a fresh-but-refused token is not retried on every dispatch; `settle --slug` still is."""
    reg = _guard_registry(tmp_path)
    fleet = _fleet(tmp_path, "can")
    ledger = tmp_path / "state" / "ledger.jsonl"
    cd.append_ledger(
        ledger,
        {
            "account": "can",
            "slug": "job1",
            "session_id": "cse_01ABCDEFGH",
            "status": "ok",
            "ts": 1.0,
        },
    )
    monkeypatch.setattr(cd.time, "time", lambda: 1_000_000.0)
    _creds(fleet, "can", expires_in_s=10 * 3600)  # fresh through the whole test: no probe path
    monkeypatch.setattr(cd, "_refresh_probe", lambda cfg, scratch: pytest.fail("no probe owed"))
    calls: list = []
    monkeypatch.setattr(cd, "_http_get", lambda u, h: calls.append(u) or (401, "revoked"))
    assert cd.main(["settle", "--all", *_g(tmp_path, fleet, reg)]) == 0
    assert cd.main(["settle", "--all", *_g(tmp_path, fleet, reg)]) == 0
    assert len(calls) == 1, "the sweep backed off"
    assert cd.main(["settle", "--slug", "job1", *_g(tmp_path, fleet, reg)]) == 0
    assert len(calls) == 2, "an explicit settle always retries"
    monkeypatch.setattr(cd.time, "time", lambda: 1_000_000.0 + cd.REFRESH_MIN_S)
    assert cd.main(["settle", "--all", *_g(tmp_path, fleet, reg)]) == 0
    assert len(calls) == 3, "after 8 h the sweep retries"
    assert cd.spent_usd(cd.read_ledger(ledger), "can", margin=25.0) == 25.0


def test_the_plan_rise_advisory_fires_from_the_previous_settle_not_the_current_one(
    monkeypatch, tmp_path, capsys
):
    """S-7 (closing round): the baseline is the settle BEFORE this one — a shadowed `rows` made it
    this one, and the advisory could never fire."""
    reg = _guard_registry(tmp_path)
    fleet = _fleet(tmp_path, "can")
    _creds(fleet, "can")
    ledger = tmp_path / "state" / "ledger.jsonl"
    for sid in ("cse_01AAAAAAAA", "cse_01BBBBBBBB"):
        cd.append_ledger(
            ledger,
            {
                "account": "can",
                "slug": sid[-4:].lower(),
                "session_id": sid,
                "status": "ok",
                "ts": 1.0,
            },
        )
    monkeypatch.setattr(cd, "active_slug", lambda: "ob")
    readings = iter([0.10, 0.30])
    monkeypatch.setattr(
        cd, "_http_get", lambda u, h: (200, json.dumps(_events(cost=0.1, plan_7d=next(readings))))
    )
    assert cd.main(["settle", "--all", *_g(tmp_path, fleet, reg)]) == 0
    err = capsys.readouterr().err
    assert "advisory" in err and "0.100 → 0.300" in err


# --- drain: a pre-flighted batch (W-b00d9d72) ------------------------------------------------------

MASTER = "a" * 40


class _FakeGit:
    """Every git read the drain makes, answered from a small model of origin and master; a
    verb in ``fail`` exits 128 with empty stdout, which is what a dead network looks like."""

    def __init__(
        self, branches=None, master_text=None, local=MASTER, origin=MASTER, dirs=(), entries=None
    ):
        self.branches = branches or {}  # name -> (tip, files, merged)
        self.master_text = master_text or {}
        self.dirs = set(dirs)
        self.entries = entries or {}  # path -> "<mode> <type>", e.g. a gitlink or a symlink
        self.master_log = ""
        self.local, self.origin = local, origin
        self.fail: set[str] = set()
        self.calls: list[tuple] = []

    def __call__(self, *args):
        self.calls.append(args)
        verb = args[0]
        if verb in self.fail:
            return 128, ""
        if verb == "ls-remote":
            lines = [f"{self.origin}\trefs/heads/master"] if self.origin else []
            lines += [f"{t}\trefs/heads/claude/{n}" for n, (t, _, _) in self.branches.items()]
            return 0, "".join(f"{ln}\n" for ln in lines)
        if verb == "rev-parse":
            return 0, f"{self.local}\n"
        if verb == "fetch":
            return 0, ""
        if verb == "merge-base":
            tip = args[2]
            merged = next(m for t, _, m in self.branches.values() if t == tip)
            return (0 if merged else 1), ""
        if verb == "diff":
            assert "--no-renames" in args and "-z" in args
            tip = args[-1].split("...", 1)[1]
            files = next(f for t, f, _ in self.branches.values() if t == tip)
            return 0, "".join(f"{p}\0" for p in files)
        if verb == "ls-tree":
            path = args[-1]
            if path in self.dirs:
                return 0, f"040000 tree x\t{path}\n"
            if path in self.entries:
                return 0, f"{self.entries[path]} x\t{path}\n"
            return 0, (f"100644 blob x\t{path}\n" if path in self.master_text else "")
        if verb == "show":
            return 0, self.master_text[args[1].split(":", 1)[1]]
        if verb == "log":
            return 0, self.master_log
        raise AssertionError(f"unexpected git {args}")


def _hub(tmp_path, monkeypatch, files=r"'(^scripts/command_run\.py$|^\.claude/hooks/)'"):
    hub = tmp_path / "hub"
    hub.mkdir(exist_ok=True)
    (hub / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: governance-sync\n"
        f"        name: sync\n        files: {files}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("FABRIK_HUB_ROOT", str(hub))


def _drain_env(tmp_path, monkeypatch, git=None, fire_rc=None):
    """A hermetic drain: a fake git, a tmp hub filter, and a fire that records its Namespace and
    ledgers an ok dispatch row as `_cmd_dispatch` would."""
    git = git or _FakeGit()
    monkeypatch.setattr(cd, "_git_run", git)
    _hub(tmp_path, monkeypatch)
    fired: list = []
    rcs = iter(fire_rc or [])

    def fire(ns):
        fired.append(ns)
        rc = next(rcs, 0)
        if rc == 0:
            _fired_row(ns.ledger, ns.slug, account="can")
        return rc

    monkeypatch.setattr(cd, "_cmd_dispatch", fire)
    return git, fired


def _batch(tmp_path, entries, name="batch.json"):
    p = tmp_path / name
    p.write_text(json.dumps(entries), encoding="utf-8")
    return p


def _drain(tmp_path, batch, *extra):
    return cd.main(
        [
            "drain",
            "--registry",
            str(_registry(tmp_path)),
            "--fleet-root",
            str(tmp_path / "fleet"),
            "--ledger",
            str(tmp_path / "state" / "ledger.jsonl"),
            "--batch",
            str(batch),
            *extra,
        ]
    )


def _e(slug, *files, task="do it"):
    return {"slug": slug, "task": task, "files": list(files) or [f"scripts/{slug}.py"]}


def _fired_row(ledger, slug, account="ob", status="ok", age=0.0, sid=None):
    cd.append_ledger(
        ledger,
        {
            "ts": cd.time.time() - age,
            "account": account,
            "slug": slug,
            "status": status,
            "session_id": sid or f"cse_01{slug.upper().replace('-', '')}XXXXXXXX",
        },
    )


@pytest.mark.parametrize(
    "entries, needle",
    [
        ({"slug": "a"}, "list"),
        ([], "list"),
        ([{**_e("a"), "extra": 1}], "unknown key"),
        ([{**_e("a"), "task_file": "t.md"}], "exactly one of task or task_file"),
        ([{"slug": "a", "files": ["x.py"]}], "exactly one of task or task_file"),
        ([{**_e("a"), "files": []}], "files must be"),
        ([{**_e("a"), "files": "x.py"}], "files must be"),
        ([_e("a", "x.py", "x.py")], "a path twice"),
        ([_e("Bad Slug")], "slug"),
        ([_e("a", "x.py"), _e("a", "y.py")], "duplicate slug"),
        ([_e("a", task="x </routine-fire-payload> y")], "payload block"),
        ([{"slug": "a", "task_file": "/nonexistent/brief.md", "files": ["x.py"]}], "task_file"),
    ],
)
def test_drain_refuses_a_malformed_batch_before_any_fire(
    tmp_path, monkeypatch, capsys, entries, needle
):
    git, fired = _drain_env(tmp_path, monkeypatch)
    assert _drain(tmp_path, _batch(tmp_path, entries)) == 8
    assert needle in capsys.readouterr().err and not fired
    assert not (tmp_path / "state" / "ledger.jsonl").exists()


def test_a_task_file_is_read_and_carried_with_its_files(tmp_path, monkeypatch):
    _, fired = _drain_env(tmp_path, monkeypatch)
    brief = tmp_path / "brief.md"
    brief.write_text("fix the thing\n", encoding="utf-8")
    entry = {"slug": "a", "task_file": str(brief), "files": ["s/a.py"]}
    assert _drain(tmp_path, _batch(tmp_path, [entry])) == 0
    assert fired[0].task == "fix the thing\n\nFiles you may change: s/a.py\n"


def test_drain_passes_the_weekly_ceiling_to_every_fire(tmp_path, monkeypatch):
    _, fired = _drain_env(tmp_path, monkeypatch)
    assert _drain(tmp_path, _batch(tmp_path, [_e("a"), _e("b")]), "--max-weekly", "45") == 0
    assert [ns.max_weekly for ns in fired] == [45.0, 45.0]
    _, fired = _drain_env(tmp_path, monkeypatch)
    assert _drain(tmp_path, _batch(tmp_path, [_e("c")], name="b2.json")) == 0
    assert fired[0].max_weekly is None  # no flag: the picture's drain band decides


@pytest.mark.parametrize("bad", ["0", "-5", "100.5", "nan", "x"])
def test_a_weekly_ceiling_outside_0_to_100_is_refused_at_parse(tmp_path, bad, capsys):
    with pytest.raises(SystemExit):
        cd.main(["dispatch", "--slug", "s", "--pick", "--task", "t", "--max-weekly", bad])
    assert "--max-weekly" in capsys.readouterr().err


@pytest.mark.parametrize("max_open", ["0", "-1"])
def test_a_max_open_below_one_is_refused(tmp_path, monkeypatch, capsys, max_open):
    _, fired = _drain_env(tmp_path, monkeypatch)
    assert _drain(tmp_path, _batch(tmp_path, [_e("a")]), "--max-open", max_open) == 8
    assert "--max-open" in capsys.readouterr().err and not fired


def test_a_second_drain_is_refused_while_the_lock_is_held(tmp_path, monkeypatch, capsys):
    git, fired = _drain_env(tmp_path, monkeypatch)
    lock = tmp_path / "state" / "cloud-drain.lock"
    lock.parent.mkdir(parents=True)
    with open(lock, "w") as fh:
        # a SHARED hold: an exclusive request conflicts with it, a shared one would not
        cd.fcntl.flock(fh, cd.fcntl.LOCK_SH)
        assert _drain(tmp_path, _batch(tmp_path, [_e("a")])) == 8
    assert "another drain" in capsys.readouterr().err and not fired


@pytest.mark.parametrize(
    "verb", ["ls-remote", "rev-parse", "fetch", "merge-base", "diff", "ls-tree", "show", "log"]
)
def test_drain_refuses_on_any_git_failure(tmp_path, monkeypatch, capsys, verb):
    git = _FakeGit(
        branches={"old": ("b" * 40, ["scripts/z.py"], False)},
        master_text={"tests/test_t.py": "def test_x():\n    pass\n"},
    )
    git.fail.add(verb)
    _, fired = _drain_env(tmp_path, monkeypatch, git)
    _fired_row(tmp_path / "state" / "ledger.jsonl", "recent")
    assert _drain(tmp_path, _batch(tmp_path, [_e("a", "tests/test_t.py")])) == 8
    assert f"git {verb} failed" in capsys.readouterr().err and not fired


@pytest.mark.parametrize("origin", ["c" * 40, ""])
def test_drain_refuses_when_local_master_is_not_origin_master(
    tmp_path, monkeypatch, capsys, origin
):
    _, fired = _drain_env(tmp_path, monkeypatch, _FakeGit(origin=origin))
    assert _drain(tmp_path, _batch(tmp_path, [_e("a")])) == 8
    assert "master" in capsys.readouterr().err and not fired


@pytest.mark.parametrize(
    "path",
    [
        "scripts/command_run.py",
        "./scripts/command_run.py",
        "scripts//command_run.py",
        ".claude/hooks/x.py",
        "scripts/cloud_dispatch.py",
        ".fabrik/cloud-routines.json",
        ".pre-commit-config.yaml",
        "commands/_sources/fabrik-task.md",
        "commands",
        "scripts/sysadmin/claude_rotate.py",
        "scripts/sysadmin",
        "tests/conftest.py",
        "tests/sub/conftest.py",
        "/etc/passwd",
        "../other/x.py",
        "..",
        ".",
        "scripts/../.claude/hooks/x.py",
        "scripts\\x.py",
        "scripts/",
        "",
        "docs",
        "vendor/sub",
        "s/link.py",
        "tests/test_home.py",
    ],
)
def test_drain_refuses_a_path_that_is_not_cloud_safe(tmp_path, monkeypatch, capsys, path):
    git = _FakeGit(
        master_text={"tests/test_home.py": "p = Path.home() / '.claude'\n"},
        dirs={"docs"},
        entries={"vendor/sub": "160000 commit", "s/link.py": "120000 blob"},
    )
    _, fired = _drain_env(tmp_path, monkeypatch, git)
    assert _drain(tmp_path, _batch(tmp_path, [_e("a", path)])) == 8
    assert "not cloud-safe" in capsys.readouterr().err and not fired


@pytest.mark.parametrize("entry", ["100644 blob", "100755 blob"])
def test_a_regular_or_executable_file_at_master_is_cloud_safe(tmp_path, monkeypatch, entry):
    git = _FakeGit(entries={"s/run.py": entry})
    _, fired = _drain_env(tmp_path, monkeypatch, git)
    assert _drain(tmp_path, _batch(tmp_path, [_e("a", "s/run.py")])) == 0
    assert [ns.slug for ns in fired] == ["a"]


@pytest.mark.parametrize(
    "text",
    [
        "p = Path.home() / 'x'\n",
        "h = Path.home\n",
        "p = os.path.expanduser('~')\n",
        "p = '~/.claude/state'\n",
        "h = os.environ['HOME']\n",
        "h = os.getenv('HOME')\n",
        "h = pwd.getpwuid(os.getuid()).pw_dir\n",
    ],
)
def test_every_home_read_spelling_refuses_a_test_file(tmp_path, monkeypatch, capsys, text):
    git = _FakeGit(master_text={"tests/test_h.py": text})
    _, fired = _drain_env(tmp_path, monkeypatch, git)
    assert _drain(tmp_path, _batch(tmp_path, [_e("a", "tests/test_h.py")])) == 8
    assert "reads the home dir" in capsys.readouterr().err and not fired


@pytest.mark.parametrize("files", ["'(unclosed'", "|", "'x'"])
def test_an_unreadable_or_uncompilable_sync_filter_refuses(tmp_path, monkeypatch, capsys, files):
    _, fired = _drain_env(tmp_path, monkeypatch)
    _hub(tmp_path, monkeypatch, files=files)
    if files == "'x'":  # readable and compilable: the control that proves the other two refuse
        assert _drain(tmp_path, _batch(tmp_path, [_e("a")])) == 0
        return
    assert _drain(tmp_path, _batch(tmp_path, [_e("a")])) == 8
    assert "governance-sync filter" in capsys.readouterr().err and not fired


def test_a_home_free_test_file_and_a_new_test_file_are_cloud_safe(tmp_path, monkeypatch):
    git = _FakeGit(master_text={"tests/test_ok.py": "def test_x():\n    assert 1\n"})
    _, fired = _drain_env(tmp_path, monkeypatch, git)
    entries = [_e("a", "tests/test_ok.py"), _e("b", "tests/test_new.py")]
    assert _drain(tmp_path, _batch(tmp_path, entries)) == 0
    assert [ns.slug for ns in fired] == ["a", "b"]


def test_drain_refuses_overlapping_file_sets(tmp_path, monkeypatch, capsys):
    git = _FakeGit(
        branches={
            "open-one": ("b" * 40, ["scripts/taken.py", "docs/my file.md"], False),
            "merged-one": ("d" * 40, ["scripts/free.py"], True),
        }
    )
    _, fired = _drain_env(tmp_path, monkeypatch, git)
    assert _drain(tmp_path, _batch(tmp_path, [_e("a", "x.py"), _e("b", "x.py")])) == 8
    assert "x.py is in both a and b" in capsys.readouterr().err
    assert _drain(tmp_path, _batch(tmp_path, [_e("a", "scripts/taken.py")])) == 8
    assert "held by claude/open-one" in capsys.readouterr().err
    assert _drain(tmp_path, _batch(tmp_path, [_e("a", "docs/my file.md")])) == 8
    assert "held by claude/open-one" in capsys.readouterr().err
    assert _drain(tmp_path, _batch(tmp_path, [_e("open-one", "y.py")])) == 8
    assert "already exists" in capsys.readouterr().err
    ledger = tmp_path / "state" / "ledger.jsonl"
    cd.append_ledger(ledger, {"kind": "drain", "slug": "inflight", "files": ["scripts/busy.py"]})
    _fired_row(ledger, "inflight")
    assert _drain(tmp_path, _batch(tmp_path, [_e("a", "scripts/busy.py")])) == 8
    assert "held by in-flight inflight" in capsys.readouterr().err and not fired
    assert _drain(tmp_path, _batch(tmp_path, [_e("a", "scripts/free.py")])) == 0
    assert [ns.slug for ns in fired] == ["a"]


def test_a_drained_runs_files_stay_held_until_its_work_lands(tmp_path, monkeypatch, capsys):
    """End to end: the drain's own row holds the files; a partly pushed branch, or one still at
    master's tip, keeps holding the declared files; the done trailer on master releases them."""
    git = _FakeGit()
    _, fired = _drain_env(tmp_path, monkeypatch, git)
    assert _drain(tmp_path, _batch(tmp_path, [_e("a", "s/a.py", "s/b.py")])) == 0
    assert _drain(tmp_path, _batch(tmp_path, [_e("b", "s/a.py")])) == 8
    assert "held by in-flight a" in capsys.readouterr().err
    git.branches = {"a": ("b" * 40, ["s/a.py"], False)}  # pushed s/a.py only so far
    assert _drain(tmp_path, _batch(tmp_path, [_e("c", "s/b.py")])) == 8
    assert "held by claude/a" in capsys.readouterr().err
    git.branches = {"a": ("d" * 40, [], True)}  # a branch at master's tip, nothing pushed yet
    assert _drain(tmp_path, _batch(tmp_path, [_e("c", "s/b.py")])) == 8
    assert "held by claude/a" in capsys.readouterr().err
    git.branches = {}  # merged and deleted: landed once master carries the done trailer
    git.master_log = f"merge a\n\n{cd.DONE_TRAILER} cse_01AXXXXXXXX\n"
    assert _drain(tmp_path, _batch(tmp_path, [_e("c", "s/b.py")])) == 0
    assert [ns.slug for ns in fired] == ["a", "c"]


@pytest.mark.parametrize(
    ("trailer_id", "lands"),
    [
        ("cse_01AXXXXXXXX", True),
        ("session_01AXXXXXXXX", True),  # what a cloud worker writes (W-3478033b's real trailer)
        ("01AXXXXXXXX", True),
        ("unknown", False),
        ("session_01AXXXXXXXY", False),
    ],
)
def test_a_done_trailer_lands_a_run_whatever_prefix_its_session_id_carries(
    tmp_path, monkeypatch, capsys, trailer_id, lands
):
    git = _FakeGit()
    _, fired = _drain_env(tmp_path, monkeypatch, git)
    assert _drain(tmp_path, _batch(tmp_path, [_e("a", "s/a.py")])) == 0
    git.master_log = f"merge a\n\n{cd.DONE_TRAILER} {trailer_id}\n"
    assert _drain(tmp_path, _batch(tmp_path, [_e("b", "s/a.py")])) == (0 if lands else 8)
    assert ("held by in-flight a" in capsys.readouterr().err) is not lands


def test_an_unknown_done_trailer_never_lands_a_run_whose_session_id_was_not_parsed(
    tmp_path, monkeypatch, capsys
):
    git = _FakeGit()
    _drain_env(tmp_path, monkeypatch, git)
    ledger = tmp_path / "state" / "ledger.jsonl"
    cd.append_ledger(ledger, {"kind": "drain", "slug": "u", "files": ["s/u.py"]})
    cd.append_ledger(
        ledger,
        {
            "ts": cd.time.time(),
            "account": "ob",
            "slug": "u",
            "status": "unparsed",
            "session_id": None,
        },
    )
    git.master_log = f"merge something\n\n{cd.DONE_TRAILER} unknown\n"
    assert _drain(tmp_path, _batch(tmp_path, [_e("b", "s/u.py")])) == 8
    assert "held by in-flight u" in capsys.readouterr().err


def test_an_in_flight_run_older_than_a_day_no_longer_holds_its_files(tmp_path, monkeypatch):
    _, fired = _drain_env(tmp_path, monkeypatch)
    ledger = tmp_path / "state" / "ledger.jsonl"
    cd.append_ledger(ledger, {"kind": "drain", "slug": "stale", "files": ["scripts/busy.py"]})
    _fired_row(ledger, "stale", age=2 * 86400)
    assert _drain(tmp_path, _batch(tmp_path, [_e("a", "scripts/busy.py")])) == 0
    assert [ns.slug for ns in fired] == ["a"]


def test_drain_refuses_past_the_open_work_cap(tmp_path, monkeypatch, capsys):
    git = _FakeGit(
        branches={"o1": ("b" * 40, ["s/1.py"], False), "m1": ("d" * 40, ["s/2.py"], True)}
    )
    _, fired = _drain_env(tmp_path, monkeypatch, git)
    _fired_row(tmp_path / "state" / "ledger.jsonl", "plain")
    entries = [_e("a", "s/a.py"), _e("b", "s/b.py")]
    assert _drain(tmp_path, _batch(tmp_path, entries), "--max-open", "3") == 8
    assert "over the cap of 3" in capsys.readouterr().err and not fired
    assert _drain(tmp_path, _batch(tmp_path, entries), "--max-open", "4") == 0
    assert len(fired) == 2


def test_drain_fires_each_entry_stops_at_the_first_failure_and_never_refires(
    tmp_path, monkeypatch, capsys
):
    _, fired = _drain_env(tmp_path, monkeypatch, fire_rc=[0, 4])
    entries = [_e("a", "s/a.py"), _e("b", "s/b.py"), _e("c", "s/c.py")]
    batch = _batch(tmp_path, entries)
    assert _drain(tmp_path, batch, "--allow-plan-usage") == 4
    assert [ns.slug for ns in fired] == ["a", "b"]
    ns = fired[0]
    assert ns.account is None and ns.force_new is False and ns.task_file is None
    assert ns.allow_plan_usage is True
    assert ns.task == "do it\n\nFiles you may change: s/a.py\n"
    err = capsys.readouterr().err
    assert (
        "drain a: fired" in err and "drain b: refused rc4" in err and "drain c: not reached" in err
    )
    rows = _ledger(tmp_path)
    assert [r["slug"] for r in rows if r.get("kind") == "drain"] == ["a", "b"]
    assert rows[0]["kind"] == "drain" and rows[0]["files"] == ["s/a.py"]
    assert _drain(tmp_path, batch) == 0
    assert [ns.slug for ns in fired] == ["a", "b", "b", "c"]
    assert "drain a: already fired" in capsys.readouterr().err


@pytest.mark.parametrize("status", ["unparsed", "error", "http_502"])
def test_a_fire_that_may_have_started_a_run_is_never_refired(tmp_path, monkeypatch, capsys, status):
    fired: list = []
    _drain_env(tmp_path, monkeypatch)
    ledger = tmp_path / "state" / "ledger.jsonl"

    def fire(ns):
        fired.append(ns)
        cd.append_ledger(ledger, {"ts": cd.time.time(), "slug": ns.slug, "status": status})
        return 1

    monkeypatch.setattr(cd, "_cmd_dispatch", fire)
    assert _drain(tmp_path, _batch(tmp_path, [_e("a", "s/a.py"), _e("b", "s/b.py")])) == 1
    err = capsys.readouterr().err
    assert f"drain a: fired? ({status}" in err and "drain b: not reached" in err
    assert _drain(tmp_path, _batch(tmp_path, [_e("a", "s/a.py")])) == 0
    assert "drain a: already fired" in capsys.readouterr().err and len(fired) == 1


@pytest.mark.parametrize("status", ["http_401", "http_429", "walled", "chain_dead"])
def test_a_fire_that_never_started_a_run_may_be_retried(tmp_path, monkeypatch, status):
    _, fired = _drain_env(tmp_path, monkeypatch)
    _fired_row(tmp_path / "state" / "ledger.jsonl", "a", status=status)
    assert _drain(tmp_path, _batch(tmp_path, [_e("a", "s/a.py")])) == 0
    assert [ns.slug for ns in fired] == ["a"]


def test_a_slug_a_sibling_fires_after_the_pre_flight_is_not_fired_again(
    tmp_path, monkeypatch, capsys
):
    _, fired = _drain_env(tmp_path, monkeypatch)
    ledger = tmp_path / "state" / "ledger.jsonl"

    def fire(ns):  # a sibling dispatch of `b` lands while `a` fires
        fired.append(ns)
        _fired_row(ns.ledger, ns.slug)
        _fired_row(ledger, "b", account="mob")
        return 0

    monkeypatch.setattr(cd, "_cmd_dispatch", fire)
    assert _drain(tmp_path, _batch(tmp_path, [_e("a", "s/a.py"), _e("b", "s/b.py")])) == 0
    assert [ns.slug for ns in fired] == ["a"]
    assert "drain b: already fired (by another session" in capsys.readouterr().err


def test_an_exception_mid_batch_still_prints_every_entrys_status(tmp_path, monkeypatch, capsys):
    _, fired = _drain_env(tmp_path, monkeypatch)
    calls = iter([0])

    def fire(ns):
        if next(calls, None) is None:
            raise cd.RegistryError("registry vanished")
        fired.append(ns)
        _fired_row(ns.ledger, ns.slug)
        return 0

    monkeypatch.setattr(cd, "_cmd_dispatch", fire)
    entries = [_e("a", "s/a.py"), _e("b", "s/b.py"), _e("c", "s/c.py")]
    assert _drain(tmp_path, _batch(tmp_path, entries)) == 1
    err = capsys.readouterr().err
    assert "drain a: fired" in err and "drain c: not reached" in err
    # b's drain row was written before its fire raised: an attempt, never "not reached"
    assert "drain b: attempted (raised before a result — read the ledger before retrying)" in err


def test_drain_dry_run_fires_nothing(tmp_path, monkeypatch, capsys):
    _, fired = _drain_env(tmp_path, monkeypatch)
    assert _drain(tmp_path, _batch(tmp_path, [_e("a", "s/a.py")]), "--dry-run") == 0
    assert "drain a: would fire" in capsys.readouterr().err and not fired
    assert not (tmp_path / "state" / "ledger.jsonl").exists()
