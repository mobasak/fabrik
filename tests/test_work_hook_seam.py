"""The Stop hook ↔ thread_anchor ↔ work store seam (T05, spec § Validation V1).

No stubs on the V1 path: a temp git repo initialised with the REAL ``scripts/work.py init``, no
``scripts/final_gate.py`` in it (so the hook takes its non-fabrik allowed exit and stores the
DECISION block), the REAL ``.claude/hooks/final_gate_stop.py`` run as a subprocess on a Stop
payload, then the REAL ``thread_anchor.py line --hook`` from a third session. The temp repo carries
no ``scripts/thread_anchor.py``, so the hook falls back to this checkout's copy (its ``__file__``).

The argv tests put a recording stub at ``<repo>/scripts/thread_anchor.py`` — the hook prefers the
repo's own copy — to see exactly what the hook passes (spec § Lifecycle — Degradation).

Hermetic: HOME, TMPDIR, THREAD_ANCHOR_DIR, COMMAND_RUN_DIR and KAIZEN_EVENTS_DIR all live under
tmp_path; the hub's own store is never read or written.
"""

from __future__ import annotations

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


def _items(repo: Path) -> list[dict]:
    store = repo / ".fabrik" / "work"
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(store.glob("W-*.json"))]


def _stop(
    env: dict[str, str], sid: str, message: str, cwd: Path | None, proc_cwd: Path | None = None
) -> subprocess.CompletedProcess:
    payload: dict = {
        "session_id": sid,
        "hook_event_name": "Stop",
        "last_assistant_message": message,
    }
    if cwd is not None:
        payload["cwd"] = str(cwd)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
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


# ── V1, end to end ────────────────────────────────────────────────────────────────────────────


def test_v1_two_stops_become_two_awaiting_items_every_session_sees(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)

    _allowed(_stop(env, "s-a", _DECISION, repo))
    awaiting = [it for it in _items(repo) if it["status"] == "awaiting-operator"]
    assert len(awaiting) == 1, _items(repo)

    _allowed(_stop(env, "s-b", _OTHER, repo))
    awaiting = [it for it in _items(repo) if it["status"] == "awaiting-operator"]
    assert len(awaiting) == 2, _items(repo)

    prompt = {"session_id": "s-c", "hook_event_name": "UserPromptSubmit", "prompt": "hi"}
    compact = {"session_id": "s-c", "hook_event_name": "SessionStart", "source": "compact"}
    for rnd in ("first", "after the state file is deleted"):
        for payload in (prompt, compact):
            out = _line(env, {**payload, "cwd": str(repo)})
            assert "Deploy the certified build to production now?" in out, (rnd, out)
            assert "Rotate the signing key to production now?" in out, (rnd, out)
            assert out.count("work: awaiting operator — W-") == 2, (rnd, out)
        (Path(env["THREAD_ANCHOR_DIR"]) / "s-c.json").unlink(missing_ok=True)


def test_a_quiet_stop_renews_the_sessions_claim(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    _work(env, repo, "add", "--kind", "task", "--title", "wire the hook")
    (item,) = _items(repo)
    _work(env, repo, "claim", item["id"], "--session", "s-cl")
    claim_path = repo / ".git" / "fabrik-work" / "claims" / f"{item['id']}.json"
    claim = json.loads(claim_path.read_text(encoding="utf-8"))
    claim["at"] = time.time() - 3600
    claim_path.write_text(json.dumps(claim), encoding="utf-8")

    _allowed(_stop(env, "s-cl", "no footer and no block at all", repo))
    renewed = json.loads(claim_path.read_text(encoding="utf-8"))
    assert renewed["at"] > time.time() - 60, renewed


def test_an_uninitialised_repo_stops_cleanly_and_gets_no_store(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env, init=False)
    _allowed(_stop(env, "s-u", _DECISION, repo))
    assert not (repo / ".fabrik").exists()


# ── the argv the hook passes (a recording stub at <repo>/scripts/thread_anchor.py) ───────────

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


@pytest.mark.parametrize("case", ["script-does-not-know-repo", "payload-has-no-cwd"])
def test_no_repo_flag_without_a_payload_cwd_or_a_knowing_script(tmp_path, case):
    env = _env(tmp_path)
    repo = _stubbed(tmp_path, env, knows_repo=case == "payload-has-no-cwd")
    if case == "payload-has-no-cwd":
        # the process cwd is the repo, so `root` resolves there and the repo's stub runs
        proc = _stop(env, "s-n", _DECISION, None, proc_cwd=repo)
    else:
        proc = _stop(env, "s-n", _DECISION, repo)
    _allowed(proc)
    argvs = _argvs(env)
    assert len(argvs) == 2, argvs
    assert all("--repo" not in argv for argv in argvs), argvs
