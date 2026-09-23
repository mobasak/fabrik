# AFTER-EDIT: scripts/governance_sync_postcommit.sh, scripts/install_post_commit_hook.sh
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


def _drive(
    tmp_path: Path, repo: Path, *, cfg_files: str | None, env_extra: dict
) -> subprocess.CompletedProcess:
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
    cfg.write_text(
        yaml.safe_dump({"repos": [{"repo": "local", "hooks": [hook]}]}), encoding="utf-8"
    )

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
    # ⚠️ BELT AND BRACES, and it is not paranoia — it is an incident report. On 2026-09-01 a
    # red-on-revert experiment ran this suite with the `_clean_env` scrub disabled AND a hostile
    # `GIT_DIR=/opt/fabrik/.git GIT_WORK_TREE=/opt/fabrik` in order to PROVE the isolation hole was
    # real. It proved it: `git add -A` + `git commit -qm "t"` below ran against the REAL repo and
    # committed a sibling session's uncommitted WIP as author `t <t@fabrik.local>` (commit
    # f7627885). Nothing was lost — everything was committed rather than destroyed — but a peer's
    # work landed in history under a meaningless author and message, and it was pushed.
    # The scrub alone is not enough, because the scrub is exactly what an experiment disables.
    # This guard is independent of it: if git would resolve ANY repo other than the one we just
    # created under tmp_path, refuse to run rather than mutate it.
    probe = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--absolute-git-dir"],
        capture_output=True,
        text=True,
        env=genv,
    )
    resolved = probe.stdout.strip()
    if resolved and Path(resolved).resolve() != (repo / ".git").resolve():
        raise AssertionError(
            f"REFUSING to run: git resolves to {resolved!r}, not the scratch repo under tmp_path. "
            f"A GIT_DIR/GIT_WORK_TREE is leaking in and `git add -A` would commit a real repo."
        )
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
        assert "REAL_SYNC_RAN" in r.stdout, (
            f"the sync was SKIPPED on a trigger commit: {r.stdout!r}"
        )


def test_a_merge_commit_that_touches_a_trigger_path_still_syncs(tmp_path: Path) -> None:
    """Merges emitted NO paths under a plain `--name-only`, so every merge silently skipped.

    A merge that RESOLVES A CONFLICT in a trigger file carries a blob that exists in no parent and
    was never synced by anyone. `--first-parent` is what makes the comment's claim true.
    """
    repo = _hub_clone(tmp_path, ["README.md"])
    # ⚠️ Every git call below MUST carry the scrubbed env for the same reason `_hub_clone` does:
    # a leaked GIT_DIR (hand-exported, or set by any wrapper)
    # points these commands at /opt/fabrik instead of the scratch repo. `_clean_env` was added
    # for `_hub_clone` and these seven calls were missed — the hole was still open here.
    genv = _clean_env()
    g = ["git", "-C", str(repo), "-c", "commit.gpgsign=false"]
    base = subprocess.run(
        [*g, "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        env=genv,
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
    r = subprocess.run(
        ["bash", str(SCRIPT)], cwd="/tmp", capture_output=True, text=True, timeout=60
    )
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
    assert "HIJACKED" not in r.stdout, (
        f"SYNC_CMD hijacked the sync without the sentinel: {r.stdout!r}"
    )
    assert "REAL_SYNC_RAN" in r.stdout, f"the real sync did not run: {r.stdout!r}"


# ── The post-commit hook must never run under pre-commit (mail 01M3492KY09K6DP47Z21XVM2SH) ──────────
#
# pre-commit stashes every unstaged change in the tree around EVERY `run` that is not --all-files /
# --files — its post-commit stage included (pre_commit/commands/run.py `stash = not args.all_files and
# not args.files`) — and restores with a tree-wide `git checkout -- .` (pre_commit/staged_files_only.py
# `_CHECKOUT_CMD`). Around a ~60 s fleet sync that silently reverted any edit a sibling session made to
# any tracked file. The class guard is on the CONFIG, so no future post-commit hook can reintroduce it.

HUB = Path(__file__).resolve().parents[2]
INSTALLER = HUB / "scripts" / "install_post_commit_hook.sh"


def _effective_stages(cfg: dict) -> list[tuple[str, list[str]]]:
    default = cfg.get("default_stages") or ["pre-commit"]
    return [
        (h["id"], h.get("stages", default))
        for repo in cfg.get("repos", [])
        for h in repo.get("hooks", [])
    ]


def test_no_pre_commit_hook_runs_at_the_post_commit_stage() -> None:
    import yaml

    cfg = yaml.safe_load((HUB / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    offenders = [hid for hid, st in _effective_stages(cfg) if "post-commit" in st]
    assert offenders == [], (
        f"{offenders} run in pre-commit's post-commit stage, which stashes and restores the WHOLE tree "
        "around the hook — install it as a plain git hook instead (scripts/install_post_commit_hook.sh)"
    )
    assert "post-commit" not in (cfg.get("default_install_hook_types") or []), (
        "a bare `pre-commit install` would overwrite the plain post-commit hook with pre-commit's shim"
    )


def test_governance_sync_regex_stays_single_sourced_in_the_config() -> None:
    """The hook entry must survive (stages: [manual]) — the wrapper reads its `files:` regex."""
    import yaml

    cfg = yaml.safe_load((HUB / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hooks = {h["id"]: h for repo in cfg["repos"] for h in repo["hooks"]}
    assert "governance-sync" in hooks and hooks["governance-sync"].get("files")
    assert hooks["governance-sync"].get("stages") == ["manual"]


def _scratch_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "hub"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=_clean_env())
    return repo


def _install(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(INSTALLER)],
        capture_output=True,
        text=True,
        env=_clean_env(GOVERNANCE_SYNC_TEST="1", GOVERNANCE_SYNC_ROOT=str(repo)),
        check=False,
    )


def test_installer_replaces_pre_commits_shim_and_is_idempotent(tmp_path: Path) -> None:
    repo = _scratch_repo(tmp_path)
    hook = repo / ".git" / "hooks" / "post-commit"
    hook.write_text("#!/usr/bin/env bash\n# File generated by pre-commit: https://pre-commit.com\n")
    first = _install(repo)
    assert first.returncode == 0, first.stderr
    body = hook.read_text(encoding="utf-8")
    assert "governance_sync_postcommit.sh" in body
    assert "pre-commit" not in body.replace("NOT pre-commit", ""), body  # never re-enters pre-commit
    assert os.access(hook, os.X_OK)
    second = _install(repo)
    assert second.returncode == 0 and hook.read_text(encoding="utf-8") == body


def test_installer_refuses_a_foreign_post_commit_hook(tmp_path: Path) -> None:
    repo = _scratch_repo(tmp_path)
    hook = repo / ".git" / "hooks" / "post-commit"
    hook.write_text("#!/bin/sh\necho someone-elses-hook\n")
    out = _install(repo)
    assert out.returncode != 0 and "foreign" in out.stderr
    assert "someone-elses-hook" in hook.read_text(encoding="utf-8")



PRE_COMMIT_BIN = HUB / ".venv" / "bin" / "pre-commit"


@pytest.mark.skipif(not PRE_COMMIT_BIN.exists(), reason="the hub venv's pre-commit is the real binary under test")
def test_a_pre_commit_takeover_never_puts_the_sync_under_pre_commit_and_the_installer_heals_it(
    tmp_path: Path,
) -> None:
    """`pre-commit install -t post-commit` keeps our hook as post-commit.legacy and runs it BEFORE its own
    (stashing) run — so the sync still runs outside pre-commit. Drive the REAL binary to pin that, then
    prove the installer restores the plain hook and drops the dead legacy copy."""
    repo = _scratch_repo(tmp_path)
    env = _clean_env()
    marker = tmp_path / "sync_env.txt"
    (repo / "scripts").mkdir()
    fake = repo / "scripts" / "governance_sync_postcommit.sh"
    fake.write_text(f'#!/usr/bin/env bash\necho "PRE_COMMIT=${{PRE_COMMIT:-unset}}" >> "{marker}"\n')
    # A LOCAL-only config: the hub's real one lists a remote repo that pre-commit would clone on every run
    # (repository.all_hooks clones before filtering by stage), making the test depend on network or cache.
    (repo / ".pre-commit-config.yaml").write_text(
        "default_install_hook_types: [pre-commit, pre-push]\n"
        "repos:\n- repo: local\n  hooks:\n  - id: governance-sync\n    name: s\n    entry: 'true'\n"
        "    language: system\n    stages: [manual]\n    files: '^x$'\n"
    )
    (repo / "a").write_text("x\n")
    git = ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git, "add", "."], check=True, env=env)
    subprocess.run([*git, "commit", "-qm", "init"], check=True, env=env)
    assert _install(repo).returncode == 0
    take = subprocess.run(
        [str(PRE_COMMIT_BIN), "install", "-t", "post-commit"], cwd=repo, env=env, capture_output=True, text=True
    )
    assert take.returncode == 0, take.stderr
    hooks = repo / ".git" / "hooks"
    assert "File generated by pre-commit" in (hooks / "post-commit").read_text()
    (repo / "a").write_text("y\n")
    subprocess.run([*git, "add", "a"], check=True, env=env)
    subprocess.run([*git, "commit", "-qm", "c"], check=True, env=env, capture_output=True)
    assert marker.read_text().strip().splitlines() == ["PRE_COMMIT=unset"], marker.read_text()
    assert _install(repo).returncode == 0
    assert "Installed by scripts/install_post_commit_hook.sh" in (hooks / "post-commit").read_text()
    assert not (hooks / "post-commit.legacy").exists()


def test_installer_refuses_when_core_hooks_path_is_set(tmp_path: Path) -> None:
    repo = _scratch_repo(tmp_path)
    subprocess.run(["git", "-C", str(repo), "config", "core.hooksPath", "elsewhere"], check=True, env=_clean_env())
    out = _install(repo)
    assert out.returncode != 0 and "core.hooksPath" in out.stderr
    assert not (repo / ".git" / "hooks" / "post-commit").exists()


def test_a_failed_write_leaves_no_temp_file_in_the_hooks_dir(tmp_path: Path) -> None:
    repo = _scratch_repo(tmp_path)
    out = subprocess.run(
        ["bash", "-c", f'ulimit -f 0; exec bash "{INSTALLER}"'],
        capture_output=True,
        text=True,
        env=_clean_env(GOVERNANCE_SYNC_TEST="1", GOVERNANCE_SYNC_ROOT=str(repo)),
        check=False,
    )
    assert out.returncode != 0
    assert [p.name for p in (repo / ".git" / "hooks").glob(".post-commit.*")] == []
