# AFTER-EDIT: scripts/governance_sync_postcommit.sh
"""The post-commit governance-sync wrapper must FAIL LOUDLY and must not SKIP.

CLAUDE.md § Sync-consciousness promises "a sync failure prints loudly with the manual re-run
command", and names this wrapper as the ENFORCER of the trigger set. Two separate defects made both
claims false, and each was found only after the previous "fix" shipped:

1. `python … | tail -3 || { echo "SYNC FAILED"; exit 1; }` under `set -u` with no `pipefail` tested
   TAIL's status — always 0 — so the failure branch was UNREACHABLE and a sync dying partway through
   48 repos exited 0 silently.
2. Adding `pipefail` then broke the DETECTION pipeline: `git log … | grep -qE` is a SIGPIPE trap,
   because `grep -q` exits at the first match and closes the pipe, so git dies with 141 and the
   pipeline reports 141 — the `if` went FALSE and the sync SKIPPED on exactly the commits that
   touched a trigger path. Measured: 10/10 misses at 5000 changed files, safe below ~1000.

⚠️ These tests drive the REAL script. An earlier version of this file asserted against synthetic
`bash -c` snippets that never referenced the script at all — it would have passed with the fix fully
reverted, and it is precisely why defect 2 shipped. A test that does not name its subject under test
is not a guard.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "governance_sync_postcommit.sh"

# ⚠️ git EXPORTS these to hooks. This suite is itself run from inside a git hook (pre-commit runs
# pytest) and by the CI dispatcher, so an inherited GIT_DIR silently redirects the script's
# `git log -1` away from the scratch repo and onto /opt/fabrik — at which point every scratch repo
# is meaningless: the non-trigger test sees hub trigger paths and goes falsely red, and a test that
# has NOT stubbed the sync would match the filter no matter what repo it built.
_SCRUB = (
    "GOVERNANCE_SYNC_TEST",
    "SYNC_CMD",
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_CONFIG_GLOBAL",
)


def _clean_env(**extra: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in _SCRUB}
    env.update(extra)
    return env

def _drive(tmp_path: Path, repo: Path, *, cfg_files: str | None, env_extra: dict) -> subprocess.CompletedProcess:
    """Run the REAL script against a scratch repo, with the pwd guard, the config it reads, and the
    real fleet sync ALL redirected. Nothing here may reach /opt/fabrik or the 48 project trees.

    `cfg_files` is the governance-sync hook's `files:` value; None omits the key entirely (the
    empty-filter case).
    """
    import yaml

    hook = {"id": "governance-sync", "name": "s", "entry": "true", "language": "system"}
    if cfg_files is not None:
        hook["files"] = cfg_files
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(yaml.safe_dump({"repos": [{"repo": "local", "hooks": [hook]}]}), encoding="utf-8")

    marker = tmp_path / "real_sync_marker.sh"
    marker.write_text("#!/usr/bin/env bash\necho REAL_SYNC_RAN\n", encoding="utf-8")
    marker.chmod(0o755)

    src = SCRIPT.read_text(encoding="utf-8")
    src = src.replace('[ "$(pwd)" = "/opt/fabrik" ]', f'[ "$(pwd)" = "{repo}" ]')
    src = src.replace("/opt/fabrik/.pre-commit-config.yaml", str(cfg))
    src = src.replace(
        "/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/sync_enforcement_to_projects.py --force",
        str(marker),
    )
    # Guard on the ABSOLUTE command path, not the bare filename: the script also NAMES the sync
    # in its operator-facing error strings ("run scripts/sync_enforcement_to_projects.py --force"),
    # and matching those made this refuse every run. What must be unreachable is the executable.
    assert "/opt/fabrik/scripts/sync_enforcement_to_projects.py" not in src, (
        "the real fleet sync is still reachable from this test — refusing to run it"
    )
    shim = tmp_path / "drive.sh"
    shim.write_text(src, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in _SCRUB}
    env.update(env_extra)
    return subprocess.run(
        ["bash", str(shim)], cwd=repo, capture_output=True, text=True, timeout=120, env=env
    )



def _hub_clone(tmp_path: Path, changed: list[str]) -> Path:
    """A throwaway git repo whose HEAD touches `changed`, with the script's pwd-guard satisfied.

    The script hard-guards `pwd == /opt/fabrik`, so we run it with cwd spoofed via a wrapper that
    the test controls; the guard itself is covered separately below.
    """
    repo = tmp_path / "hub"
    repo.mkdir()
    genv = _clean_env()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=genv)
    for cfg in (("user.email", "t@fabrik.local"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(repo), "config", *cfg], check=True, env=genv)
    for rel in changed:
        f = repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=genv)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "commit.gpgsign=false", "commit", "-qm", "t"],
        check=True,
        env=genv,
    )
    return repo


def test_the_script_enables_pipefail() -> None:
    """Anchored on the `set` LINE, not the substring.

    ⚠️ `"pipefail" in src` passed against a file whose option had been removed, because the comment
    above it explains why pipefail matters — the test graded its own documentation.
    """
    lines = SCRIPT.read_text(encoding="utf-8").splitlines()
    set_lines = [ln.strip() for ln in lines if ln.strip().startswith("set ")]
    assert set_lines, "the script declares no `set` options at all"
    assert any("pipefail" in ln for ln in set_lines), (
        f"no `set` line enables pipefail — the SYNC FAILED branch is unreachable. set: {set_lines}"
    )


def test_detection_is_not_a_pipeline_and_sees_merges() -> None:
    """The anti-regression guard for BOTH shell defects, as a LIVE test.

    ⚠️ This was a helper (`_detection_shape`) that NOTHING called, and round 4's `--first-parent`
    edit falsified its literal — so after round 3 added it, the SIGPIPE guard was enforced by
    nothing at all. A guard that is never invoked is indistinguishable from a deleted one.
    """
    src = SCRIPT.read_text(encoding="utf-8")
    assert 'grep -qE "$FILTER" <<<"$NAMES"' in src, (
        "detection is a PIPELINE again — `git log | grep -q` SIGPIPEs under pipefail and silently "
        "skips the sync on large commits"
    )
    # ⚠️ CODE lines only. `--first-parent` appears 3x in the script and 2 of those are the comment
    # explaining why it is required — so a bare `in src` passes with the flag deleted from the one
    # line that matters. That is verbatim the defect the sibling test above records as already
    # found and fixed, reproduced here 15 lines below its own description of it. Strip comments.
    code = [ln for ln in src.splitlines() if not ln.lstrip().startswith("#")]
    assert any("git log -1 --first-parent" in ln for ln in code), (
        "without --first-parent a merge emits NO paths and silently skips the sync"
    )


def test_a_failing_sync_prints_loudly_and_exits_nonzero(tmp_path: Path) -> None:
    """The fail-loud branch — driven through `_drive()`, which makes the real sync UNREACHABLE.

    ⚠️ Round 4 wrote this test outside `_drive()`: it patched only the pwd guard, so the shim still
    carried the live `sync_enforcement_to_projects.py --force` and the ONLY thing between pytest and
    a 48-repo write was the sentinel env pair. The `boom` assertion was described as "what pins that
    shut" — it is evaluated AFTER `subprocess.run` returns, i.e. after the sync would already have
    written. Prevention has to be structural: `_drive()` swaps the sync literal for a marker and
    refuses to run if the absolute path survives. `REAL_SYNC_RAN` absence is the positive proof the
    injection took.
    """
    if not shutil.which("bash"):  # pragma: no cover
        pytest.skip("bash unavailable")

    repo = _hub_clone(tmp_path, [".windsurf/rules/core/00-x.md"])
    fail_sh = tmp_path / "failing_sync.sh"
    fail_sh.write_text("#!/usr/bin/env bash\necho boom\nexit 3\n", encoding="utf-8")
    fail_sh.chmod(0o755)

    r = _drive(
        tmp_path,
        repo,
        cfg_files=r"^\.windsurf/rules/",
        env_extra={"GOVERNANCE_SYNC_TEST": "1", "SYNC_CMD": str(fail_sh)},
    )
    assert "boom" in r.stdout, f"the INJECTED sync never ran: {r.stdout!r}"
    assert "REAL_SYNC_RAN" not in r.stdout, "the injection did not take — the real sync path ran"
    assert "SYNC FAILED" in r.stdout, (
        f"a failing sync must print loudly with the re-run command; stdout={r.stdout!r}"
    )
    assert r.returncode == 1, f"a failing sync must exit non-zero, got {r.returncode}"


def test_an_empty_filter_is_refused_rather_than_matching_everything(tmp_path: Path) -> None:
    """Drive the REAL script against a config whose governance-sync hook has NO `files:` key.

    ⚠️ This was a substring assertion (`'[ -n "$FILTER" ]' in src`) that never ran the guard and
    would have passed against `[ -n "$FILTER" ] || echo warn` — i.e. with the fail-open fully
    restored. `grep -qE ""` matches every line, so an empty filter treats EVERY commit as a
    trigger and silently defeats the single-sourcing contract.
    """
    repo = _hub_clone(tmp_path, ["README.md"])  # deliberately NOT a trigger path
    r = _drive(tmp_path, repo, cfg_files=None, env_extra={})
    assert "filter is EMPTY" in r.stdout, f"an empty filter was not refused: {r.stdout!r}"
    assert r.returncode == 1, f"an empty filter must exit non-zero, got {r.returncode}"
    assert "REAL_SYNC_RAN" not in r.stdout, "an empty filter synced anyway — fail-open"


def test_a_non_trigger_commit_does_not_sync(tmp_path: Path) -> None:
    """The filter's whole job, exercised end to end rather than asserted about."""
    repo = _hub_clone(tmp_path, ["README.md"])
    r = _drive(tmp_path, repo, cfg_files=r"^\.windsurf/rules/", env_extra={})
    assert "REAL_SYNC_RAN" not in r.stdout, f"a non-trigger commit synced: {r.stdout!r}"
    assert r.returncode == 0


def test_a_trigger_commit_syncs_even_with_thousands_of_changed_files(tmp_path: Path) -> None:
    """The SIGPIPE regression, through the REAL script — not a hand-copied snippet.

    ⚠️ The previous version built its own bash snippet and asserted the script CONTAINED a
    here-string. That went red on a straight revert, but it could not catch a pipeline
    re-introduced elsewhere, and grep-on-a-here-string cannot SIGPIPE, so its positive result was
    guaranteed regardless of the script. This drives the script itself at a size where the
    pipeline form measurably failed 10/10.
    """
    repo = _hub_clone(
        tmp_path, [".windsurf/rules/core/00-x.md"] + [f"docs/f{i}.md" for i in range(3000)]
    )
    for _ in range(3):
        r = _drive(tmp_path, repo, cfg_files=r"^\.windsurf/rules/", env_extra={})
        assert "REAL_SYNC_RAN" in r.stdout, f"the sync was SKIPPED on a trigger commit: {r.stdout!r}"


def test_a_merge_commit_that_touches_a_trigger_path_still_syncs(tmp_path: Path) -> None:
    """Merges emitted NO paths under a plain `--name-only`, so every merge silently skipped.

    A merge that RESOLVES A CONFLICT in a trigger file carries a blob that exists in no parent and
    was never synced by anyone. `--first-parent` is what makes the comment's claim true.
    """
    repo = _hub_clone(tmp_path, ["README.md"])
    # ⚠️ Every git call below MUST carry the scrubbed env for the same reason `_hub_clone` does:
    # git EXPORTS GIT_DIR to hooks, this suite runs from inside one, and an inherited GIT_DIR
    # points these commands at /opt/fabrik instead of the scratch repo. `_clean_env` was added
    # for `_hub_clone` and these seven calls were missed — the hole was still open here.
    genv = _clean_env()
    g = ["git", "-C", str(repo), "-c", "commit.gpgsign=false"]
    base = subprocess.run(
        [*g, "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True, env=genv
    ).stdout.strip()  # master or main, depending on the box's git default
    subprocess.run([*g, "checkout", "-qb", "feat"], check=True, env=genv)
    trig = repo / ".windsurf" / "rules" / "core" / "00-x.md"
    trig.parent.mkdir(parents=True, exist_ok=True)
    trig.write_text("y\n", encoding="utf-8")
    subprocess.run([*g, "add", "-A"], check=True, env=genv)
    subprocess.run([*g, "commit", "-qm", "feat"], check=True, env=genv)
    subprocess.run([*g, "checkout", "-q", base], check=True, env=genv)
    (repo / "other.txt").write_text("o\n", encoding="utf-8")
    subprocess.run([*g, "add", "-A"], check=True, env=genv)
    subprocess.run([*g, "commit", "-qm", "other"], check=True, env=genv)
    subprocess.run([*g, "merge", "-q", "--no-ff", "feat", "-m", "merge"], check=True, env=genv)

    r = _drive(tmp_path, repo, cfg_files=r"^\.windsurf/rules/", env_extra={})
    assert "REAL_SYNC_RAN" in r.stdout, (
        f"a MERGE carrying a trigger path did not sync — --first-parent missing? {r.stdout!r}"
    )


def test_the_wrapper_still_no_ops_outside_the_hub_checkout() -> None:
    """`pipefail` must not disturb the worktree guard — a bare render from a worktree PRUNES.

    ⚠️ Narrow by construction: this exercises ONLY the early-exit at the top of the script and
    provides no coverage of detection or sync. Stated so it is never mistaken for broader proof —
    the previous version of this file offered exactly this as its behavioural test.
    """
    r = subprocess.run(["bash", str(SCRIPT)], cwd="/tmp", capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"the wrapper must exit 0 outside /opt/fabrik: {r.stderr}"


def test_sync_cmd_is_ignored_without_the_test_sentinel(tmp_path: Path) -> None:
    """A stray exported SYNC_CMD must NOT replace the fleet sync from inside a git hook.

    ⚠️ This was `assert 'GOVERNANCE_SYNC_TEST' in src` — it proved the string appears, not that the
    override is ignored, which is the entire invariant. Driven for real now: SYNC_CMD is set, the
    sentinel is not, and the REAL sync (stubbed to a marker) must be the thing that runs.
    """
    repo = _hub_clone(tmp_path, [".windsurf/rules/core/00-x.md"])
    hijack = tmp_path / "hijack.sh"
    hijack.write_text("#!/usr/bin/env bash\necho HIJACKED\n", encoding="utf-8")
    hijack.chmod(0o755)
    r = _drive(tmp_path, repo, cfg_files=r"^\.windsurf/rules/", env_extra={"SYNC_CMD": str(hijack)})
    assert "HIJACKED" not in r.stdout, f"SYNC_CMD hijacked the sync without the sentinel: {r.stdout!r}"
    assert "REAL_SYNC_RAN" in r.stdout, f"the real sync did not run: {r.stdout!r}"
