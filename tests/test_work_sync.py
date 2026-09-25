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
    """Pretty-printed, sorted-key, one-field-per-line — matching the store's own ``_dump`` — so a
    git diff of just one field (e.g. ``note``) never touches the ``"status"`` line's own text."""
    _item_file(tree, item_id).write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


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


def _spec_raw(repo: Path, name: str, status_line: str) -> str:
    """A spec whose header carries the LITERAL ``status_line`` text — for grammar-form and
    trailing-annotation probes ``_spec`` can't express."""
    d = repo / "docs" / "superpowers" / "specs"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.md"
    p.write_text(f"# {name}\n\n{status_line}\nOwner: infra\n", encoding="utf-8")
    return f"docs/superpowers/specs/{name}.md"


def _plan_file(repo: Path, name: str, status: str, extra: str = "") -> str:
    """A standalone dated plan file; returns its repo-relative posix path."""
    d = repo / "docs" / "development" / "plans"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.md"
    p.write_text(f"# {name}\n\nStatus: {status}\n{extra}\nOwner: infra\n", encoding="utf-8")
    return f"docs/development/plans/{name}.md"


def _plan_file_raw(repo: Path, name: str, status_line: str) -> str:
    """A standalone dated plan file whose header carries the LITERAL ``status_line`` text."""
    d = repo / "docs" / "development" / "plans"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.md"
    p.write_text(f"# {name}\n\n{status_line}\nOwner: infra\n", encoding="utf-8")
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


def _worktree(repo: Path, env: dict[str, str], name: str = "wt") -> Path:
    wt = repo.parent / name
    _git(repo, env, "worktree", "add", "-q", "-b", name, str(wt))
    return wt.resolve()


def _decisions_md(repo: Path, text: str) -> None:
    (repo / "docs").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "DECISIONS.md").write_text(text, encoding="utf-8")


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


# ── review pass 1 (rev-T02/fixes-1.md) — reader reuse, path normalisation, status grammar, ────
# ── age source, readings robustness, base-branch reads, and the closed missing-test gap ───────


def test_board_states_fn_reuses_the_real_check_plan_tickets_module():
    """A-S1: check_plan_tickets.py's @dataclass looks up sys.modules[cls.__module__] while
    processing its class body; importing it by path WITHOUT registering it in sys.modules first
    always failed, so "reuse the real reader" was permanently dead code. Probed read-only against
    THIS worktree's own scripts/enforcement/ (never a fixture copy, and nothing is written)."""
    work = _work_module()
    fn = work._board_states_fn(REPO)
    assert fn is not work._fallback_board_states
    # the module name is now repo-hash-suffixed (A-O19, T02 review pass 2) — prefix, not equality
    assert fn.__module__.startswith("_work_check_plan_tickets_")


def test_enforcement_import_failure_warns_at_most_once_per_process(tmp_path, monkeypatch):
    """A-O5: check_convergence was re-imported (and, on failure, re-warned) for every spec/plan
    _drift_report read — once per FILE, not once per process."""
    env = _env(tmp_path)
    work = _in_process(tmp_path, monkeypatch, env)
    repo = _store(tmp_path, env)  # no scripts/enforcement/ here -> the import always fails
    for i in range(3):
        _spec(repo, f"2026-09-24-spec-{i}-design", "CONVERGED")

    calls: list[str] = []
    orig_warn = work._warn

    def counting_warn(msg: str) -> None:
        calls.append(msg)
        orig_warn(msg)

    monkeypatch.setattr(work, "_warn", counting_warn)
    work._drift_report(repo)

    hits = [m for m in calls if "check_convergence import failed" in m]
    assert len(hits) == 1, f"expected exactly one warning, got {len(hits)}: {hits}"


def test_active_lock_naming_the_plan_directory_clears_class_3(tmp_path):
    """A-O1/A-O2: a plan-locks entry may name the plan-SET DIRECTORY (no .md), not the spine."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _plan_dir(repo, "2026-09-24-plan-in-progress", "IN-PROGRESS")
    plan_dir_rel = "docs/development/plans/2026-09-24-plan-in-progress"
    _lock(repo, plan_dir_rel, "2026-09-24-plan-in-progress")

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 3) == []


def test_item_link_naming_the_plan_directory_counts_for_class_2(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    old = datetime.now(UTC) - timedelta(days=10)
    plan = _plan_dir(repo, "2026-09-24-plan-2-stale", "CONVERGED")
    plan_dir_rel = "docs/development/plans/2026-09-24-plan-2-stale"
    _add(repo, env, title="linked via the directory", kind="task", link=f"plan={plan_dir_rel}")
    _commit_store(repo, env, "seed")
    _commit_dated(repo, env, [plan], "age it", old)

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 2) == []


def test_item_link_naming_the_plan_directory_counts_for_class_4(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    plan = _plan_dir(repo, "2026-09-24-plan-4-executed", "EXECUTED")
    plan_dir_rel = "docs/development/plans/2026-09-24-plan-4-executed"
    _add(
        repo,
        env,
        title="linked via the directory, still open",
        kind="task",
        link=f"plan={plan_dir_rel}",
    )

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 4) == [f"DRIFT 4 (blocking)  {plan}"]


def test_status_grammar_accepts_a_bold_wrapped_status_word(tmp_path):
    """A-O3/A-O7: "**Status**:" (bold wraps only the word, colon plain) is a shape the reused
    _STATUS_LINE misses entirely but check_convergence's own ANY_STATUS_LINE recognises."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    plan = _plan_file_raw(repo, "2026-09-24-plan-bold-word", "**Status**: IN-PROGRESS")

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 8) == []
    assert _drift_lines(out, 3) == [f"DRIFT 3 (blocking)  {plan}"]


def test_status_grammar_accepts_a_bulleted_status_line(tmp_path):
    """A-O3/A-O7: "- Status:" (a bullet-prefixed line)."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    plan = _plan_file_raw(repo, "2026-09-24-plan-bulleted", "- Status: IN-PROGRESS")

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 8) == []
    assert _drift_lines(out, 3) == [f"DRIFT 3 (blocking)  {plan}"]


def test_spec_status_value_naming_implemented_is_excluded_from_class_1(tmp_path):
    """A-O3/A-O7: "CONVERGED, IMPLEMENTED in D-12" is excluded from class 1 — the value NAMES
    IMPLEMENTED even though the primary word is CONVERGED."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _spec_raw(repo, "2026-09-24-carried-forward-design", "Status: CONVERGED, IMPLEMENTED in D-12")

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 1) == []


def test_spec_status_value_naming_superseded_is_excluded_from_class_1(tmp_path):
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _spec_raw(repo, "2026-09-24-carried-forward-design", "Status: CONVERGED, SUPERSEDED by D-9")

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 1) == []


def test_class_2_age_uses_the_last_status_changing_commit_not_the_last_touch(tmp_path):
    """A-S2: a plan CONVERGED 10 days ago, then re-committed TODAY for an unrelated typo fix,
    still drifts — the file's last-commit time must not reset the clock."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    old = datetime.now(UTC) - timedelta(days=10)
    plan = _plan_dir(repo, "2026-09-24-plan-2-typo", "CONVERGED")
    _commit_dated(repo, env, [plan], "converge it", old)
    (repo / plan).write_text((repo / plan).read_text() + "\nTypo fixed.\n", encoding="utf-8")
    _git(repo, env, "add", plan)
    _git(repo, env, "commit", "-q", "-m", "fix a typo")

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 2) == [f"DRIFT 2 (blocking)  {plan}"]


def test_class_6_age_uses_the_last_status_changing_commit_an_old_note_edit_stays_exempt(
    tmp_path,
):
    """A-S3: an old done item, re-touched TODAY for a note edit, stays exempt — the item's
    last-commit time must not reset the 14-day clock either."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env, title="done long ago")
    it = _item(repo, item)
    it.update(status="done", evidence="f" * 40)  # bad evidence
    _write_item(repo, item, it)
    old = datetime.now(UTC) - timedelta(days=20)
    rel = f".fabrik/work/{item}.json"
    _commit_dated(repo, env, [rel], "close it", old)
    it["note"] = "just a note, today"
    _write_item(repo, item, it)
    _git(repo, env, "add", rel)
    _git(repo, env, "commit", "-q", "-m", "add a note")

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 6) == []


def test_sync_check_tolerates_a_non_dict_counts_reading_and_stays_advisory(tmp_path):
    """A-O4: a sync row whose counts is a LIST (not a dict) must never crash sync --check, and
    must be treated as NOT clean (conservatively dirty)."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _plan_dir(repo, "2026-09-24-plan-in-progress", "IN-PROGRESS")
    migrated_at = datetime.now(UTC) - timedelta(days=10)
    _seed_migration(repo, env, migrated_at)
    for i in range(1, 8):
        _append_clean_reading(repo, migrated_at + timedelta(days=i, hours=1))
    path = _shared(repo) / "readings.jsonl"
    with path.open("a", encoding="utf-8") as f:
        row = {
            "at": (migrated_at + timedelta(days=4, hours=2)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "kind": "sync",
            "counts": [1, 2, 3],
            "blocking_active": False,
        }
        f.write(json.dumps(row) + "\n")

    r = run(["sync", "--check"], env, repo)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "Traceback" not in r.stderr


def test_class_6_stale_marker_reads_status_from_the_recorded_base_branch(tmp_path):
    """A-O9: "still open in the main checkout" means the store's RECORDED base branch — a stale
    marker's item read from a worktree where it locally shows done, but the base branch still
    shows open (unmerged), must still be flagged. The item carries VALID evidence, so class 6a
    (bad-evidence-within-14-days) cannot also explain a DRIFT 6 hit — only 6b (the stale marker)
    can."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)  # base_branch recorded = "main" (init's own branch)
    item = _add(repo, env, title="reads open on main, done only in a worktree")
    _commit_store(repo, env, "seed store")
    wt = _worktree(repo, env)

    it = _item(wt, item)
    it["status"] = "done"
    _write_item(wt, item, it)
    _git(wt, env, "add", ".fabrik")
    _git(wt, env, "commit", "-q", "-m", f"done locally, never merged to main ({item})")
    sha = _git(wt, env, "rev-parse", "HEAD").strip()
    it["evidence"] = sha
    _write_item(wt, item, it)
    _git(wt, env, "add", ".fabrik")
    _git(wt, env, "commit", "-q", "-m", "record evidence")

    _marker(repo, item, age_days=20, tree=str(wt))

    out = _ok(["status"], env, wt)
    lines = "\n".join(_drift_lines(out, 6))
    assert f".fabrik/work/{item}.json" in lines, (
        "the item reads open on the recorded base branch (main) — a stale marker must flag it "
        "even though the worktree's own local copy reads done"
    )


def test_a_dirty_reading_inside_the_window_keeps_sync_advisory(tmp_path):
    """A-O6: one dirty reading inside the 7-day window breaks the consecutive-clean-days streak,
    even with real class-3 drift live in the tree."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _plan_dir(repo, "2026-09-24-plan-in-progress", "IN-PROGRESS")
    migrated_at = datetime.now(UTC) - timedelta(days=10)
    _seed_migration(repo, env, migrated_at)
    for i in range(1, 8):
        _append_clean_reading(repo, migrated_at + timedelta(days=i, hours=1))
    path = _shared(repo) / "readings.jsonl"
    with path.open("a", encoding="utf-8") as f:
        row = {
            "at": (migrated_at + timedelta(days=4, hours=2)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "kind": "sync",
            "counts": {"3": 1},
            "blocking_active": False,
        }
        f.write(json.dumps(row) + "\n")

    r = run(["sync", "--check"], env, repo)
    assert r.returncode == 0, r.stdout


def test_a_reading_at_migrated_at_itself_does_not_count_toward_the_window(tmp_path):
    """B-H1: "at or before migrated_at does not count" — a reading exactly AT migrated_at, plus
    only 6 real days after it, must stay advisory (not silently treated as a 7th day)."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _plan_dir(repo, "2026-09-24-plan-in-progress", "IN-PROGRESS")
    migrated_at = datetime.now(UTC) - timedelta(days=10)
    _seed_migration(repo, env, migrated_at)
    _append_clean_reading(repo, migrated_at)
    for i in range(1, 7):
        _append_clean_reading(repo, migrated_at + timedelta(days=i, hours=1))

    r = run(["sync", "--check"], env, repo)
    assert r.returncode == 0, r.stdout


def test_7_clean_readings_on_non_consecutive_days_stay_advisory(tmp_path):
    """B-S1: 7 clean readings that skip a day are not 7 CONSECUTIVE clean calendar days."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _plan_dir(repo, "2026-09-24-plan-in-progress", "IN-PROGRESS")
    migrated_at = datetime.now(UTC) - timedelta(days=20)
    _seed_migration(repo, env, migrated_at)
    for i in (1, 2, 3, 4, 5, 6, 8):
        _append_clean_reading(repo, migrated_at + timedelta(days=i, hours=1))

    r = run(["sync", "--check"], env, repo)
    assert r.returncode == 0, r.stdout


def test_a_fresh_closed_marker_is_not_class_6(tmp_path):
    """B-S2: a marker well under 14 days old never trips class 6, regardless of the item's own
    status."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env, title="closed just now, still open here")
    _marker(repo, item, age_days=1)

    out = _ok(["status"], env, repo)
    assert f".fabrik/work/{item}.json" not in "\n".join(_drift_lines(out, 6))


def test_class_1_excluded_by_an_item_link(tmp_path):
    """B-S3 (part 1): an item's links.spec naming a CONVERGED spec excludes it from class 1."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    spec = _spec(repo, "2026-09-24-linked-spec-design", "CONVERGED")
    _add(repo, env, title="tracks the spec", kind="task", link=f"spec={spec}")

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 1) == []


def test_a_superseded_and_an_implemented_spec_are_excluded_from_class_1(tmp_path):
    """B-S3 (part 2): SUPERSEDED and IMPLEMENTED as the PRIMARY status word — the ordinary case
    the `primary != "CONVERGED"` gate already covers, pinned as a regression guard."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _spec(repo, "2026-09-24-superseded-spec-design", "SUPERSEDED")
    _spec(repo, "2026-09-24-implemented-spec-design", "IMPLEMENTED")

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 1) == []


def test_a_decisions_row_naming_the_spec_does_not_exclude_it_from_class_1(tmp_path):
    """Spec § Drift class 1: "A DECISIONS row naming the spec does not exclude it" — only a
    plan citation or an item link excludes a spec from class 1, never a DECISIONS.md mention."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    spec = _spec(repo, "2026-09-24-orphan-with-decision-design", "CONVERGED")
    _decisions_md(repo, f"# Decisions\n\n- D-311 — approved {spec} — 2026-09-24\n")

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 1) == [f"DRIFT 1 (advisory)  {spec}"]


def _archived_plan_dir(repo: Path, name: str, status: str, extra: str = "") -> str:
    """A plan set moved to ``docs/development/plans/archived/`` at its close."""
    d = repo / "docs" / "development" / "plans" / "archived" / name
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.md"
    p.write_text(f"# {name}\n\nStatus: {status}\n{extra}\nOwner: infra\n", encoding="utf-8")
    return f"docs/development/plans/archived/{name}/{name}.md"


def test_a_spec_named_by_an_archived_plan_is_carried_forward(tmp_path):
    """Class 1 is "no plan names it": a plan archived at its close still names its spec, so the
    spec is not drift. Measured at the hub's adoption: 24 of 28 class-1 lines were specs whose
    plan had been archived."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    carried = _spec(repo, "2026-09-24-shipped-design", "CONVERGED")
    orphan = _spec(repo, "2026-09-24-orphan-design", "CONVERGED")
    _archived_plan_dir(repo, "2026-09-24-plan-1-shipped", "EXECUTED", extra=f"Spec: {carried}\n")

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 1) == [f"DRIFT 1 (advisory)  {orphan}"]


def test_an_archived_executed_plan_with_an_open_linked_item_is_class_4(tmp_path):
    """Class 4 names an EXECUTED plan with an item still open against it; a plan is archived at
    EXECUTED, so the archived set is exactly where that item hides."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    plan = _archived_plan_dir(repo, "2026-09-24-plan-1-archived", "EXECUTED")
    _add(repo, env, title="still open", kind="task", link=f"plan={plan}")

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 4) == [f"DRIFT 4 (blocking)  {plan}"]


def test_a_link_written_before_the_plan_was_archived_still_counts_for_class_4(tmp_path):
    """D7 W2-S1: an item linked while its plan was live keeps the live path after the plan moves
    to archived/; that link means the archived plan, so the open item is class 4."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    plan = _archived_plan_dir(repo, "2026-09-24-plan-1-moved", "EXECUTED")
    live_link = "docs/development/plans/2026-09-24-plan-1-moved/2026-09-24-plan-1-moved.md"
    _add(repo, env, title="linked before the move", kind="task", link=f"plan={live_link}")

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 4) == [f"DRIFT 4 (blocking)  {plan}"]


def test_an_archived_plan_is_never_a_subject_of_classes_2_3_or_8(tmp_path):
    """Archived plans are settled: a stale CONVERGED, a lock-less IN-PROGRESS or an odd Status
    value there is history, not drift."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    old = datetime.now(UTC) - timedelta(days=30)
    a = _archived_plan_dir(repo, "2026-08-01-plan-1-old-converged", "CONVERGED")
    b = _archived_plan_dir(repo, "2026-08-01-plan-2-old-in-progress", "IN-PROGRESS")
    c = _archived_plan_dir(repo, "2026-08-01-plan-3-odd", "ABANDONED")
    _commit_dated(repo, env, [a, b, c], "age them", old)

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 2) == []
    assert _drift_lines(out, 3) == []
    assert _drift_lines(out, 8) == []


# ── review pass 2 (rev-T02/fixes-2.md) — 8 defects introduced or left open by pass 1 ──────────


def test_status_grammar_accepts_bold_colon_after_a_bullet_or_a_quote(tmp_path):
    """A-O3: the bold wraps the WHOLE `Status:` token (colon inside the bold), after a bullet or
    a blockquote marker — `- **Status:** X`, `> **Status:** X` — with the closing `**` followed
    by a space before the value."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    p1 = _plan_file_raw(repo, "2026-09-24-plan-bullet-bold-colon", "- **Status:** IN-PROGRESS")
    p2 = _plan_file_raw(repo, "2026-09-24-plan-quote-bold-colon", "> **Status:** IN-PROGRESS")

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 8) == []
    assert set(_drift_lines(out, 3)) == {
        f"DRIFT 3 (blocking)  {p1}",
        f"DRIFT 3 (blocking)  {p2}",
    }


def test_status_line_raw_takes_the_earliest_match_by_position(tmp_path):
    """A-O18: the reused/fallback regex can match a LATER body line (a plain `Status:` inside
    `## Notes`) that the rich regex would never need, while ONLY the rich regex can parse the
    REAL header a few lines above (bold closes BEFORE the colon — a shape the narrow regex,
    which requires the literal contiguous run "Status:", cannot match at all). Trying the narrow
    regex first and keeping ITS match unconditionally makes the later, irrelevant line win; the
    earliest match by position must win instead."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    plan = _plan_file_raw(
        repo,
        "2026-09-24-plan-precedence",
        "**Status**: IN_PROGRESS\n\n## Notes\nStatus: CONVERGED in the spec it implements",
    )

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 8) == []
    assert _drift_lines(out, 3) == [f"DRIFT 3 (blocking)  {plan}"]


def test_class_2_pickaxe_pattern_ignores_prose_mentioning_status(tmp_path):
    """A-O13: the pickaxe pattern must match the Status HEADER line, not any prose line that
    happens to contain the word — a later commit adding "See the status page for details." must
    not reset class 2's age clock."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    old = datetime.now(UTC) - timedelta(days=10)
    plan = _plan_dir(repo, "2026-09-24-plan-prose-status", "CONVERGED")
    _commit_dated(repo, env, [plan], "converge it", old)
    (repo / plan).write_text(
        (repo / plan).read_text() + "\nSee the status page for details.\n", encoding="utf-8"
    )
    _git(repo, env, "add", plan)
    _git(repo, env, "commit", "-q", "-m", "note")

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 2) == [f"DRIFT 2 (blocking)  {plan}"]


def test_class_6_uncommitted_status_flip_uses_mtime_not_the_old_commit(tmp_path):
    """A-O17: a committed `open` item, then flipped to `done` with bad evidence ONLY in the
    working tree (never committed), must read as fresh (age ~0) — not as the age of the original
    20-day-old commit that only ever recorded `open`."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env, title="open, then done uncommitted")
    rel = f".fabrik/work/{item}.json"
    old = datetime.now(UTC) - timedelta(days=20)
    _commit_dated(repo, env, [".fabrik"], "seed", old)

    it = _item(repo, item)
    it.update(status="done", evidence="f" * 40)
    _write_item(repo, item, it)  # uncommitted

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 6) == [f"DRIFT 6 (blocking)  {rel}"]


def test_normalize_repo_path_strips_a_trailing_slash_before_directory_expansion(tmp_path):
    """A-O14: a plan lock and an item link both naming `plan-dir/` (trailing slash) must resolve
    to the same-stem spine — not `plan-dir//plan-dir.md`."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    _plan_dir(repo, "2026-09-24-plan-trailing-slash", "IN-PROGRESS")
    plan_dir_rel = "docs/development/plans/2026-09-24-plan-trailing-slash/"
    _lock(repo, plan_dir_rel, "2026-09-24-plan-trailing-slash")

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 3) == []


def test_item_link_with_a_trailing_slash_also_resolves(tmp_path):
    """A-O14, the item-link half: `plan-dir/` (trailing slash) must count as linking the plan."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    plan = _plan_dir(repo, "2026-09-24-plan-4-trailing-slash", "EXECUTED")
    plan_dir_rel = "docs/development/plans/2026-09-24-plan-4-trailing-slash/"
    _add(
        repo,
        env,
        title="linked via a trailing-slash directory",
        kind="task",
        link=f"plan={plan_dir_rel}",
    )

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 4) == [f"DRIFT 4 (blocking)  {plan}"]


def test_implemented_superseded_exclusion_is_case_sensitive(tmp_path):
    """A-O15: the exclusion words must match UPPERCASE only. "CONVERGED (not yet implemented)"
    (lowercase, prose) stays in class 1; "CONVERGED, IMPLEMENTED in D-12" (the real annotation
    shape, uppercase) stays excluded."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    prose = _spec_raw(
        repo, "2026-09-24-not-yet-implemented-design", "Status: CONVERGED (not yet implemented)"
    )
    _spec_raw(
        repo, "2026-09-24-really-implemented-design", "Status: CONVERGED, IMPLEMENTED in D-12"
    )

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 1) == [f"DRIFT 1 (advisory)  {prose}"]


def test_class_6_base_ref_renamed_falls_back_to_the_current_tree(tmp_path):
    """A-O16: the recorded base branch ("main") renamed away ("trunk") must fall back to the
    CURRENT TREE, exactly as when no base is recorded — never flag purely because the recorded
    ref no longer resolves. Evidence is VALID (a real commit naming the item) so class 6a
    (bad-evidence-within-14-days) cannot also explain a hit — only 6b (the stale-marker read) can
    (mirrors the T02 pass-1 lesson: an item with no evidence lets 6a mask what 6b is doing)."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)  # base_branch recorded = "main"
    item = _add(repo, env, title="done everywhere, only the ref name changed")
    it = _item(repo, item)
    it["status"] = "done"
    _write_item(repo, item, it)
    _git(repo, env, "add", ".fabrik")
    _git(repo, env, "commit", "-q", "-m", f"done ({item})")
    sha = _git(repo, env, "rev-parse", "HEAD").strip()
    it["evidence"] = sha
    _write_item(repo, item, it)
    _git(repo, env, "add", ".fabrik")
    _git(repo, env, "commit", "-q", "-m", "record evidence")
    _git(repo, env, "branch", "-m", "main", "trunk")

    _marker(repo, item, age_days=20)

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 6) == [], (
        "the item is done on every branch; only the RECORDED ref name is gone — a renamed base "
        "must fall back to the current tree, not flag on a read failure"
    )


def test_import_enforcement_repo_collision_never_overwrites_another_repos_module(
    tmp_path, monkeypatch
):
    """A-O19 (part 1): sys.modules was keyed `_work_<name>`, shared across every repo. A FAILING
    import from repo B popped repo A's already-registered module out of sys.modules, even though
    repo A's import had already succeeded."""
    env = _env(tmp_path)
    work = _in_process(tmp_path, monkeypatch, env)
    a = tmp_path / "a" / "scripts" / "enforcement"
    a.mkdir(parents=True)
    (a / "check_x.py").write_text("V = 1\n", encoding="utf-8")
    b = tmp_path / "b" / "scripts" / "enforcement"
    b.mkdir(parents=True)
    (b / "check_x.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")

    ma = work._import_enforcement(tmp_path / "a", "check_x")
    assert ma is not None and ma.V == 1
    before = [k for k, v in sys.modules.items() if v is ma]
    assert before, "repo A's module must be registered in sys.modules"

    mb = work._import_enforcement(tmp_path / "b", "check_x")
    assert mb is None

    after = [k for k, v in sys.modules.items() if v is ma]
    assert after == before, "repo B's failed import must not de-register repo A's module"
    assert work._import_enforcement(tmp_path / "a", "check_x") is ma


def test_import_enforcement_catches_systemexit_and_falls_back(tmp_path, monkeypatch):
    """A-O19 (part 2): a module that calls sys.exit() at import time raises SystemExit, which is
    not an Exception subclass — the "never raises" contract must catch it too (never
    KeyboardInterrupt) and fall back with one warning."""
    env = _env(tmp_path)
    work = _in_process(tmp_path, monkeypatch, env)
    c = tmp_path / "c" / "scripts" / "enforcement"
    c.mkdir(parents=True)
    (c / "check_x.py").write_text("raise SystemExit(3)\n", encoding="utf-8")

    calls: list[str] = []
    orig_warn = work._warn

    def counting_warn(msg: str) -> None:
        calls.append(msg)
        orig_warn(msg)

    monkeypatch.setattr(work, "_warn", counting_warn)

    result = work._import_enforcement(tmp_path / "c", "check_x")

    assert result is None
    assert any("check_x import failed" in m for m in calls)


# ── review pass 3 (rev-T02/fixes-3.md) — 2 defects introduced by the pass-2 fixes ─────────────


def test_class_6_dirty_notes_only_edit_does_not_take_mtime(tmp_path):
    """A-O20: an item done 40 days ago (bad evidence), then given an UNCOMMITTED notes-only edit,
    must still read its age from the commit history — its "status" field is UNCHANGED between the
    working copy and HEAD, so this is "dirty" but not a genuine status flip."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    item = _add(repo, env, title="done long ago, bad evidence")
    it = _item(repo, item)
    it.update(status="done", evidence="f" * 40)
    _write_item(repo, item, it)
    rel = f".fabrik/work/{item}.json"
    old = datetime.now(UTC) - timedelta(days=40)
    _commit_dated(repo, env, [rel], "close it", old)

    it["note"] = "just a note, uncommitted"
    _write_item(repo, item, it)  # dirty (git status shows it modified); "status" itself unchanged

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 6) == []


def test_class_2_dirty_body_typo_still_drifts(tmp_path):
    """A-O20: an old CONVERGED plan given an UNCOMMITTED body-only typo fix must still drift —
    its Status: line is UNCHANGED between the working copy and HEAD, so the dirty flag alone must
    not force a fresh (mtime) reading."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    old = datetime.now(UTC) - timedelta(days=10)
    plan = _plan_dir(repo, "2026-09-24-plan-dirty-typo", "CONVERGED")
    _commit_dated(repo, env, [plan], "converge it", old)

    (repo / plan).write_text((repo / plan).read_text() + "\nTypo fixed.\n", encoding="utf-8")
    # left UNCOMMITTED on purpose

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 2) == [f"DRIFT 2 (blocking)  {plan}"]


def test_class_2_pickaxe_finds_tab_indented_header_and_ignores_t_prose(tmp_path):
    """A-O21: git -G is POSIX ERE, where a bracket expression has no backslash-escape support —
    `[ \\t]` means "space, OR a literal backslash, OR the letter t" (three characters), never
    "space or tab". A TAB-indented header was therefore invisible to the pickaxe, while a line
    merely starting "t Status: ..." was wrongly treated as one. `[[:blank:]]` (space-or-tab, no
    escape needed) fixes both: the tab-indented commit's age is found, and a later t-prose commit
    does not reset it."""
    env = _env(tmp_path)
    repo = _store(tmp_path, env)
    old = datetime.now(UTC) - timedelta(days=10)
    plan = _plan_file_raw(repo, "2026-09-24-plan-tab-header", "\tStatus: CONVERGED")
    _commit_dated(repo, env, [plan], "converge it (tab-indented header)", old)
    (repo / plan).write_text(
        (repo / plan).read_text() + "\nt Status: prose about something\n", encoding="utf-8"
    )
    _git(repo, env, "add", plan)
    _git(repo, env, "commit", "-q", "-m", "unrelated t-status prose")

    out = _ok(["status"], env, repo)
    assert _drift_lines(out, 2) == [f"DRIFT 2 (blocking)  {plan}"]
