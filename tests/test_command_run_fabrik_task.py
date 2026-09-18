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
import os
import re
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
        files: '(^templates/governance/|^\\.claude/hooks/|^scripts/enforcement/|^docs/reference/technology-stack-decision-guide\\.md$)'
        pass_filenames: false
"""

_ALL_NO = "decision=yes,heavy=no,mechanism=no,oneway=no,tradeoffs=no"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _commit(repo: Path, path: str, msg: str, also: str | None = None) -> None:
    """Stage the named path(s) in the throwaway fixture repo and commit them."""
    paths = [path] + ([also] if also else [])
    subprocess.run(["git", "add", "--", *paths], cwd=str(repo), check=True, timeout=15)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg],
        cwd=str(repo),
        check=True,
        timeout=15,
    )


def _porcelain(repo: Path, path: str) -> str:
    """The fixture repo's own view of one path — used to ASSERT the fixture is in the state the
    grader claims, so a symlink test can never pass because the setup silently did nothing."""
    return subprocess.run(
        ["git", "--literal-pathspecs", "status", "--porcelain", "--", path],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout


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
    run_dir: Path, repo: Path, hub: Path, tmp_path: Path
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

    # A `--declare` member with no `=` is the likeliest mistake there is, so it NAMES itself and
    # the member rather than surfacing as an anonymous exception class.
    r2 = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", "decision,heavy=no"),
        cwd=repo,
        extra_env=env,
    )
    assert r2.returncode == 1, r2.stdout + r2.stderr
    assert "REFUSED — fabrik-task: --declare members must be k=v: decision" in r2.stdout
    assert not (run_dir / "s1.json").exists()

    # The exception arm itself, driven by a REAL escape: no `git` on PATH. Anything raised inside
    # the lane block must become rc 1 + the template + no record — never `main`'s fail-soft rc 0,
    # which reads to the agent exactly like a record that opened.
    nogit = tmp_path / "nogit"
    nogit.mkdir()
    r3 = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", _ALL_NO),
        cwd=repo,
        extra_env={**env, "PATH": str(nogit)},
    )
    assert r3.returncode == 1, r3.stdout + r3.stderr
    assert "REFUSED — fabrik-task: start could not complete (FileNotFoundError)" in r3.stdout
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
    # The seam value the plan's Interfaces declares — "ok"|"unavailable", nothing else. A
    # `!= "unavailable"` assertion passes against any string and cannot catch a drifted seam.
    assert _rec(run_dir)["declared"]["sync_test"] == "ok"


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

    # A directory and an out-of-repo path are CORRECTIONS, not lane verdicts. Their OWN session
    # ids: reusing the id of the call that just succeeded would let a stale record satisfy an
    # assertion about a refusal.
    bad = _cr(
        run_dir,
        *_start("--file", "src", "--declare", _ALL_NO),
        cwd=repo,
        sid="s-dir",
        extra_env={"FABRIK_HUB_ROOT": str(hub)},
    )
    assert bad.returncode == 1 and "is a directory — declare files" in bad.stdout
    assert not (run_dir / "s-dir.json").exists()
    out = _cr(
        run_dir,
        *_start("--file", str(hub / ".pre-commit-config.yaml"), "--declare", _ALL_NO),
        cwd=repo,
        sid="s-out",
        extra_env={"FABRIK_HUB_ROOT": str(hub)},
    )
    assert out.returncode == 1 and "is outside the repository" in out.stdout
    assert not (run_dir / "s-out.json").exists()


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

    # Same STRING is not the same BEHAVIOUR. The gate's whole purpose is to predict what
    # `grep -qE` will do in `governance_sync_postcommit.sh`, and Python's `re` and POSIX ERE are
    # different engines — an ERE-only construct added to the hub's scalar would keep both
    # readers byte-equal while the gate and the sync quietly disagreed about which paths are
    # sync paths. Compare what they MATCH over the hub's real tracked file list, with the
    # population stated.
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=str(_HUB_CONFIG.parent),
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout.splitlines()
    assert len(tracked) > 100, f"only {len(tracked)} tracked files — is this the hub?"
    pat = __import__("re").compile(theirs)
    by_python = {f for f in tracked if pat.search(f)}
    ere = subprocess.run(
        ["grep", "-E", "-e", theirs],
        input="\n".join(tracked),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert ere.returncode in (0, 1), ere.stderr
    by_ere = set(ere.stdout.splitlines())
    assert by_python == by_ere, (
        f"engines disagree over {len(tracked)} tracked files: "
        f"python-only={sorted(by_python - by_ere)[:5]} ere-only={sorted(by_ere - by_python)[:5]}"
    )
    assert by_python, f"the filter matched 0 of {len(tracked)} tracked files"


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


# ------------------------------------------- fixup round: the territory round 1 never reached


def test_a_fourth_declared_file_routes_to_the_spec_chain(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """The lane's HEADLINE behaviour, and nothing in the first batch declared more than three
    files — raising the cap to 4 left every grader green. Three is the boundary that must still
    START; the fourth is the spec chain's."""
    env = {"FABRIK_HUB_ROOT": str(hub)}
    three = _cr(
        run_dir,
        *_start(
            "--file",
            "src/a.py",
            "--file",
            "src/c.py",
            "--file",
            "src/d.py",
            "--declare",
            _ALL_NO,
        ),
        cwd=repo,
        sid="s-3",
        extra_env=env,
    )
    assert three.returncode == 0, three.stdout + three.stderr
    assert len(_rec(run_dir, "s-3")["declared"]["files"]) == 3

    four = _cr(
        run_dir,
        *_start(
            "--file",
            "src/a.py",
            "--file",
            "src/c.py",
            "--file",
            "src/d.py",
            "--file",
            "scripts/plain.py",
            "--declare",
            _ALL_NO,
        ),
        cwd=repo,
        sid="s-4",
        extra_env=env,
    )
    assert four.returncode == 1, four.stdout + four.stderr
    assert "REFUSED — fabrik-task: files > 3 → /fabrik-spec" in four.stdout
    assert not (run_dir / "s-4.json").exists()


def test_every_declared_answer_names_its_own_lane(run_dir: Path, repo: Path, hub: Path) -> None:
    """Four of the seven lane outcomes had ZERO occurrences in the first batch — deleting their
    branches left every grader green. Each answer names the lane its message promises, and the
    spec chain outranks the right-now lanes when both trip."""
    env = {"FABRIK_HUB_ROOT": str(hub)}
    cases = [
        (
            "decision=yes,heavy=yes,mechanism=no,oneway=no,tradeoffs=no",
            "REFUSED — fabrik-task: heavy → right-now + /fabrik-review",
        ),
        (
            "decision=yes,heavy=no,mechanism=no,oneway=yes,tradeoffs=no",
            "REFUSED — fabrik-task: oneway → /fabrik-spec",
        ),
        (
            "decision=yes,heavy=no,mechanism=no,oneway=no,tradeoffs=yes",
            "REFUSED — fabrik-task: tradeoffs → /fabrik-spec",
        ),
        (
            "decision=no,heavy=no,mechanism=no,oneway=no,tradeoffs=no",
            "REFUSED — fabrik-task: decision=no → right-now + /fabrik-review-scoped",
        ),
    ]
    for i, (declare, expected) in enumerate(cases):
        r = _cr(
            run_dir,
            *_start("--file", "scripts/plain.py", "--declare", declare),
            cwd=repo,
            sid=f"s-lane{i}",
            extra_env=env,
        )
        assert r.returncode == 1, r.stdout + r.stderr
        assert expected in r.stdout, f"{declare} -> {r.stdout!r}"
        assert not (run_dir / f"s-lane{i}.json").exists()

    # PRECEDENCE: a sync path AND a spec-chain answer — the spec chain is the one named.
    both = _cr(
        run_dir,
        *_start(
            "--file",
            "scripts/enforcement/check_x.py",
            "--declare",
            "decision=yes,heavy=yes,mechanism=no,oneway=yes,tradeoffs=no",
        ),
        cwd=repo,
        sid="s-prec",
        extra_env=env,
    )
    assert both.returncode == 1, both.stdout + both.stderr
    assert "REFUSED — fabrik-task: oneway → /fabrik-spec" in both.stdout


def test_out_of_domain_declare_values_are_refused(run_dir: Path, repo: Path, hub: Path) -> None:
    """A typo failed OPEN into the cheapest lane: four keys are tested `== "yes"`, so `yse` and
    `nope` both read as *no*, and every typo persisted verbatim into a seam the plan declares as
    yes|no. The correction prints beside the other flag gaps, not after a second round trip."""
    r = _cr(
        run_dir,
        *_start(
            "--file",
            "scripts/plain.py",
            "--declare",
            "decision=yes,heavy=yse,mechanism=nope,oneway=no,tradeoffs=1",
        ),
        cwd=repo,
        extra_env={"FABRIK_HUB_ROOT": str(hub)},
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "REFUSED — fabrik-task: --declare values must be yes|no: " in r.stdout
    for bad in ("heavy=yse", "mechanism=nope", "tradeoffs=1"):
        assert bad in r.stdout, r.stdout
    assert "decision=yes" not in r.stdout and "oneway=no" not in r.stdout
    assert not (run_dir / "s1.json").exists()


def test_duplicate_declared_paths_are_de_duplicated(run_dir: Path, repo: Path, hub: Path) -> None:
    """The cap counted OCCURRENCES: one file named four times routed a ONE-file task into the
    spec chain, and named twice it reached the record twice — which T01b re-measures against."""
    r = _cr(
        run_dir,
        *_start(
            "--file",
            "src/a.py",
            "--file",
            "./src/a.py",
            "--file",
            "src/./a.py",
            "--file",
            "src/a.py",
            "--declare",
            _ALL_NO,
        ),
        cwd=repo,
        extra_env={"FABRIK_HUB_ROOT": str(hub)},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rec(run_dir)["declared"]["files"] == ["src/a.py"]


def test_a_declared_symlink_keeps_its_spelling_and_its_dirtiness(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """`resolve()` followed the link, so the path that reached the record, the dirty probe and
    the sync regex was the TARGET. A dirty declared symlink was therefore a SILENT SUCCESS —
    probed against a clean target — and the record named a file the agent never declared."""
    env = {"FABRIK_HUB_ROOT": str(hub)}
    (repo / "src" / "link.py").symlink_to("a.py")
    _commit(repo, "src/link.py", "link")
    clean = _cr(
        run_dir,
        *_start("--file", "src/link.py", "--declare", _ALL_NO),
        cwd=repo,
        sid="s-link",
        extra_env=env,
    )
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert _rec(run_dir, "s-link")["declared"]["files"] == ["src/link.py"], "the link, not a.py"

    # Retarget the LINK so the porcelain sees the symlink itself as modified; a.py stays clean.
    (repo / "src" / "link.py").unlink()
    (repo / "src" / "link.py").symlink_to("c.py")
    assert _porcelain(repo, "src/link.py").strip(), "fixture: the symlink must read as modified"
    assert not _porcelain(repo, "src/a.py").strip(), "fixture: the target must stay clean"
    dirty = _cr(
        run_dir,
        *_start("--file", "src/link.py", "--declare", _ALL_NO),
        cwd=repo,
        sid="s-link2",
        extra_env=env,
    )
    assert dirty.returncode == 1, dirty.stdout + dirty.stderr
    assert "REFUSED — fabrik-task: src/link.py dirty at start" in dirty.stdout


def test_a_glob_metacharacter_in_a_declared_path_is_literal(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """A declared path is a FILENAME, never a pathspec. Without `--literal-pathspecs` the probe
    read `src/rep[1].py` as a glob, matched its DIRTY sibling `src/rep1.py`, and refused a clean
    start while naming a file the agent never declared — fail-CLOSED, but still wrong."""
    (repo / "src" / "rep[1].py").write_text("x = 1\n", encoding="utf-8")
    (repo / "src" / "rep1.py").write_text("x = 1\n", encoding="utf-8")
    _commit(repo, "src/rep[1].py", "glob", also="src/rep1.py")
    (repo / "src" / "rep1.py").write_text("x = 2\n", encoding="utf-8")  # the SIBLING is dirty

    r = _cr(
        run_dir,
        *_start("--file", "src/rep[1].py", "--declare", _ALL_NO),
        cwd=repo,
        extra_env={"FABRIK_HUB_ROOT": str(hub)},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rec(run_dir)["declared"]["files"] == ["src/rep[1].py"]


def test_design_outside_the_lane_is_refused(run_dir: Path, repo: Path) -> None:
    """`start` refuses `--file`/`--declare` outside the lane and `--design` had no mirror: rc 0,
    the pinned line printed, nothing stored — every signal of success and the design gone."""
    ok = _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-review",
        "--phases",
        "3",
        "--terminal",
        "t",
        cwd=repo,
    )
    assert ok.returncode == 0, ok.stdout + ok.stderr
    d = repo / "d.md"
    d.write_text("PROBLEM: x\n", encoding="utf-8")
    r = _cr(run_dir, "step", "--phase", "2", "--design", str(d), cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "REFUSED — --design belongs to --command fabrik-task" in r.stdout
    rec = _rec(run_dir)
    assert "design" not in rec and rec["phase"] == 1, "the phase must NOT advance"


def test_the_design_cap_accepts_exactly_the_cap(
    run_dir: Path, repo: Path, hub: Path, tmp_path: Path
) -> None:
    """Only 2001 was ever sent, so flipping `>` to `>=` left every grader green. Exactly 2000 —
    `_LEDGER_FIELD_CAP` — must SUCCEED; the cap is a ceiling, not a limit to duck under."""
    env = {"FABRIK_HUB_ROOT": str(hub)}
    ok = _cr(
        run_dir,
        *_start("--file", "scripts/plain.py", "--declare", _ALL_NO),
        cwd=repo,
        extra_env=env,
    )
    assert ok.returncode == 0, ok.stdout + ok.stderr
    exact = tmp_path / "exact.md"
    exact.write_text("y" * 2000, encoding="utf-8")
    r = _cr(run_dir, "step", "--phase", "2", "--design", str(exact), cwd=repo, extra_env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    rec = _rec(run_dir)
    assert len(rec["design"]) == 2000 and rec["phase"] == 2


def test_an_empty_design_still_cannot_be_overwritten(
    run_dir: Path, repo: Path, hub: Path, tmp_path: Path
) -> None:
    """The already-recorded guard was a TRUTHINESS test, so an empty design file set `design=''`
    and the next `--design` overwrote it silently — the one input on which "no later step
    overwrites it" must hold is exactly the one it failed on."""
    env = {"FABRIK_HUB_ROOT": str(hub)}
    ok = _cr(
        run_dir,
        *_start("--file", "scripts/plain.py", "--declare", _ALL_NO),
        cwd=repo,
        extra_env=env,
    )
    assert ok.returncode == 0, ok.stdout + ok.stderr
    empty = tmp_path / "empty.md"
    empty.write_text("", encoding="utf-8")
    first = _cr(run_dir, "step", "--phase", "2", "--design", str(empty), cwd=repo, extra_env=env)
    assert first.returncode == 0, first.stdout + first.stderr
    assert _rec(run_dir)["design"] == ""

    later = tmp_path / "later.md"
    later.write_text("a real design\n", encoding="utf-8")
    second = _cr(run_dir, "step", "--phase", "3", "--design", str(later), cwd=repo, extra_env=env)
    assert second.returncode == 0, second.stdout + second.stderr
    assert "NOTE — fabrik-task: design already recorded" in second.stderr
    assert _rec(run_dir)["design"] == ""


def test_outside_a_git_repo_the_sha_says_no_repo(run_dir: Path, tmp_path: Path, hub: Path) -> None:
    """`sha: unavailable` conflated "a repo with no commits" with "not a repo at all", and in the
    second the dirty check never ran — a state T01b's re-measure must be able to tell apart."""
    plain = tmp_path / "plain-dir"
    (plain / "src").mkdir(parents=True)
    (plain / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    r = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", _ALL_NO),
        cwd=plain,
        extra_env={"FABRIK_HUB_ROOT": str(hub)},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rec(run_dir)["declared"]["sha"] == "no-repo"


@pytest.mark.parametrize(
    ("name", "body"),
    [
        # A FOLDED scalar: `>-` extracted literally compiles and matches NOTHING, so every sync
        # path starts clean with no warning — the lane test silently off.
        ("folded", "        files: >-\n          (^scripts/enforcement/)\n"),
        # A BLOCK scalar: `|` compiles to an EMPTY ALTERNATION that matches EVERY path, so every
        # fabrik-task start in every repo is refused.
        ("block", "        files: |\n          (^scripts/enforcement/)\n"),
    ],
)
def test_a_block_or_folded_scalar_fails_open(
    run_dir: Path, repo: Path, tmp_path: Path, name: str, body: str
) -> None:
    """Both are the "an empty regex is truthy" hazard in a spelling the scan cannot read, and
    NEITHER printed the warning line, because the extracted indicator compiles fine."""
    h = tmp_path / f"hub-{name}"
    h.mkdir()
    (h / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: governance-sync\n        name: x\n"
        + body,
        encoding="utf-8",
    )
    r = _cr(
        run_dir,
        *_start("--file", "scripts/enforcement/check_x.py", "--declare", _ALL_NO),
        cwd=repo,
        extra_env={"FABRIK_HUB_ROOT": str(h)},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rec(run_dir)["declared"]["sync_test"] == "unavailable"
    assert "sync lane test SKIPPED" in r.stderr, r.stderr


def test_a_bare_dash_item_terminates_the_block(run_dir: Path, repo: Path, tmp_path: Path) -> None:
    """The block terminator required `"- "`, but a bare `-` on its own line with the mapping keys
    beneath it is equally legal YAML — so a governance-sync block that lost its `files:` walked
    straight into the NEXT hook and adopted its regex, silently."""
    h = tmp_path / "hub-dash"
    h.mkdir()
    (h / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks:\n      - id: governance-sync\n        name: x\n"
        "      -\n        id: later\n        files: '(^src/)'\n",
        encoding="utf-8",
    )
    r = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", _ALL_NO),
        cwd=repo,
        extra_env={"FABRIK_HUB_ROOT": str(h)},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rec(run_dir)["declared"]["sync_test"] == "unavailable"
    assert "sync lane test SKIPPED" in r.stderr, r.stderr


def test_the_id_may_sit_anywhere_in_the_hook_item(
    run_dir: Path, repo: Path, tmp_path: Path
) -> None:
    """The anchor demanded `- id: governance-sync` as the item's FIRST line, so a `name:`-first
    reordering of the hub's own config turned the fleet's sync lane test off with only a stderr
    line. The id is found anywhere in the item, and a `files:` written ABOVE it is still read."""
    h = tmp_path / "hub-name-first"
    h.mkdir()
    (h / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks:\n      - name: Sync governance\n"
        "        files: '(^scripts/enforcement/)'\n        id: governance-sync\n",
        encoding="utf-8",
    )
    r = _cr(
        run_dir,
        *_start("--file", "scripts/enforcement/check_x.py", "--declare", _ALL_NO),
        cwd=repo,
        extra_env={"FABRIK_HUB_ROOT": str(h)},
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "REFUSED — fabrik-task: sync → right-now + /fabrik-review" in r.stdout
    assert "sync lane test SKIPPED" not in r.stderr


# ═══════════════════════════════════════════════════════════════════════════════════════════
# T01b — the CLOSE-time re-measure (spec § Chosen approach, Phase 5: invariants (i)-(vi)),
# the four `--commit` refusal CONDITIONS carrying THREE messages, and `upgrade` keying.
#
# Eight Behavior-Contract rows, six refusal graders (one per close-time CONDITION), and the
# residue graders for the classes T01a's own review named: a guard inside a scope where it can
# never fire, presence-vs-truthiness, an anchor matched by equality where the live text has a
# suffix, a `check=True` turning an rc signal into a silent success, and a grader that cannot
# reach the branch it claims to cover.
# ═══════════════════════════════════════════════════════════════════════════════════════════

# The close verbs REFUSE without a structured verdict (`_feedback_lacks_substance`). Every close
# below is SETUP for an assertion about the lane's two row fields, so the verdict is supplied
# once here rather than at thirty call sites.
_FB = "confusion: none · waste: none · change: none · filed: none — surfaces exercised: the lane"

# A hub config whose governance-sync regex carries BOTH alternatives row 3 needs: a whole-PREFIX
# one (`scripts/enforcement/`) and a single-FILE one that is ALSO a Doc Sync Matrix prefix member
# (`docs/reference/technology-stack-decision-guide.md`). The live hub filter carries both; the
# T01a fixture carries only the first, and row 3's union is unfalsifiable without the second.
_FIXTURE_CONFIG_SYNC = """\
repos:
  - repo: local
    hooks:
      - id: governance-sync
        name: Sync governance + enforcement to all projects
        files: '(^scripts/enforcement/|^docs/reference/technology-stack-decision-guide\\.md$)'
"""

# ⚠️ The heading carries its live SUFFIX. An equality read finds nothing here, exactly as it
# finds nothing in both live copies, and EXCL silently collapses to the six-constant fallback.
# The SECOND `## ` section carries a backticked `.md` token that must NEVER reach EXCL — that is
# what makes the block terminator falsifiable rather than decorative.
_FIXTURE_CLAUDE = """\
# Contract — a fixture

## Doc Sync Matrix (update matched docs in same change — gate-enforced)
| Change | Update |
|---|---|
| New env var | `.env.example` + `docs/CONFIGURATION.md` |
| Code/Docker/deps changed | `CHANGELOG.md` |
| Feature shipped | `docs/FEATURES.md` |
| Schema migration | Alembic + `db/schema.sql` |
| New subsystem | a DEDICATED doc — `docs/reference/<name>.md` (box-local → `docs/workstation/<name>.md`) |

## Agent Provenance Trailers
| Trailer | Update |
|---|---|
| `Agent-Role` | `docs/NOT_A_MATRIX_ROW.md` |
"""
# ⚠️ The decoy sits in the SECOND cell of that table, the column the parser reads. An earlier
# cut put it in the third and the block-terminator grader could not fail: deleting the
# terminator changed nothing, because the token was never in a cell the parser looked at —
# "a grader that cannot reach the branch it claims to cover", caught by mutating the terminator.


@pytest.fixture
def hub_sync(tmp_path: Path) -> Path:
    h = tmp_path / "hub-sync"
    h.mkdir()
    (h / ".pre-commit-config.yaml").write_text(_FIXTURE_CONFIG_SYNC, encoding="utf-8")
    return h


def _write(repo: Path, rel: str, text: str = "y\n") -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _commit_all(repo: Path, msg: str) -> str:
    """Stage everything in the THROWAWAY fixture repo and commit it; return the new HEAD.

    `git add -A` is a HARD STOP on the shared tree and a fixture convenience here: `repo` is a
    `tmp_path` git repo this test built three lines ago and nobody else can be writing to it.
    """
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True, timeout=15)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg],
        cwd=str(repo),
        check=True,
        timeout=15,
    )
    return _head(repo)


def _seed_claude(
    repo: Path, text: str = _FIXTURE_CLAUDE, also: dict[str, str] | None = None
) -> None:
    """Commit the matrix BEFORE the measured commit — a `CLAUDE.md` created in the SAME commit
    would be an undeclared path OF that commit and would count itself."""
    (repo / "CLAUDE.md").write_text(text, encoding="utf-8")
    for rel, body in (also or {}).items():
        _write(repo, rel, body)
    _commit_all(repo, "seed the matrix")


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "-q", "--verify", "HEAD"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    ).stdout.strip()


def _rows(run_dir: Path) -> list[dict]:
    """The fleet usage ledger this close wrote — throwaway, beside the throwaway record dir."""
    p = run_dir.parent / "command-feedback.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _events(run_dir: Path) -> list[dict]:
    out = []
    for f in sorted((run_dir.parent / "events").rglob("*.jsonl")):
        for ln in f.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                out.append(json.loads(ln))
    return out


def _close_run(
    run_dir: Path,
    repo: Path,
    hub: Path,
    verb: str,
    *extra: str,
    command: str = "fabrik-task",
    sid: str = "s1",
) -> subprocess.CompletedProcess[str]:
    return _cr(
        run_dir,
        verb,
        "--command",
        command,
        *extra,
        "--feedback",
        _FB,
        cwd=repo,
        sid=sid,
        extra_env={"FABRIK_HUB_ROOT": str(hub)},
    )


def _start_task(
    run_dir: Path, repo: Path, hub: Path, *files: str, sid: str = "s1"
) -> subprocess.CompletedProcess[str]:
    argv: list[str] = []
    for f in files:
        argv += ["--file", f]
    r = _cr(
        run_dir,
        *_start(*argv, "--declare", _ALL_NO),
        cwd=repo,
        sid=sid,
        extra_env={"FABRIK_HUB_ROOT": str(hub)},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    return r


# ---------------------------------------------------------------- T01b row 1


def test_an_undeclared_path_in_the_commit_is_counted(
    run_dir: Path, repo: Path, hub_sync: Path
) -> None:
    """Row 1. Declared `src/a.py`; the commit changed it AND added `src/b2.py`. The field's
    grammar is `<n> · commit=<sha> · paths=<first three>` — commit BEFORE paths (D-294), because
    `_cap_field` truncates the TAIL and three deep paths push the value past the 2,000 cap, where
    the spec's own `paths=`-first order loses the SHA entirely."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub_sync, "src/a.py")
    _write(repo, "src/a.py", "x = 2\n")
    _write(repo, "src/b2.py")
    sha = _commit_all(repo, "the change")

    r = _close_run(
        run_dir, repo, hub_sync, "done", "--commit", sha, "--evidence", "the grader is green"
    )
    assert r.returncode == 0, r.stdout + r.stderr
    row = _rows(run_dir)[-1]
    assert row["oversized_mini"] == f"1 · commit={sha} · paths=src/b2.py", row["oversized_mini"]
    assert "upgrade" not in row


# ---------------------------------------------------------------- T01b row 2


def test_the_matrix_destinations_are_excluded_at_close_time(
    run_dir: Path, repo: Path, hub_sync: Path
) -> None:
    """Row 2. The Doc Sync Matrix's *Update* column is parsed from `CLAUDE.md` AT CLOSE TIME, so
    `docs/FEATURES.md` — a matrix destination that is NOT one of the six fallback constants — is
    excluded and the count is 0."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub_sync, "src/a.py")
    _write(repo, "src/a.py", "x = 2\n")
    _write(repo, "CHANGELOG.md", "# changelog\n")
    _write(repo, "docs/FEATURES.md", "# features\n")
    sha = _commit_all(repo, "docs")
    r = _close_run(run_dir, repo, hub_sync, "done", "--commit", sha, "--evidence", "green")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rows(run_dir)[-1]["oversized_mini"] == "0"


def test_a_token_under_the_next_heading_never_reaches_excl(
    run_dir: Path, repo: Path, hub_sync: Path
) -> None:
    """The block terminator, falsifiably. `docs/NOT_A_MATRIX_ROW.md` is backticked, ends `.md`,
    and sits under the `## Agent Provenance Trailers` heading. A scan that runs to end-of-file
    excludes it and reads 0 here."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub_sync, "src/a.py")
    _write(repo, "src/a.py", "x = 2\n")
    _write(repo, "docs/NOT_A_MATRIX_ROW.md", "# no\n")
    sha = _commit_all(repo, "decoy")
    r = _close_run(run_dir, repo, hub_sync, "done", "--commit", sha, "--evidence", "green")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (
        _rows(run_dir)[-1]["oversized_mini"] == f"1 · commit={sha} · paths=docs/NOT_A_MATRIX_ROW.md"
    )


# ---------------------------------------------------------------- T01b row 3


def test_the_union_counts_a_sync_hit_that_excl_already_covered(
    run_dir: Path, repo: Path, hub_sync: Path
) -> None:
    """Row 3. Set B of invariant (v) takes EVERY sync hit, excluded or not — it is not a third
    arm of one exclusion chain. The commit renames a DECLARED file into `scripts/enforcement/`
    (the destination inherits its source's membership, so set A is empty) and writes
    `docs/reference/technology-stack-decision-guide.md` (a matrix EXCL PREFIX member). Both are
    sync hits, so the row counts BOTH. A three-way-exclusion reading scores 0 here."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub_sync, "src/a.py")
    subprocess.run(
        ["git", "mv", "src/a.py", "scripts/enforcement/a.py"], cwd=str(repo), check=True, timeout=15
    )
    _write(repo, "docs/reference/technology-stack-decision-guide.md", "# stack\n")
    sha = _commit_all(repo, "sync")
    r = _close_run(run_dir, repo, hub_sync, "done", "--commit", sha, "--evidence", "green")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rows(run_dir)[-1]["oversized_mini"] == (
        f"2 · commit={sha} · paths=docs/reference/technology-stack-decision-guide.md,"
        "scripts/enforcement/a.py"
    ), _rows(run_dir)[-1]["oversized_mini"]


def test_a_rename_destination_inherits_its_sources_membership(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """The membership half of row 3, isolated from the sync half (this fixture's filter never
    hits `src/`). A DECLARED `src/a.py` renamed to `src/moved.py` counts 0 — the destination
    inherits — while an UNDECLARED source contributes on its own membership."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub, "src/a.py")
    subprocess.run(["git", "mv", "src/a.py", "src/moved.py"], cwd=str(repo), check=True, timeout=15)
    sha = _commit_all(repo, "mv")
    r = _close_run(run_dir, repo, hub, "done", "--commit", sha, "--evidence", "green")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rows(run_dir)[-1]["oversized_mini"] == "0"

    _start_task(run_dir, repo, hub, "src/c.py", sid="s2")
    subprocess.run(
        ["git", "mv", "src/b.py", "src/b_moved.py"], cwd=str(repo), check=True, timeout=15
    )
    sha = _commit_all(repo, "mv an undeclared one")
    r = _close_run(run_dir, repo, hub, "done", "--commit", sha, "--evidence", "green", sid="s2")
    assert r.returncode == 0, r.stdout + r.stderr
    # BOTH tokens of the pair contribute: the source is judged on its own membership like any
    # other path, and the destination inherits a non-membership.
    assert _rows(run_dir)[-1]["oversized_mini"] == (
        f"2 · commit={sha} · paths=src/b.py,src/b_moved.py"
    ), _rows(run_dir)[-1]["oversized_mini"]


def test_a_copy_and_a_rename_in_one_commit_are_split_on_three_fields(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """Invariant (iii)'s field structure. `-z` TERMINATES every field and BOTH `R` and `C` are
    THREE fields; a splitter that takes three only for `R` reads a `C100` destination as the next
    STATUS and every later field is off by one. The non-ASCII path is the `-z` half: without it
    git emits `"caf\\303\\251.md"` and no declared spelling can match its own diff line."""
    body = "".join(f"line {i} of a file long enough for rename detection\n" for i in range(40))
    _seed_claude(repo, also={"src/a.py": body})
    _start_task(run_dir, repo, hub, "src/a.py")
    subprocess.run(
        ["git", "mv", "src/a.py", "src/renamed.py"], cwd=str(repo), check=True, timeout=15
    )
    _write(repo, "src/copy.py", body)
    _write(repo, "src/café.md", "n\n")
    sha = _commit_all(repo, "rename and copy")
    raw = subprocess.run(
        [
            "git",
            "-c",
            "core.quotePath=false",
            "diff",
            "--name-status",
            "-M",
            "-C",
            "-z",
            f"{sha}~1",
            sha,
        ],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    ).stdout
    assert "C" in {f[:1] for f in raw.split("\0")}, ("the fixture did not produce a COPY", raw)

    r = _close_run(run_dir, repo, hub, "done", "--commit", sha, "--evidence", "green")
    assert r.returncode == 0, r.stdout + r.stderr
    # `src/renamed.py` inherits the declared `src/a.py` — a RENAME moves declared work and its
    # source ceases to exist. `src/copy.py` does NOT: a COPY leaves the source in place and the
    # destination is a brand-new file nobody declared, so it counts. The non-ASCII add is the
    # other undeclared path — and its name arrives UNQUOTED.
    assert (
        _rows(run_dir)[-1]["oversized_mini"] == f"2 · commit={sha} · paths=src/café.md,src/copy.py"
    ), _rows(run_dir)[-1]["oversized_mini"]


# ---------------------------------------------------------------- T01b row 4 (six refusals)


def test_an_empty_commit_value_gets_its_own_message(run_dir: Path, repo: Path, hub: Path) -> None:
    """Condition 1. The quoted substitution delivers `''` when the capture file is absent or
    empty, and the tool cannot tell which — so the remedy is to re-read the file. An ABSENT
    `--commit` is a DIFFERENT mistake and this text would send it to a file that does not exist.
    Presence, not truthiness: `""` must reach THIS arm, never the `no-commit` one."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub, "src/a.py")
    r = _close_run(run_dir, repo, hub, "done", "--commit", "", "--evidence", "green")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "--commit is empty — re-read the capture file" in r.stdout, r.stdout
    assert _rec(run_dir)["state"] == "running"
    assert _rows(run_dir) == []


def test_a_done_without_commit_is_refused_and_names_the_capture(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """Condition 2. Required on `done` only when the LIVE record's command is `fabrik-task` —
    argparse cannot see the record, so the check lives in `_close`."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub, "src/a.py")
    r = _close_run(run_dir, repo, hub, "done", "--evidence", "green")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "done needs --commit" in r.stdout, r.stdout
    assert "capture" in r.stdout
    assert "re-read the capture file" not in r.stdout, "the EMPTY-value remedy, on an ABSENT flag"
    assert _rec(run_dir)["state"] == "running"


def test_a_merge_commit_is_refused(run_dir: Path, repo: Path, hub: Path) -> None:
    """Condition 3. A merge has two parents, so its diff against `~1` is ONE side's only — a
    number that would silently describe the wrong change. § EXIT's local-merge disposition passes
    the merged BRANCH's own commit instead. Shares its message with condition 4."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub, "src/a.py")
    base = subprocess.run(
        ["git", "symbolic-ref", "--short", "-q", "HEAD"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    ).stdout.strip()
    subprocess.run(["git", "checkout", "-q", "-b", "side"], cwd=str(repo), check=True, timeout=15)
    _write(repo, "src/side.py")
    _commit_all(repo, "side")
    subprocess.run(["git", "checkout", "-q", base], cwd=str(repo), check=True, timeout=15)
    _write(repo, "src/a.py", "x = 3\n")
    _commit_all(repo, "main")
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "merge",
            "--no-ff",
            "-q",
            "-m",
            "merge",
            "side",
        ],
        cwd=str(repo),
        check=True,
        timeout=15,
    )
    sha = _head(repo)
    parents = subprocess.run(
        ["git", "log", "-1", "--format=%p", sha],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    ).stdout.split()
    assert len(parents) == 2, ("the fixture did not actually build a merge", parents)

    r = _close_run(run_dir, repo, hub, "done", "--commit", sha, "--evidence", "green")
    assert r.returncode == 1, r.stdout + r.stderr
    assert f"--commit {sha} is not this run's commit" in r.stdout, r.stdout
    assert _rec(run_dir)["state"] == "running"


def test_a_commit_dated_before_the_run_is_refused(run_dir: Path, repo: Path, hub: Path) -> None:
    """Condition 4. A STALE capture file — a previous run's SHA — resolves perfectly and has one
    parent. Its committer date is what refuses it, and it shares condition 3's message: both
    answer the same question, "this is not this run's commit"."""
    _seed_claude(repo)
    _write(repo, "src/old.py")
    subprocess.run(["git", "add", "-A"], cwd=str(repo), check=True, timeout=15)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "old"],
        cwd=str(repo),
        check=True,
        timeout=15,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(repo),
            "GIT_COMMITTER_DATE": "2020-01-01T00:00:00+0000",
            "GIT_AUTHOR_DATE": "2020-01-01T00:00:00+0000",
        },
    )
    stale = _head(repo)
    _start_task(run_dir, repo, hub, "src/a.py")
    r = _close_run(run_dir, repo, hub, "done", "--commit", stale, "--evidence", "green")
    assert r.returncode == 1, r.stdout + r.stderr
    assert f"--commit {stale} is not this run's commit" in r.stdout, r.stdout
    assert _rec(run_dir)["state"] == "running"


def test_commit_on_any_other_command_is_refused(run_dir: Path, repo: Path, hub: Path) -> None:
    """Condition 5, and the guard-inside-a-scope-it-can-never-fire class T01a's review named.
    This refusal sits OUTSIDE the `command == fabrik-task` block: placed inside it, `--commit` on
    any other command is SILENTLY ACCEPTED — on a script fleet-synced to ~46 repos, that breaks
    the byte-identical promise everywhere at once."""
    r = _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-spec",
        "--phases",
        "2",
        "--terminal",
        "the spec is converged",
        cwd=repo,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    r = _close_run(
        run_dir,
        repo,
        hub,
        "done",
        "--commit",
        _head(repo),
        "--evidence",
        "green",
        command="fabrik-spec",
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "REFUSED — --commit belongs to --command fabrik-task" in r.stdout, r.stdout
    assert _rec(run_dir)["state"] == "running"


def test_an_upgrade_sync_claim_with_no_sync_hit_is_refused(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """Condition 6. `UPGRADE: sync` is the lane's widest claim — it says this change reaches ~46
    repos. A commit whose paths the sync regex never matches cannot have made it."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub, "src/a.py")
    _write(repo, "src/a.py", "x = 2\n")
    sha = _commit_all(repo, "not a sync change")
    r = _close_run(
        run_dir,
        repo,
        hub,
        "done",
        "--commit",
        sha,
        "--evidence",
        "UPGRADE: sync — the governance filter",
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "claims UPGRADE: sync but the commit has no sync-regex hit" in r.stdout, r.stdout
    assert _rec(run_dir)["state"] == "running"


# ---------------------------------------------------------------- T01b row 5


def test_upgrade_is_anchored_and_keyed(run_dir: Path, repo: Path, hub_sync: Path) -> None:
    """Row 5. ANCHORED, never a substring search: `--evidence "fix complete; no UPGRADE: was
    required"` writes `upgrade: was` under an unanchored reading. A bare `UPGRADE:` with no token
    writes NO field and never raises (an IndexError here becomes a SILENT rc 0). The match is
    case-SENSITIVE."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub_sync, "src/a.py")
    r = _close_run(
        run_dir,
        repo,
        hub_sync,
        "handoff",
        "--resume",
        "docs/development/reviews/x.md",
        "--reason",
        "UPGRADE: mechanism — the size gate wants a fourth test",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    row = _rows(run_dir)[-1]
    assert row["upgrade"] == "mechanism", row
    assert row["oversized_mini"] == "unmeasurable=no-commit"

    # `UPGRADE:sync` — no space after the colon is still a token — on a done with a real hit.
    _start_task(run_dir, repo, hub_sync, "src/b.py", sid="s2")
    _write(repo, "scripts/enforcement/check_new.py", "x = 1\n")
    sha = _commit_all(repo, "a sync change")
    r = _close_run(
        run_dir,
        repo,
        hub_sync,
        "done",
        "--commit",
        sha,
        "--evidence",
        "UPGRADE:sync — no space after the colon",
        sid="s2",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rows(run_dir)[-1]["upgrade"] == "sync"

    # Unanchored, bare, and lowercase — none of the three writes the field.
    #
    # ⚠️ Every close below asserts that the close ACTUALLY HAPPENED, not merely that it exited 0.
    # `main`'s fail-soft turns any exception into rc 0 with no record and no ledger row, so
    # `rows[-1]` would then be the PREVIOUS close's row — which of course has no `upgrade`. An
    # earlier cut asserted rc 0 + `rows[-1]` alone and stayed GREEN with `rest[0]` raising
    # IndexError on the bare `UPGRADE:`; the grader for the very trap the source documents could
    # not fail. The row COUNT and the record's own state are what close that.
    for sid, text in (
        ("s3", "fix complete; no UPGRADE: was required"),
        ("s4", "UPGRADE:"),
        ("s5", "upgrade: mechanism"),
    ):
        _start_task(run_dir, repo, hub_sync, "src/c.py", sid=sid)
        before = len(_rows(run_dir))
        r = _close_run(run_dir, repo, hub_sync, "blocked", "--reason", text, sid=sid)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "BLOCKED /fabrik-task — run record closed." in r.stdout, (sid, r.stdout, r.stderr)
        assert _rec(run_dir, sid)["state"] == "blocked", (sid, r.stderr)
        rows = _rows(run_dir)
        assert len(rows) == before + 1, (sid, before, len(rows), r.stderr)
        assert "upgrade" not in rows[-1], (sid, text, rows[-1])


def test_a_review_close_carries_neither_lane_field(run_dir: Path, repo: Path, hub: Path) -> None:
    """The negative grader (step 6). Invariant (i): the re-measure runs ONLY on a record whose
    `command` is `fabrik-task`. `/fabrik-review-scoped` is a review-family close that owes no
    artifact, so this grader reaches the close ITSELF rather than stopping at the artifact floor
    — the "a grader that cannot reach the branch it claims to cover" class."""
    r = _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-review-scoped",
        "--phases",
        "1",
        "--terminal",
        "a delta round confirms zero",
        cwd=repo,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    r = _close_run(
        run_dir,
        repo,
        hub,
        "done",
        "--evidence",
        "UPGRADE: sync — a claim this command may make freely",
        command="fabrik-review-scoped",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    row = _rows(run_dir)[-1]
    assert "oversized_mini" not in row and "upgrade" not in row, row
    assert [e for e in _events(run_dir) if e.get("event") == "run_close"]
    assert all(
        "oversized_mini" not in e and "upgrade" not in e
        for e in _events(run_dir)
        if e.get("event") == "run_close"
    )
    # `in`, not `[-1]`: the close prints the advisory QUEUE line after this one.
    assert "DONE /fabrik-review-scoped — run record closed." in r.stdout.splitlines()


# ---------------------------------------------------------------- T01b row 6


def test_a_root_commit_is_diffed_against_the_empty_tree(
    run_dir: Path, tmp_path: Path, hub: Path
) -> None:
    """Row 6. A root commit has NO parent, so `<c>~1` does not resolve — its diff is taken
    against the empty tree `4b825dc…`. A repo whose FIRST commit is the run's commit is the
    scaffold case, and reading it as `no-git` would hide the whole change."""
    r = tmp_path / "virgin"
    r.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(r), check=True, timeout=15)
    _write(r, "src/only.py")
    run = _cr(
        run_dir,
        *_start("--file", "src/only.py", "--declare", _ALL_NO),
        cwd=r,
        extra_env={"FABRIK_HUB_ROOT": str(hub)},
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert _rec(run_dir)["declared"]["sha"] == "unavailable"
    _write(r, "src/undeclared.py")
    sha = _commit_all(r, "root")
    assert (
        subprocess.run(
            ["git", "log", "-1", "--format=%p", sha],
            cwd=str(r),
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        ).stdout.strip()
        == ""
    ), "the fixture did not build a ROOT commit"
    out = _close_run(run_dir, r, hub, "done", "--commit", sha, "--evidence", "green")
    assert out.returncode == 0, out.stdout + out.stderr
    assert _rows(run_dir)[-1]["oversized_mini"] == f"1 · commit={sha} · paths=src/undeclared.py"


# ---------------------------------------------------------------- T01b row 7


def test_no_commit_wins_unconditionally_over_sync_unavailable(
    run_dir: Path, repo: Path, tmp_path: Path
) -> None:
    """Row 7. `handoff`/`blocked` may close before any commit exists, so an ABSENT `--commit` is
    `unmeasurable=no-commit`, never a refusal — and `no-commit` WINS unconditionally: with no
    diff the membership arm cannot run, so `sync_test-unavailable` is UNREACHABLE here even
    though the sync filter is unreadable at both `start` and this close."""
    _seed_claude(repo)
    nowhere = tmp_path / "no-hub"
    nowhere.mkdir()
    r = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", _ALL_NO),
        cwd=repo,
        extra_env={"FABRIK_HUB_ROOT": str(nowhere)},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rec(run_dir)["declared"]["sync_test"] == "unavailable"
    out = _close_run(
        run_dir,
        repo,
        nowhere,
        "handoff",
        "--resume",
        "docs/development/reviews/x.md",
        "--reason",
        "UPGRADE: mechanism — routed",
    )
    assert out.returncode == 0, out.stdout + out.stderr
    row = _rows(run_dir)[-1]
    assert row["oversized_mini"] == "unmeasurable=no-commit", row
    assert row["upgrade"] == "mechanism"


def test_sync_test_unavailable_is_reported_only_when_no_count_wins(
    run_dir: Path, repo: Path, tmp_path: Path, hub: Path
) -> None:
    """The third `unmeasurable` reason and its PRECEDENCE. Reachable ONLY on a close that DID
    carry a commit, and only when the membership arm produced nothing — a count still wins,
    because a count is a real measurement of the half that could be measured."""
    _seed_claude(repo)
    nowhere = tmp_path / "no-hub"
    nowhere.mkdir()
    r = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", _ALL_NO),
        cwd=repo,
        extra_env={"FABRIK_HUB_ROOT": str(hub)},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    _write(repo, "src/a.py", "x = 2\n")
    sha = _commit_all(repo, "declared only")
    out = _close_run(run_dir, repo, nowhere, "done", "--commit", sha, "--evidence", "green")
    assert out.returncode == 0, out.stdout + out.stderr
    assert _rows(run_dir)[-1]["oversized_mini"] == "unmeasurable=sync_test-unavailable"

    # A COUNT wins over the same unreadable filter.
    _start_task(run_dir, repo, nowhere, "src/b.py", sid="s2")
    _write(repo, "src/b.py", "x = 2\n")
    _write(repo, "src/extra.py")
    sha = _commit_all(repo, "and an undeclared one")
    out = _close_run(
        run_dir, repo, nowhere, "done", "--commit", sha, "--evidence", "green", sid="s2"
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert _rows(run_dir)[-1]["oversized_mini"] == f"1 · commit={sha} · paths=src/extra.py"


# ---------------------------------------------------------------- T01b row 8


def test_the_matrix_parser_reads_every_row_of_the_live_contract() -> None:
    """Row 8. Executed against the LIVE `CLAUDE.md` — the file the close actually parses, not a
    fixture of it. 22 table rows today; 25 tokens: 23 concrete paths plus the two `<name>`
    prefixes. The DENOMINATOR is derived independently of the parser, so a parser that reads six
    rows fails loudly instead of agreeing with itself."""
    mod = _load("cr_matrix", _SCRIPT)
    root = Path(__file__).resolve().parents[1]
    lines = (root / "CLAUDE.md").read_text(encoding="utf-8").splitlines()
    toks = mod._doc_sync_tokens("\n".join(lines))
    assert toks == {
        ".env.example",
        "CHANGELOG.md",
        "INDEX.md",
        "PORTS.md",
        "db/schema.sql",
        "docs/BUSINESS_MODEL.md",
        "docs/CONFIGURATION.md",
        "docs/DECISIONS.md",
        "docs/DEPLOYMENT.md",
        "docs/FEATURES.md",
        "docs/LESSONS_LEARNT.md",
        "docs/OPERATIONS.md",
        "docs/QUICKSTART.md",
        "docs/README.md",
        "docs/RESILIENCE.md",
        "docs/SERVICES.md",
        "docs/STRATEGIC_BACKLOG.md",
        "docs/TROUBLESHOOTING.md",
        "docs/data-contract.md",
        "docs/design-system.md",
        "docs/flows.md",
        "docs/reference/",
        "docs/ui-design.md",
        "docs/workstation/",
        # `lessons-learnt.md` is NOT here on purpose: the row's parenthetical names it as prose
        # ("lowercase … is legacy-tolerated") and a bare token with no `/` is not a destination —
        # this set pinned the harvest defect until the whole-plan review (F5).
    }, sorted(toks)
    assert len(toks) == 24  # 24: the LESSONS row's parenthetical `lessons-learnt.md` is prose, not a destination (F5)
    assert sum(1 for t in toks if t.endswith("/")) == 2

    at = next(i for i, ln in enumerate(lines) if ln.startswith("## Doc Sync Matrix"))
    end = next((i for i in range(at + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    body = [ln for ln in lines[at:end] if ln.startswith("|")]
    assert len(body) - 2 == 22, len(body)
    assert lines[at] != "## Doc Sync Matrix", (
        "the live heading carries a SUFFIX — an equality read finds nothing and EXCL silently "
        "collapses from 26 paths to 6"
    )


def test_docs_capabilities_is_a_real_file() -> None:
    """Invariant (iv)'s named constant. `docs/CAPABILITIES.md` is NOT a Doc Sync Matrix row — it
    is the corpus inventory's documentation landing site — so it is a constant in the source, and
    a constant naming a file that does not exist is an exclusion nobody can ever earn."""
    mod = _load("cr_caps", _SCRIPT)
    assert (Path(__file__).resolve().parents[1] / mod._TASK_CAPABILITIES).is_file()


def test_a_repo_without_the_matrix_falls_back_to_six_constants(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """Invariant (iv)'s FALLBACK, stated in the docstring and GRADED here: a repo whose
    `CLAUDE.md` lacks the section (or has no `CLAUDE.md` at all) excludes the five ledger files
    plus `docs/CAPABILITIES.md` — never a fourth `unmeasurable` reason."""
    mod = _load("cr_fallback", _SCRIPT)
    assert mod._task_excl(repo) == set(mod._TASK_LEDGER_EXCL) | {mod._TASK_CAPABILITIES}
    assert len(mod._task_excl(repo)) == 6

    _start_task(run_dir, repo, hub, "src/a.py")
    _write(repo, "docs/STRATEGIC_BACKLOG.md", "# backlog\n")
    _write(repo, "docs/CAPABILITIES.md", "# caps\n")
    _write(repo, "docs/FEATURES.md", "# features\n")  # a matrix row — NOT one of the six
    sha = _commit_all(repo, "docs")
    out = _close_run(run_dir, repo, hub, "done", "--commit", sha, "--evidence", "green")
    assert out.returncode == 0, out.stdout + out.stderr
    assert _rows(run_dir)[-1]["oversized_mini"] == f"1 · commit={sha} · paths=docs/FEATURES.md"


def test_the_matrix_scan_falls_back_to_end_of_file() -> None:
    """The scan's END when NO later `## ` exists. An unguarded `next()` raises StopIteration, and
    `main`'s fail-soft turns that into rc 0 with no measurement at all."""
    mod = _load("cr_eof", _SCRIPT)
    text = _FIXTURE_CLAUDE.split("## Agent Provenance Trailers")[0]
    assert "## Doc Sync Matrix" in text and text.count("## ") == 1
    toks = mod._doc_sync_tokens(text)
    assert "docs/FEATURES.md" in toks and "docs/reference/" in toks
    assert "docs/NOT_A_MATRIX_ROW.md" not in toks


def test_the_measure_never_refuses_when_git_is_unavailable(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """`unmeasurable=no-git`, never rc-0-by-exception and never a refusal: a MEASUREMENT failure
    must not block a close, or the record stays `running` and the Stop hook blocks the turn
    forever. Driven by removing git from PATH — the real failure, not a patched flag."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub, "src/a.py")
    _write(repo, "src/a.py", "x = 2\n")
    _write(repo, "src/gone.py")
    sha = _commit_all(repo, "change")
    empty = run_dir.parent / "nogit"
    empty.mkdir(exist_ok=True)
    out = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-task",
        "--commit",
        sha,
        "--evidence",
        "green",
        "--feedback",
        _FB,
        cwd=repo,
        extra_env={"PATH": str(empty), "FABRIK_HUB_ROOT": str(hub)},
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert _rows(run_dir)[-1]["oversized_mini"] == "unmeasurable=no-git", _rows(run_dir)[-1]
    assert _rec(run_dir)["state"] == "done"


def test_the_close_event_mirrors_the_two_row_fields(
    run_dir: Path, repo: Path, hub_sync: Path
) -> None:
    """Step 5: the `run_close` event dict carries what the row carries, or the event stream and
    the ledger disagree about the same close and nothing downstream can repair it."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub_sync, "src/a.py")
    _write(repo, "src/a.py", "x = 2\n")
    _write(repo, "src/loose.py")
    sha = _commit_all(repo, "change")
    out = _close_run(
        run_dir,
        repo,
        hub_sync,
        "done",
        "--commit",
        sha,
        "--evidence",
        "UPGRADE: mechanism — a new seam",
    )
    assert out.returncode == 0, out.stdout + out.stderr
    closes = [e for e in _events(run_dir) if e.get("event") == "run_close"]
    assert len(closes) == 1, _events(run_dir)
    assert closes[0]["oversized_mini"] == f"1 · commit={sha} · paths=src/loose.py"
    assert closes[0]["upgrade"] == "mechanism"


def test_a_refused_close_emits_no_run_close_event(run_dir: Path, repo: Path, hub: Path) -> None:
    """The ORDERING constraint, falsifiably. `_flush_events` runs in a `finally`, so a refusal
    placed AFTER the `_queue` call leaves a `run_close {verdict: done}` event on the stream for a
    close that never happened — exactly what the NOT-CLOSED path deletes that event to prevent."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub, "src/a.py")
    out = _close_run(run_dir, repo, hub, "done", "--commit", "", "--evidence", "green")
    assert out.returncode == 1, out.stdout + out.stderr
    assert [e for e in _events(run_dir) if e.get("event") == "run_close"] == []


def test_the_field_is_capped_and_keeps_the_sha() -> None:
    """D-294's whole reason. `_cap_field` truncates the TAIL, so `commit=<sha>` comes FIRST: the
    spec's `paths=`-first order loses the SHA entirely on three deep paths."""
    mod = _load("cr_cap", _SCRIPT)
    deep = ["src/" + ("d" * 700) + f"/{i}.py" for i in range(3)]
    val = mod._task_field(9, "f" * 40, deep)
    assert len(val) > mod._LEDGER_FIELD_CAP
    capped = mod._cap_field(val)
    assert capped.startswith("9 · commit=" + "f" * 40)
    assert len(capped) == mod._LEDGER_FIELD_CAP


def test_only_the_first_three_paths_are_named(run_dir: Path, repo: Path, hub: Path) -> None:
    """`paths=<first three>` — the COUNT is the whole set, the names are a sample. A field that
    named all of them would be the truncation D-294 reordered the grammar to survive."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub, "src/a.py")
    for n in ("p1", "p2", "p3", "p4", "p5"):
        _write(repo, f"src/{n}.py")
    sha = _commit_all(repo, "five loose files")
    out = _close_run(run_dir, repo, hub, "done", "--commit", sha, "--evidence", "green")
    assert out.returncode == 0, out.stdout + out.stderr
    assert _rows(run_dir)[-1]["oversized_mini"] == (
        f"5 · commit={sha} · paths=src/p1.py,src/p2.py,src/p3.py"
    )


def test_an_undecodable_claude_md_still_falls_back(run_dir: Path, repo: Path, hub: Path) -> None:
    """`_task_excl`'s docstring says an UNREADABLE `CLAUDE.md` falls back to the six constants.
    An undecodable one raises `UnicodeDecodeError` — a `ValueError`, NOT an `OSError` — so an
    `except OSError` arm lets it escape to the caller and record `unmeasurable=no-git`: a reason
    that is false (git is fine) and that discards a count this repo could still produce."""
    mod = _load("cr_undecodable", _SCRIPT)
    (repo / "CLAUDE.md").write_bytes(b"## Doc Sync Matrix (x)\n| a | `\xff\xfe.md` |\n")
    assert mod._task_excl(repo) == set(mod._TASK_LEDGER_EXCL) | {mod._TASK_CAPABILITIES}

    _commit_all(repo, "an undecodable contract")
    _start_task(run_dir, repo, hub, "src/a.py")
    _write(repo, "src/a.py", "x = 2\n")
    _write(repo, "src/loose.py")
    sha = _commit_all(repo, "change")
    out = _close_run(run_dir, repo, hub, "done", "--commit", sha, "--evidence", "green")
    assert out.returncode == 0, out.stdout + out.stderr
    assert _rows(run_dir)[-1]["oversized_mini"] == f"1 · commit={sha} · paths=src/loose.py"


# ------------------------------------------------- T01b acceptance review, round 1


def test_an_upgrade_sync_claim_survives_an_unreadable_filter(
    run_dir: Path, repo: Path, tmp_path: Path
) -> None:
    """B1. The `pat is not None` guard at `:3224` is a DELIBERATE fail-open: an unreadable sync
    filter cannot REFUTE a sync claim, because refusing on it would turn a spoke's missing hub
    file into a refused close. Condition 6 refuses only when the filter is READABLE and matched
    nothing. Dropping the guard makes this close refuse, and nothing else in the suite sees it."""
    _seed_claude(repo)
    nowhere = tmp_path / "no-hub"
    nowhere.mkdir()
    r = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", _ALL_NO),
        cwd=repo,
        extra_env={"FABRIK_HUB_ROOT": str(nowhere)},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    _write(repo, "src/a.py", "x = 2\n")
    sha = _commit_all(repo, "declared only, filter unreadable")
    out = _close_run(
        run_dir,
        repo,
        nowhere,
        "done",
        "--commit",
        sha,
        "--evidence",
        "UPGRADE: sync — claimed against a filter that cannot be read",
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert "no sync-regex hit" not in out.stdout, out.stdout
    # NOT plain `sync`: an unreadable filter cannot REFUTE the claim, and it cannot CONFIRM
    # one either. The first cut of this grader asserted `== "sync"` and pinned that hole.
    assert _rows(run_dir)[-1]["upgrade"] == "sync (unverified)", _rows(run_dir)[-1]


def test_a_matrix_prefix_row_excludes_its_whole_directory(
    run_dir: Path, repo: Path, hub_sync: Path
) -> None:
    """B2. `_task_excluded`'s `<name>`-prefix branch (`:3004-3006`). `docs/workstation/` is a
    Doc Sync Matrix prefix token AND is provably NOT a sync-regex hit under the fixture filter
    (which matches only `^scripts/enforcement/` and one `docs/reference/` file) — so set B cannot
    smuggle this path in and the exclusion is the ONLY thing keeping the count at 0. Reducing the
    function to `path in excl` makes this count 1."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub_sync, "src/a.py")
    _write(repo, "src/a.py", "x = 2\n")
    _write(repo, "docs/workstation/box-notes.md", "# notes\n")
    sha = _commit_all(repo, "declared file plus a matrix-prefix doc")
    out = _close_run(run_dir, repo, hub_sync, "done", "--commit", sha, "--evidence", "green")
    assert out.returncode == 0, out.stdout + out.stderr
    assert _rows(run_dir)[-1]["oversized_mini"] == "0", _rows(run_dir)[-1]


@pytest.mark.parametrize(
    "kind", ["blob", "unresolvable"], ids=["a-blob-sha", "an-unresolvable-sha"]
)
def test_a_commit_that_does_not_resolve_to_a_commit_is_refused(
    run_dir: Path, repo: Path, hub_sync: Path, kind: str
) -> None:
    """B3. The `cat-file -t` guard (`:3127-3133`). A truncated or corrupted capture file hands the
    close a sha that resolves to a BLOB, or to nothing at all — both land in the same `ok=False`
    bucket as the merge and the stale date, sharing their message. Every other `--commit` test
    supplies a real commit, so deleting this guard changed nothing in the suite.

    ⚠️ This grader covers the BEHAVIOUR — a sha that is not a commit is refused — which three
    legs deliver JOINTLY, so deleting the `cat-file` guard alone leaves it green. The input
    that isolates this guard is an ANNOTATED TAG (it resolves, peels, dates and diffs
    perfectly), and it has its own grader below. Found by T01b's delta review."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub_sync, "src/a.py")
    _write(repo, "src/a.py", "x = 2\n")
    _commit_all(repo, "a real commit that is not the one we pass")
    if kind == "blob":
        bad = subprocess.run(
            ["git", "hash-object", "-w", "src/a.py"],
            cwd=str(repo),
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()
    else:
        bad = "0" * 40
    out = _close_run(run_dir, repo, hub_sync, "done", "--commit", bad, "--evidence", "green")
    assert out.returncode == 1, out.stdout + out.stderr
    assert f"--commit {bad} is not this run's commit" in out.stdout, out.stdout
    assert _rec(run_dir)["state"] == "running"


def test_the_sync_refusal_names_the_flag_the_closing_verb_actually_takes(
    run_dir: Path, repo: Path, hub_sync: Path
) -> None:
    """B4. `flag = "evidence" if args.cmd == "done" else "reason"` (`:3229`). A `handoff` carries
    its claim in `--reason`, so a refusal telling the agent to fix `--evidence` names a flag that
    close does not take. Only the `done` arm was exercised, so the ternary could be swapped with
    the whole suite still green."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub_sync, "src/a.py")
    _write(repo, "src/a.py", "x = 2\n")
    sha = _commit_all(repo, "no sync path here")
    out = _close_run(
        run_dir,
        repo,
        hub_sync,
        "handoff",
        "--resume",
        "docs/development/reviews/x.md",
        "--commit",
        sha,
        "--reason",
        "UPGRADE: sync — claimed on a handoff",
    )
    assert out.returncode == 1, out.stdout + out.stderr
    assert "--reason claims UPGRADE: sync" in out.stdout, out.stdout
    assert "--evidence claims" not in out.stdout, out.stdout
    assert _rec(run_dir)["state"] == "running"


def _mutate_rec(run_dir: Path, sid: str = "s1", **kw: object) -> None:
    """Hand-edit a record on disk. The close must survive shapes `start` can no longer produce:
    a half-written file, an older vintage of this script, a hand-repaired record."""
    f = run_dir / f"{sid}.json"
    rec = json.loads(f.read_text(encoding="utf-8"))
    rec.update(kw)
    f.write_text(json.dumps(rec), encoding="utf-8")


def test_a_copy_of_a_declared_file_is_counted_not_inherited(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """A1 — the lane's cheapest COBRA path, found by the T01b acceptance review. `cp` a declared
    file to a new name and the destination is a brand-new file nobody declared; folding `C` into
    `R` let it inherit the source's membership and score 0. A RENAME's destination inherits (the
    source ceases to exist); a COPY's does not (the source survives)."""
    body = "".join(f"line {i} of a file long enough for copy detection\n" for i in range(40))
    _seed_claude(repo, also={"a.py": body})
    _start_task(run_dir, repo, hub, "a.py")
    _write(repo, "a.py", body + "# edited\n")
    _write(repo, "b_undeclared.py", body)
    sha = _commit_all(repo, "declare one file, ship two")
    out = _close_run(run_dir, repo, hub, "done", "--commit", sha, "--evidence", "green")
    assert out.returncode == 0, out.stdout + out.stderr
    assert _rows(run_dir)[-1]["oversized_mini"] == (f"1 · commit={sha} · paths=b_undeclared.py"), (
        _rows(run_dir)[-1]["oversized_mini"]
    )


def test_a_broken_git_environment_never_refuses_the_close(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """A2 — the fail-CLOSED hole. `_task_git` is `check=False`, so a broken git environment
    returns rc 128 rather than raising, and reading that rc as "the commit is disqualified"
    refused the close, left the record `running` and made `done` UNREACHABLE — the Stop hook then
    blocks the turn, in ~46 repos. A git that cannot name its own git dir is a MEASUREMENT
    failure and must reach the catch-all. Driven by a half-written `.git/config`, the real
    failure (`safe.directory` ownership is the same rc on every verb)."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub, "src/a.py")
    _write(repo, "src/a.py", "x = 2\n")
    sha = _commit_all(repo, "change")
    cfg = repo / ".git" / "config"
    cfg.write_text(cfg.read_text(encoding="utf-8") + "\n[core\n", encoding="utf-8")
    out = _close_run(run_dir, repo, hub, "done", "--commit", sha, "--evidence", "green")
    assert out.returncode == 0, out.stdout + out.stderr
    assert _rows(run_dir)[-1]["oversized_mini"] == "unmeasurable=no-git", _rows(run_dir)[-1]
    assert _rec(run_dir)["state"] == "done"


@pytest.mark.parametrize(
    "files", ["mas.txt", ["mas.txt", 7]], ids=["a-string-scalar", "a-non-string-member"]
)
def test_a_corrupt_declared_block_refuses_to_publish_a_count(
    run_dir: Path, repo: Path, hub: Path, files: object
) -> None:
    """A5 + its element half. A `files` STRING scalar became a set of CHARACTERS, so the declared
    file failed its own membership test and was scored oversized. Guarding only the CONTAINER left
    the same class open one level down: `["mas.txt", 7]` silently dropped the bad member and still
    published a confident number. Both are equally corrupt and neither is measurable.

    The reason stays `no-git` — invariant (vi)'s grammar is closed at three and the mislabel
    (a healthy git reported as an outage) is routed to the backlog, not fixed by a fourth."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub, "mas.txt")
    _mutate_rec(run_dir, declared={"files": files, "sync_test": "ok"})
    _write(repo, "mas.txt", "y\n")
    _write(repo, "extra.txt", "y\n")
    sha = _commit_all(repo, "corrupt record")
    out = _close_run(run_dir, repo, hub, "done", "--commit", sha, "--evidence", "green")
    assert out.returncode == 0, out.stdout + out.stderr
    assert _rows(run_dir)[-1]["oversized_mini"] == "unmeasurable=no-git", _rows(run_dir)[-1]
    assert _rec(run_dir)["state"] == "done"


def test_an_unverifiable_sync_claim_is_recorded_as_unverified(
    run_dir: Path, repo: Path, hub_sync: Path
) -> None:
    """A6. `UPGRADE: sync` is the lane's widest claim — it says this change reaches ~46 repos.
    A close carrying no commit has no diff, so the refutation arm cannot run and the claim was
    recorded exactly as a verified one. The row must not assert what nothing checked."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub_sync, "src/a.py")
    out = _close_run(
        run_dir,
        repo,
        hub_sync,
        "blocked",
        "--reason",
        "UPGRADE: sync — missing infra, nothing committed",
    )
    assert out.returncode == 0, out.stdout + out.stderr
    row = _rows(run_dir)[-1]
    assert row["upgrade"] == "sync (unverified)", row
    assert row["oversized_mini"] == "unmeasurable=no-commit", row


def test_an_annotated_tag_sha_is_refused(run_dir: Path, repo: Path, hub_sync: Path) -> None:
    """The input that ISOLATES the `cat-file -t` guard. A blob or a garbage sha is caught by the
    parent-count leg two lines below as well, so deleting the guard leaves those green — an
    annotated tag is the one shape that resolves, peels through `rev-parse …^{commit}`, dates and
    diffs perfectly, and is still not this run's commit. Found by T01b's delta review, which
    deleted the whole guard and watched all 59 graders pass."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub_sync, "src/a.py")
    _write(repo, "src/a.py", "x = 2\n")
    _write(repo, "src/undeclared.py")
    _commit_all(repo, "two files")
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "tag", "-a", "v1", "-m", "annotated"],
        cwd=str(repo),
        check=True,
        timeout=15,
    )
    tag = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", "v1"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    ).stdout.strip()
    out = _close_run(run_dir, repo, hub_sync, "done", "--commit", tag, "--evidence", "green")
    assert out.returncode == 1, out.stdout + out.stderr
    assert f"--commit {tag} is not this run's commit" in out.stdout, out.stdout
    assert _rec(run_dir)["state"] == "running"


def test_a_truncated_rename_tail_is_dropped_not_guessed(tmp_path: Path, monkeypatch) -> None:
    """The splitter's truncated `R`/`C` arm. Falling through to the 2-field arm re-reads a
    truncated rename's SOURCE as an independent DESTINATION, so the count gains a path the commit
    never added and `_task_field` NAMES it in the ledger row. Shipped with no grader at all until
    T01b's delta review reverted the `break` and watched all 59 pass."""
    mod = _load("cr_pairs", _SCRIPT)

    class _R:
        returncode = 0
        stderr = ""

        def __init__(self, out: str) -> None:
            self.stdout = out

    monkeypatch.setattr(mod, "_task_git", lambda root, *a: _R("M\0src/a.py\0R100\0src/b.py\0"))
    assert mod._task_diff_pairs(tmp_path, "base", "sha") == [("M", None, "src/a.py")]


def test_an_ambient_git_dir_cannot_relocate_the_measurement(
    run_dir: Path, repo: Path, hub: Path, tmp_path: Path
) -> None:
    """The one-variable launder. git reads the REPOSITORY out of the environment before it looks
    at `cwd`, so an ambient `GIT_DIR` — leaked from a hook, a shell, or this repo's own
    private-index recipe, which exports `GIT_INDEX_FILE` and warns that it leaks — made every git
    call in the re-measure answer about a repository the close never named. Pointed at a decoy
    holding only the declared file it produced a VERIFIED-looking `0` for a two-file commit;
    pointed at any other real repo it refused an honest close and left the record `running`.
    Both directions reproduced by T01b's delta review."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub, "src/a.py")
    _write(repo, "src/a.py", "x = 2\n")
    _write(repo, "src/undeclared.py")
    sha = _commit_all(repo, "declared plus one undeclared")

    decoy = tmp_path / "decoy"
    decoy.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(decoy), check=True, timeout=15)
    (decoy / "src").mkdir()
    (decoy / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(decoy), check=True, timeout=15)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "decoy"],
        cwd=str(decoy),
        check=True,
        timeout=15,
    )

    out = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-task",
        "--commit",
        sha,
        "--evidence",
        "green",
        "--feedback",
        _FB,
        cwd=repo,
        extra_env={"FABRIK_HUB_ROOT": str(hub), "GIT_DIR": str(decoy / ".git")},
    )
    assert out.returncode == 0, out.stdout + out.stderr
    # The HONEST count, taken from the run's own repository — not the decoy's `0`, and not a
    # refusal of a commit that exists exactly where the record says it does.
    assert _rows(run_dir)[-1]["oversized_mini"] == (
        f"1 · commit={sha} · paths=src/undeclared.py"
    ), _rows(run_dir)[-1]["oversized_mini"]
    assert _rec(run_dir)["state"] == "done"


# ------------------------------------------------- T01b round 4: the git-environment class


def test_an_ambient_git_work_tree_cannot_relocate_the_repo_the_record_names(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """`GIT_WORK_TREE` moves `rev-parse --show-toplevel`, which is what CHOOSES the repository the
    whole re-measure is taken against. The first cut scrubbed the calls that USE that answer and
    left the call that PRODUCES it ambient, so the relocation was still reachable one hop up: the
    start gate's dirty check silently skipped, `declared.sha` degraded to `unavailable`, and the
    close landed `unmeasurable=no-git` at `state: done`. Here the declared path is DIRTY, so the
    honest answer is a refusal — and it must survive the variable."""
    _seed_claude(repo, also={"src/a.py": "x = 1\n"})
    _write(repo, "src/a.py", "x = 2\n")  # dirty at start, uncommitted
    outer = repo.parent
    r = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", _ALL_NO),
        cwd=repo,
        extra_env={"FABRIK_HUB_ROOT": str(hub), "GIT_WORK_TREE": str(outer)},
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "dirty at start" in r.stdout, r.stdout


def test_an_ambient_git_config_count_cannot_launder_the_count(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """`GIT_CONFIG_COUNT=bogus` makes EVERY git verb exit 128 (`fatal: unable to parse command-line
    config`), so an honest oversized count laundered to `unmeasurable` at rc 0 — the same cobra
    outcome the scrub exists to prevent, through a variable the first list did not carry. The repo
    already enumerated it in `tests/conftest.py` after a measured incident; two lists for one class
    disagreeing is the defect this closes."""
    _seed_claude(repo)
    _start_task(run_dir, repo, hub, "src/a.py")
    _write(repo, "src/a.py", "x = 2\n")
    _write(repo, "src/b.py")
    sha = _commit_all(repo, "one declared, one not")
    out = _close_run(run_dir, repo, hub, "done", "--commit", sha, "--evidence", "green")
    assert out.returncode == 0, out.stdout + out.stderr
    honest = _rows(run_dir)[-1]["oversized_mini"]
    assert honest == f"1 · commit={sha} · paths=src/b.py", honest

    # the same close, only the environment differs
    _start_task(run_dir, repo, hub, "src/a.py", sid="s2")
    _write(repo, "src/a.py", "x = 3\n")
    _write(repo, "src/c.py")
    sha2 = _commit_all(repo, "again")
    out2 = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-task",
        "--commit",
        sha2,
        "--evidence",
        "green",
        "--feedback",
        _FB,
        cwd=repo,
        sid="s2",
        extra_env={"FABRIK_HUB_ROOT": str(hub), "GIT_CONFIG_COUNT": "bogus"},
    )
    assert out2.returncode == 0, out2.stdout + out2.stderr
    got = _rows(run_dir)[-1]["oversized_mini"]
    assert got == f"1 · commit={sha2} · paths=src/c.py", got


def test_an_ambient_pathspec_var_cannot_forge_a_dirty_declared_path(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """`--literal-pathspecs` is added here for a real reason (a glob sibling made a clean
    `src/rep[1].py` read as dirty), but git treats it as INCOMPATIBLE with the other global
    pathspec vars and fails hard rather than ignoring them. Both pathspec-bearing size-gate calls
    read a non-zero rc as DIRTY, so `GIT_ICASE_PATHSPECS=1` refused a perfectly clean declared path
    — and the refusal text told the agent to go accuse a peer of WIP that does not exist."""
    _seed_claude(repo, also={"src/a.py": "x = 1\n"})
    r = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", _ALL_NO),
        cwd=repo,
        extra_env={"FABRIK_HUB_ROOT": str(hub), "GIT_ICASE_PATHSPECS": "1"},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "dirty at start" not in r.stdout, r.stdout


def test_the_scrub_covers_every_relocating_var_the_test_harness_scrubs(tmp_path: Path) -> None:
    """Two lists for one class in one repo is the drift defect. `tests/conftest.py` carries an
    incident-driven `_GIT_ENV_LEAKS`; this module carries `_GIT_ENV_OVERRIDES`. The harness list
    legitimately holds MORE (it scrubs authorship vars, because test helpers COMMIT and this module
    runs no committing verb) — but every var it scrubs that can relocate or reconfigure a READ must
    also be here, or a var added there silently stops being scrubbed in ~46 repos."""
    import ast as _ast

    mod = _load("cr_env", _SCRIPT)
    conftest = _ast.parse(
        (_SCRIPT.resolve().parents[1] / "tests" / "conftest.py").read_text("utf-8")
    )
    leaks: set[str] = set()
    for node in _ast.walk(conftest):
        if isinstance(node, _ast.Assign) and any(
            getattr(t, "id", "") == "_GIT_ENV_LEAKS" for t in node.targets
        ):
            leaks = {e.value for e in node.value.elts if isinstance(e, _ast.Constant)}
    assert leaks, "conftest._GIT_ENV_LEAKS not found — the drift check is grading nothing"
    authorship = {
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
    }
    missing = (leaks - authorship) - set(mod._GIT_ENV_OVERRIDES)
    assert not missing, f"scrubbed by the harness but not by this module: {sorted(missing)}"


def test_the_scrub_is_a_filter_not_a_replacement(monkeypatch) -> None:
    """`env=` REPLACES the environment wholesale, so a scrub written as a literal dict would strip
    `HOME` (git reads `~/.gitconfig`) and `PATH` (git would not be found at all)."""
    mod = _load("cr_filter", _SCRIPT)
    monkeypatch.setenv("GIT_DIR", "/nowhere/.git")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.bare")
    env = mod._scrubbed_git_env()
    assert "GIT_DIR" not in env
    assert "GIT_CONFIG_KEY_0" not in env, "the numbered injection payload must go too"
    assert env.get("HOME") == os.environ.get("HOME")
    assert env.get("PATH") == os.environ.get("PATH")


def test_every_arm_that_could_not_refute_a_sync_claim_says_so(
    run_dir: Path, repo: Path, hub: Path, tmp_path: Path
) -> None:
    """Invariant: `UPGRADE: sync` is the widest claim the lane makes, and a row must never assert a
    reach nothing checked. FOUR arms reach the marking and the first cut guarded ONE — the delta
    review deleted the call on the exception arm, and forced `sync_tested` True on the count and
    zero arms, with all 63 graders still green each time. Each arm is exercised here.

    A: the measurement RAISED (broken git). B: the filter became unreadable at CLOSE and there was
    still something to COUNT. C: the same with nothing to count. All three must read
    `sync (unverified)`.

    ⚠️ Each arm STARTS against a readable hub and only loses the filter at close. Starting
    without one sets `declared.sync_test: unavailable`, and arm C then lands on
    `unmeasurable=sync_test-unavailable` — a DIFFERENT branch, already covered elsewhere, which
    is how the first cut of this grader silently tested the same arm twice."""
    nowhere = tmp_path / "no-hub"
    nowhere.mkdir()

    # --- arm B: a count, taken with no readable sync filter
    _seed_claude(repo, also={"src/a.py": "x = 1\n"})
    r = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", _ALL_NO),
        cwd=repo,
        extra_env={"FABRIK_HUB_ROOT": str(nowhere)},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    _write(repo, "src/a.py", "x = 2\n")
    _write(repo, "src/z.py")
    sha = _commit_all(repo, "one undeclared")
    out = _close_run(
        run_dir, repo, nowhere, "done", "--commit", sha, "--evidence", "UPGRADE: sync — claimed"
    )
    assert out.returncode == 0, out.stdout + out.stderr
    row = _rows(run_dir)[-1]
    assert row["upgrade"] == "sync (unverified)", ("arm B", row)
    assert row["oversized_mini"] == f"1 · commit={sha} · paths=src/z.py", ("arm B", row)

    # --- arm C: the same close with nothing to count
    r = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", _ALL_NO),
        cwd=repo,
        sid="s2",
        extra_env={"FABRIK_HUB_ROOT": str(hub)},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    _write(repo, "src/a.py", "x = 3\n")
    sha2 = _commit_all(repo, "declared only")
    out2 = _close_run(
        run_dir,
        repo,
        nowhere,
        "done",
        "--commit",
        sha2,
        "--evidence",
        "UPGRADE: sync — claimed",
        sid="s2",
    )
    assert out2.returncode == 0, out2.stdout + out2.stderr
    row2 = _rows(run_dir)[-1]
    assert row2["upgrade"] == "sync (unverified)", ("arm C", row2)
    # The start read the filter, the close could not: the count arm found nothing and the sync
    # arm never ran, so the row must SAY so. This line asserted `"0"` — F1's false-clean score,
    # pinned as expected behaviour — until the whole-plan review executed the transition.
    assert row2["oversized_mini"] == "unmeasurable=sync_test-unavailable", ("arm C", row2)

    # --- arm A: the measurement RAISED
    r = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", _ALL_NO),
        cwd=repo,
        sid="s3",
        extra_env={"FABRIK_HUB_ROOT": str(hub)},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    _write(repo, "src/a.py", "x = 4\n")
    sha3 = _commit_all(repo, "third")
    cfg = repo / ".git" / "config"
    cfg.write_text(cfg.read_text(encoding="utf-8") + "\n[core\n", encoding="utf-8")
    out3 = _close_run(
        run_dir,
        repo,
        nowhere,
        "done",
        "--commit",
        sha3,
        "--evidence",
        "UPGRADE: sync — claimed",
        sid="s3",
    )
    assert out3.returncode == 0, out3.stdout + out3.stderr
    row3 = _rows(run_dir)[-1]
    assert row3["upgrade"] == "sync (unverified)", ("arm A", row3)
    assert row3["oversized_mini"] == "unmeasurable=no-git", ("arm A", row3)


def test_an_ambient_git_config_parameters_cannot_skip_the_dirty_check(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """`GIT_CONFIG_COUNT` was scrubbed as half of the RECONFIG channel and `GIT_CONFIG_PARAMETERS`
    — git's OWN `-c` propagation variable, exported into every hook and subprocess whenever the
    invoking command carried `-c`, which the hub contract mandates — was not. A malformed value
    makes every git verb exit 128, the dirty check reads that as "not a repo", and a declared
    path carrying a sibling's WIP STARTS with `sha: "no-repo"` (whole-plan review, executed).
    The harness's own leak list shared the omission, so the two lists graded each other green."""
    (repo / "src" / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    env = {"FABRIK_HUB_ROOT": str(hub), "GIT_CONFIG_PARAMETERS": "'core.'"}
    r = _cr(run_dir, *_start("--file", "src/a.py", "--declare", _ALL_NO), cwd=repo, extra_env=env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "REFUSED — fabrik-task: src/a.py dirty at start" in r.stdout
    assert not (run_dir / "s1.json").exists()


_LOWERCASE_PROSE_MATRIX = """\
## Doc Sync Matrix (update matched docs in same change)
| Change | Update |
|---|---|
| Code changed | `CHANGELOG.md` (lowercase `changelog.md` is tolerated) |
| Ports | `PORTS.md` |
"""


def test_the_matrix_harvest_takes_destinations_never_prose_and_matches_case() -> None:
    r"""The LESSONS row reads `\`docs/LESSONS_LEARNT.md\` (canonical name; lowercase
    \`lessons-learnt.md\` is legacy-tolerated)`, and the harvest took BOTH backticked tokens — so a
    repo-ROOT file named `lessons-learnt.md` was excluded from every close in 47 repos because a
    word appeared inside a parenthetical (whole-plan review, executed: root `lessons-learnt.md`
    scored `0`). Prose in this matrix lives in parentheses; destinations never do. And exclusion
    is exact-case: `docs/changelog.md` is not `CHANGELOG.md`."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("command_run_probe", _SCRIPT)
    cr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cr)
    toks = cr._doc_sync_tokens((_SCRIPT.resolve().parents[1] / "CLAUDE.md").read_text(encoding="utf-8"))
    assert "docs/LESSONS_LEARNT.md" in toks
    assert "lessons-learnt.md" not in toks, "a parenthetical aside was harvested as a destination"
    assert cr._task_excluded("CHANGELOG.md", {"CHANGELOG.md"})
    assert not cr._task_excluded("docs/changelog.md", {"docs/CHANGELOG.md"})
    assert not cr._task_excluded("changelog.md", {"CHANGELOG.md"})
    # The HARVEST is case-exact too: a case-insensitive membership test re-admits the prose token
    # in its lowercase spelling — F5 reborn (delta round: the mutant survived every case above).
    low = cr._doc_sync_tokens(_LOWERCASE_PROSE_MATRIX)
    assert "CHANGELOG.md" in low and "changelog.md" not in low, sorted(low)
    # And the frozen root set is a COPY of a live list: a matrix row naming a new root file would
    # silently fall out of EXCL in ~46 repos. Read the root tokens OUT of both live matrices with
    # an extraction the harvest does not share (a `bare ⊆ set` check through the harvest itself is
    # circular — the harvest drops exactly what the set drops, executed) and pin equality both ways.
    for p in ("CLAUDE.md", "templates/governance/CLAUDE.md"):
        text = (_SCRIPT.resolve().parents[1] / p).read_text("utf-8")
        body = text[text.index("## Doc Sync Matrix"):]
        body = body[: body.index("\n## ", 1)] if "\n## " in body[1:] else body
        cells = [ln.split("|")[2] for ln in body.splitlines() if ln.startswith("| ") and ln.count("|") >= 3]
        cells = [re.sub(r"\([^()]*\)", "", c) for c in cells[1:]]
        roots = {m for c in cells for m in re.findall(r"`([^`/\s]+\.(?:md|example))`", c)}  # a doc, never a script
        assert roots == cr._TASK_ROOT_DESTINATIONS, (p, sorted(roots ^ cr._TASK_ROOT_DESTINATIONS))


def test_the_refusal_names_the_first_row_that_fires_inside_each_tier(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """Nothing pinned the order of the chain at all — not inside a tier and not the tier boundary
    either: the only 4-file grader declares `_ALL_NO`, so `files>3`↔`mechanism` was unobservable,
    and the first cut of THIS docstring claimed that boundary was pinned elsewhere (delta round:
    every one of the six adjacent swaps survived 73 cases except the two pinned here). Two of the
    survivors change the ROUTE, not the label — `tradeoffs`↔`sync` sends spec-chain work to the
    right-now lane, `heavy`↔`decision` downgrades a heavy surface to the scoped review — so every
    adjacent pair is pinned. The contract's sentence ("the first row that fires wins"; rows 2-5
    over 1/1b over 4b) is what the refusal TELLS the agent to re-read."""
    env = {"FABRIK_HUB_ROOT": str(hub)}
    _seed_claude(repo, also={"scripts/enforcement/x.py": "x = 1\n", "src/a.py": "x = 1\n",
                             "src/b.py": "x = 1\n", "src/c.py": "x = 1\n", "src/d.py": "x = 1\n"})
    four = ("--file", "src/a.py", "--file", "src/b.py", "--file", "src/c.py", "--file", "src/d.py")
    cases = (
        (("--file", "src/a.py"), "decision=yes,heavy=no,mechanism=yes,oneway=yes,tradeoffs=no", "mechanism →"),
        (("--file", "src/a.py"), "decision=yes,heavy=no,mechanism=no,oneway=yes,tradeoffs=yes", "oneway →"),
        (("--file", "scripts/enforcement/x.py"), "decision=yes,heavy=no,mechanism=no,oneway=no,tradeoffs=yes", "tradeoffs →"),
        (("--file", "scripts/enforcement/x.py"), "decision=yes,heavy=yes,mechanism=no,oneway=no,tradeoffs=no", "sync →"),
        (("--file", "src/a.py"), "decision=no,heavy=yes,mechanism=no,oneway=no,tradeoffs=no", "heavy →"),
        (four, "decision=yes,heavy=no,mechanism=yes,oneway=no,tradeoffs=no", "files"),
    )
    for files, declare, label in cases:
        r = _cr(run_dir, *_start(*files, "--declare", declare), cwd=repo, extra_env=env)
        assert r.returncode == 1 and f"fabrik-task: {label}" in r.stdout, (label, r.stdout)


def test_a_rename_of_an_excluded_sync_hit_counts_its_source(
    run_dir: Path, repo: Path, hub: Path
) -> None:
    """Set B walks BOTH sides of a rename (`for p in (src, dst)`), and nothing pinned the source
    side: the mutant `for p in (dst,)` survived all 66 (whole-plan review, executed). The source
    is observable through B ALONE only when set A cannot take it — i.e. when it is a MEMBER
    (here: excluded by the `docs/reference/` matrix prefix) that is ALSO a sync hit. The live
    filter has exactly two such paths; `_FIXTURE_CONFIG` now carries one of them for this reason.
    A first cut renamed a non-member `scripts/enforcement/` file and set A counted the source
    regardless, so the mutant survived the guard that was written to kill it."""
    env = {"FABRIK_HUB_ROOT": str(hub)}
    src, dst = "docs/reference/technology-stack-decision-guide.md", "docs/reference/renamed-guide.md"
    _seed_claude(repo, also={src: "# guide\n", "src/a.py": "x = 1\n"})
    r = _cr(run_dir, *_start("--file", "src/a.py", "--declare", _ALL_NO), cwd=repo, extra_env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    _write(repo, "src/a.py", "x = 2\n")
    subprocess.run(["git", "mv", src, dst], cwd=repo, check=True)
    sha = _commit_all(repo, "move the guide out of the filter")
    out = _close_run(run_dir, repo, hub, "done", "--commit", sha, "--evidence", "e")
    assert out.returncode == 0, out.stdout + out.stderr
    got = _rows(run_dir)[-1]["oversized_mini"]
    assert got == f"1 · commit={sha} · paths={src}", got

