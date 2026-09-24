"""Behavior contract for `status`, `sync --check` and the derived drift classes (ticket T02).

Spec and plan state is never copied into the store: `status`/`sync` read spec/plan `Status:`
lines, plan locks, and the store's own items directly, every time. Every test runs against a
throwaway git repo under `tmp_path` with an explicit `env=` — real spec/plan/ticket files and
`.fabrik/plan-locks/*.json`, never the hub's own tree.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "work.py"

_BLOCK = (
    "DECISION NEEDED (ground: gate)\n"
    "- Question: Deploy the certified build to production now?\n"
    "- Why it is yours: gate — Gate 2, a destructive/irreversible action needing authorisation.\n"
    "- Options: A — deploy now · B — hold for one more smoke pass\n"
    "- Recommendation: A — the certification gauntlet already passed."
)


def _work_module() -> ModuleType:
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import work
    finally:
        sys.path.remove(str(SCRIPT.parent))
    return work


def _env(tmp_path: Path) -> dict[str, str]:
    for sub in ("home", "tmp"):
        (tmp_path / sub).mkdir(exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_path / "home"),
        "TMPDIR": str(tmp_path / "tmp"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }


def _git(cwd: Path, env: dict[str, str], *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout


def _repo(tmp_path: Path, env: dict[str, str]) -> Path:
    work = tmp_path / "repo"
    _git(tmp_path, env, "init", "-q", "-b", "main", str(work))
    (work / "README").write_text("seed\n", encoding="utf-8")
    _git(work, env, "add", "README")
    _git(work, env, "commit", "-q", "-m", "seed")
    return work.resolve()


def run(
    args: list[str], env: dict[str, str], cwd: Path, timeout: float = 60
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _ok(args: list[str], env: dict[str, str], cwd: Path) -> str:
    r = run(args, env, cwd)
    assert r.returncode == 0, (args, r.stdout, r.stderr)
    return r.stdout


def _store(tmp_path: Path, env: dict[str, str], distributor: str = "intel") -> Path:
    repo = _repo(tmp_path, env)
    _ok(["init", "--distributor", distributor], env, repo)
    return repo


def _add(tree: Path, env: dict[str, str], title: str = "T", kind: str = "backlog", **kw) -> str:
    args = ["add", "--kind", kind, "--title", title]
    for key, val in kw.items():
        args += [f"--{key}", val]
    out = _ok(args, env, tree)
    return Path(out.strip().splitlines()[-1]).stem


def _item_file(tree: Path, item_id: str) -> Path:
    return tree / ".fabrik" / "work" / f"{item_id}.json"


def _item(tree: Path, item_id: str) -> dict:
    return json.loads(_item_file(tree, item_id).read_text(encoding="utf-8"))


def _write_item(tree: Path, item_id: str, data: dict) -> None:
    _item_file(tree, item_id).write_text(json.dumps(data), encoding="utf-8")


def _shared(repo: Path) -> Path:
    return repo / ".git" / "fabrik-work"


def _commit_store(repo: Path, env: dict[str, str], msg: str = "store") -> None:
    _git(repo, env, "add", ".fabrik")
    _git(repo, env, "commit", "-q", "-m", msg)


def _commit_dated(
    repo: Path, env: dict[str, str], paths: list[str], msg: str, when: datetime
) -> None:
    """A commit whose author/committer date is ``when`` — the property `_commit_epoch` reads,
    never the filesystem mtime (a checkout resets that to `now`)."""
    dated = dict(env)
    iso = when.strftime("%Y-%m-%dT%H:%M:%S")
    dated["GIT_AUTHOR_DATE"] = iso
    dated["GIT_COMMITTER_DATE"] = iso
    _git(repo, dated, "add", *paths)
    _git(repo, dated, "commit", "-q", "-m", msg)


def _spec(repo: Path, name: str, status: str) -> str:
    """``docs/superpowers/specs/<name>.md``; returns its repo-relative posix path."""
    d = repo / "docs" / "superpowers" / "specs"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.md"
    p.write_text(f"# {name}\n\nStatus: {status}\nOwner: infra\n", encoding="utf-8")
    return f"docs/superpowers/specs/{name}.md"


def _plan_file(repo: Path, name: str, status: str, extra: str = "") -> str:
    """A standalone dated plan file; returns its repo-relative posix path."""
    d = repo / "docs" / "development" / "plans"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.md"
    p.write_text(f"# {name}\n\nStatus: {status}\n{extra}\nOwner: infra\n", encoding="utf-8")
    return f"docs/development/plans/{name}.md"


def _plan_dir(repo: Path, name: str, status: str, board: str = "") -> str:
    """A same-stem spine inside a dated plan-set directory; returns its repo-relative posix path."""
    d = repo / "docs" / "development" / "plans" / name
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.md"
    p.write_text(f"# {name}\n\nStatus: {status}\nOwner: infra\n{board}\n", encoding="utf-8")
    return f"docs/development/plans/{name}/{name}.md"


def _lock(repo: Path, plan_rel: str, slug: str, status: str = "active") -> None:
    d = repo / ".fabrik" / "plan-locks"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug}.json").write_text(
        json.dumps({"plan": plan_rel, "status": status}), encoding="utf-8"
    )


def _marker(repo: Path, item_id: str, *, age_days: float, tree: str = "") -> None:
    d = _shared(repo) / "closed"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{item_id}.json").write_text(
        json.dumps(
            {
                "id": item_id,
                "status": "done",
                "at": time.time() - age_days * 86400,
                "tree": tree,
                "session": "s",
                "agent": "",
            }
        ),
        encoding="utf-8",
    )


def _drift_lines(stdout: str, cls: int) -> list[str]:
    prefix = f"DRIFT {cls} ("
    return [ln for ln in stdout.splitlines() if ln.startswith(prefix)]


def _reading_rows(repo: Path) -> list[dict]:
    path = _shared(repo) / "readings.jsonl"
    if not path.is_file():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


# ── row 1: each of the eight drift classes, isolated by its own fixture path ─────────────────


def test_status_lists_each_drift_class_by_its_own_fixture_paths(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)

    clean_spec = _spec(repo, "2026-09-24-clean-spec-design", "CONVERGED")
    class1_spec = _spec(repo, "2026-09-24-orphan-spec-design", "CONVERGED")

    clean_plan = _plan_file(repo, "2026-09-24-plan-clean", "DRAFT", extra=f"Spec: {clean_spec}\n")
    old = datetime.now(UTC) - timedelta(days=10)
    class2_plan = _plan_dir(repo, "2026-09-24-plan-2-stale-converged", "CONVERGED")
    class3_plan = _plan_dir(repo, "2026-09-24-plan-3-in-progress", "IN-PROGRESS")
    class4_plan = _plan_dir(repo, "2026-09-24-plan-4-executed-open", "EXECUTED")
    class8_plan = _plan_file(repo, "2026-09-24-plan-8-weird", "WEIRD")

    class4_item = _add(repo, env, title="still open", kind="task", link=f"plan={class4_plan}")
    class6_item = _add(repo, env, title="bad evidence")
    it = _item(repo, class6_item)
    it.update(status="done", evidence="0" * 40)
    _write_item(repo, class6_item, it)

    _commit_store(repo, env, "seed store + fixtures")
    _commit_dated(repo, env, [class2_plan], "age the stale plan", old)

    (repo / "docs" / "STRATEGIC_BACKLOG.md").write_text(
        "# Strategic Backlog\n\n"
        "<!-- AUTO-GENERATED:BACKLOG:START -->\n- W-00000000 stale\n"
        "<!-- AUTO-GENERATED:BACKLOG:END -->\n",
        encoding="utf-8",
    )
    backlog_item = _add(repo, env, title="fresh backlog row")

    out = _ok(["status"], env, repo)

    assert _drift_lines(out, 1) == [f"DRIFT 1 (advisory)  {class1_spec}"]
    assert _drift_lines(out, 2) == [f"DRIFT 2 (blocking)  {class2_plan}"]
    assert _drift_lines(out, 3) == [f"DRIFT 3 (blocking)  {class3_plan}"]
    assert _drift_lines(out, 4) == [f"DRIFT 4 (blocking)  {class4_plan}"]
    assert _drift_lines(out, 6) == [f"DRIFT 6 (blocking)  .fabrik/work/{class6_item}.json"]
    assert _drift_lines(out, 7) == ["DRIFT 7 (advisory)  docs/STRATEGIC_BACKLOG.md"]
    assert _drift_lines(out, 8) == [f"DRIFT 8 (advisory)  {class8_plan}"]

    for cls in range(1, 9):
        for clean in (clean_spec, clean_plan):
            assert clean not in "\n".join(_drift_lines(out, cls)), (cls, clean)
    assert class4_item  # the linking item exists — silences flake8 unused-var noise
    assert backlog_item


def test_status_lists_a_corrupt_and_a_vocabulary_violating_item_as_class_5(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    corrupt = repo / ".fabrik" / "work" / "W-baaaaaaa.json"
    corrupt.write_text("{not json", encoding="utf-8")
    bad_status = repo / ".fabrik" / "work" / "W-cccccccc.json"
    bad_status.write_text(
        json.dumps({"id": "W-cccccccc", "status": "weird", "title": "x"}), encoding="utf-8"
    )
    out = _ok(["status"], env, repo)
    lines = _drift_lines(out, 5)
    assert ".fabrik/work/W-baaaaaaa.json" in "\n".join(lines)
    assert ".fabrik/work/W-cccccccc.json" in "\n".join(lines)


# ── row 2: plan-status normalisation ──────────────────────────────────────────────────────────


def test_plan_status_normalisation_only_flags_the_unrecognised_value(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _plan_dir(repo, "2026-09-24-plan-a-in-progress", "IN_PROGRESS")
    _plan_dir(repo, "2026-09-24-plan-b-complete", "COMPLETE")
    _plan_dir(repo, "2026-09-24-plan-c-planned", "PLANNED")
    weird = _plan_dir(repo, "2026-09-24-plan-d-weird", "WEIRD")

    out = _ok(["status"], env, repo)
    lines = _drift_lines(out, 8)
    assert lines == [f"DRIFT 8 (advisory)  {weird}"]


def test_status_reads_the_ticket_board_for_its_progress_line(tmp_path):
    board = (
        "\n## Ticket Board\n\n"
        "| Ticket | Title | State | Commit |\n"
        "|---|---|---|---|\n"
        "| T01 | thing one | ✅ | abc |\n"
        "| T02 | thing two | 🔵 | |\n"
    )
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    plan = _plan_dir(repo, "2026-09-24-plan-with-board", "IN-PROGRESS", board=board)
    _lock(repo, plan, "2026-09-24-plan-with-board")  # silence class 3 — not under test here

    out = _ok(["status"], env, repo)
    assert f"PLAN             {plan}  tickets 1/2 done" in out.splitlines()


# ── row 3: class 6 — bad evidence, legacy exemption, a stale residue-free closed marker ───────


def test_class_6_flags_bad_evidence_and_a_stale_open_marker_but_exempts_legacy(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)

    recent_bad = _add(repo, env, title="recent, bad evidence")
    it = _item(repo, recent_bad)
    it.update(status="done", evidence="f" * 40)
    _write_item(repo, recent_bad, it)

    legacy_bad = _add(repo, env, title="legacy, bad evidence")
    it = _item(repo, legacy_bad)
    it.update(status="done", evidence="e" * 40, legacy=True)
    _write_item(repo, legacy_bad, it)

    stale_marker_item = _add(repo, env, title="closed elsewhere, still open here")
    _marker(repo, stale_marker_item, age_days=20, tree=str(repo.parent / "elsewhere"))

    out = _ok(["status"], env, repo)
    lines = "\n".join(_drift_lines(out, 6))
    assert f".fabrik/work/{recent_bad}.json" in lines
    assert f".fabrik/work/{stale_marker_item}.json" in lines
    assert f".fabrik/work/{legacy_bad}.json" not in lines


# ── row 4: sync --check on a fresh (unmigrated) store ─────────────────────────────────────────


def test_sync_check_prints_drift_and_appends_a_reading_but_stays_advisory_pre_migration(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    plan = _plan_dir(repo, "2026-09-24-plan-in-progress", "IN-PROGRESS")

    r = run(["sync", "--check"], env, repo)
    assert r.returncode == 0, r.stderr
    assert f"DRIFT 3 (blocking)  {plan}" in r.stdout

    rows = _reading_rows(repo)
    assert len(rows) == 1
    assert rows[0]["kind"] == "sync"
    assert rows[0]["counts"]["3"] == 1
    assert rows[0]["blocking_active"] is False


# ── row 5: sync blocks only after migrated_at + 7 consecutive clean calendar days ─────────────


def _seed_migration(repo: Path, env: dict[str, str], migrated_at: datetime) -> None:
    cfg_path = repo / ".fabrik" / "work" / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["migrated_at"] = migrated_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")


def _append_clean_reading(repo: Path, when: datetime) -> None:
    path = _shared(repo) / "readings.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "at": when.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "kind": "sync",
        "counts": {str(n): 0 for n in range(1, 9)},
        "blocking_active": False,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def test_sync_blocks_once_7_consecutive_clean_calendar_days_follow_migration(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    plan = _plan_dir(repo, "2026-09-24-plan-in-progress", "IN-PROGRESS")
    migrated_at = datetime.now(UTC) - timedelta(days=10)
    _seed_migration(repo, env, migrated_at)
    for i in range(1, 8):
        _append_clean_reading(repo, migrated_at + timedelta(days=i, hours=1))

    r = run(["sync", "--check"], env, repo)
    assert r.returncode == 1, r.stdout
    assert f"DRIFT 3 (blocking)  {plan}" in r.stdout


def test_sync_stays_advisory_with_only_6_consecutive_clean_calendar_days(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _plan_dir(repo, "2026-09-24-plan-in-progress", "IN-PROGRESS")
    migrated_at = datetime.now(UTC) - timedelta(days=10)
    _seed_migration(repo, env, migrated_at)
    for i in range(1, 7):
        _append_clean_reading(repo, migrated_at + timedelta(days=i, hours=1))

    r = run(["sync", "--check"], env, repo)
    assert r.returncode == 0, r.stdout


# ── row 6: sync --check on a repo with no store ───────────────────────────────────────────────


def test_sync_check_on_a_store_less_repo_prints_one_line_and_creates_nothing(tmp_path):
    env = _env(tmp_path)
    repo = _repo(tmp_path, env)
    r = run(["sync", "--check"], env, repo)
    assert r.returncode == 0
    assert len(r.stdout.strip().splitlines()) == 1
    assert not (repo / ".fabrik").exists()
    assert not (repo / ".git" / "fabrik-work").exists()


# ── row 7: status lists only the untracked item file as uncommitted ──────────────────────────


def test_status_lists_only_the_untracked_item_as_uncommitted(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    committed = _add(repo, env, title="committed")
    _commit_store(repo, env, "commit one item")
    untracked = _add(repo, env, title="untracked")

    out = _ok(["status"], env, repo)
    lines = [ln for ln in out.splitlines() if ln.startswith("UNCOMMITTED")]
    assert any(untracked in ln for ln in lines)
    assert not any(committed in ln for ln in lines)


# ── the enforcement-reader fallback (a repo without scripts/enforcement/) ─────────────────────


def test_missing_enforcement_readers_fall_back_and_say_so_on_stderr(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _spec(repo, "2026-09-24-orphan-spec-design", "CONVERGED")
    r = run(["status"], env, repo)
    assert r.returncode == 0
    assert "check_convergence import failed" in r.stderr
    assert "check_stage_artifacts import failed" in r.stderr
    assert "fallback" in r.stderr


# ── in-process: `_drift_report` and `_sync_blocking_active` are correctly re-derived ──────────


def test_drift_report_is_re_derived_not_cached(tmp_path, monkeypatch):
    env = _env(tmp_path)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("CLAUDE_AGENT", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    work = _work_module()
    repo = _store(tmp_path, env)
    plan = _plan_dir(repo, "2026-09-24-plan-in-progress", "IN-PROGRESS")
    report = work._drift_report(repo)
    assert report[3] == [plan]
    _lock(repo, plan, "2026-09-24-plan-in-progress")
    report_after = work._drift_report(repo)
    assert report_after[3] == []


# ── producer fixes from T04's review (P1: foreign claim renewal; P2: hook git budgets) ────────


def _in_process(tmp_path, monkeypatch, env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("CLAUDE_AGENT", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    return _work_module()


def test_ensure_decision_items_never_renews_a_passed_sessions_claim(tmp_path, monkeypatch):
    """P1: T04's second chance can pass ANOTHER (possibly dead) session's id to rescue its
    DECISION slot. `ensure_decision_items` must not renew that session's claim — a dead
    session's lease would otherwise be extended to a full 2h, defeating read-time expiry."""
    env = _env(tmp_path)
    work = _in_process(tmp_path, monkeypatch, env)
    repo = _store(tmp_path, env)
    item = _add(repo, env, title="claimed by a session that then died")
    _ok(["claim", item, "--session", "dead-session"], env, repo)
    claim_path = _shared(repo) / "claims" / f"{item}.json"
    before = claim_path.read_bytes()

    ids = work.ensure_decision_items(repo, [(_BLOCK, "digest-1", "dead-session")])

    assert ids and len(ids) == 1  # the decision item was still created/found
    after = claim_path.read_bytes()
    assert after == before, (
        "ensure_decision_items renewed 'dead-session's claim — it must renew no passed "
        "session's claim; only on_harvest renews, and only its own session"
    )


def test_ensure_decision_item_singular_also_never_renews_a_passed_sessions_claim(
    tmp_path, monkeypatch
):
    env = _env(tmp_path)
    work = _in_process(tmp_path, monkeypatch, env)
    repo = _store(tmp_path, env)
    item = _add(repo, env, title="claimed by a session that then died")
    _ok(["claim", item, "--session", "dead-session"], env, repo)
    claim_path = _shared(repo) / "claims" / f"{item}.json"
    before = claim_path.read_bytes()

    got = work.ensure_decision_item(
        repo, block=_BLOCK, msg_digest="digest-2", session="dead-session"
    )

    assert got is not None
    assert claim_path.read_bytes() == before


def test_on_harvest_still_renews_only_its_own_session(tmp_path, monkeypatch):
    """The mirror of the P1 fix: on_harvest's own contract is unchanged — it renews the
    HARVESTER's claim (the session actually calling it), never a foreign one."""
    env = _env(tmp_path)
    work = _in_process(tmp_path, monkeypatch, env)
    repo = _store(tmp_path, env)
    item = _add(repo, env, title="claimed by the harvesting session")
    _ok(["claim", item, "--session", "live-session"], env, repo)
    claim_path = _shared(repo) / "claims" / f"{item}.json"
    before = claim_path.read_bytes()

    work.on_harvest(repo, session="live-session")

    assert claim_path.read_bytes() != before, "on_harvest must renew its OWN session's claim"


def test_has_store_caches_repo_root_so_two_calls_run_git_once(tmp_path, monkeypatch):
    """P2a: repo_root/the common dir are cached per process, keyed by the resolved input path —
    a hook calling a hook-facing function twice must not pay for `git rev-parse` twice."""
    env = _env(tmp_path)
    work = _in_process(tmp_path, monkeypatch, env)
    repo = _store(tmp_path, env)

    calls = []
    real_run = subprocess.run

    def counting_run(cmd, *a, **kw):
        if isinstance(cmd, list) and cmd[:1] == ["git"]:
            calls.append(cmd)
        return real_run(cmd, *a, **kw)

    monkeypatch.setattr(subprocess, "run", counting_run)

    assert work.has_store(repo) is True
    assert work.has_store(repo) is True

    git_calls = [c for c in calls if "rev-parse" in c and "--show-toplevel" in c]
    assert len(git_calls) == 1, f"expected one cached rev-parse, got {len(git_calls)}: {calls}"


def test_hook_facing_calls_fail_open_fast_when_git_is_slow(tmp_path, monkeypatch):
    """P2b: every hook-facing function runs its git calls with HOOK_GIT_TIMEOUT_S (1.0 s), never
    the CLI's 10 s — against a 5 s Stop subprocess / 10 s prompt hook a slow git must fail open
    well under 2 s, not burn the full CLI budget."""
    env = _env(tmp_path)
    work = _in_process(tmp_path, monkeypatch, env)
    repo = _store(tmp_path, env)

    shim_dir = tmp_path / "slow-git-bin"
    shim_dir.mkdir()
    shim = shim_dir / "git"
    shim.write_text("#!/bin/sh\nsleep 3\nexit 1\n", encoding="utf-8")
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", f"{shim_dir}:{env['PATH']}")
    # a fresh, never-before-resolved path so the P2a cache cannot short-circuit this probe
    unresolved_repo = repo / "sub" / "dir"
    unresolved_repo.mkdir(parents=True)

    start = time.monotonic()
    result = work.has_store(unresolved_repo)
    elapsed = time.monotonic() - start

    assert result is False, "a timed-out git must fail OPEN to has_store's empty value"
    assert elapsed < 2.0, f"took {elapsed:.2f}s — HOOK_GIT_TIMEOUT_S was not applied"
