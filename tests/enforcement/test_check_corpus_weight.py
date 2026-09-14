"""Behavior contract for scripts/enforcement/check_corpus_weight.py.

The check's whole value is a WARN that can never red a gate in ~46 synced repos, so every test builds a
REAL git repo with a REAL bare remote and runs the check as a SUBPROCESS — exactly how `final_gate`
invokes it (`run_optional_check` reds the gate on ANY non-zero exit, `warn_only` or not). The byte
sizes, the baseline file, git staging and the exit code are the things under test; none can be faked
with mocks. One state — an unexpected internal exception — cannot be produced from disk, so that single
grader imports the copied module in-process and monkeypatches `base_sizes` to raise.

Rows A1–A15 of the plan's Phase A Behavior Contract, one grader each.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

CHECK = Path(__file__).resolve().parents[2] / "scripts" / "enforcement" / "check_corpus_weight.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """An OWNER repo (it has `commands/_sources/`) with a bare remote, so `origin/master` resolves."""
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "master")
    _git(work, "config", "user.email", "t@t")
    _git(work, "config", "user.name", "t")
    (work / "CLAUDE.md").write_text("x" * 100, encoding="utf-8")
    rules = work / ".windsurf" / "rules"
    rules.mkdir(parents=True)
    (rules / "a.md").write_text("y" * 50, encoding="utf-8")
    (rules / "b.yaml").write_text("z" * 30, encoding="utf-8")
    (rules / "core").mkdir()  # a NESTED file: without it the is_file() filter is never expressed
    (rules / "core" / "c.md").write_text("w" * 20, encoding="utf-8")
    (work / "commands" / "_sources").mkdir(parents=True)  # the owner marker, deliberately empty
    dest = work / "scripts" / "enforcement"
    dest.mkdir(parents=True)
    shutil.copy2(CHECK, dest / CHECK.name)
    bare = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", "master", str(bare)], check=True, capture_output=True
    )
    _git(work, "remote", "add", "origin", str(bare))
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "base")
    _git(work, "push", "-q", "origin", "master")
    return work


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A NON-owner repo: the governance files are sync copies, so there is no `commands/_sources/`."""
    work = tmp_path / "proj"
    work.mkdir()
    _git(work, "init", "-q", "-b", "master")
    _git(work, "config", "user.email", "t@t")
    _git(work, "config", "user.name", "t")
    (work / "CLAUDE.md").write_text("x" * 100, encoding="utf-8")
    dest = work / "scripts" / "enforcement"
    dest.mkdir(parents=True)
    shutil.copy2(CHECK, dest / CHECK.name)
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "base")
    return work


def _run(repo: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(repo / "scripts" / "enforcement" / CHECK.name), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env={**os.environ},
        check=False,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _baseline_path(repo: Path) -> Path:
    return repo / ".fabrik" / "corpus-weight-baseline.json"


def _wt_baseline(wt: Path) -> Path:
    """A worktree carries its own `.fabrik/`; the check resolves ROOT from its own file location."""
    (wt / ".fabrik").mkdir(parents=True, exist_ok=True)
    return wt / ".fabrik" / "corpus-weight-baseline.json"


def _baseline(repo: Path) -> dict[str, Any] | None:
    f = _baseline_path(repo)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def _grow(repo: Path, surface: str = "CLAUDE.md", extra: int = 40) -> None:
    """Add *extra* bytes to a surface in the TREE only — the base ref keeps its old size."""
    target = repo / surface
    target.write_text(target.read_text(encoding="utf-8") + "g" * extra, encoding="utf-8")


def _shrink(repo: Path, surface: str = "CLAUDE.md", keep: int = 20) -> None:
    (repo / surface).write_text("x" * keep, encoding="utf-8")


def _seed_and_push(repo: Path) -> None:
    """Commit + push the tree so the base ref equals the tree (no growth)."""
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "sync")
    _git(repo, "push", "-q", "origin", "master")


def _import_check(repo: Path, name: str):  # noqa: ANN202 — a module object
    """Import the repo's OWN copy, so its module-level ROOT/BASELINE resolve inside the fixture."""
    path = repo / "scripts" / "enforcement" / CHECK.name
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- A1 ---------------------------------------------------------------------------------------


def test_no_baseline_still_grades_vs_base_and_writes_nothing(repo: Path) -> None:
    """The base verdict does not need a baseline — the check is live from its very first run."""
    _grow(repo)
    rc, out = _run(repo)
    assert rc == 0, out
    assert "no baseline — run --seed at a corpus state you accept" in out
    assert "ADDS 40 B to CLAUDE.md" in out
    assert not _baseline_path(repo).exists(), "a plain run with no baseline must write nothing"


# --- A2 ---------------------------------------------------------------------------------------


def test_seed_writes_the_baseline_shape_and_stages_it(repo: Path) -> None:
    """The trend record's shape IS the contract: one int per owned surface, the ref it was taken
    against, an ISO-8601 stamp — and it is staged, so the record rides with the change that moved it."""
    rc, out = _run(repo, "--seed")
    assert rc == 0, out
    payload = _baseline(repo)
    assert payload is not None
    assert payload["surfaces"] == {"CLAUDE.md": 100, "commands/_sources": 0, ".windsurf/rules": 100}
    assert all(isinstance(v, int) for v in payload["surfaces"].values())
    assert payload["ref"] == "origin/master"
    assert payload["seeded_at"].endswith("Z") and "T" in payload["seeded_at"]
    assert "seeded 3 surface(s) at origin/master" in out
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert ".fabrik/corpus-weight-baseline.json" in staged, (
        "the tightened floor rides with its commit"
    )


# --- A3 ---------------------------------------------------------------------------------------


def test_growth_vs_base_warns_and_never_reds(repo: Path) -> None:
    """The ONE line that ever warns: it names the surface, the bytes and the ref, exits 0, and leaves
    the baseline alone — the baseline is the trend record and never triggers a verdict."""
    _run(repo, "--seed")
    before = _baseline(repo)
    _grow(repo, extra=25)
    rc, out = _run(repo)
    assert rc == 0, out
    assert "⚠ corpus-weight: this change ADDS 25 B to CLAUDE.md (base origin/master → tree)" in out
    assert "cites the D-row naming what the growth retires" in out
    assert _baseline(repo) == before, "a growth never touches the baseline"


# --- A4 ---------------------------------------------------------------------------------------


def test_strict_exit_tracks_grew(repo: Path, tmp_path: Path) -> None:
    """Growth → 1; equal → 0; no base ref → 0 (`grew` is False by definition when base is None)."""
    _grow(repo, extra=10)
    rc_grow, out_grow = _run(repo, "--strict")
    assert rc_grow == 1, out_grow

    _seed_and_push(repo)
    rc_equal, out_equal = _run(repo, "--strict")
    assert rc_equal == 0, out_equal

    _git(repo, "remote", "remove", "origin")
    rc_noref, out_noref = _run(repo, "--strict")
    assert rc_noref == 0, out_noref
    assert "no base ref — growth vs base not measured" in out_noref


# --- A5 ---------------------------------------------------------------------------------------


def test_exit_is_zero_on_every_path_without_strict(
    repo: Path, project: Path, tmp_path: Path
) -> None:
    """Nine states, one loop: a non-zero exit here reds the completion gate in ~46 synced repos."""
    # 1 no baseline
    assert _run(repo)[0] == 0
    # 2 growth
    _grow(repo, extra=15)
    assert _run(repo)[0] == 0
    # 3 seed, then equal
    _run(repo, "--seed")
    _seed_and_push(repo)
    assert _run(repo)[0] == 0
    # 4 shrink (a tightening write)
    _shrink(repo, keep=10)
    assert _run(repo)[0] == 0
    # 5 non-owner
    assert _run(project)[0] == 0
    # 6 gitignored baseline — UNTRACKED, because a tracked path is not ignored and does travel to CI
    _git(repo, "rm", "-q", "--cached", ".fabrik/corpus-weight-baseline.json")
    _baseline_path(repo).unlink()
    (repo / ".gitignore").write_text(".fabrik/\n", encoding="utf-8")
    rc_ignored, out_ignored = _run(repo)
    assert rc_ignored == 0, out_ignored
    assert "is gitignored here — the ratchet is local-only" in out_ignored
    # 7 no base ref
    _git(repo, "remote", "remove", "origin")
    assert _run(repo)[0] == 0
    # 8 worktree
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", "-b", "side", str(wt))
    (wt / "commands" / "_sources").mkdir(parents=True, exist_ok=True)
    rc_wt, out_wt = _run(wt)
    assert rc_wt == 0, out_wt
    # 9 an unexpected exception — RuntimeError, a type no call site catches. The ref is pinned too:
    # state 7 removed the remote, and without a ref `base_sizes` is never reached and the state is
    # VACUOUS — a grader that cannot express the failure has proven nothing.
    mod = _import_check(repo, "cw_boom")

    def boom(*_a: object, **_k: object) -> dict[str, int | None]:
        raise RuntimeError("injected")

    mod.diff_base = lambda *_a, **_k: "origin/master"
    mod.base_sizes = boom
    assert mod.main([]) == 0
    assert mod.main(["--strict"]) == 0, "an internal error is never a red, --strict included"


def test_an_internal_error_says_so(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The internal-error line is the disclosure half of A5's ninth state."""
    mod = _import_check(repo, "cw_boom_line")

    def boom(*_a: object, **_k: object) -> dict[str, int | None]:
        raise RuntimeError("injected")

    mod.diff_base = lambda *_a, **_k: "origin/master"
    mod.base_sizes = boom
    assert mod.main([]) == 0
    assert (
        "corpus-weight: internal error — RuntimeError: injected (reporting only)"
        in capsys.readouterr().out
    )


# --- A6 ---------------------------------------------------------------------------------------


def test_check_never_writes_even_with_seed_or_reseed(repo: Path) -> None:
    """`--check` is the gate's own mode: it reports in full and touches nothing under `.fabrik/`."""
    rc, out = _run(repo, "--check", "--seed")
    assert rc == 0, out
    assert "would seed 3 surface(s) at origin/master (--check: not written)" in out
    assert not _baseline_path(repo).exists()

    rc, out = _run(repo, "--check", "--reseed")
    assert rc == 0, out
    assert "would reseed 3 surface(s) at origin/master (--check: not written)" in out
    assert not _baseline_path(repo).exists()

    _run(repo, "--seed")
    stamp = _baseline_path(repo).read_bytes()
    rc, out = _run(repo, "--check", "--seed")
    assert rc == 0, out
    assert "baseline exists — use --reseed" in out
    assert _baseline_path(repo).read_bytes() == stamp, (
        "--check --seed over an existing baseline is inert"
    )


# --- A7 ---------------------------------------------------------------------------------------


def test_a_shrink_tightens_the_baseline_except_under_check(repo: Path) -> None:
    """The ratchet only ever tightens, and `--check` is the gate's own mode: it reports the tightening
    it would make and writes nothing."""
    _run(repo, "--seed")
    _shrink(repo, keep=20)
    rc, out = _run(repo, "--check")
    assert rc == 0, out
    assert "would ratchet DOWN CLAUDE.md 100 → 20 — --check writes nothing" in out
    assert _baseline(repo)["surfaces"]["CLAUDE.md"] == 100  # type: ignore[index]

    rc, out = _run(repo)
    assert rc == 0, out
    assert "ratcheted DOWN CLAUDE.md 100 → 20" in out
    after = _baseline(repo)["surfaces"]  # type: ignore[index]
    assert after["CLAUDE.md"] == 20
    # the merge must PRESERVE every other surface's record — writing only the tightened surface
    # would erase the trend for the rest, silently, on any shrink
    assert after[".windsurf/rules"] == 100, after
    assert after["commands/_sources"] == 0, after


# --- A8 ---------------------------------------------------------------------------------------


def test_seed_is_a_noop_over_an_existing_baseline_and_reseed_creates_or_overwrites(
    repo: Path,
) -> None:
    """`--seed` establishes a floor once; `--reseed` is the deliberate re-baselining a D-row cites.
    Confusing the two would let any run silently raise the record it is meant to hold."""
    _run(repo, "--seed")
    _grow(repo, extra=33)
    rc, out = _run(repo, "--seed")
    assert rc == 0, out
    assert "baseline exists — use --reseed" in out
    assert _baseline(repo)["surfaces"]["CLAUDE.md"] == 100  # type: ignore[index]

    rc, out = _run(repo, "--reseed")
    assert rc == 0, out
    assert "reseeded 3 surface(s) at origin/master" in out
    assert _baseline(repo)["surfaces"]["CLAUDE.md"] == 133  # type: ignore[index]

    _baseline_path(repo).unlink()
    rc, out = _run(repo, "--reseed")
    assert rc == 0, out
    assert "reseeded 3 surface(s)" in out
    assert _baseline(repo) is not None, "--reseed creates one when none exists"


# --- A9 ---------------------------------------------------------------------------------------


def test_a_repo_without_commands_sources_owns_nothing_and_seeds_nothing(project: Path) -> None:
    """A synced project's CLAUDE.md is a byte-identical copy it may not fix — budgeting it is wallpaper."""
    rc, out = _run(project, "--seed")
    assert rc == 0, out
    assert out.strip() == (
        "corpus-weight: not the hub — every governance surface here is a copy; nothing to budget"
    )
    assert not _baseline_path(project).exists()


# --- A10 --------------------------------------------------------------------------------------


def test_above_baseline_but_equal_to_base_does_not_warn(repo: Path) -> None:
    """The baseline is the TREND record; only the base ref triggers a verdict."""
    _run(repo, "--seed")
    _grow(repo, extra=45)
    _seed_and_push(repo)  # the base now carries the growth too
    rc, out = _run(repo)
    assert rc == 0, out
    assert "ADDS" not in out
    assert "OK — no owned surface grew vs origin/master" in out


# --- A11 --------------------------------------------------------------------------------------


def test_no_base_ref_is_a_dash_and_says_so(repo: Path) -> None:
    """With no resolvable base the check cannot know whether anything grew — it says exactly that
    rather than printing a delta against nothing."""
    _git(repo, "remote", "remove", "origin")
    rc, out = _run(repo)
    assert rc == 0, out
    assert "no base ref — growth vs base not measured" in out
    assert "· base — (—)" in out


# --- A12 --------------------------------------------------------------------------------------


def test_a_surface_absent_at_base_is_not_reported_as_an_addition(repo: Path) -> None:
    """A surface with no blob at the base ref is ABSENT, which is not the same as present-and-empty."""
    frag = repo / "commands" / "_fragments"
    frag.mkdir(parents=True)
    (frag / "f.md").write_text("f" * 70, encoding="utf-8")
    rc, out = _run(repo)
    assert rc == 0, out
    assert "commands/_fragments 70 B" in out
    assert (
        "commands/_fragments 70 B · baseline — (—) · base origin/master (absent — not budgeted)"
        in out
    )
    assert "ADDS 70 B to commands/_fragments" not in out


# --- A13 --------------------------------------------------------------------------------------


def test_directory_surfaces_count_every_file_on_both_sides(repo: Path) -> None:
    """`.windsurf/rules/CLAIMS.yaml` is governance too — an `.md`-only filter hides a whole file."""
    rc, out = _run(repo)
    assert rc == 0, out
    assert ".windsurf/rules 100 B" in out, (
        "50 (.md) + 30 (.yaml) + 20 (nested core/c.md), files only"
    )
    assert "· base origin/master (—)" in out, "the base side counted both too, so the delta is 0"


# --- A14 --------------------------------------------------------------------------------------


def test_help_states_what_it_writes_and_when_it_exits_nonzero(repo: Path) -> None:
    """I5 — an agent must know what the script does to their tree BEFORE they run it."""
    rc, out = _run(repo, "--help")
    assert rc == 0, out
    for phrase in ("--seed", "--reseed", "--check", "--strict"):
        assert phrase in out
    low = out.lower()
    assert "writes" in low
    assert "never writes" in low or "writes nothing" in low
    assert "exit" in low and "0" in out


# --- A15 --------------------------------------------------------------------------------------


def test_a_worktree_reports_and_never_writes(repo: Path, tmp_path: Path) -> None:
    """A tightening `git add` inside a sibling's worktree is exactly the collision I6 forbids."""
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", "-b", "side", str(wt))
    (wt / "commands" / "_sources").mkdir(parents=True, exist_ok=True)
    assert (wt / ".git").is_file(), "a worktree's .git is a FILE — that is the gate"

    for args in (("--seed",), ("--reseed",), ()):
        rc, out = _run(wt, *args)
        assert rc == 0, out
        assert "worktree — reporting only, nothing written" in out
    assert not _baseline_path(wt).exists()
    assert not _baseline_path(repo).exists()


# --- round-2 graders: the five states the first pass could not express -------------------------


def test_an_unreadable_subtree_is_never_ratcheted(repo: Path) -> None:
    """`Path.rglob` SWALLOWS PermissionError, so an unreadable subtree read as a smaller surface and
    the plain run tightened the committed trend record to a bogus value the ratchet can never walk
    back (review round 1, Opus seat, executed). Unmeasurable must mean skipped, not shrunk."""
    if os.geteuid() == 0:
        pytest.skip("root reads every directory")
    sub = repo / ".windsurf" / "rules" / "core"
    _run(repo, "--seed")
    before = _baseline(repo)["surfaces"][".windsurf/rules"]  # type: ignore[index]
    sub.chmod(0o000)
    try:
        rc, out = _run(repo)
        assert rc == 0, out
        assert ".windsurf/rules UNREADABLE" in out, out
        assert "ratcheted DOWN .windsurf/rules" not in out, "an unreadable surface is not a shrink"
        assert _baseline(repo)["surfaces"][".windsurf/rules"] == before  # type: ignore[index]
    finally:
        sub.chmod(0o755)


def test_a_surface_deleted_from_the_tree_is_reported_not_silently_dropped(repo: Path) -> None:
    """A deleted governance surface is the LARGEST possible regression; the first pass filtered it
    out of the report entirely, so a 1-byte trim was caught and a whole-surface loss was not."""
    _run(repo, "--seed")
    shutil.rmtree(repo / ".windsurf" / "rules")
    rc, out = _run(repo)
    assert rc == 0, out
    assert ".windsurf/rules absent from the tree" in out, out
    assert _baseline(repo)["surfaces"][".windsurf/rules"] == 100  # type: ignore[index]


def test_a_corrupt_baseline_says_so_instead_of_reading_as_absent(repo: Path) -> None:
    """A malformed trend record used to print "no baseline": the ratchet stopped and said nothing."""
    _run(repo, "--seed")
    _baseline_path(repo).write_text('{"surfaces": {"CLAUDE.md": "100"}}', encoding="utf-8")
    rc, out = _run(repo)
    assert rc == 0, out
    assert "is unreadable or malformed — no trend is being kept" in out, out
    assert "no baseline — run --seed" not in out, "a corrupt record is not an absent one"

    _baseline_path(repo).write_text("{not json", encoding="utf-8")
    rc, out = _run(repo)
    assert rc == 0, out
    assert "is unreadable or malformed" in out, out


def test_a_symlink_counts_on_neither_side(repo: Path) -> None:
    """`git ls-tree` stores a link as a blob sized by its TARGET PATH; counting it on either side
    invents a delta no change can clear — an unfixable ⚠ is wallpaper.

    BOTH halves are pinned. The tree half: the link adds nothing to the byte total. The base half:
    the committed link must add nothing either — otherwise the base reads LARGER than the tree, the
    surface looks like a shrink, and a genuine growth up to the link's target-path length is masked.
    """
    (repo / ".windsurf" / "rules" / "link.md").symlink_to("../../a-long-target-name.md")
    _seed_and_push(repo)  # the link is COMMITTED, so it is a 120000 blob at the base ref too
    rc, out = _run(repo)
    assert rc == 0, out
    assert ".windsurf/rules 100 B" in out, "the symlink added nothing to the tree side"
    # the delta cell is `—` only when the base skipped the link as well
    assert ".windsurf/rules 100 B · baseline — (—) · base origin/master (—)" in out, out
    assert "ADDS" not in out, out


def test_a_surface_missing_from_the_baseline_is_named(repo: Path) -> None:
    """`--seed` is a no-op once a baseline exists, so a surface created later never entered the
    trend record — silently, forever. It is now named on every plain run."""
    _run(repo, "--seed")
    frag = repo / "commands" / "_fragments"
    frag.mkdir(parents=True)
    (frag / "f.md").write_text("f" * 40, encoding="utf-8")
    rc, out = _run(repo)
    assert rc == 0, out
    assert "commands/_fragments is not in the baseline — --reseed to include it" in out, out


def test_a_worktree_names_the_request_it_skipped(repo: Path, tmp_path: Path) -> None:
    """An agent who deliberately ran --seed in a worktree got silence; the gate is now named."""
    wt = tmp_path / "wt2"
    _git(repo, "worktree", "add", "-q", "-b", "side2", str(wt))
    (wt / "commands" / "_sources").mkdir(parents=True, exist_ok=True)
    rc, out = _run(wt, "--seed")
    assert rc == 0, out
    assert "--seed skipped — a worktree never writes the baseline" in out, out
    assert "not a git checkout" not in out, out
    rc, out = _run(wt, "--reseed")
    assert rc == 0, out
    assert "--reseed skipped — a worktree never writes the baseline" in out, out
    assert not _baseline_path(wt).exists()


def test_help_discloses_that_a_write_also_stages(repo: Path) -> None:
    """I5: the index mutation was undisclosed — `--help` named the file but never the `git add`."""
    rc, out = _run(repo, "--help")
    assert rc == 0, out
    assert "git add" in out, out
    assert "writes and stages nothing" in out, out


def test_a_write_never_drops_a_surface_it_could_not_measure(repo: Path) -> None:
    """A transient permission error must not erase a surface's trend record: `--reseed` used to
    write only the MEASURED surfaces, so the unreadable one's baseline key vanished for good —
    the same class the plain run's fix closed, left open on the write path (review round 2)."""
    if os.geteuid() == 0:
        pytest.skip("root reads every directory")
    _run(repo, "--seed")
    assert _baseline(repo)["surfaces"][".windsurf/rules"] == 100  # type: ignore[index]
    sub = repo / ".windsurf" / "rules" / "core"
    sub.chmod(0o000)
    try:
        rc, out = _run(repo, "--reseed")
        assert rc == 0, out
        assert "kept at its previous baseline" in out, out
        assert _baseline(repo)["surfaces"][".windsurf/rules"] == 100, "the record survived"  # type: ignore[index]
    finally:
        sub.chmod(0o755)


def test_a_worktree_never_claims_a_tightening_it_did_not_write(repo: Path, tmp_path: Path) -> None:
    """The plain run is the only write path the gate's no-flag call shape reaches, and in a worktree
    it printed `ratcheted DOWN` in the past tense while writing nothing (review round 2)."""
    _run(repo, "--seed")
    wt = tmp_path / "wt3"
    _git(repo, "worktree", "add", "-q", "-b", "side3", str(wt))
    (wt / "commands" / "_sources").mkdir(parents=True, exist_ok=True)
    shutil.copy2(_baseline_path(repo), _wt_baseline(wt))
    (wt / "CLAUDE.md").write_text("x" * 10, encoding="utf-8")
    rc, out = _run(wt)
    assert rc == 0, out
    assert "would ratchet DOWN CLAUDE.md 100 → 10 — a worktree never writes the baseline" in out, (
        out
    )
    assert "ratcheted DOWN CLAUDE.md 100 → 10" not in out.replace("would ratchet", "x"), out


def test_a_symlinked_surface_is_named_a_symlink_not_unreadable(repo: Path, tmp_path: Path) -> None:
    """A link to a perfectly readable directory is skipped BY POLICY; calling it UNREADABLE sends
    the reader hunting a permission problem that does not exist. A DANGLING link is reported too —
    it used to vanish from the report entirely (review round 2)."""
    real = tmp_path / "real-rules"
    real.mkdir()
    (real / "r.md").write_text("r" * 12, encoding="utf-8")
    shutil.rmtree(repo / ".windsurf" / "rules")
    (repo / ".windsurf" / "rules").symlink_to(real)
    rc, out = _run(repo)
    assert rc == 0, out
    assert ".windsurf/rules a symlink — counted on neither side" in out, out
    assert "UNREADABLE" not in out, out

    (repo / ".windsurf" / "rules").unlink()
    (repo / ".windsurf" / "rules").symlink_to(tmp_path / "nowhere-at-all")
    rc, out = _run(repo)
    assert rc == 0, out
    assert ".windsurf/rules a DANGLING symlink — the surface it pointed at is gone" in out, out
    assert ".windsurf/rules a symlink — counted on neither side" not in out, (
        "a dangling link is the surface being GONE, never the benign policy skip"
    )
    # A dangling link at a surface the BASE ref still knows is caught by the base clause. The clause
    # only the link itself can satisfy is a surface absent from BOTH base and baseline — a NEW one:
    (repo / "commands" / "_fragments").symlink_to(tmp_path / "nowhere-either")
    rc, out = _run(repo)
    assert rc == 0, out
    assert "commands/_fragments a DANGLING symlink" in out, (
        "a dangling link with no base blob and no baseline key is still reported"
    )


def test_seed_is_a_noop_over_a_corrupt_baseline_too(repo: Path) -> None:
    """`--help` says --seed writes "when none exists". A corrupt file EXISTS, and --seed used to
    overwrite it while the ⚠ in the same breath told the operator to use --reseed."""
    _run(repo, "--seed")
    _baseline_path(repo).write_text("not json at all", encoding="utf-8")
    rc, out = _run(repo, "--seed")
    assert rc == 0, out
    assert "baseline exists — use --reseed" in out, out
    assert _baseline_path(repo).read_text(encoding="utf-8") == "not json at all", "untouched"


def test_a_write_drops_a_retired_baseline_key_and_names_it(repo: Path) -> None:
    """The preserved merge kept EVERY prior key, so a retired or renamed surface's entry was
    immortal and nothing ever named it — `--reseed` stopped being the rebuild its own `--help`
    promises (review round 3). It now drops keys outside `SURFACES` and says which."""
    _run(repo, "--seed")
    path = _baseline_path(repo)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["surfaces"]["commands/_retired"] = 9999
    path.write_text(json.dumps(payload), encoding="utf-8")

    rc, out = _run(repo, "--reseed", "--check")
    assert rc == 0, out
    assert "would drop commands/_retired from the baseline (--check: not written)" in out, out
    assert "commands/_retired" in _baseline_path(repo).read_text(encoding="utf-8"), "dry run"

    rc, out = _run(repo, "--reseed")
    assert rc == 0, out
    assert "dropped commands/_retired from the baseline" in out, out
    assert "commands/_retired" not in _baseline_path(repo).read_text(encoding="utf-8")


def test_the_dry_run_reports_what_a_write_would_keep(repo: Path) -> None:
    """`--help` says --check reports IN FULL; the real --reseed named every preserved surface and
    the dry run named none, so an operator could not see the carry-over (review round 3)."""
    if os.geteuid() == 0:
        pytest.skip("root reads every directory")
    _run(repo, "--seed")
    sub = repo / ".windsurf" / "rules" / "core"
    sub.chmod(0o000)
    try:
        rc, out = _run(repo, "--reseed", "--check")
        assert rc == 0, out
        assert "would keep .windsurf/rules at its previous baseline" in out, out
    finally:
        sub.chmod(0o755)


def test_a_baseline_path_that_is_not_a_file_names_its_own_cause(repo: Path) -> None:
    """A DIRECTORY at the baseline path routed --seed to --reseed and --reseed into the internal
    error handler: both documented paths failed and the cause was never named (review round 3)."""
    _baseline_path(repo).parent.mkdir(parents=True, exist_ok=True)
    _baseline_path(repo).mkdir()
    for args in (("--seed",), ("--reseed",), ()):
        rc, out = _run(repo, *args)
        assert rc == 0, out
        assert "is not a regular file — no trend can be kept or rebuilt" in out, (args, out)
        assert "internal error" not in out, (args, out)
        assert "a worktree never writes" not in out, (args, out)
        assert "baseline exists — use --reseed" not in out, (args, out)
    assert _baseline_path(repo).is_dir(), "nothing tried to write through it"


def test_a_tree_with_no_git_is_not_called_a_worktree(tmp_path: Path) -> None:
    """`writable` is False for a worktree AND for an owner tree with no `.git` at all (a `cp -a`, an
    export, a container COPY). Both printed "worktree"; only one is one (review round 3)."""
    tree = tmp_path / "exported"
    (tree / "commands" / "_sources").mkdir(parents=True)
    (tree / "CLAUDE.md").write_text("x" * 30, encoding="utf-8")
    dest = tree / "scripts" / "enforcement"
    dest.mkdir(parents=True)
    shutil.copy2(CHECK, dest / CHECK.name)
    assert not (tree / ".git").exists()

    rc, out = _run(tree)
    assert rc == 0, out
    assert "not a git checkout — reporting only, nothing written" in out, out
    assert "worktree —" not in out, out

    # C1: the skip line must name THIS cause, not the worktree one — three causes, one ladder
    rc, out = _run(tree, "--reseed")
    assert rc == 0, out
    assert "--reseed skipped — this tree is not a git checkout" in out, out
    assert "a worktree never writes" not in out, out
