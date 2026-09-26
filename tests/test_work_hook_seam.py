"""The Stop hook ↔ thread_anchor ↔ work store seam (T05, spec § Validation V1).

No stubs on the V1 path: a temp git repo initialised with the REAL ``scripts/work.py init``, no
``scripts/final_gate.py`` in it (so the hook takes its non-fabrik allowed exit and stores the
DECISION block), the REAL ``.claude/hooks/final_gate_stop.py`` run as a subprocess on a Stop
payload, then the REAL ``thread_anchor.py line --hook`` from a third session. The temp repo carries
no ``scripts/thread_anchor.py``, so the hook falls back to this checkout's copy (its ``__file__``).

The fabrik-style tests add a fake ``scripts/final_gate.py`` (the same fixture shape as
``tests/test_stop_hook_quota_hold_exemption.py``) to drive the hook's OTHER allowed exits — the
pass-through and the quota hold — and a blocked Stop.

The argv tests put a recording stub at ``<repo>/scripts/thread_anchor.py`` — the hook prefers the
repo's own copy — to see exactly what the hook passes (spec § Lifecycle — Degradation).

Hermetic: HOME, TMPDIR, THREAD_ANCHOR_DIR, COMMAND_RUN_DIR, KAIZEN_EVENTS_DIR, ROTATE_STATE_DIR and
QUOTA_STOP_TICK_LOG all live under tmp_path; the hub's own store is never read or written.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / ".claude" / "hooks" / "final_gate_stop.py"
TA = REPO / "scripts" / "thread_anchor.py"
WORK = REPO / "scripts" / "work.py"

_DECISION = (
    "Certified build is ready.\n\n"
    "DECISION NEEDED (ground: gate)\n"
    "- Question: Deploy the certified build to production now?\n"
    "- Why it is yours: gate — Gate 2, a destructive/irreversible action needing authorisation.\n"
    "- Options: A — deploy now · B — hold for one more smoke pass\n"
    "- Recommendation: A — the certification gauntlet already passed.\n\n"
    "NEXT: operator decision — see DECISION NEEDED above"
)
_OTHER = _DECISION.replace("Deploy the certified build", "Rotate the signing key")

_FAKE_GATE = """#!/usr/bin/env python3
import json, os, sys
fails = [f for f in os.environ.get("FAKE_FAILS", "").split(",") if f]
if not fails:
    print(json.dumps({"status": "success", "failures": []})); sys.exit(0)
print(json.dumps({"status": "failure", "failures": [{"check": c} for c in fails]}))
sys.exit(1)
"""


def _env(tmp_path: Path) -> dict[str, str]:
    for sub in ("home", "runs", "threads", "tmp", "events", "state"):
        (tmp_path / sub).mkdir(exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path / "home"),
        "TMPDIR": str(tmp_path / "tmp"),
        "THREAD_ANCHOR_DIR": str(tmp_path / "threads"),
        "COMMAND_RUN_DIR": str(tmp_path / "runs"),
        "KAIZEN_EVENTS_DIR": str(tmp_path / "events"),
        "ROTATE_STATE_DIR": str(tmp_path / "state"),
        "QUOTA_STOP_TICK_LOG": str(tmp_path / "state" / "tick.log"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }


def _git(cwd: Path, env: dict[str, str], *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True)


def _work(env: dict[str, str], repo: Path, *args: str) -> str:
    proc = subprocess.run(
        [sys.executable, str(WORK), "--repo", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _repo(tmp_path: Path, env: dict[str, str], init: bool = True) -> Path:
    repo = tmp_path / "wrepo"
    _git(tmp_path, env, "init", "-q", str(repo))
    (repo / "README").write_text("seed\n", encoding="utf-8")
    _git(repo, env, "add", "README")
    _git(repo, env, "commit", "-q", "-m", "seed")
    if init:
        _work(env, repo, "init", "--distributor", "intel")
    assert not (repo / "scripts" / "final_gate.py").exists()
    return repo.resolve()


def _fabrik_repo(tmp_path: Path, env: dict[str, str]) -> Path:
    """An initialised repo WITH a fake final gate: the hook enforces, so its non-fabrik exit is
    never taken and only the pass-through or the quota hold can store a DECISION block."""
    repo = _repo(tmp_path, env)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "final_gate.py").write_text(_FAKE_GATE, encoding="utf-8")
    return repo


def _items(repo: Path) -> list[dict]:
    store = repo / ".fabrik" / "work"
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(store.glob("W-*.json"))]


def _awaiting(repo: Path) -> list[dict]:
    return [it for it in _items(repo) if it["status"] == "awaiting-operator"]


def _stop(
    env: dict[str, str],
    sid: str,
    message: str | None,
    cwd: Path | str | None,
    proc_cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    payload: dict = {"session_id": sid, "hook_event_name": "Stop"}
    if message is not None:
        payload["last_assistant_message"] = message
    if cwd is not None:
        payload["cwd"] = str(cwd)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        cwd=proc_cwd or Path(env["TMPDIR"]),
    )


def _line(env: dict[str, str], payload: dict) -> str:
    proc = subprocess.run(
        [sys.executable, str(TA), "line", "--hook"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def _allowed(proc: subprocess.CompletedProcess) -> None:
    assert proc.returncode == 0, proc.stderr
    assert '"decision": "block"' not in proc.stdout, proc.stdout


def _blocked(proc: subprocess.CompletedProcess) -> None:
    assert proc.returncode == 0, proc.stderr
    assert '"decision": "block"' in proc.stdout, (proc.stdout, proc.stderr)


def _claimed(env: dict[str, str], repo: Path, sid: str) -> Path:
    """An item claimed by ``sid`` whose lease was taken an hour ago; returns the claim file."""
    _work(env, repo, "add", "--kind", "task", "--title", "wire the hook")
    (item,) = _items(repo)
    _work(env, repo, "claim", item["id"], "--session", sid)
    claim_path = repo / ".git" / "fabrik-work" / "claims" / f"{item['id']}.json"
    claim = json.loads(claim_path.read_text(encoding="utf-8"))
    claim["at"] = time.time() - 3600
    claim_path.write_text(json.dumps(claim), encoding="utf-8")
    return claim_path


def _renewed(claim_path: Path) -> bool:
    return json.loads(claim_path.read_text(encoding="utf-8"))["at"] > time.time() - 60


# ── V1, end to end (the non-fabrik allowed exit) ──────────────────────────────────────────────


def test_v1_two_stops_become_two_awaiting_items_every_session_sees(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)

    _allowed(_stop(env, "s-a", _DECISION, repo))
    assert len(_awaiting(repo)) == 1, _items(repo)

    _allowed(_stop(env, "s-b", _OTHER, repo))
    assert len(_awaiting(repo)) == 2, _items(repo)

    prompt = {"session_id": "s-c", "hook_event_name": "UserPromptSubmit", "prompt": "hi"}
    compact = {"session_id": "s-c", "hook_event_name": "SessionStart", "source": "compact"}
    for rnd in ("first", "after the state file is deleted"):
        for payload in (prompt, compact):
            out = _line(env, {**payload, "cwd": str(repo)})
            assert "Deploy the certified build to production now?" in out, (rnd, out)
            assert "Rotate the signing key to production now?" in out, (rnd, out)
            assert out.count("work: awaiting operator — W-") == 2, (rnd, out)
        (Path(env["THREAD_ANCHOR_DIR"]) / "s-c.json").unlink(missing_ok=True)


# ── V1 (T05b): a NEXT claims the item it names, or becomes the session's one `next` item ─────


def _task(env: dict[str, str], repo: Path, title: str) -> str:
    before = {it["id"] for it in _items(repo)}
    _work(env, repo, "add", "--kind", "task", "--title", title)
    (new,) = [it["id"] for it in _items(repo) if it["id"] not in before]
    return new


def _by_id(repo: Path) -> dict[str, dict]:
    return {it["id"]: it for it in _items(repo)}


def _item_files(repo: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in (repo / ".fabrik" / "work").glob("W-*.json")}


def _claim(repo: Path, item_id: str) -> dict | None:
    path = repo / ".git" / "fabrik-work" / "claims" / f"{item_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _open_nexts(repo: Path, sid: str) -> list[dict]:
    return [
        it
        for it in _items(repo)
        if it["kind"] == "next" and it["status"] == "open" and it["links"]["session"] == sid
    ]


def _said(nxt: str) -> str:
    return f"Done with that step.\n\nNEXT: {nxt}\n"


def test_v1_a_next_claims_the_item_it_names_or_becomes_the_sessions_next_item(tmp_path):
    """Spec § Validation V1 through the REAL Stop hook, one session (s-1) walking every rule, then
    a second session (s-2) whose Stop closes a third session's (s-3) 8-day-old `next` item. s-2
    also holds the item s-1 names in its last NEXT, and ends on that item — its own claim renews."""
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    a = _task(env, repo, "wire the harvest")
    c = _task(env, repo, "write the seam test")
    h = _task(env, repo, "land the docs")
    _allowed(_stop(env, "s-x", _DECISION, repo))  # another session's question: an awaiting item
    (awaiting,) = [it["id"] for it in _awaiting(repo)]
    _work(env, repo, "claim", h, "--session", "s-2")

    # three Stops on free text the register accepts: ONE open `next` item, the last text
    stamps = []
    for nxt in (
        "command 1 of 5 — the audit",
        "phase B of the rollout",
        "docs/development/plans/2026-09-25-plan-1-x.md step 2",
    ):
        _allowed(_stop(env, "s-1", _said(nxt), repo))
        (mine,) = _open_nexts(repo, "s-1")
        assert mine["next"] == nxt, mine
        stamps.append(mine["next_at"])
    assert stamps == sorted(stamps) and len(set(stamps)) == 3, stamps
    thread = mine["id"]

    # a NEXT naming an open item: claims it, sets its next, and supersedes the `next` item
    finish = f"finish {a} — then the docs"
    _allowed(_stop(env, "s-1", _said(finish), repo))
    items = _by_id(repo)
    assert items[a]["next"] == finish and (_claim(repo, a) or {}).get("session") == "s-1"
    assert (items[thread]["status"], items[thread]["note"]) == ("dropped", "superseded")
    assert _open_nexts(repo, "s-1") == []

    # an operator-decision NEXT naming an id: no claim, no item file changed
    files = _item_files(repo)
    _allowed(_stop(env, "s-1", _said(f"operator decision: approve {c} first"), repo))
    assert _item_files(repo) == files and _claim(repo, c) is None

    # awaiting id first, open id second: only the second is claimed and updated
    mixed = f"answer {awaiting} then {c}"
    _allowed(_stop(env, "s-1", _said(mixed), repo))
    items = _by_id(repo)
    assert (_claim(repo, c) or {}).get("session") == "s-1" and items[c]["next"] == mixed
    assert _claim(repo, awaiting) is None and items[awaiting].get("next") != mixed

    # a NEXT naming only an item another live session holds: no claim, no item file changed
    files = _item_files(repo)
    held = _claim(repo, h)
    _allowed(_stop(env, "s-1", _said(f"pair on {h}"), repo))
    assert _item_files(repo) == files
    assert _claim(repo, h) == held and (held or {}).get("session") == "s-2"

    # a third session's `next` item, 8 days idle — planted only now, after s-1's last Stop,
    # because any harvest closes it
    _allowed(_stop(env, "s-3", _said("command 2 of 9 — the census"), repo))
    (idle,) = _open_nexts(repo, "s-3")
    old = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 8 * 86400))
    idle.update(next_at=old, created=old)
    path = repo / ".fabrik" / "work" / f"{idle['id']}.json"
    path.write_text(json.dumps(idle, indent=2) + "\n", encoding="utf-8")

    _allowed(_stop(env, "s-2", _said(f"continue {h} — the docs pass"), repo))
    items = _by_id(repo)
    assert (items[idle["id"]]["status"], items[idle["id"]]["note"]) == ("dropped", "idle 7 days")
    assert (_claim(repo, h) or {}).get("session") == "s-2" and _renewed_claim(repo, h, held)

    # the whole store: ONE superseded `next` item; s-1 holds exactly the first named item and
    # the second id of the mixed line
    superseded = [
        it for it in items.values() if it["kind"] == "next" and it.get("note") == "superseded"
    ]
    assert [it["id"] for it in superseded] == [thread], superseded
    held_by_1 = sorted(i for i in items if (_claim(repo, i) or {}).get("session") == "s-1")
    assert held_by_1 == sorted([a, c]), held_by_1


def _renewed_claim(repo: Path, item_id: str, before: dict | None) -> bool:
    now = _claim(repo, item_id) or {}
    return bool(before) and now.get("at", 0) > (before or {}).get("at", 0)


# ── the other allowed exits and a blocked Stop (a fabrik-style repo) ─────────────────────────


def test_the_pass_through_exit_stores_the_decision_item(tmp_path):
    env = _env(tmp_path)
    repo = _fabrik_repo(tmp_path, env)
    _allowed(_stop(env, "s-p", _DECISION, repo))
    assert len(_awaiting(repo)) == 1, _items(repo)


def test_the_quota_hold_exit_stores_the_decision_item(tmp_path):
    """The hold's exit is the ONLY allowed one here: without the stamp the red gate blocks and no
    block is stored (the control half)."""
    env = {**_env(tmp_path), "FAKE_FAILS": "A,B"}
    repo = _fabrik_repo(tmp_path, env)
    (Path(env["TMPDIR"]) / "fabrik-gate-baseline-s-q.json").write_text('["A"]', encoding="utf-8")
    _blocked(_stop(env, "s-q", _DECISION, repo))
    assert _awaiting(repo) == [], _items(repo)

    state = Path(env["ROTATE_STATE_DIR"])
    (state / "fleet-exhausted").write_text("0", encoding="utf-8")
    Path(env["QUOTA_STOP_TICK_LOG"]).write_text("fresh\n", encoding="utf-8")
    _allowed(_stop(env, "s-q", _DECISION, repo))
    assert len(_awaiting(repo)) == 1, _items(repo)


def test_a_hook_error_after_the_judgement_still_stores_the_decision(tmp_path, monkeypatch):
    """D7 W4-O4: the fail-open catch-all ALLOWS the Stop, so an accepted DECISION block judged
    before the error is stored there too — never lost in both the slot and the store."""
    import io

    env = _env(tmp_path)
    repo = _fabrik_repo(tmp_path, env)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    hook = _hook_module()

    def boom(*a, **kw):
        raise RuntimeError("injected after the judgement")

    monkeypatch.setattr(hook, "_read_counters", boom)
    payload = {
        "session_id": "s-err",
        "hook_event_name": "Stop",
        "last_assistant_message": _DECISION,
        "cwd": str(repo),
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert hook.main([]) == 0
    assert len(_awaiting(repo)) == 1, _items(repo)


def test_a_blocked_stop_still_renews_the_claim(tmp_path):
    """The plain harvest runs on EVERY Stop, so a blocked turn is a heartbeat too."""
    env = {**_env(tmp_path), "FAKE_FAILS": "A,B"}
    repo = _fabrik_repo(tmp_path, env)
    (Path(env["TMPDIR"]) / "fabrik-gate-baseline-s-bl.json").write_text('["A"]', encoding="utf-8")
    claim_path = _claimed(env, repo, "s-bl")
    _blocked(_stop(env, "s-bl", "no footer and no block at all", repo))
    assert _renewed(claim_path)


# ── the heartbeat ────────────────────────────────────────────────────────────────────────────


def test_a_quiet_stop_renews_the_sessions_claim(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    claim_path = _claimed(env, repo, "s-cl")
    _allowed(_stop(env, "s-cl", "no footer and no block at all", repo))
    assert _renewed(claim_path)


def test_a_stop_with_no_text_at_all_still_renews_the_claim(tmp_path):
    """The flush race: no last_assistant_message and no transcript. The heartbeat still beats, and
    the empty harvest stores nothing in the session's anchor state (no NEXT, no anchor)."""
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    claim_path = _claimed(env, repo, "s-e")
    _allowed(_stop(env, "s-e", None, repo))
    assert _renewed(claim_path)
    assert not (Path(env["THREAD_ANCHOR_DIR"]) / "s-e.json").exists()


def test_an_uninitialised_repo_stops_cleanly_and_gets_no_store(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env, init=False)
    _allowed(_stop(env, "s-u", _DECISION, repo))
    _allowed(_stop(env, "s-u2", None, repo))
    assert not (repo / ".fabrik").exists()


# ── the argv the hook passes ─────────────────────────────────────────────────────────────────

_STUB = (
    "import json, os, sys\n"
    "# accepts --decision-ok{extra}\n"
    "sys.stdin.read()\n"
    "with open(os.environ['ARGV_LOG'], 'a', encoding='utf-8') as f:\n"
    "    f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
)


def _stubbed(tmp_path: Path, env: dict[str, str], knows_repo: bool) -> Path:
    repo = _repo(tmp_path, env, init=False)
    (repo / "scripts").mkdir()
    extra = " and --repo" if knows_repo else ""
    (repo / "scripts" / "thread_anchor.py").write_text(_STUB.format(extra=extra), encoding="utf-8")
    env["ARGV_LOG"] = str(tmp_path / "argv.log")
    return repo


def _argvs(env: dict[str, str]) -> list[list[str]]:
    log = Path(env["ARGV_LOG"])
    return [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines()]


def test_payload_cwd_and_a_knowing_script_pass_repo_to_both_harvests(tmp_path):
    env = _env(tmp_path)
    repo = _stubbed(tmp_path, env, knows_repo=True)
    _allowed(_stop(env, "s-k", _DECISION, repo))
    argvs = _argvs(env)
    assert len(argvs) == 2, argvs  # the plain harvest and the decision harvest
    assert "--decision-ok" in argvs[1], argvs
    for argv in argvs:
        assert argv[argv.index("--repo") + 1] == str(repo), argvs


@pytest.mark.parametrize("case", ["script-does-not-know-repo", "payload-has-no-cwd", "dot"])
def test_no_repo_flag_without_an_absolute_payload_cwd_or_a_knowing_script(tmp_path, case):
    """The hook runs FROM the repo (its process cwd), so a cwd-relative `root` resolves there and
    the repo's stub records the argv — exactly where an os.getcwd() fallback would point
    `--repo` (a `.` from /opt/fabrik would have written the hub's live store)."""
    env = _env(tmp_path)
    repo = _stubbed(tmp_path, env, knows_repo=case != "script-does-not-know-repo")
    cwd = {"script-does-not-know-repo": str(repo), "payload-has-no-cwd": None, "dot": "."}[case]
    _allowed(_stop(env, "s-n", _DECISION, cwd, proc_cwd=repo))
    argvs = _argvs(env)
    assert len(argvs) == 2, argvs
    assert all("--repo" not in argv for argv in argvs), argvs


def _hook_module():
    spec = importlib.util.spec_from_file_location("final_gate_stop_seam", HOOK)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize(
    "cwd", [".", "x", "wrepo", "-foo", " /tmp ", "/tmp ", "\t/tmp", "", "   ", None, 7]
)
def test_repo_argv_refuses_every_cwd_that_is_not_an_absolute_path_as_given(tmp_path, cwd):
    ta = tmp_path / "thread_anchor.py"
    ta.write_text("# knows --repo\n", encoding="utf-8")
    assert _hook_module()._repo_argv(ta, cwd) == []


def test_repo_argv_passes_an_absolute_cwd_exactly_as_given(tmp_path):
    ta = tmp_path / "thread_anchor.py"
    ta.write_text("# knows --repo\n", encoding="utf-8")
    hook = _hook_module()
    assert hook._repo_argv(ta, str(tmp_path)) == ["--repo", str(tmp_path)]
    assert hook._repo_argv(tmp_path / "missing.py", str(tmp_path)) == []
    assert hook._repo_argv(None, str(tmp_path)) == []
