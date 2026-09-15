"""Behavior contract for scripts/enforcement/check_lint_ratchet.py.

The ratchet's whole value is a per-repo baseline that can only shrink, so every test builds a REAL git
repo with REAL ruff errors and runs the check as a SUBPROCESS — exactly how `final_gate` invokes it. The
error count, the baseline file, and git staging are the things under test; none can be faked with mocks.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

CHECK = Path(__file__).resolve().parents[2] / "scripts" / "enforcement" / "check_lint_ratchet.py"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "src").mkdir()
    dest = tmp_path / "scripts" / "enforcement"
    dest.mkdir(parents=True)
    shutil.copy2(CHECK, dest / CHECK.name)
    return tmp_path


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


def _set_errors(repo: Path, n: int) -> None:
    """Write a src file with exactly ``n`` ruff errors (n unused imports — code F401)."""
    mods = ["os", "sys", "json", "re", "io", "abc", "csv", "gc", "ssl", "pdb"]
    assert n <= len(mods)
    (repo / "src" / "a.py").write_text("".join(f"import {m}\n" for m in mods[:n]))
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "x"], cwd=repo, check=True)


def _baseline(repo: Path) -> int | None:
    f = repo / ".fabrik" / "lint-baseline.json"
    return json.loads(f.read_text())["ruff_errors"] if f.exists() else None


def test_first_run_seeds_the_baseline_and_passes(repo: Path) -> None:
    """Nothing is ever blocked on the run that establishes the floor."""
    _set_errors(repo, 2)
    rc, out = _run(repo)
    assert rc == 0, out
    assert "SEEDED at 2" in out
    assert _baseline(repo) == 2


def test_a_rise_fails_the_gate(repo: Path) -> None:
    """The core promise: an agent can never ADD a new lint error."""
    _set_errors(repo, 2)
    _run(repo)  # seed at 2
    _set_errors(repo, 3)  # +1
    rc, out = _run(repo)
    assert rc == 1, out
    assert "ROSE 2 → 3" in out


def test_check_mode_fails_on_a_rise_but_never_rewrites(repo: Path) -> None:
    """CI/read-only: still blocks a rise, but must not mutate the tracked baseline."""
    _set_errors(repo, 2)
    _run(repo)  # seed at 2
    _set_errors(repo, 4)
    rc, out = _run(repo, "--check")
    assert rc == 1, out
    assert _baseline(repo) == 2, "--check must not tighten OR loosen the baseline"


def test_a_drop_ratchets_the_baseline_down(repo: Path) -> None:
    """The floor can only shrink — a run that lowers the count commits the new, tighter floor."""
    _set_errors(repo, 3)
    _run(repo)  # seed at 3
    _set_errors(repo, 1)
    rc, out = _run(repo)
    assert rc == 0, out
    assert "ratcheted DOWN 3 → 1" in out
    assert _baseline(repo) == 1


def test_a_later_rise_back_to_the_old_count_is_blocked(repo: Path) -> None:
    """After a ratchet-down, the OLD count is now new debt — the floor does not spring back up."""
    _set_errors(repo, 3)
    _run(repo)
    _set_errors(repo, 1)
    _run(repo)  # ratchet to 1
    _set_errors(repo, 3)  # back up — was fine before, is debt now
    rc, out = _run(repo)
    assert rc == 1, out
    assert "ROSE 1 → 3" in out


def test_zero_is_locked(repo: Path) -> None:
    """A clean repo seeds at 0 and stays there — zero-tolerance, permanently."""
    _set_errors(repo, 0)
    _run(repo)  # seed at 0
    rc, out = _run(repo)
    assert rc == 0, out
    assert "LOCKED" in out
    # and adding a single error now fails
    _set_errors(repo, 1)
    rc2, _ = _run(repo)
    assert rc2 == 1


def test_ratchet_down_stages_the_baseline(repo: Path) -> None:
    """The tightened floor must ride along with the change that lowered it (auto-staged)."""
    _set_errors(repo, 3)
    _run(repo)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=repo, check=True)
    _set_errors(repo, 1)
    _run(repo)  # ratchet down
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert ".fabrik/lint-baseline.json" in staged


def _mod(tmp_path, monkeypatch, name: str, *, version: str, count: int):
    """Load the check as a module against a scratch ROOT, with ruff stubbed."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, CHECK)
    lr = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(lr)
    monkeypatch.setattr(lr, "ROOT", tmp_path)
    monkeypatch.setattr(lr, "BASELINE", tmp_path / ".fabrik" / "lint-baseline.json")
    monkeypatch.setattr(lr, "_baseline_is_gitignored", lambda: False)
    monkeypatch.setattr(lr, "_ruff_version", lambda: version)
    monkeypatch.setattr(lr, "_ruff_count", lambda: count)
    return lr


def _write_baseline_file(tmp_path: Path, text: str) -> None:
    (tmp_path / ".fabrik").mkdir(exist_ok=True)
    (tmp_path / ".fabrik" / "lint-baseline.json").write_text(text)


def _baseline_text(tmp_path: Path) -> str:
    return (tmp_path / ".fabrik" / "lint-baseline.json").read_text()


def test_a_linter_version_change_fails_once_and_names_the_explicit_reseed(
    tmp_path, monkeypatch, capsys
):
    """T12.1 (01M1RE497): the old behaviour re-seeded at the current count and PASSED, so the
    reference this ratchet measures against could move on any run with no act by anyone — real debt
    landing in the same change as a ruff bump was absorbed into the new floor and never seen. A
    version change is now a one-time RED naming the exact re-seed command."""
    lr = _mod(tmp_path, monkeypatch, "lint_ratchet_v1", version="0.15.12", count=390)
    _write_baseline_file(tmp_path, '{"ruff_errors": 388, "ruff_version": "0.14.0"}\n')

    monkeypatch.setattr(sys, "argv", ["check_lint_ratchet.py"])
    rc = lr.main()
    out = capsys.readouterr().out
    assert rc == 1, "a ruleset change must not pass silently"
    assert "--reseed" in out and "0.14.0" in out and "0.15.12" in out and "390" in out
    assert json.loads(_baseline_text(tmp_path)) == {
        "ruff_errors": 388,
        "ruff_version": "0.14.0",
    }, "a refusal must not rewrite the floor it refused to trust"

    # the escape exists, is one command, and is explicit.
    monkeypatch.setattr(sys, "argv", ["check_lint_ratchet.py", "--reseed"])
    assert lr.main() == 0
    assert "RE-SEEDED" in capsys.readouterr().out
    assert json.loads(_baseline_text(tmp_path)) == {
        "ruff_errors": 390,
        "ruff_version": "0.15.12",
    }

    # and once re-seeded the ordinary ratchet resumes under the new version.
    monkeypatch.setattr(lr, "_ruff_count", lambda: 391)
    monkeypatch.setattr(sys, "argv", ["check_lint_ratchet.py"])
    assert lr.main() != 0


def test_reseed_under_check_refuses_to_write(tmp_path, monkeypatch, capsys):
    """`--check` is the read-only mode the gate runs; `--reseed --check` reports the re-seed it
    WOULD do and touches nothing, or `--check` stops being read-only."""
    lr = _mod(tmp_path, monkeypatch, "lint_ratchet_v2", version="0.15.12", count=390)
    _write_baseline_file(tmp_path, '{"ruff_errors": 388, "ruff_version": "0.14.0"}\n')
    monkeypatch.setattr(sys, "argv", ["check_lint_ratchet.py", "--reseed", "--check"])
    assert lr.main() == 0
    out = capsys.readouterr().out
    assert "would RE-SEED" in out, "read-only mode must not claim a write it did not make"
    assert json.loads(_baseline_text(tmp_path)) == {
        "ruff_errors": 388,
        "ruff_version": "0.14.0",
    }

    # and WITHOUT --reseed, --check reds on the version change like every other mode — the old
    # behaviour returned 0 here, which is what made the floor drift invisible in the gate.
    monkeypatch.setattr(sys, "argv", ["check_lint_ratchet.py", "--check"])
    assert lr.main() == 1
    assert json.loads(_baseline_text(tmp_path)) == {
        "ruff_errors": 388,
        "ruff_version": "0.14.0",
    }


def test_the_floor_is_the_committed_blob_not_a_working_tree_file(repo: Path) -> None:
    """T12.1: the floor was read from the working-tree file, so a sibling's uncommitted re-seed —
    or this gate's own un-pushed tightening — moved a bar that CI reads from HEAD. Three sessions
    share this tree; the committed blob is the only floor that binds."""
    _set_errors(repo, 2)
    _run(repo)  # seed at 2 (written + staged)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "commit the floor at 2"], cwd=repo, check=True)

    # a sibling (or a stale local run) leaves a LOWER floor in the working tree, uncommitted.
    (repo / ".fabrik" / "lint-baseline.json").write_text('{"ruff_errors": 0}\n')
    rc, out = _run(repo, "--check")
    assert rc == 0, out  # 2 == the COMMITTED floor of 2; the uncommitted 0 must not red it
    assert "0" not in out.split("baseline")[-1].split("\n")[0] or "== baseline" in out

    # and the reverse: an uncommitted HIGHER floor must not license a rise past the committed one.
    # Restore the committed blob first — `_set_errors` commits everything, and leaving the 0 in the
    # tree would commit IT and make the floor 0 for the wrong reason.
    subprocess.run(
        ["git", "checkout", "-q", "--", ".fabrik/lint-baseline.json"], cwd=repo, check=True
    )
    _set_errors(repo, 5)
    (repo / ".fabrik" / "lint-baseline.json").write_text('{"ruff_errors": 9}\n')
    rc2, out2 = _run(repo, "--check")
    assert rc2 == 1, out2
    assert "ROSE 2 → 5" in out2


def test_the_version_comes_from_the_interpreter_that_produced_the_count(tmp_path) -> None:
    """T12.1 root cause: the count ran `sys.executable -m ruff` while the version ran a bare `ruff`
    off PATH — routinely two different installs, so the guard compared a version that did not
    produce the count. Both must name the same interpreter."""
    src = CHECK.read_text(encoding="utf-8")
    count_call = src.split("def _ruff_count")[1].split("def ")[0]
    version_call = src.split("def _ruff_version")[1].split("def ")[0]
    assert 'sys.executable, "-m", "ruff", "check"' in count_call
    assert 'sys.executable, "-m", "ruff", "--version"' in version_call
    assert '["ruff", "--version"]' not in src, "a bare PATH ruff is a different binary"


def test_a_rise_names_the_offending_files_and_marks_the_callers_own(repo: Path) -> None:
    """T12.1: `ROSE 2 → 5` told the caller nothing about WHERE, and on a tree three sessions share
    it did not even say whether the debt was theirs. The failure now lists per-file counts and marks
    the ones inside the caller's own diff."""
    _set_errors(repo, 2)
    _run(repo)  # seed at 2
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "floor"], cwd=repo, check=True)

    # a sibling's COMMITTED file raises the count; the caller's own edit is elsewhere and clean.
    (repo / "src" / "sibling.py").write_text("import os\nimport sys\nimport json\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "sibling debt"], cwd=repo, check=True)
    (repo / "src" / "mine.py").write_text('"""clean."""\n')
    subprocess.run(["git", "add", "--", "src/mine.py"], cwd=repo, check=True)

    rc, out = _run(repo, "--check")
    assert rc == 1, out
    assert "src/sibling.py" in out, "the failure must name the file carrying the debt"
    assert "3  src/sibling.py" in out.replace("   ", " ").replace("  ", " ").replace("  ", " ") or (
        "src/sibling.py" in out and "3" in out
    )
    assert "in YOUR diff" not in out.split("src/sibling.py")[1].split("\n")[0], (
        "a sibling's committed file is not in the caller's diff and must not be marked as theirs"
    )
    assert "none of the offending files is in your diff" in out


def test_a_rise_in_the_callers_own_file_is_marked_as_theirs(repo: Path) -> None:
    """The mirror of the test above: when the debt IS the caller's, the marker must appear — a
    marker that never fires is the same as no marker."""
    _set_errors(repo, 2)
    _run(repo)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "floor"], cwd=repo, check=True)

    (repo / "src" / "mine.py").write_text("import os\nimport sys\n")
    subprocess.run(["git", "add", "--", "src/mine.py"], cwd=repo, check=True)
    rc, out = _run(repo, "--check")
    assert rc == 1, out
    assert "src/mine.py" in out
    assert "in YOUR diff" in out
    assert "none of the offending files is in your diff" not in out


def test_a_reseed_clears_the_block_before_the_commit(repo: Path) -> None:
    """The remedy the version-mismatch branch prints must be FOLLOWABLE.

    Two correct changes interacted into an unsatisfiable gate: `_baseline_payload` reads
    `git show HEAD:<rel>` so a local edit cannot lower the committed floor, and the mismatch
    branch returns 1 so a ruleset change cannot be absorbed silently. Together, executed:

        run 1 plain     -> rc 1, "re-seed explicitly with `… --reseed`"
        run 2 --reseed  -> rc 0, writes and stages the working tree
        run 3 plain     -> rc 1   (identical — the read is HEAD-bound)
        run 4 git add   -> rc 1   (`git show HEAD:` is blind to the index)

    The completion contract requires a green gate BEFORE the commit, so the only exit was to
    commit while red — in every repo carrying this synced check, the moment its baseline gains a
    `ruff_version` key. `_write_baseline` writes that key on every seed, so the immune repos arm
    themselves on their next write.
    """
    _set_errors(repo, 0)
    (repo / ".fabrik").mkdir(exist_ok=True)
    (repo / ".fabrik" / "lint-baseline.json").write_text(
        '{"ruff_errors": 0, "ruff_version": "0.0.1-OLD"}\n', encoding="utf-8"
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "committed baseline"], cwd=repo, check=True)

    rc, _ = _run(repo)
    assert rc == 1, "a ruleset change must not be absorbed silently"

    rc, _ = _run(repo, "--reseed")
    assert rc == 0

    rc, out = _run(repo)
    assert rc == 0, f"the re-seed did not clear the block — the remedy is unfollowable:\n{out}"
    assert "NOT COMMITTED" in out, out


def test_the_count_floor_is_still_head_bound_under_the_SAME_ruleset(repo: Path) -> None:
    """The MIRROR of the version relief — re-cut, because the first version tested the wrong state.

    The HEAD-bound floor exists so a SIBLING's uncommitted re-seed cannot raise the bar under the
    SAME ruleset. Forging the floor in the MISMATCH state (which the first cut did) is not that
    state: there, the local count is the only one measured under the live ruleset, so honouring it
    is the fix for the absorption regression below — and the old grader would have blocked it.
    """
    _set_errors(repo, 0)
    (repo / ".fabrik").mkdir(exist_ok=True)
    live = _run(repo, "--reseed")
    assert live[0] == 0
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "floor 0 under the live ruleset"], cwd=repo, check=True)

    _set_errors(repo, 3)  # real debt, above the committed floor of 0, SAME ruleset
    bl = repo / ".fabrik" / "lint-baseline.json"
    bl.write_text(
        bl.read_text(encoding="utf-8").replace('"ruff_errors": 0', '"ruff_errors": 999'),
        encoding="utf-8",
    )
    rc, out = _run(repo)
    assert rc == 1, f"a forged LOCAL floor lowered the gate under the same ruleset:\n{out}"


def test_a_reseed_clears_the_block_when_the_ruleset_RAISED_the_count(repo: Path) -> None:
    """The direction the motivating incident actually took (youtube 01M1H0D5: 390 against a stored
    388 after a ruff release WIDENED a rule) — and the direction the first cut of the un-wedge did
    not handle. There the relief never fired, so the block stayed, the truthful "not comparable"
    error was replaced by a FALSE "New lint debt is not allowed" sending an agent to fix debt
    nobody added, and `--reseed` went inert because it is only honoured inside the branch the
    relief suppressed."""
    _set_errors(repo, 2)
    (repo / ".fabrik").mkdir(exist_ok=True)
    (repo / ".fabrik" / "lint-baseline.json").write_text(
        '{"ruff_errors": 2, "ruff_version": "0.0.1-OLD"}\n', encoding="utf-8"
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "floor 2 under an old ruleset"], cwd=repo, check=True)

    _set_errors(repo, 3)  # the RULESET reads more, not the author adding debt
    assert _run(repo)[0] == 1
    assert _run(repo, "--reseed")[0] == 0
    rc, out = _run(repo)
    assert rc == 0, f"the re-seed did NOT clear the block in the RAISED direction:\n{out}"
    assert "New lint debt is not allowed" not in out, (
        f"blamed the caller for a ruleset change:\n{out}"
    )


def test_an_uncommitted_reseed_cannot_absorb_real_debt_into_the_old_floor(repo: Path) -> None:
    """The regression the first un-wedge introduced, and the reason un-wedging by fail-open is a
    worse trade than the wedge. Taking the VERSION relief while keeping HEAD's COUNT re-opens the
    cobra the error text names two lines away: HEAD's count was measured under the OLD ruleset, so
    when the new ruleset is LOOSER the stale floor sits above the honest one and everything between
    is free debt. Executed at the first cut: floor 5/OLD, today's ruleset reads 2, the author adds
    2 REAL errors -> `ratcheted DOWN 5 -> 4`, rc 0 GREEN, honest floor of 2 overwritten with 4."""
    _set_errors(repo, 2)
    (repo / ".fabrik").mkdir(exist_ok=True)
    (repo / ".fabrik" / "lint-baseline.json").write_text(
        '{"ruff_errors": 5, "ruff_version": "0.0.1-OLD"}\n', encoding="utf-8"
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "a LOOSER old floor"], cwd=repo, check=True)

    assert _run(repo, "--reseed")[0] == 0  # honest count under the live ruleset is 2

    # ⚠️ NOT `_set_errors` here — it does `git add -A` and COMMITS, which would commit the
    # re-seeded baseline too and erase the very mismatch this test needs. The scenario is an
    # UNCOMMITTED re-seed beside newly-written debt, so the source is written directly and the
    # premise is asserted from HEAD before the verdict is believed.
    mods = ["os", "sys", "json", "re"]
    (repo / "src" / "a.py").write_text("".join(f"import {m}\n" for m in mods), encoding="utf-8")
    head_baseline = subprocess.run(
        ["git", "show", "HEAD:.fabrik/lint-baseline.json"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert '"ruff_errors": 5' in head_baseline, (
        f"premise broken — HEAD floor moved: {head_baseline}"
    )

    rc, out = _run(repo)
    assert rc == 1, f"2 real new lint errors were absorbed into the old floor:\n{out}"
