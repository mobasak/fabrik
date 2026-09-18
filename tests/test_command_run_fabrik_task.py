"""T01a — the `/fabrik-task` lane's SIZE gate at `start` and the `design` field at `step`.

Eight behaviour graders, one per Behavior Contract row, plus the PyYAML-equality grader the
stdlib `files:` extraction owes its canonical consumer: `scripts/governance_sync_postcommit.sh`
parses the SAME scalar of the SAME file with PyYAML, so the two readings must agree or the
lane's most consequential test and the post-commit sync have silently split.

Every grader drives the real script in a subprocess against a throwaway `COMMAND_RUN_DIR` and a
throwaway git repo — the live `~/.claude/state/` store is never written and no `$HOME`-rooted
`.claude*` path is ever read.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "command_run.py"
_HUB_CONFIG = Path("/opt/fabrik/.pre-commit-config.yaml")

# The fixture hub's config. TWO `files:` scalars precede the governance-sync one, so an
# extraction that takes "the first `files:` in the file" — or a positional index — fails the
# sync graders loudly instead of passing on the hub's happy accident of ordering.
_FIXTURE_CONFIG = """\
repos:
  - repo: local
    hooks:
      - id: some-other-hook
        name: not the one
        files: '^never/match/me/'
      - id: another-hook
        name: also not the one
        files: ^docs/DECISIONS\\.md$
      - id: governance-sync
        name: Sync governance + enforcement to all projects
        entry: bash /opt/fabrik/scripts/governance_sync_postcommit.sh
        language: system
        stages: [post-commit]
        always_run: true
        files: '(^templates/governance/|^\\.claude/hooks/|^scripts/enforcement/)'
        pass_filenames: false
"""

_ALL_NO = "decision=yes,heavy=no,mechanism=no,oneway=no,tradeoffs=no"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _events_dir(run_dir: Path) -> Path:
    d = run_dir.parent / "events"
    d.mkdir(exist_ok=True)
    return d


def _cr(
    run_dir: Path,
    *args: str,
    sid: str | None = "s1",
    cwd: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """The `tests/test_command_run.py:43-82` harness, minus the close-verb feedback injection
    (nothing here closes a run) and plus a throwaway HOME so no test reads the operator's
    real git config or state."""
    env = {
        "PATH": "/usr/bin:/bin",
        "COMMAND_RUN_DIR": str(run_dir),
        # Never let a test emit into the operator's real event store.
        "KAIZEN_EVENTS_DIR": str(_events_dir(run_dir)),
        "HOME": str(run_dir.parent / "home"),
    }
    (run_dir.parent / "home").mkdir(exist_ok=True)
    if sid is not None:
        env["CLAUDE_SESSION_ID"] = sid
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(cwd) if cwd else None,
        env=env,
    )


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    d = tmp_path / "command-runs"
    d.mkdir()
    return d


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A git repo whose declared paths are TRACKED and CLEAN — the only state a lane start
    accepts (`tests/test_command_run.py:495-510` shape)."""
    r = tmp_path / "repo"
    (r / "scripts" / "enforcement").mkdir(parents=True)
    (r / "src").mkdir(parents=True)
    (r / "scripts" / "plain.py").write_text("x = 1\n", encoding="utf-8")
    (r / "scripts" / "enforcement" / "check_x.py").write_text("x = 1\n", encoding="utf-8")
    for n in "abcd":
        (r / "src" / f"{n}.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=r, check=True, timeout=15)
    subprocess.run(["git", "add", "-A"], cwd=r, check=True, timeout=15)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"],
        cwd=r,
        check=True,
        timeout=15,
    )
    return r


@pytest.fixture
def hub(tmp_path: Path) -> Path:
    h = tmp_path / "hub"
    h.mkdir()
    (h / ".pre-commit-config.yaml").write_text(_FIXTURE_CONFIG, encoding="utf-8")
    return h


def _start(*extra: str) -> list[str]:
    return [
        "start",
        "--command",
        "fabrik-task",
        "--phases",
        "5",
        "--terminal",
        "the change ships with its grader",
        *extra,
    ]


def _rec(run_dir: Path, sid: str = "s1") -> dict:
    return json.loads((run_dir / f"{sid}.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- row 1


def test_start_refuses_a_gapped_declaration_and_never_exits_0_on_an_exception(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """Row 1. A bare `fabrik-task` start passes every lane test VACUOUSLY (zero files ≤ 3, no
    path for the regex or the dirty check, no answer to refuse on), so it is refused and BOTH
    gaps print, one line each. And an exception anywhere inside the lane block returns 1 with
    its own template — never `main`'s fail-soft rc 0 (`scripts/command_run.py:2557-2559`),
    which would leave the agent believing a record opened when none did."""
    env = {"FABRIK_HUB_ROOT": str(hub)}
    r = _cr(run_dir, *_start(), cwd=repo, extra_env=env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "REFUSED — fabrik-task: missing --file" in r.stdout
    assert (
        "REFUSED — fabrik-task: missing --declare keys: "
        "decision, heavy, mechanism, oneway, tradeoffs" in r.stdout
    )
    assert not (run_dir / "s1.json").exists(), "a refused start must open no record"

    # A `--declare` item with no `=` raises inside the parse; the lane block owns it.
    r2 = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", "decision"),
        cwd=repo,
        extra_env=env,
    )
    assert r2.returncode == 1, r2.stdout + r2.stderr
    assert "REFUSED — fabrik-task: start could not complete (ValueError)" in r2.stdout
    assert not (run_dir / "s1.json").exists()


# ---------------------------------------------------------------- row 2


def test_lane_flags_are_refused_under_any_other_command(run_dir: Path, repo: Path) -> None:
    """Row 2. `--file`/`--declare` belong to one command, and every OTHER command's start is
    byte-identical to today's — one line, the pinned line, and a record with no lane keys."""
    r = _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-review",
        "--phases",
        "3",
        "--terminal",
        "t",
        "--file",
        "src/a.py",
        cwd=repo,
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "REFUSED — --file/--declare belong to --command fabrik-task" in r.stdout
    assert not (run_dir / "s1.json").exists()

    clean = _cr(
        run_dir, "start", "--command", "fabrik-review", "--phases", "3", "--terminal", "t", cwd=repo
    )
    assert clean.returncode == 0, clean.stdout + clean.stderr
    lines = clean.stdout.splitlines()
    assert len(lines) == 1 and lines[0].startswith("RUN: /fabrik-review"), clean.stdout
    rec = _rec(run_dir)
    assert "declared" not in rec and "design" not in rec

    step = _cr(run_dir, "step", "--phase", "2", "--title", "t", cwd=repo)
    assert step.returncode == 0, step.stdout + step.stderr
    assert len(step.stdout.splitlines()) == 1 and step.stdout.startswith("RUN: /fabrik-review")


# ---------------------------------------------------------------- row 3


def test_a_sync_path_names_the_review_lane_and_the_spec_chain_wins(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """Row 3. The governance-sync filter is read from the HUB config by the `- id:` anchor
    (two decoy `files:` scalars precede it), and a declared path it matches routes to
    right-now + the full review — unless a spec-chain answer also tripped, which takes
    precedence."""
    env = {"FABRIK_HUB_ROOT": str(hub)}
    r = _cr(
        run_dir,
        *_start("--file", "scripts/enforcement/check_x.py", "--declare", _ALL_NO),
        cwd=repo,
        extra_env=env,
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "REFUSED — fabrik-task: sync → right-now + /fabrik-review" in r.stdout
    assert not (run_dir / "s1.json").exists()

    r2 = _cr(
        run_dir,
        *_start(
            "--file",
            "scripts/enforcement/check_x.py",
            "--declare",
            "decision=yes,heavy=no,mechanism=yes,oneway=no,tradeoffs=no",
        ),
        cwd=repo,
        extra_env=env,
    )
    assert r2.returncode == 1, r2.stdout + r2.stderr
    assert "REFUSED — fabrik-task: mechanism → /fabrik-spec" in r2.stdout

    # A non-sync path with the same answers starts: the decoy scalars matched nothing.
    r3 = _cr(
        run_dir,
        *_start("--file", "scripts/plain.py", "--declare", _ALL_NO),
        cwd=repo,
        extra_env=env,
    )
    assert r3.returncode == 0, r3.stdout + r3.stderr
    assert _rec(run_dir)["declared"]["sync_test"] != "unavailable"


# ---------------------------------------------------------------- row 4


def test_a_dirty_declared_path_refuses_and_an_absent_one_starts(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """Row 4. Work done before the record opened is observable exactly once: the declared path
    is dirty at `start`. Tracked-and-modified and present-and-untracked both refuse (the second
    only because `git diff --quiet` reads an untracked path as CLEAN); an ABSENT path — deleted
    or never created — is not dirty and starts."""
    env = {"FABRIK_HUB_ROOT": str(hub)}
    (repo / "src" / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    r = _cr(run_dir, *_start("--file", "src/a.py", "--declare", _ALL_NO), cwd=repo, extra_env=env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "REFUSED — fabrik-task: src/a.py dirty at start" in r.stdout
    assert "message the author" in r.stdout
    assert not (run_dir / "s1.json").exists()

    (repo / "src" / "untracked.py").write_text("x = 1\n", encoding="utf-8")
    r2 = _cr(
        run_dir,
        *_start("--file", "src/untracked.py", "--declare", _ALL_NO),
        cwd=repo,
        extra_env=env,
    )
    assert r2.returncode == 1, r2.stdout + r2.stderr
    assert "REFUSED — fabrik-task: src/untracked.py dirty at start" in r2.stdout

    (repo / "src" / "b.py").unlink()  # tracked, deleted — absent, so not dirty
    r3 = _cr(
        run_dir,
        *_start("--file", "src/b.py", "--file", "src/does-not-exist.py", "--declare", _ALL_NO),
        cwd=repo,
        extra_env=env,
    )
    assert r3.returncode == 0, r3.stdout + r3.stderr


# ---------------------------------------------------------------- row 5


def test_a_valid_declaration_persists_and_prints_the_record_id(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """Row 5. The record carries the seven declared keys plus `sha`, every path normalised to
    repo-root-relative (the sync regex is `^`-anchored per alternative, so a two-character
    spelling would otherwise clear the lane's most consequential test), and stdout carries
    `RECORD: <started_at>` after the pinned line so the agent pastes the id rather than
    retyping a `%z` timestamp."""
    r = _cr(
        run_dir,
        *_start(
            "--surface",
            "the lane's size gate",
            "--file",
            "./scripts/plain.py",
            "--file",
            str(repo / "src" / "a.py"),
            "--file",
            "src/./c.py",
            "--declare",
            _ALL_NO,
        ),
        cwd=repo,
        extra_env={"FABRIK_HUB_ROOT": str(hub)},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    rec = _rec(run_dir)
    d = rec["declared"]
    assert set(d) == {
        "files",
        "decision",
        "heavy",
        "mechanism",
        "oneway",
        "tradeoffs",
        "sync_test",
        "sha",
    }
    assert d["files"] == ["scripts/plain.py", "src/a.py", "src/c.py"]
    assert d["decision"] == "yes" and d["heavy"] == "no" and d["tradeoffs"] == "no"
    assert len(d["sha"]) == 40 and d["sha"] != "unavailable"

    lines = r.stdout.splitlines()
    assert lines[0].startswith("RUN: /fabrik-task")
    assert lines[1] == f"RECORD: {rec['started_at']}", r.stdout

    # A directory and an out-of-repo path are CORRECTIONS, not lane verdicts.
    bad = _cr(
        run_dir,
        *_start("--file", "src", "--declare", _ALL_NO),
        cwd=repo,
        extra_env={"FABRIK_HUB_ROOT": str(hub)},
    )
    assert bad.returncode == 1 and "is a directory — declare files" in bad.stdout
    out = _cr(
        run_dir,
        *_start("--file", str(hub / ".pre-commit-config.yaml"), "--declare", _ALL_NO),
        cwd=repo,
        extra_env={"FABRIK_HUB_ROOT": str(hub)},
    )
    assert out.returncode == 1 and "is outside the repository" in out.stdout


# ---------------------------------------------------------------- row 6 (a)


def test_the_stdlib_files_scalar_equals_pyyamls_on_the_live_hub_file(monkeypatch) -> None:
    """Row 6a. `scripts/governance_sync_postcommit.sh:28-30` reads this same scalar with
    PyYAML. If the stdlib extraction and PyYAML ever disagree, the lane's sync test and the
    post-commit sync have split — a folded or re-quoted scalar fails HERE first. PyYAML is a
    GRADER dependency only; `command_run.py` is stdlib-only (`:46-60`)."""
    yaml = pytest.importorskip("yaml")
    if not _HUB_CONFIG.exists():
        pytest.skip(f"no hub config at {_HUB_CONFIG}")
    cr = _load("cr_sync", _SCRIPT)
    monkeypatch.setenv("FABRIK_HUB_ROOT", str(_HUB_CONFIG.parent))
    mine = cr._sync_filter_source()

    cfg = yaml.safe_load(_HUB_CONFIG.read_text(encoding="utf-8"))
    theirs = None
    for r in cfg.get("repos", []):
        for h in r.get("hooks", []):
            if h.get("id") == "governance-sync":
                theirs = h.get("files", "")
    assert theirs, "the live hub config has no governance-sync files: scalar"
    assert mine == theirs, f"stdlib {len(mine or '')} chars vs PyYAML {len(theirs)}"
    # The denominator for the equality claim: the byte length both readings agreed on.
    assert len(theirs) > 100, len(theirs)


# ---------------------------------------------------------------- row 6 (b)


def test_an_unreadable_sync_filter_fails_open_visibly(
    run_dir: Path, repo: Path, tmp_path: Path
) -> None:
    """Row 6b. A hub file that cannot be read — a spoke, a container, a permissions change —
    must never refuse every start, and an EMPTY scalar must never become an empty regex
    (`re.search('', p)` is truthy, so it would match every path). It fails OPEN with
    `sync_test: unavailable` AND one stderr line at START, because a silent skip makes a
    project-repo agent's start byte-identical to a clean one."""
    skip = "⚠ fabrik-task: sync lane test SKIPPED (cannot read the governance-sync filter)"

    absent = tmp_path / "no-hub"
    absent.mkdir()
    r = _cr(
        run_dir,
        *_start("--file", "scripts/enforcement/check_x.py", "--declare", _ALL_NO),
        cwd=repo,
        extra_env={"FABRIK_HUB_ROOT": str(absent)},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rec(run_dir)["declared"]["sync_test"] == "unavailable"
    assert skip in r.stderr, r.stderr

    empty = tmp_path / "empty-hub"
    empty.mkdir()
    (empty / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: governance-sync\n"
        "        name: x\n        files: ''\n",
        encoding="utf-8",
    )
    r2 = _cr(
        run_dir,
        *_start("--file", "scripts/enforcement/check_x.py", "--declare", _ALL_NO),
        cwd=repo,
        sid="s2",
        extra_env={"FABRIK_HUB_ROOT": str(empty)},
    )
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert _rec(run_dir, "s2")["declared"]["sync_test"] == "unavailable"
    assert skip in r2.stderr

    # A governance-sync block that LOST its `files:` key must not adopt a LATER hook's regex.
    # The next hook lists `name:` first, so a terminator keyed on `- id:` alone walks straight
    # into it and compiles `^scripts/` — refusing the wrong starts, in silence, with no
    # `unavailable` signal anywhere. Fail-open is the only safe direction here.
    lost = tmp_path / "lost-key-hub"
    lost.mkdir()
    (lost / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: governance-sync\n        name: x\n"
        "      - name: a later hook whose id comes second\n        files: '^scripts/'\n"
        "        id: something-else\n",
        encoding="utf-8",
    )
    r3 = _cr(
        run_dir,
        *_start("--file", "scripts/enforcement/check_x.py", "--declare", _ALL_NO),
        cwd=repo,
        sid="s3",
        extra_env={"FABRIK_HUB_ROOT": str(lost)},
    )
    assert r3.returncode == 0, r3.stdout + r3.stderr
    assert _rec(run_dir, "s3")["declared"]["sync_test"] == "unavailable"
    assert skip in r3.stderr


# ---------------------------------------------------------------- row 7


def test_step_design_is_recorded_once_and_refused_over_the_cap(
    run_dir: Path, repo: Path, hub: Path, tmp_path: Path
) -> None:
    """Row 7. The six design fields outlive scratch by living in the record: `phase_title` is a
    scalar the next `step` overwrites (`:2789`) and `pinned_line` floods every turn with it, so
    `--design` takes a PATH and stores its TEXT — once. A second `--design` is a warned no-op
    (a refusal would wedge the phase, and with it the Stop hook); an unreadable path or one
    over `_LEDGER_FIELD_CAP` refuses WITHOUT advancing the phase, because a refusal that
    advanced would emit a `phase` event for a step that did not happen."""
    env = {"FABRIK_HUB_ROOT": str(hub)}
    ok = _cr(
        run_dir,
        *_start("--file", "scripts/plain.py", "--declare", _ALL_NO),
        cwd=repo,
        extra_env=env,
    )
    assert ok.returncode == 0, ok.stdout + ok.stderr

    design = tmp_path / "design.md"
    design.write_text("PROBLEM: x\nAPPROACH: y\nTERMINAL: z\n", encoding="utf-8")
    s = _cr(
        run_dir,
        "step",
        "--phase",
        "2",
        "--title",
        f"design: {design}",
        "--design",
        str(design),
        cwd=repo,
        extra_env=env,
    )
    assert s.returncode == 0, s.stdout + s.stderr
    rec = _rec(run_dir)
    assert rec["design"] == design.read_text(encoding="utf-8")
    assert rec["phase"] == 2

    second = tmp_path / "second.md"
    second.write_text("a different design\n", encoding="utf-8")
    s2 = _cr(run_dir, "step", "--phase", "3", "--design", str(second), cwd=repo, extra_env=env)
    assert s2.returncode == 0, s2.stdout + s2.stderr
    assert "NOTE — fabrik-task: design already recorded; this --design was ignored" in s2.stderr
    rec2 = _rec(run_dir)
    assert rec2["design"] == design.read_text(encoding="utf-8")
    assert rec2["phase"] == 3

    # Fresh record: the cap and the unreadable path both refuse WITHOUT advancing.
    fresh = _cr(
        run_dir,
        *_start("--file", "scripts/plain.py", "--declare", _ALL_NO),
        cwd=repo,
        sid="s3",
        extra_env=env,
    )
    assert fresh.returncode == 0, fresh.stdout + fresh.stderr
    big = tmp_path / "big.md"
    big.write_text("x" * 2001, encoding="utf-8")
    over = _cr(
        run_dir,
        "step",
        "--phase",
        "2",
        "--design",
        str(big),
        cwd=repo,
        sid="s3",
        extra_env=env,
    )
    assert over.returncode == 1, over.stdout + over.stderr
    assert "REFUSED — fabrik-task: --design is 2001 chars, the cap is 2000" in over.stdout
    assert _rec(run_dir, "s3")["phase"] == 1
    assert "design" not in _rec(run_dir, "s3")

    gone = _cr(
        run_dir,
        "step",
        "--phase",
        "2",
        "--design",
        str(tmp_path / "never-written.md"),
        cwd=repo,
        sid="s3",
        extra_env=env,
    )
    assert gone.returncode == 1, gone.stdout + gone.stderr
    assert "cannot be read" in gone.stdout
    assert _rec(run_dir, "s3")["phase"] == 1


# ---------------------------------------------------------------- row 8


def test_a_repo_with_no_commits_records_sha_unavailable(
    run_dir: Path, tmp_path: Path, hub: Path
) -> None:
    """Row 8. `git rev-parse -q --verify HEAD` is rc 1 before the first commit (the bare form
    is rc 128 and prints the literal `HEAD`), and `git diff --quiet HEAD` is rc 128 there — so
    the dirty check is SKIPPED rather than reading every path as dirty. Same fail-open shape as
    the sync test: a scaffold's first change is not a lane violation."""
    r = tmp_path / "virgin"
    (r / "src").mkdir(parents=True)
    (r / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=r, check=True, timeout=15)

    out = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", _ALL_NO),
        cwd=r,
        extra_env={"FABRIK_HUB_ROOT": str(hub)},
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert _rec(run_dir)["declared"]["sha"] == "unavailable"
