"""T08 — `command_run.py` wired to `task_lane` (plan 2026-10-02-plan-1): the lane v2 `start`.

Every grader drives the real script in a subprocess against a throwaway `COMMAND_RUN_DIR` and a
throwaway git repo (`tests/test_command_run_fabrik_task.py`'s harness, reused): the live state
dir is never written and no `$HOME`-rooted `.claude*` path is read. The lane switch is the
FIXTURE repo's own `.fabrik/lane.json`, so the hub's switch never leaks into a grader.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.test_command_run_fabrik_task import _cr, _rec, _start

_V2 = "decision=yes,heavy=no,mechanism=no,oneway=no,tradeoffs=no,consumers=internal"


def _git(repo: Path, *a: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *a],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    ).stdout.strip()


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    d = tmp_path / "state" / "command-runs"
    d.mkdir(parents=True)
    return d


def _repo(tmp_path: Path, *, lane: int | None) -> Path:
    r = tmp_path / "repo"
    (r / "src").mkdir(parents=True)
    (r / "api").mkdir()
    for n in "abcdefgh":
        (r / "src" / f"{n}.py").write_text("x = 1\n", encoding="utf-8")
    (r / "api" / "openapi.yaml").write_text("openapi: 3.1.0\n", encoding="utf-8")
    _git(r, "init", "-q", "-b", "master")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "base")
    if lane is not None:
        (r / ".fabrik").mkdir()
        (r / ".fabrik" / "lane.json").write_text(json.dumps({"version": lane}), encoding="utf-8")
        _git(r, "add", ".fabrik/lane.json")
        _git(r, "commit", "-qm", "lane switch")
    return r


def _files(*names: str) -> list[str]:
    out: list[str] = []
    for n in names:
        out += ["--file", n]
    return out


def _ledger(run_dir: Path) -> list[dict]:
    p = run_dir.parent / "lane-refusals.jsonl"
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln]


def test_without_a_switch_the_start_is_v2_and_names_the_default(
    run_dir: Path, tmp_path: Path
) -> None:
    """No `.fabrik/lane.json` is lane v2 (D-507): a 4-file start is admitted, stamped `gate: 2`,
    and `start` names the switch `default` rather than an uncommitted one."""
    repo = _repo(tmp_path, lane=None)
    four = _files("src/a.py", "src/b.py", "src/c.py", "src/d.py")
    r = _cr(run_dir, *_start(*four, "--declare", _V2), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "lane: v2 (switch default) · review: scoped" in r.stdout
    d = _rec(run_dir)["declared"]
    assert (d["gate"], d["lane_switch"]) == (2, "default")


def test_an_invalid_committed_switch_is_labelled_invalid_not_uncommitted(
    run_dir: Path, tmp_path: Path
) -> None:
    """A committed but unreadable `.fabrik/lane.json` falls back to the default with a warning,
    and `start` names the switch `invalid` — `uncommitted` would send the reader hunting for
    pending edits that do not exist (review of D-507, A-S-2)."""
    repo = _repo(tmp_path, lane=None)
    (repo / ".fabrik").mkdir()
    (repo / ".fabrik" / "lane.json").write_text('{"version": 3}', encoding="utf-8")
    _git(repo, "add", ".fabrik/lane.json")
    _git(repo, "commit", "-qm", "a bad switch")
    r = _cr(run_dir, *_start("--file", "src/a.py", "--declare", _V2), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "lane: v2 (switch invalid) · review: scoped" in r.stdout
    assert ".fabrik/lane.json: version 3 is not one of" in r.stderr
    assert _rec(run_dir)["declared"]["lane_switch"] == "invalid"


def test_a_v1_pin_keeps_the_v1_gate_and_stamps_nothing(run_dir: Path, tmp_path: Path) -> None:
    """A repo that pins `{"version": 1}`: a 4-file start is the v1 `files > 3` refusal, a
    1-file start opens a record with no `gate` key and prints `lane: v1`."""
    repo = _repo(tmp_path, lane=1)
    four = _files("src/a.py", "src/b.py", "src/c.py", "src/d.py")
    r = _cr(run_dir, *_start(*four, "--declare", _V2), cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "REFUSED — fabrik-task: files > 3 → /fabrik-spec" in r.stdout
    r = _cr(run_dir, *_start("--file", "src/a.py", "--declare", _V2), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "lane: v1" in r.stdout.splitlines()
    assert "gate" not in _rec(run_dir)["declared"]
    assert _ledger(run_dir) == []


def test_v1_ignores_the_v2_flags_with_a_note(run_dir: Path, tmp_path: Path) -> None:
    """Command text naming `--appetite` must keep working in a repo that pins v1."""
    repo = _repo(tmp_path, lane=1)
    r = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", _V2, "--appetite", "60"),
        cwd=repo,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "--appetite ignored — this repo runs lane v1" in r.stderr
    assert "appetite" not in _rec(run_dir)["declared"]


def test_v2_admits_a_six_file_feature_and_names_the_switch_commit(
    run_dir: Path, tmp_path: Path
) -> None:
    """Row 2 (V1). With the switch at version 2 a 6-file start is admitted, stamped `gate: 2`
    with the full review it owes (> 5 files), and `start` prints `lane: v2` and the commit that
    set the switch."""
    repo = _repo(tmp_path, lane=2)
    switch = _git(repo, "rev-parse", "HEAD")
    six = _files(*(f"src/{n}.py" for n in "abcdef"))
    r = _cr(run_dir, *_start(*six, "--declare", _V2, "--appetite", "90"), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"lane: v2 (switch {switch}) · review: full · appetite: 90 min" in r.stdout
    d = _rec(run_dir)["declared"]
    assert (d["gate"], d["review"], d["appetite"], d["consumers"]) == (2, "full", 90, "internal")
    assert d["lane_switch"] == switch
    assert len(d["files"]) == 6


def test_v2_five_files_owe_the_scoped_review_and_the_default_appetite(
    run_dir: Path, tmp_path: Path
) -> None:
    """The full-review boundary is > 5: five files are the scoped review."""
    repo = _repo(tmp_path, lane=2)
    five = _files(*(f"src/{n}.py" for n in "abcde"))
    r = _cr(run_dir, *_start(*five, "--declare", _V2), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    d = _rec(run_dir)["declared"]
    assert (d["review"], d["appetite"]) == ("scoped", 240)


def test_v2_tradeoffs_with_why_is_ledgered_and_refused(run_dir: Path, tmp_path: Path) -> None:
    """Row 2 (V9; W-25318990). `tradeoffs=yes` with `--why` routes to the chain, and the refusal
    is written as one row of the ledger under the state dir's PARENT, carrying the why, the
    files, the session and the repo's git common dir — and its id is printed."""
    repo = _repo(tmp_path, lane=2)
    decl = _V2.replace("tradeoffs=no", "tradeoffs=yes")
    r = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", decl, "--why", "queue vs cron"),
        cwd=repo,
    )
    assert r.returncode == 1, r.stdout + r.stderr
    rows = _ledger(run_dir)
    assert len(rows) == 1
    row = rows[0]
    assert row["why"] == "queue vs cron"
    assert row["files"] == ["src/a.py"]
    assert row["session"] == "s1"
    assert row["route"] == "chain: tradeoffs"
    assert Path(row["repo"]) == (repo / ".git").resolve()
    assert f"REFUSED — fabrik-task: tradeoffs → /fabrik-spec (refusal {row['id']})" in r.stdout
    assert not (run_dir / "s1.json").exists()


def test_v2_tradeoffs_without_why_is_refused_naming_the_flag(run_dir: Path, tmp_path: Path) -> None:
    repo = _repo(tmp_path, lane=2)
    decl = _V2.replace("tradeoffs=no", "tradeoffs=yes")
    r = _cr(run_dir, *_start("--file", "src/a.py", "--declare", decl), cwd=repo)
    assert r.returncode == 1
    assert "--why is required with tradeoffs=yes" in r.stdout
    assert _ledger(run_dir) == []


def test_v2_a_contract_path_is_the_chain_and_ledgered(run_dir: Path, tmp_path: Path) -> None:
    repo = _repo(tmp_path, lane=2)
    r = _cr(run_dir, *_start("--file", "api/openapi.yaml", "--declare", _V2), cwd=repo)
    assert r.returncode == 1
    assert "contract: api/openapi.yaml → /fabrik-spec" in r.stdout
    assert [row["route"] for row in _ledger(run_dir)] == ["chain: contract"]


def test_v2_a_missing_consumers_key_is_refused(run_dir: Path, tmp_path: Path) -> None:
    repo = _repo(tmp_path, lane=2)
    decl = _V2.replace(",consumers=internal", "")
    r = _cr(run_dir, *_start("--file", "src/a.py", "--declare", decl), cwd=repo)
    assert r.returncode == 1
    assert "missing --declare keys: consumers" in r.stdout
    assert not (run_dir / "s1.json").exists()


def test_v2_from_downgrade_is_recorded(run_dir: Path, tmp_path: Path) -> None:
    repo = _repo(tmp_path, lane=2)
    r = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", _V2, "--from-downgrade", "LR-0a1b2c3d"),
        cwd=repo,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rec(run_dir)["declared"]["from_downgrade"] == "LR-0a1b2c3d"


def test_the_v2_flags_are_refused_under_any_other_command(run_dir: Path, tmp_path: Path) -> None:
    repo = _repo(tmp_path, lane=2)
    for flag, val in (("--appetite", "30"), ("--why", "x"), ("--from-downgrade", "LR-1")):
        r = _cr(
            run_dir,
            "start",
            "--command",
            "fabrik-review",
            "--phases",
            "3",
            flag,
            val,
            cwd=repo,
        )
        assert r.returncode == 1, flag
        assert "belong to --command fabrik-task" in r.stdout


# ---------------------------------------------------------------- the v2 close (row 3, row 6)

_FB = "confusion: none · waste: none · change: none · filed: none — surfaces exercised: the lane"


def _rows(run_dir: Path) -> list[dict]:
    p = run_dir.parent / "command-feedback.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _edit_commit(repo: Path, rel: str, text: str) -> str:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    _git(repo, "add", "--", rel)
    _git(repo, "commit", "-qm", f"edit {rel}")
    return _git(repo, "rev-parse", "HEAD")


def _design(run_dir: Path, repo: Path, approach: str, mirror: str = "none") -> None:
    d = repo.parent / "design.md"
    d.write_text(
        f"PROBLEM: x\nAPPROACH: {approach}\nDECISION: reversible\nMIRROR: {mirror}\n"
        "OUT: none\nTERMINAL: green\n\n## Behaviours\n- one — `tests/test_x.py::test_one`\n",
        encoding="utf-8",
    )
    r = _cr(run_dir, "step", "--phase", "2", "--title", "design", "--design", str(d), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr


def _close(run_dir: Path, repo: Path, verb: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return _cr(run_dir, verb, "--command", "fabrik-task", *extra, "--feedback", _FB, cwd=repo)


def _started_v2(run_dir: Path, tmp_path: Path, *extra: str) -> Path:
    repo = _repo(tmp_path, lane=2)
    r = _cr(run_dir, *_start("--file", "src/a.py", "--declare", _V2, *extra), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    return repo


_TESTS_NOTE = "[command_run] NOTE — fabrik-task: "


def test_v2_design_refuses_a_declared_path_it_does_not_name(run_dir: Path, tmp_path: Path) -> None:
    """kaizen 01M4RNGC0H row 1791764963: a declared `--file` the design note never backticks is
    refused AT `--design`, before anything is stored, so the note is fixed before the build — not
    amended (and counted) after it, as the close's refusal forces."""
    repo = _started_v2(run_dir, tmp_path, "--file", "src/b.py")
    d = repo.parent / "design.md"
    d.write_text(
        "PROBLEM: x\nAPPROACH: edit `src/a.py`\nDECISION: reversible\nMIRROR: none\n"
        "OUT: none\nTERMINAL: green\n",
        encoding="utf-8",
    )
    r = _cr(run_dir, "step", "--phase", "2", "--title", "design", "--design", str(d), cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "not named in the design note's APPROACH or MIRROR: src/b.py" in r.stdout
    assert "design" not in _rec(run_dir)
    _design(run_dir, repo, "edit `src/a.py` and `src/b.py`")
    assert "design" in _rec(run_dir)


def test_v2_start_lists_the_tests_that_name_a_declared_script(
    run_dir: Path, tmp_path: Path
) -> None:
    """kaizen 01M4RNGC0H row 1791827964: `start` names the tracked tests that load a declared
    script, so the grader path is declared the first time; a near-miss name lists nothing."""
    repo = _repo(tmp_path, lane=2)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_alpha.py").write_text("from a import x\n", encoding="utf-8")
    (repo / "tests" / "test_near.py").write_text("# ab.py\nimport ab\n", encoding="utf-8")
    _git(repo, "add", "tests")
    _git(repo, "commit", "-qm", "tests")
    r = _cr(
        run_dir, *_start("--file", "src/a.py", "--file", "src/b.py", "--declare", _V2), cwd=repo
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _TESTS_NOTE + "1 test file(s) name src/a.py: tests/test_alpha.py" in r.stderr
    assert "name src/b.py" not in r.stderr, r.stderr
    # the same advice once the design is stored — the step where a grader can still be named
    d = repo.parent / "design.md"
    d.write_text("APPROACH: edit `src/a.py` and `src/b.py`\nMIRROR: none\n", encoding="utf-8")
    r = _cr(run_dir, "step", "--phase", "2", "--title", "design", "--design", str(d), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _TESTS_NOTE + "1 test file(s) name src/a.py: tests/test_alpha.py" in r.stderr


def test_v2_the_tests_note_anchors_a_declared_path(run_dir: Path, tmp_path: Path) -> None:
    """D-796 review A-S1: the repo-path match is anchored like the basename match — a test that
    names `xsrc/c.py`, `src/c.py.bak` or `src/c.py-old` does not name `src/c.py` (review A-S1,
    A-S3), while a sentence ending `src/c.py.` still does. `c.py` is made non-unique, so only the path
    pattern can match here."""
    repo = _repo(tmp_path, lane=2)
    (repo / "lib").mkdir()
    (repo / "lib" / "c.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_x.py").write_text(
        "# xsrc/c.py\n# src/c.py.bak\n# src/c.py-old\n", encoding="utf-8"
    )
    (repo / "tests" / "test_y.py").write_text("# see src/c.py.\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "c")
    r = _cr(run_dir, *_start("--file", "src/c.py", "--declare", _V2), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _TESTS_NOTE + "1 test file(s) name src/c.py: tests/test_y.py" in r.stderr


def test_v2_done_accepts_an_undeclared_review_receipt(run_dir: Path, tmp_path: Path) -> None:
    """A run's own nested-review receipt is its evidence, like a Doc Sync ledger: committing
    `docs/development/reviews/<x>-review.md` without naming it in APPROACH/MIRROR (or passing it
    as `--review`) no longer refuses `done` (kaizen 01M4RP9QCR). A `.py` hidden there still does."""
    repo = _started_v2(run_dir, tmp_path)
    _design(run_dir, repo, "edit `src/a.py`")
    a = _edit_commit(repo, "src/a.py", "x = 2\n")
    b = _edit_commit(repo, "docs/development/reviews/2026-10-13-x-review.md", "# Review\n")
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", a, b)
    assert r.returncode == 0, r.stdout + r.stderr


def _commit_with_msg(repo: Path, rel: str, msg: Path, subject: str) -> str:
    msg.write_text(f"{subject}\n\nbody\n", encoding="utf-8")
    (repo / rel).write_text(subject + "\n", encoding="utf-8")
    _git(repo, "add", "--", rel)
    _git(repo, "commit", "-q", "-F", str(msg))
    return _git(repo, "rev-parse", "HEAD")


def test_capture_appends_the_sha_found_by_subject_never_head(run_dir: Path, tmp_path: Path) -> None:
    """Phase 5's capture as one verb (kaizen 01M55GGMS5): each call appends the sha whose subject is
    the message file's first line — so a sibling's commit landing on top (HEAD moved) is never
    captured — and the file reads back as `done --commit $(cat …)` wants it."""
    repo = _repo(tmp_path, lane=None)
    cap = tmp_path / "durable" / "commit.sha"
    m1, m2 = tmp_path / "m1.txt", tmp_path / "m2.txt"
    a = _commit_with_msg(repo, "src/a.py", m1, "fix: the first change")
    _commit_with_msg(repo, "src/b.py", tmp_path / "other.txt", "chore: a sibling lands on top")
    r = _cr(run_dir, "capture", "--msg", str(m1), "--out", str(cap), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == a
    b = _commit_with_msg(repo, "src/c.py", m2, "fix: the second change")
    r = _cr(run_dir, "capture", "--msg", str(m2), "--out", str(cap), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert cap.read_text(encoding="utf-8").split() == [a, b]


def test_capture_refuses_with_rc_1_and_appends_nothing(run_dir: Path, tmp_path: Path) -> None:
    """A subject no commit carries, a missing message file and a blank subject each exit 1 —
    never the CLI's fail-soft 0 — and leave the capture file untouched."""
    repo = _repo(tmp_path, lane=None)
    cap = tmp_path / "commit.sha"
    unseen = tmp_path / "unseen.txt"
    unseen.write_text("fix: never committed\n", encoding="utf-8")
    empty = tmp_path / "empty.txt"
    # an all-blank message: git drops leading blank lines, so `\\nbody` is the subject "body" and
    # would refuse for a different reason (review B-haiku NEW-1)
    empty.write_text("  \n\n \n", encoding="utf-8")
    cases = (
        (unseen, "no commit has"),
        (tmp_path / "missing.txt", "cannot read"),
        (empty, "empty subject"),
    )
    for msg, why in cases:  # each refusal for ITS reason, not merely refused
        r = _cr(run_dir, "capture", "--msg", str(msg), "--out", str(cap), cwd=repo)
        assert r.returncode == 1, (msg, r.stdout + r.stderr)
        assert "REFUSED — capture" in r.stderr and why in r.stderr, (msg, r.stderr)
    assert not cap.exists()


def test_capture_exits_1_never_the_fail_soft_0_on_a_bad_message_or_no_git(
    run_dir: Path, tmp_path: Path
) -> None:
    """A non-UTF-8 message file and a `git` missing from PATH both raised out of `_capture_commit`
    into main()'s catch-all, which returns 0 with no sha (review A-sonnet): each is a refusal."""
    repo = _repo(tmp_path, lane=None)
    cap = tmp_path / "commit.sha"
    bad = tmp_path / "bad.txt"
    bad.write_bytes(b"\xff\xfe not utf-8\n")
    r = _cr(run_dir, "capture", "--msg", str(bad), "--out", str(cap), cwd=repo)
    assert r.returncode == 1 and "REFUSED — capture" in r.stderr, r.stdout + r.stderr
    good = tmp_path / "good.txt"
    _commit_with_msg(repo, "src/a.py", good, "fix: a real subject")
    nogit = tmp_path / "empty-bin"
    nogit.mkdir()
    r = _cr(
        run_dir,
        "capture",
        "--msg",
        str(good),
        "--out",
        str(cap),
        cwd=repo,
        extra_env={"PATH": str(nogit)},
    )
    assert r.returncode == 1 and "git log failed" in r.stderr, r.stdout + r.stderr
    assert not cap.exists()


def test_capture_skips_leading_blank_lines_as_git_does(run_dir: Path, tmp_path: Path) -> None:
    """git drops a message's leading blank lines, so its subject is the first non-blank paragraph;
    capture read the blank lines as an empty subject (review round 2)."""
    repo = _repo(tmp_path, lane=None)
    msg = tmp_path / "lead.txt"
    msg.write_text("  \n\nfix: after blank lines\n\nbody\n", encoding="utf-8")
    (repo / "src" / "a.py").write_text("x = 6\n", encoding="utf-8")
    _git(repo, "add", "--", "src/a.py")
    _git(repo, "commit", "-q", "-F", str(msg))
    sha = _git(repo, "rev-parse", "HEAD")
    cap = tmp_path / "commit.sha"
    r = _cr(run_dir, "capture", "--msg", str(msg), "--out", str(cap), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert cap.read_text(encoding="utf-8").split() == [sha]


def test_capture_ends_the_subject_at_a_whitespace_only_line(run_dir: Path, tmp_path: Path) -> None:
    """git ends the subject paragraph at a line holding only spaces; capture joined the body onto the
    subject there and refused the commit (review A-haiku N-1)."""
    repo = _repo(tmp_path, lane=None)
    msg = tmp_path / "ws.txt"
    msg.write_text("fix: the subject\n   \nthe body\n", encoding="utf-8")
    (repo / "src" / "a.py").write_text("x = 8\n", encoding="utf-8")
    _git(repo, "add", "--", "src/a.py")
    _git(repo, "commit", "-q", "-F", str(msg))
    sha = _git(repo, "rev-parse", "HEAD")
    cap = tmp_path / "commit.sha"
    r = _cr(run_dir, "capture", "--msg", str(msg), "--out", str(cap), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert cap.read_text(encoding="utf-8").split() == [sha]


def test_capture_finds_a_subject_git_stored_with_leading_spaces(
    run_dir: Path, tmp_path: Path
) -> None:
    """git keeps a subject's leading spaces in `%s`; capture strips its own side, so an exact
    comparison could never match such a commit (review A-haiku)."""
    repo = _repo(tmp_path, lane=None)
    msg = tmp_path / "padded.txt"
    msg.write_text("  fix:  a padded   subject  \n", encoding="utf-8")  # inner runs too
    (repo / "src" / "a.py").write_text("x = 7\n", encoding="utf-8")
    _git(repo, "add", "--", "src/a.py")
    _git(repo, "commit", "-q", "-F", str(msg))
    sha = _git(repo, "rev-parse", "HEAD")
    cap = tmp_path / "commit.sha"
    r = _cr(run_dir, "capture", "--msg", str(msg), "--out", str(cap), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert cap.read_text(encoding="utf-8").split() == [sha]


def test_capture_reads_a_wrapped_subject_as_git_does(run_dir: Path, tmp_path: Path) -> None:
    """git's `%s` joins the first paragraph's lines with spaces; a first-line-only read refused a
    legitimate commit whose subject wraps (review A-sonnet)."""
    repo = _repo(tmp_path, lane=None)
    msg = tmp_path / "wrapped.txt"
    msg.write_text("fix: a subject that\nwraps onto a second line\n\nbody\n", encoding="utf-8")
    (repo / "src" / "a.py").write_text("x = 9\n", encoding="utf-8")
    _git(repo, "add", "--", "src/a.py")
    _git(repo, "commit", "-q", "-F", str(msg))
    sha = _git(repo, "rev-parse", "HEAD")
    cap = tmp_path / "commit.sha"
    r = _cr(run_dir, "capture", "--msg", str(msg), "--out", str(cap), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert cap.read_text(encoding="utf-8").split() == [sha]


def test_capture_refuses_when_the_newest_match_only_quotes_the_subject(
    run_dir: Path, tmp_path: Path
) -> None:
    """`--grep` reads whole messages, so a NEWER commit quoting the subject in its body is the match
    found; its own subject differs, and capture must refuse rather than append that sha (review
    B-sonnet: no test reached the subject-equality check)."""
    repo = _repo(tmp_path, lane=None)
    msg = tmp_path / "m.txt"
    _commit_with_msg(repo, "src/a.py", msg, "fix: the real change")
    quoting = tmp_path / "q.txt"
    quoting.write_text("chore: a later one\n\nfollows fix: the real change\n", encoding="utf-8")
    (repo / "src" / "b.py").write_text("x = 3\n", encoding="utf-8")
    _git(repo, "add", "--", "src/b.py")
    _git(repo, "commit", "-q", "-F", str(quoting))
    cap = tmp_path / "commit.sha"
    r = _cr(run_dir, "capture", "--msg", str(msg), "--out", str(cap), cwd=repo)
    assert r.returncode == 1 and "REFUSED — capture" in r.stderr, r.stdout + r.stderr
    assert not cap.exists()


def test_v2_done_drops_empty_comma_pieces_and_refuses_a_bare_comma(
    run_dir: Path, tmp_path: Path
) -> None:
    """`--commit a,` closes as `--commit a`; `--commit ,` has nothing left and is refused as an
    empty value, the same as `--commit ""` (review B-sonnet: empty pieces were untested)."""
    repo = _started_v2(run_dir, tmp_path)
    _design(run_dir, repo, "edit `src/a.py`")
    a = _edit_commit(repo, "src/a.py", "x = 2\n")
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", ",")
    assert r.returncode == 1 and "--commit is empty" in r.stdout + r.stderr, r.stdout + r.stderr
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", f"{a},")
    assert r.returncode == 0, r.stdout + r.stderr


def test_v2_done_takes_a_comma_list_of_commits_as_the_space_form(
    run_dir: Path, tmp_path: Path
) -> None:
    """`--commit a,b` closes exactly as `--commit a b`: a sha never holds a comma, so the split is
    unambiguous; before it, the comma list was refused as "not this run's commit", which reads
    like a wrong sha (kaizen 01M55GGMS5, feedback row 1792251777)."""
    repo = _started_v2(run_dir, tmp_path)
    _design(run_dir, repo, "edit `src/a.py`")
    a = _edit_commit(repo, "src/a.py", "x = 2\n")
    b = _edit_commit(repo, "docs/development/reviews/2026-10-13-x-review.md", "# Review\n")
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", f"{a},{b}")
    assert r.returncode == 0, r.stdout + r.stderr


def test_v2_done_still_refuses_a_source_file_under_the_reviews_dir(
    run_dir: Path, tmp_path: Path
) -> None:
    """The receipt exemption is `.md` only: an undeclared `.py` under the reviews dir is a
    hiding place, never evidence (design critiques, Opus + Fable)."""
    repo = _started_v2(run_dir, tmp_path)
    _design(run_dir, repo, "edit `src/a.py`")
    a = _edit_commit(repo, "src/a.py", "x = 2\n")
    b = _edit_commit(repo, "docs/development/reviews/helper.py", "x = 1\n")
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", a, b)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "docs/development/reviews/helper.py" in r.stdout


def test_v2_done_refuses_an_undeclared_path_until_it_is_amended(
    run_dir: Path, tmp_path: Path
) -> None:
    """Row 3 (V4, D3.3). Two commits: the second touches `src/b.py`, which the design never
    named — `done --commit A B` is refused naming it; one `--design-amend` later it closes, and
    the row counts the amendment and the lines added."""
    repo = _started_v2(run_dir, tmp_path)
    _design(run_dir, repo, "edit `src/a.py`")
    a = _edit_commit(repo, "src/a.py", "x = 2\n")
    b = _edit_commit(repo, "src/b.py", "x = 2\ny = 3\n")
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", a, b)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "not named in the design note's APPROACH or MIRROR: src/b.py" in r.stdout
    assert _rec(run_dir)["state"] == "running"
    r = _cr(run_dir, "step", "--phase", "2", "--design-amend", "src/b.py", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", a, b)
    assert r.returncode == 0, r.stdout + r.stderr
    row = _rows(run_dir)[-1]
    assert (row["design_amends"], row["loc_added"], row["oversized_mini"]) == ("1", "3", "0")
    assert row["over_appetite"] == "no"


def test_v2_done_treats_the_work_store_as_a_ledger_not_an_undeclared_path(
    run_dir: Path, tmp_path: Path
) -> None:
    """W-b43ce8bc (lane v2's first run, D-506): a work item a verb changed is committed WITH the
    task (CLAUDE.md § Work items), and the close refused `.fabrik/work/W-*.json` as a path the
    design never named — `task_lane` already excludes the store from its own measurement."""
    repo = _started_v2(run_dir, tmp_path)
    _design(run_dir, repo, "edit `src/a.py`")
    a = _edit_commit(repo, "src/a.py", "x = 2\n")
    w = _edit_commit(repo, ".fabrik/work/W-1a2b3c4d.json", "{}\n")
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", a, w)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rows(run_dir)[-1]["oversized_mini"] == "0", _rows(run_dir)[-1]


def test_v2_a_contract_hit_at_close_owes_a_receipt_and_blocked_does_not(
    run_dir: Path, tmp_path: Path
) -> None:
    """Row 3 (V3, D1; W-0a89f069). A commit touching a contract path, declared
    `consumers=internal` and named in the design, is a close-time contract hit: `done` is refused
    until `--review` names a full-review receipt; `blocked` closes without one and records the
    upgrade."""
    repo = _started_v2(run_dir, tmp_path)
    _design(run_dir, repo, "edit `src/a.py` and `api/openapi.yaml`")
    c = _edit_commit(repo, "api/openapi.yaml", "openapi: 3.1.1\n")
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", c)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "UPGRADE: contract — api/openapi.yaml" in r.stdout
    assert "done needs --review" in r.stdout
    r = _close(run_dir, repo, "blocked", "--reason", "missing infra", "--commit", c)
    assert r.returncode == 0, r.stdout + r.stderr
    row = _rows(run_dir)[-1]
    assert (row["upgrade"], row["upgrades"]) == ("contract", "contract")


def test_v2_a_valid_full_review_receipt_buys_the_contract_close(
    run_dir: Path, tmp_path: Path
) -> None:
    """Row 3. The same contract hit closes `done` once `--review` names a CONVERGED
    `/fabrik-review` receipt whose surface contains the commit; an unfinished receipt is refused
    with the receipt check's reason."""
    import sys

    from tests.test_review_receipt import _complete
    from tests.test_task_lane_receipt import RECEIPT_SCRIPT, REL

    repo = _started_v2(run_dir, tmp_path)
    _design(run_dir, repo, "edit `src/a.py` and `api/openapi.yaml`")
    base = _git(repo, "rev-parse", "HEAD")
    c = _edit_commit(repo, "api/openapi.yaml", "openapi: 3.1.1\n")
    out = repo / REL
    made = subprocess.run(
        [
            sys.executable,
            str(RECEIPT_SCRIPT),
            "--init",
            "--project-root",
            str(repo),
            "--out",
            str(out),
            "--changed",
            "api/openapi.yaml",
            "--range",
            f"{base}..{c}",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert made.returncode == 0, made.stderr
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", c, "--review", REL)
    assert r.returncode == 1, "an unfinished receipt must not buy the close"
    assert "REFUSED — fabrik-task: --review" in r.stdout
    out.write_text(_complete(out.read_text(encoding="utf-8")), encoding="utf-8")
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", c, "--review", REL)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rows(run_dir)[-1]["upgrade"] == "contract"


def test_v2_a_ledger_commit_after_the_reviewed_tip_closes(run_dir: Path, tmp_path: Path) -> None:
    """W-0b900e92 (site-provisioner 01M4F5HTPS): a receipt over the code commit, followed by the
    CHANGELOG commit made after the review, closes `done` with both listed in the order made; a
    later `.py` under an excluded prefix row (`.fabrik/work/`) is not a ledger and refuses."""
    import sys

    from tests.test_review_receipt import _complete
    from tests.test_task_lane_receipt import RECEIPT_SCRIPT, REL

    repo = _started_v2(run_dir, tmp_path)
    _design(run_dir, repo, "edit `src/a.py` and `api/openapi.yaml`")
    base = _git(repo, "rev-parse", "HEAD")
    c = _edit_commit(repo, "api/openapi.yaml", "openapi: 3.1.1\n")
    out = repo / REL
    made = subprocess.run(
        [
            sys.executable,
            str(RECEIPT_SCRIPT),
            "--init",
            "--project-root",
            str(repo),
            "--out",
            str(out),
            "--changed",
            "api/openapi.yaml",
            "--range",
            f"{base}..{c}",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert made.returncode == 0, made.stderr
    out.write_text(_complete(out.read_text(encoding="utf-8")), encoding="utf-8")
    ledger = _edit_commit(repo, "CHANGELOG.md", "## [Unreleased]\n")
    late = _edit_commit(repo, ".fabrik/work/x.py", "x = 1\n")
    r = _close(
        run_dir, repo, "done", "--evidence", "g", "--commit", c, ledger, late, "--review", REL
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "REFUSED — fabrik-task: --review (d)" in r.stdout and ".fabrik/work/x.py" in r.stdout
    # a contract file is `.json` under the excluded `.fabrik/work/` row, yet never a ledger (review B1)
    schema = _edit_commit(repo, ".fabrik/work/x.schema.json", "{}\n")
    r = _close(
        run_dir, repo, "done", "--evidence", "g", "--commit", c, ledger, schema, "--review", REL
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "--review (d)" in r.stdout and ".fabrik/work/x.schema.json" in r.stdout
    r = _close(run_dir, repo, "done", "--evidence", "g", "--commit", c, ledger, "--review", REL)
    assert r.returncode == 0, r.stdout + r.stderr


def test_v2_the_row_carries_from_downgrade_and_the_evidence_upgrade_token(
    run_dir: Path, tmp_path: Path
) -> None:
    """Row 6. `--from-downgrade` reaches the close row; an evidence `UPGRADE:` token keeps its
    single-token `upgrade` field."""
    repo = _started_v2(run_dir, tmp_path, "--from-downgrade", "LR-0a1b2c3d")
    _design(run_dir, repo, "edit `src/a.py`")
    a = _edit_commit(repo, "src/a.py", "x = 2\n")
    r = _close(run_dir, repo, "done", "--evidence", "UPGRADE: heavy — green", "--commit", a)
    assert r.returncode == 0, r.stdout + r.stderr
    row = _rows(run_dir)[-1]
    assert (row["from_downgrade"], row["upgrade"]) == ("LR-0a1b2c3d", "heavy")
    assert "upgrades" not in row


def test_review_and_several_commits_are_refused_on_a_v1_run(run_dir: Path, tmp_path: Path) -> None:
    """The unstamped close stays today's: one commit, no receipt."""
    repo = _repo(tmp_path, lane=1)
    r = _cr(run_dir, *_start("--file", "src/a.py", "--declare", _V2), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    a = _edit_commit(repo, "src/a.py", "x = 2\n")
    b = _edit_commit(repo, "src/a.py", "x = 3\n")
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", a, b)
    assert r.returncode == 1
    assert "this run is lane v1 — pass ONE --commit" in r.stdout
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", b, "--review", "x.md")
    assert r.returncode == 1
    assert "--review needs a lane v2 run" in r.stdout


# ---------------------------------------------------------------- appetite (row 5) and row fields (row 6)


def _age(run_dir: Path, minutes: int, *, mark: bool = False, sid: str = "s1") -> None:
    """Move the record's clock back: the run's start, or the open phase mark's start."""
    import time as _t

    p = run_dir / f"{sid}.json"
    rec = json.loads(p.read_text(encoding="utf-8"))
    when = _t.time() - minutes * 60
    if mark:
        rec["phase_marks"][-1]["started"] = when
    else:
        rec["started_epoch"] = when
    p.write_text(json.dumps(rec), encoding="utf-8")


def test_v2_task_line_shows_elapsed_over_appetite_and_the_order_past_2x(
    run_dir: Path, tmp_path: Path
) -> None:
    """Row 5 (V6, D4). A task started `--appetite 60`: at 61 minutes `line` shows the elapsed
    segment with no order; at 121 it carries the UPGRADE order, and the close records
    `over_appetite: yes` and the `appetite` upgrade."""
    repo = _started_v2(run_dir, tmp_path, "--appetite", "60")
    _design(run_dir, repo, "edit `src/a.py`")
    _age(run_dir, 61)
    line = _cr(run_dir, "line", cwd=repo).stdout
    assert " · elapsed 61/60" in line and "past 2×" not in line
    _age(run_dir, 121)
    line = _cr(run_dir, "line", cwd=repo).stdout
    assert " · elapsed 121/60 ⚠️ past 2× — UPGRADE: appetite" in line
    a = _edit_commit(repo, "src/a.py", "x = 2\n")
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", a)
    assert r.returncode == 0, r.stdout + r.stderr
    row = _rows(run_dir)[-1]
    assert (row["over_appetite"], row["upgrade"]) == ("yes", "appetite")


def test_v2_a_plan_phase_appetite_marks_and_counts_the_overrun(
    run_dir: Path, tmp_path: Path
) -> None:
    """Row 5 (V10, D11). An execute-plan phase entered `step --appetite 30`: at 61 minutes `line`
    prints the re-plan order; the next phase ends the mark; the close counts one mark and one
    overrun."""
    repo = _repo(tmp_path, lane=2)
    r = _cr(run_dir, "start", "--command", "fabrik-execute-plan", "--phases", "3", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    r = _cr(run_dir, "step", "--phase", "1", "--title", "one", "--appetite", "30", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    _age(run_dir, 61, mark=True)
    line = _cr(run_dir, "line", cwd=repo).stdout
    assert "(one) · elapsed 61/30 ⚠️ past 2× — stop and re-plan the rest of THIS phase" in line
    r = _cr(run_dir, "step", "--phase", "2", "--title", "two", cwd=repo)
    assert "elapsed" not in r.stdout, "the next phase ends the mark"
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-execute-plan",
        "--evidence",
        "x",
        "--feedback",
        _FB,
        cwd=repo,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    row = _rows(run_dir)[-1]
    assert (row["phase_marks"], row["over_appetite_phases"]) == ("1", "1")


def test_v1_step_appetite_is_ignored_and_the_row_keeps_its_shape(
    run_dir: Path, tmp_path: Path
) -> None:
    """Row 1 (a v1 pin) for D11: lane v1, so `--appetite` is noted and nothing is marked."""
    repo = _repo(tmp_path, lane=1)
    _cr(run_dir, "start", "--command", "fabrik-execute-plan", "--phases", "3", cwd=repo)
    r = _cr(run_dir, "step", "--phase", "1", "--title", "one", "--appetite", "30", cwd=repo)
    assert r.returncode == 0
    assert "--appetite ignored — this repo runs lane v1" in r.stderr
    _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-execute-plan",
        "--evidence",
        "x",
        "--feedback",
        _FB,
        cwd=repo,
    )
    row = _rows(run_dir)[-1]
    assert "phase_marks" not in row and "parent" not in row


def test_v2_a_nested_review_row_names_its_parent_and_a_small_spec_its_size(
    run_dir: Path, tmp_path: Path
) -> None:
    """Row 6. A `/fabrik-review` nested under a running `/fabrik-task` writes `parent:
    fabrik-task`; a `/fabrik-spec` close on a spec carrying `Size: small` writes `size: small`."""
    repo = _started_v2(run_dir, tmp_path)
    r = _cr(run_dir, "start", "--command", "fabrik-review", "--phases", "3", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    _cr(run_dir, "round", "--findings", "0", "--confirmed", "0", cwd=repo)
    r = _cr(
        run_dir,
        "blocked",
        "--command",
        "fabrik-review",
        "--reason",
        "missing infra",
        "--feedback",
        _FB,
        cwd=repo,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rows(run_dir)[-1]["parent"] == "fabrik-task"

    spec = repo / "docs" / "superpowers" / "specs" / "2026-10-02-x-design.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        "# X\n\n**Status:** DRAFT\nSize: small (≈200 lines, 3 files)\n\n## Goal\n", encoding="utf-8"
    )
    r = _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-spec",
        "--phases",
        "7",
        "--surface",
        "docs/superpowers/specs/2026-10-02-x-design.md",
        cwd=repo,
        sid="s2",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-spec",
        "--evidence",
        "x",
        "--feedback",
        _FB,
        cwd=repo,
        sid="s2",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rows(run_dir)[-1]["size"] == "small"


# ---------------------------------------------------------------- the nested review (row 4) and --surface


def _review_rounds(run_dir: Path, repo: Path) -> str:
    r = _cr(run_dir, "start", "--command", "fabrik-review", "--phases", "3", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    r = _cr(run_dir, "round", "--findings", "5", "--confirmed", "5", "--own-fix", "0", cwd=repo)
    assert "SCOPE GROWTH" not in r.stdout, "round 1 is the full pass"
    r = _cr(run_dir, "round", "--findings", "2", "--confirmed", "2", "--own-fix", "2", cwd=repo)
    return r.stdout


def test_v2_a_review_nested_under_a_task_stops_at_its_first_own_fix_round(
    run_dir: Path, tmp_path: Path
) -> None:
    """Row 4 (V8, D8). Under a running `/fabrik-task` an own-fix-only round 2 prints the in-lane
    stop; the same two rounds with no task parent print nothing (the ordinary window needs 3)."""
    repo = _started_v2(run_dir, tmp_path)
    out = _review_rounds(run_dir, repo)
    assert "SCOPE GROWTH (in-lane) — round 2 confirmed ONLY defects inside" in out
    assert "mostly" not in out.split("SCOPE GROWTH (in-lane)")[1].split("\n")[0]
    # `round` prints the in-lane message whole (its text is pinned in test_command_run.py) and
    # nothing but print's newline follows it
    assert out.rstrip("\n").endswith(
        "\n⚠️  SCOPE GROWTH (in-lane) — round 2 confirmed ONLY defects inside text this review "
        "itself added (confirmed/own-fix: 2/2) under a running /fabrik-task.\n"
        "    Exit (term-edit / term-coverage § Scope-growth stop, lane variant): STOP the hunt — "
        "fix the window's open defects, route the remaining own-fix work to /fabrik-spec or a "
        "backlog row with a named destination, re-verify the fixed set alone, and close on a "
        "`confirmed: 0 · fixed: 0 · unexecuted: 0` round (D-355); the receipt carries "
        "`**Lane:** fabrik-task`.\n"
        "    (Advisory only — nothing is blocked.)"
    ), out

    other = tmp_path / "other-state" / "command-runs"
    other.mkdir(parents=True)
    out = _review_rounds(other, repo)
    assert "SCOPE GROWTH" not in out


def test_v1_a_nested_review_keeps_the_ordinary_window(run_dir: Path, tmp_path: Path) -> None:
    """Row 1 (a v1 pin) for D8."""
    repo = _repo(tmp_path, lane=1)
    r = _cr(run_dir, *_start("--file", "src/a.py", "--declare", _V2), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SCOPE GROWTH" not in _review_rounds(run_dir, repo)


@pytest.mark.parametrize("command", ["fabrik-spec-review", "fabrik-plan-review"])
def test_v2_spec_and_plan_review_need_a_surface(
    run_dir: Path, tmp_path: Path, command: str
) -> None:
    """Row 6 (W-25318990). At v2 the start without `--surface` is refused naming the flag; with
    it, it opens; at v1 the bare start opens as before."""
    repo = _repo(tmp_path, lane=2)
    r = _cr(run_dir, "start", "--command", command, "--phases", "3", cwd=repo)
    assert r.returncode == 1
    assert f"REFUSED — {command}: --surface <the spec or plan path> is required" in r.stdout
    r = _cr(run_dir, "start", "--command", command, "--phases", "3", "--surface", "x.md", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    v1 = _repo(tmp_path / "v1", lane=1)
    other = tmp_path / "v1-state" / "command-runs"
    other.mkdir(parents=True)
    r = _cr(other, "start", "--command", command, "--phases", "3", cwd=v1)
    assert r.returncode == 0, r.stdout + r.stderr


def test_v2_a_spec_downgrade_handoff_names_its_refusal(run_dir: Path, tmp_path: Path) -> None:
    """D9 / T06's join: a `/fabrik-spec` handoff whose reason opens `DOWNGRADE: <refusal id>`
    writes `from_downgrade` on its row; any other reason writes nothing."""
    repo = _repo(tmp_path, lane=2)
    seed = repo / "docs" / "seed.md"
    seed.parent.mkdir(parents=True, exist_ok=True)
    seed.write_text(
        "# seed\n\n## RESUME\n- /fabrik-task --from-downgrade LR-0a1b2c3d\n", encoding="utf-8"
    )
    for sid, reason, want in (
        ("s1", "DOWNGRADE: LR-0a1b2c3d — one reversible decision", "LR-0a1b2c3d"),
        ("s2", "the brief needs a design after all", None),
    ):
        r = _cr(run_dir, "start", "--command", "fabrik-spec", "--phases", "7", cwd=repo, sid=sid)
        assert r.returncode == 0, r.stdout + r.stderr
        r = _cr(
            run_dir,
            "handoff",
            "--command",
            "fabrik-spec",
            "--resume",
            "docs/seed.md",
            "--reason",
            reason,
            "--feedback",
            _FB,
            cwd=repo,
            sid=sid,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        assert _rows(run_dir)[-1].get("from_downgrade") == want


def test_v2_the_in_lane_stop_needs_an_own_fix_only_round_and_a_review(
    run_dir: Path, tmp_path: Path
) -> None:
    """T04-O5/O6: a round that is only MOSTLY own-fix (2 of 3) does not take the in-lane stop,
    and a non-review command nested under the task keeps the ordinary window."""
    repo = _started_v2(run_dir, tmp_path)
    r = _cr(run_dir, "start", "--command", "fabrik-review", "--phases", "3", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    _cr(run_dir, "round", "--findings", "5", "--confirmed", "5", "--own-fix", "0", cwd=repo)
    r = _cr(run_dir, "round", "--findings", "3", "--confirmed", "3", "--own-fix", "2", cwd=repo)
    assert "SCOPE GROWTH (in-lane)" not in r.stdout

    other = tmp_path / "s2" / "command-runs"
    other.mkdir(parents=True)
    repo2 = _repo(tmp_path / "two", lane=2)
    r = _cr(other, *_start("--file", "src/a.py", "--declare", _V2), cwd=repo2)
    assert r.returncode == 0, r.stdout + r.stderr
    r = _cr(other, "start", "--command", "fabrik-doc-converge", "--phases", "3", cwd=repo2)
    assert r.returncode == 0, r.stdout + r.stderr
    _cr(other, "round", "--findings", "5", "--confirmed", "5", "--own-fix", "0", cwd=repo2)
    r = _cr(other, "round", "--findings", "2", "--confirmed", "2", "--own-fix", "2", cwd=repo2)
    assert "SCOPE GROWTH (in-lane)" not in r.stdout


def test_the_documented_multi_commit_close_parses_as_separate_shas(tmp_path: Path) -> None:
    """T07-S3, routed to T08 (where the space-separated parser lives): the command text's capture
    file APPENDS each commit and is expanded UNQUOTED, so a two-commit run reaches `--commit` as two
    arguments — executed through bash and the real parser, never matched as prose."""
    import importlib.util
    import re as _re
    import sys as _sys

    root = Path(__file__).resolve().parents[1]
    src = (root / "commands/_sources/fabrik-task.md").read_text(encoding="utf-8")
    assert 'echo "$sha" >> <durable>/commit.sha' in src, "the capture must append"
    m = _re.search(r"--commit (\$\(cat <durable>[^)]*\))", src)
    assert m, "the done line must expand the capture file UNQUOTED"
    cap = tmp_path / "commit.sha"
    cap.write_text("aaaa111\nbbbb222\n", encoding="utf-8")
    expr = m.group(1).replace(m.group(1)[6:-1], str(cap))
    words = subprocess.run(
        ["bash", "-c", f'printf "%s\\n" --commit {expr}'],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    ).stdout.split()
    spec = importlib.util.spec_from_file_location("_cr_parse", root / "scripts/command_run.py")
    cr = importlib.util.module_from_spec(spec)
    _sys.modules["_cr_parse"] = cr
    spec.loader.exec_module(cr)
    args = cr._build_parser().parse_args(
        ["done", "--command", "fabrik-task", "--evidence", "x", *words]
    )
    assert args.commit == ["aaaa111", "bbbb222"]


def test_v2_a_failed_measurement_refuses_done_and_lets_blocked_close(
    run_dir: Path, tmp_path: Path
) -> None:
    """Whole-plan review D-O2/A-O2/B-O3: on a gate-2 record a measurement that cannot run (here a
    corrupt declared appetite) must not accept `done` — it would admit an unreviewed contract hit;
    `blocked` still closes, and its row still reads as a v2 close."""
    repo = _started_v2(run_dir, tmp_path)
    _design(run_dir, repo, "edit `src/a.py`")
    a = _edit_commit(repo, "src/a.py", "x = 2\n")
    p = run_dir / "s1.json"
    rec = json.loads(p.read_text(encoding="utf-8"))
    rec["declared"]["appetite"] = "not-a-number"
    p.write_text(json.dumps(rec), encoding="utf-8")
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", a)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "the lane v2 close could not measure the run (ValueError)" in r.stdout
    assert _rec(run_dir)["state"] == "running"
    r = _close(run_dir, repo, "blocked", "--reason", "missing infra", "--commit", a)
    assert r.returncode == 0, r.stdout + r.stderr
    row = _rows(run_dir)[-1]
    assert (row["oversized_mini"], row["over_appetite"]) == ("unmeasurable=no-git", "unmeasurable")


def test_v2_from_downgrade_must_be_a_refusal_id(run_dir: Path, tmp_path: Path) -> None:
    """D7 A-O5: the report joins on this id, so a free string is refused."""
    repo = _repo(tmp_path, lane=2)
    r = _cr(
        run_dir,
        *_start("--file", "src/a.py", "--declare", _V2, "--from-downgrade", "whatever"),
        cwd=repo,
    )
    assert r.returncode == 1
    assert "is not a refusal id (LR-xxxxxxxx)" in r.stdout


def test_a_late_surface_still_sizes_the_spec_and_a_stamped_run_keeps_v2_fields(
    run_dir: Path, tmp_path: Path
) -> None:
    """D7 A-O1: `done --surface` names the spec at close and the row still carries `size`.
    D7 A-O4: a run stamped gate 2 keeps its v2 row fields after the switch is removed."""
    repo = _repo(tmp_path, lane=2)
    spec = repo / "docs" / "superpowers" / "specs" / "2026-10-02-y-design.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# Y\n\n**Status:** DRAFT\nSize: small\n\n## Goal\n", encoding="utf-8")
    r = _cr(run_dir, "start", "--command", "fabrik-spec", "--phases", "7", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    rel = "docs/superpowers/specs/2026-10-02-y-design.md"
    r = _cr(
        run_dir,
        "done",
        "--command",
        "fabrik-spec",
        "--evidence",
        "x",
        "--surface",
        rel,
        "--feedback",
        _FB,
        cwd=repo,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rows(run_dir)[-1].get("size") == "small"

    other = tmp_path / "o" / "command-runs"
    other.mkdir(parents=True)
    repo2 = _repo(tmp_path / "two", lane=2)
    r = _cr(other, *_start("--file", "src/a.py", "--declare", _V2), cwd=repo2)
    assert r.returncode == 0, r.stdout + r.stderr
    r = _cr(other, "start", "--command", "fabrik-review", "--phases", "3", cwd=repo2)
    assert r.returncode == 0, r.stdout + r.stderr
    _git(repo2, "rm", "-q", ".fabrik/lane.json")
    _git(repo2, "commit", "-qm", "switch off")
    r = _cr(
        other,
        "blocked",
        "--command",
        "fabrik-review",
        "--reason",
        "missing infra",
        "--feedback",
        _FB,
        cwd=repo2,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rows(other)[-1].get("parent") == "fabrik-task"


def test_an_absolute_review_path_is_compared_repo_relative(tmp_path: Path) -> None:
    """D7 B-O2: the `--review` path the close exempts is spelled as the committed rows spell it —
    an absolute path inside the repo is relativised; one outside is kept for the receipt check to
    refuse."""
    import importlib.util
    import sys as _sys

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("_cr_rel", root / "scripts/command_run.py")
    cr = importlib.util.module_from_spec(spec)
    _sys.modules["_cr_rel"] = cr
    spec.loader.exec_module(cr)
    repo = tmp_path / "r"
    (repo / "docs").mkdir(parents=True)
    inside = repo / "docs" / "x-review.md"
    assert cr._repo_rel(repo, str(inside)) == "docs/x-review.md"
    assert cr._repo_rel(repo, "/elsewhere/y.md") == "/elsewhere/y.md"
    assert cr._repo_rel(repo, None) is None
    link = tmp_path / "link"
    link.symlink_to(repo, target_is_directory=True)
    assert cr._repo_rel(repo, str(link / "docs" / "x-review.md")) == "docs/x-review.md"


def test_a_present_but_broken_task_lane_says_so_and_runs_v1(run_dir: Path, tmp_path: Path) -> None:
    """D7 A-S2: a task_lane.py that does not import must not downgrade silently."""
    import shutil
    import sys as _sys

    root = Path(__file__).resolve().parents[1]
    tree = tmp_path / "tree" / "scripts"
    tree.mkdir(parents=True)
    shutil.copy(root / "scripts/command_run.py", tree / "command_run.py")
    (tree / "task_lane.py").write_text("this is not python(\n", encoding="utf-8")
    repo = _repo(tmp_path, lane=2)
    r = subprocess.run(
        [
            _sys.executable,
            str(tree / "command_run.py"),
            *_start("--file", "src/a.py", "--declare", _V2),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(repo),
        env={
            "PATH": "/usr/bin:/bin",
            "COMMAND_RUN_DIR": str(run_dir),
            "HOME": str(tmp_path / "home"),
            "CLAUDE_SESSION_ID": "s1",
            "KAIZEN_EVENTS_DIR": str(tmp_path / "ev"),
        },
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "task_lane.py did not import (SyntaxError) — lane v1" in r.stderr
    assert "lane: v1" in r.stdout


def test_v1_admits_exactly_three_files(run_dir: Path, tmp_path: Path) -> None:
    """D7 A-H9: the v1 file cap's boundary — three files start, four are refused (above)."""
    repo = _repo(tmp_path, lane=1)
    r = _cr(
        run_dir, *_start(*_files("src/a.py", "src/b.py", "src/c.py"), "--declare", _V2), cwd=repo
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "lane: v1" in r.stdout.splitlines()


def test_a_stamped_task_keeps_its_v2_row_fields_after_the_switch_is_removed(
    run_dir: Path, tmp_path: Path
) -> None:
    """D7 AB-O3: the record's OWN gate-2 stamp (not only a parent's) keeps the v2 row fields."""
    repo = _started_v2(run_dir, tmp_path)
    r = _cr(run_dir, "step", "--phase", "2", "--title", "d", "--appetite", "30", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    _git(repo, "rm", "-q", ".fabrik/lane.json")
    _git(repo, "commit", "-qm", "switch off")
    r = _close(run_dir, repo, "blocked", "--reason", "missing infra")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rows(run_dir)[-1].get("phase_marks") == "1"


# ---------------------------------------------------------------- `step --terminal-amend` (kaizen 01M4DB7C7V)

_START_TERMINAL = "the change ships with its grader"


def _amend(run_dir: Path, repo: Path, text: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return _cr(run_dir, "step", "--phase", "2", *extra, "--terminal-amend", text, cwd=repo)


def test_v2_a_terminal_amend_before_the_design_restates_the_run_and_keeps_its_history(
    run_dir: Path, tmp_path: Path
) -> None:
    """The critiques narrow the work before the design lands: the terminal is restated, the pinned
    RUN: line shows it, and the history keeps the original. A same-text amend changes nothing."""
    repo = _started_v2(run_dir, tmp_path)
    r = _amend(run_dir, repo, "only the parser ships")
    assert r.returncode == 0, r.stdout + r.stderr
    rec = _rec(run_dir)
    assert rec["terminal"] == "only the parser ships"
    (h,) = rec["terminal_amends"]
    assert (h["from"], h["to"]) == (_START_TERMINAL, "only the parser ships") and h["at"], h
    line = _cr(run_dir, "line", cwd=repo)
    assert "terminal: only the parser ships" in line.stdout, line.stdout
    r = _amend(run_dir, repo, "only the parser ships")
    assert r.returncode == 0 and "NOTE" in (r.stdout + r.stderr), r.stdout + r.stderr
    assert len(_rec(run_dir)["terminal_amends"]) == 1, "a same-text amend is a no-op"
    d = repo.parent / "design.md"
    d.write_text(
        "PROBLEM: x\nAPPROACH: edit `src/a.py`\nDECISION: reversible\nMIRROR: none\nOUT: none\n"
        "TERMINAL: green\n\n## Behaviours\n- one — `tests/test_x.py::test_one`\n",
        encoding="utf-8",
    )
    r = _amend(run_dir, repo, "the parser and its grader ship", "--design", str(d))
    assert r.returncode == 0, r.stdout + r.stderr
    rec = _rec(run_dir)
    assert rec["terminal"] == "the parser and its grader ship" and "design" in rec, rec
    assert [x["to"] for x in rec["terminal_amends"]] == [
        "only the parser ships",
        "the parser and its grader ship",
    ]


def test_v2_a_terminal_amend_after_the_design_or_off_fabrik_task_is_refused(
    run_dir: Path, tmp_path: Path
) -> None:
    """Restating after the design lands would move the goal to fit the build — even on a re-entered
    phase 2; another command, blank text and a newline are refused too, the record unchanged."""
    repo = _started_v2(run_dir, tmp_path)
    for bad in ("", "   ", "two\nlines"):
        r = _amend(run_dir, repo, bad)
        assert r.returncode == 1 and "REFUSED" in r.stdout, (bad, r.stdout + r.stderr)
    _design(run_dir, repo, "edit `src/a.py`")
    _edit_commit(repo, "src/a.py", "x = 2\n")
    assert _cr(run_dir, "step", "--phase", "4", cwd=repo).returncode == 0
    before = _rec(run_dir)
    r = _amend(run_dir, repo, "whatever got built")
    assert r.returncode == 1 and "REFUSED" in r.stdout and "design" in r.stdout, r.stdout + r.stderr
    after = _rec(run_dir)
    assert after["terminal"] == _START_TERMINAL and "terminal_amends" not in after
    assert after["phase"] == before["phase"] == 4, "a refused step moves nothing"
    other = _repo(tmp_path / "other", lane=2)
    r = _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-review",
        "--phases",
        "3",
        "--terminal",
        "quiet",
        sid="s2",
        cwd=other,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    r = _cr(run_dir, "step", "--phase", "2", "--terminal-amend", "x", sid="s2", cwd=other)
    assert r.returncode == 1 and "fabrik-task" in r.stdout, r.stdout + r.stderr


def test_v2_the_close_row_counts_terminal_amends(run_dir: Path, tmp_path: Path) -> None:
    """Every close of an amended run counts the restatements — a `blocked` close with no commit
    included — and a run that never amends keeps its row shape (no field)."""
    repo = _started_v2(run_dir, tmp_path)
    assert _amend(run_dir, repo, "narrower").returncode == 0
    assert _amend(run_dir, repo, "narrower still").returncode == 0
    r = _close(run_dir, repo, "blocked", "--reason", "missing infra — searched: x — missing: y")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rows(run_dir)[-1]["terminal_amends"] == "2"
    plain = _started_v2(run_dir, tmp_path / "plain")
    r = _close(run_dir, plain, "blocked", "--reason", "missing infra — searched: x — missing: y")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "terminal_amends" not in _rows(run_dir)[-1]


def test_v2_an_unreadable_design_beside_a_terminal_amend_refuses_the_whole_step(
    run_dir: Path, tmp_path: Path
) -> None:
    """Review A-S2: `--design <unreadable>` and `--terminal-amend` in one call refuse together — the
    terminal is not restated by a step whose design never landed."""
    repo = _started_v2(run_dir, tmp_path)
    r = _amend(run_dir, repo, "narrower", "--design", str(repo.parent / "no-such-design.md"))
    assert r.returncode == 1 and "cannot be read" in r.stdout, r.stdout + r.stderr
    rec = _rec(run_dir)
    assert (
        rec["terminal"] == _START_TERMINAL and "terminal_amends" not in rec and "design" not in rec
    )


def test_v2_the_loop_notice_reads_the_terminal_a_same_step_amend_leaves(
    run_dir: Path, tmp_path: Path
) -> None:
    """Review A-S1: the zero-rounds NOTICE fires on a loop-shaped terminal; computed before the amend,
    it judged the terminal being replaced. A run started loop-shaped and amended in the same step
    to a linear terminal gets no notice."""
    repo = _repo(tmp_path, lane=2)
    argv = _start("--file", "src/a.py", "--declare", _V2)
    argv[argv.index("--terminal") + 1] = "confirmed: 0 closing round"
    assert _cr(run_dir, *argv, cwd=repo).returncode == 0
    r = _cr(run_dir, "step", "--phase", "3", "--terminal-amend", "the parser ships", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ZERO rounds" not in r.stderr, r.stderr


def test_v2_a_refused_terminal_amend_raises_no_loop_notice(run_dir: Path, tmp_path: Path) -> None:
    """Review A-S4: the notice runs after every refusal, so a loop-shaped amend that is refused (the
    design is already recorded) neither restates the terminal nor raises a notice about it."""
    repo = _started_v2(run_dir, tmp_path)
    _design(run_dir, repo, "edit `src/a.py`")
    r = _cr(
        run_dir, "step", "--phase", "3", "--terminal-amend", "confirmed: 0 closing round", cwd=repo
    )
    assert r.returncode == 1 and "REFUSED" in r.stdout, r.stdout + r.stderr
    assert "ZERO rounds" not in r.stderr, r.stderr
    assert _rec(run_dir)["terminal"] == _START_TERMINAL


def test_v2_a_design_that_cites_a_file_by_line_or_symbol_names_that_file(
    run_dir: Path, tmp_path: Path
) -> None:
    """W-ebbedc88: a design note cites code as `path:N-M` or `path::symbol`; the citation names
    the file, so the close admits its commit without a --design-amend."""
    repo = _started_v2(run_dir, tmp_path)
    _design(run_dir, repo, "edit `src/a.py:1-3` and `src/b.py::helper`")
    a = _edit_commit(repo, "src/a.py", "x = 2\n")
    b = _edit_commit(repo, "src/b.py", "def helper():\n    return 1\n")
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", a, b)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rows(run_dir)[-1]["design_amends"] == "0"


def test_v2_a_quoted_multi_sha_commit_value_names_the_fix(run_dir: Path, tmp_path: Path) -> None:
    """W-ebbedc88: `--commit "$(cat commit.sha)"` over a two-line capture arrives as ONE value;
    the refusal says --commit takes one sha per value."""
    repo = _started_v2(run_dir, tmp_path)
    _design(run_dir, repo, "edit `src/a.py`")
    a = _edit_commit(repo, "src/a.py", "x = 2\n")
    b = _edit_commit(repo, "src/a.py", "x = 3\n")
    r = _close(run_dir, repo, "done", "--evidence", "green", "--commit", f"{a}\n{b}")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "takes one sha per value" in r.stdout, r.stdout
    assert _rec(run_dir)["state"] == "running"


# ── the two-sided gate (kaizen 01M4XQN131A897DAFH628FJFKJ, D-858): `/fabrik-spec start` through
# `task_lane.admit`, opt-in on `--file`/`--declare` ──────────────────────────────────────────────


def _spec_start(*extra: str) -> list[str]:
    return ["start", "--command", "fabrik-spec", "--phases", "7", "--terminal", "a DRAFT", *extra]


def _spec_handoff(run_dir: Path, repo: Path, reason: str, sid: str = "s1"):
    seed = repo / "docs" / "seed.md"
    seed.parent.mkdir(parents=True, exist_ok=True)
    seed.write_text("# seed\n\n## RESUME\n- /fabrik-task the brief\n", encoding="utf-8")
    return _cr(
        run_dir,
        "handoff",
        "--command",
        "fabrik-spec",
        "--resume",
        "docs/seed.md",
        "--reason",
        reason,
        "--feedback",
        _FB,
        cwd=repo,
        sid=sid,
    )


def test_spec_gate_a_flagless_spec_start_is_admitted_and_noted_as_ungated(
    run_dir: Path, tmp_path: Path
) -> None:
    """Behaviour 1 + fold 3: no `--file`/`--declare` keeps today's start, and the start says the
    gate did not run; its close row carries `lane_gate: none` so the ungated population is
    counted."""
    repo = _repo(tmp_path, lane=2)
    r = _cr(run_dir, *_spec_start(), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "lane gate not run — pass --file/--declare" in r.stderr
    assert _rec(run_dir).get("lane_gate") == "none" and "declared" not in _rec(run_dir)
    assert _ledger(run_dir) == []
    r = _spec_handoff(run_dir, repo, "the brief needs a design after all")
    assert r.returncode == 0, r.stdout + r.stderr
    row = _rows(run_dir)[-1]
    assert row["lane_gate"] == "none" and "downgrade" not in row and "from_downgrade" not in row


def test_spec_gate_a_lane_verdict_refuses_the_spec_naming_why(
    run_dir: Path, tmp_path: Path
) -> None:
    """Behaviour 2: the gate routes the declaration to the lane → refused, no record, no row."""
    repo = _repo(tmp_path, lane=2)
    r = _cr(run_dir, *_spec_start("--file", "src/a.py", "--declare", _V2), cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "REFUSED — fabrik-spec: admitted → lane" in r.stdout
    assert '--why "<the test the gate cannot see>"' in r.stdout
    assert not (run_dir / "s1.json").exists()
    assert _ledger(run_dir) == []


def test_spec_gate_an_overridden_spec_start_is_admitted_and_ledgered(
    run_dir: Path, tmp_path: Path
) -> None:
    """Behaviour 3 + folds 2, 3, 8: `--why` admits; one `spec-start` row with the verdict, the why
    and the restart; the record carries the id; the close row joins it."""
    repo = _repo(tmp_path, lane=2)
    r = _cr(
        run_dir,
        *_spec_start("--file", "src/a.py", "--declare", _V2, "--why", "the UI contract is unknown"),
        cwd=repo,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    rows = _ledger(run_dir)
    assert len(rows) == 1
    row = rows[0]
    assert row["route"] == "spec-start" and row["verdict"] == "lane"
    assert row["why"] == "the UI contract is unknown" and row["files"] == ["src/a.py"]
    assert row["restart"] == f"/fabrik-task --from-downgrade {row['id']}"
    assert row["session"] == "s1" and Path(row["repo"]) == (repo / ".git").resolve()
    d = _rec(run_dir)["declared"]
    assert (d["gate"], d["verdict"], d["spec_refusal"], d["why"]) == (
        2,
        "lane",
        row["id"],
        "the UI contract is unknown",
    )
    assert _rec(run_dir)["lane_gate"] == "lane"
    assert f"lane gate: lane · spec-start refusal {row['id']}" in r.stdout
    assert "review: None" not in r.stdout and "appetite: None" not in r.stdout
    # the handoff joins the record's OWN refusal even in the no-refusal reason form
    r = _spec_handoff(run_dir, repo, "DOWNGRADE: no-refusal — six answers, small")
    assert r.returncode == 0, r.stdout + r.stderr
    fb = _rows(run_dir)[-1]
    assert (fb["lane_gate"], fb["spec_refusal"], fb["downgrade"], fb["from_downgrade"]) == (
        "lane",
        row["id"],
        "refusal",
        row["id"],
    )
    # C-S-2: a reason's LR- id never overrides the record's own row (a pasted id cannot mis-join)
    r = _cr(
        run_dir,
        *_spec_start("--file", "src/b.py", "--declare", _V2, "--why", "unknown"),
        cwd=repo,
        sid="s2",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    own = _rec(run_dir, "s2")["declared"]["spec_refusal"]
    r = _spec_handoff(run_dir, repo, "DOWNGRADE: LR-0a1b2c3d — stale id pasted", sid="s2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rows(run_dir)[-1]["from_downgrade"] == own


def test_spec_gate_a_chain_verdict_is_admitted_without_a_row_and_stamped(
    run_dir: Path, tmp_path: Path
) -> None:
    """Behaviour 4 + fold 3: the chain is where the work belongs — no row, but the verdict rides
    the record and the close row (the chain-shaped cobra is a counted verdict)."""
    repo = _repo(tmp_path, lane=2)
    decl = _V2.replace("tradeoffs=no", "tradeoffs=yes")
    r = _cr(
        run_dir, *_spec_start("--file", "src/a.py", "--declare", decl, "--why", "A vs B"), cwd=repo
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _ledger(run_dir) == []
    d = _rec(run_dir)["declared"]
    assert (d["verdict"], d["why"], d.get("spec_refusal")) == ("chain: tradeoffs", "A vs B", None)
    assert "lane gate: chain: tradeoffs" in r.stdout
    # C-S-1: an explicit --appetite reaches the record (the `--appetite 241` lie is counted)
    r = _cr(
        run_dir,
        *_spec_start(
            "--file", "src/b.py", "--declare", decl, "--why", "A vs B", "--appetite", "60"
        ),
        cwd=repo,
        sid="s2",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert _rec(run_dir, "s2")["declared"]["appetite"] == 60
    r = _spec_handoff(run_dir, repo, "the brief needs a design after all")
    assert _rows(run_dir)[-1]["lane_gate"] == "chain: tradeoffs"


def test_spec_gate_a_right_now_verdict_is_refused_outright(run_dir: Path, tmp_path: Path) -> None:
    """Fold 6: `decision=no` is a pure fix — a spec is not openable over it by prose."""
    repo = _repo(tmp_path, lane=2)
    decl = _V2.replace("decision=yes", "decision=no")
    for extra in ((), ("--why", "please")):
        r = _cr(run_dir, *_spec_start("--file", "src/a.py", "--declare", decl, *extra), cwd=repo)
        assert r.returncode == 1, r.stdout + r.stderr
        assert "REFUSED — fabrik-spec: decision=no → right-now + /fabrik-review-scoped" in r.stdout
        assert "re-declare decision=yes" in r.stdout
    assert not (run_dir / "s1.json").exists() and _ledger(run_dir) == []


def test_spec_gate_from_downgrade_stays_task_only_and_v1_ignores_the_flags(
    run_dir: Path, tmp_path: Path
) -> None:
    """Behaviour 5 + fold 4: `--from-downgrade` names a task restarted FROM a spec; a v1 repo takes
    the flags, notes them and never runs the v1 router (which would refuse a spec INTO the
    chain)."""
    repo = _repo(tmp_path, lane=2)
    r = _cr(run_dir, *_spec_start("--from-downgrade", "LR-0a1b2c3d"), cwd=repo)
    assert r.returncode == 1 and "belong to --command fabrik-task" in r.stdout
    v1 = _repo(tmp_path / "v1", lane=1)
    four = _files("src/a.py", "src/b.py", "src/c.py", "src/d.py")
    decl = _V2.replace("oneway=no", "oneway=yes")
    r = _cr(run_dir, *_spec_start(*four, "--declare", decl), cwd=v1, sid="s9")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "--file, --declare ignored — this repo runs lane v1" in r.stderr
    assert "declared" not in _rec(run_dir, "s9") and _ledger(run_dir) == []


def test_spec_gate_a_dirty_path_or_a_directory_never_refuses_a_spec(
    run_dir: Path, tmp_path: Path
) -> None:
    """Fold 5: a spec designs — a sibling's WIP on the surface is a note, and a directory is a
    legitimate surface."""
    repo = _repo(tmp_path, lane=2)
    (repo / "src" / "a.py").write_text("x = 2\n", encoding="utf-8")  # dirty
    r = _cr(
        run_dir,
        *_spec_start(
            "--file", "src/a.py", "--file", "api", "--declare", _V2, "--why", "unknown UI"
        ),
        cwd=repo,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "src/a.py dirty at start" in r.stderr and "REFUSED" not in r.stdout
    d = _rec(run_dir)["declared"]
    assert d["dirty"] == ["src/a.py"] and d["files"] == ["src/a.py", "api"]


def test_spec_gate_the_no_refusal_downgrade_writes_downgrade_never_a_fake_id(
    run_dir: Path, tmp_path: Path
) -> None:
    """Behaviour 6 + fold 1: on a flagless spec the no-refusal form records `downgrade:
    no-refusal` and NO `from_downgrade` (kaizen's text: "this form records no from_downgrade and
    mis-joins nothing"); the `LR-` form records both."""
    repo = _repo(tmp_path, lane=2)
    for sid, reason, want in (
        ("s1", "DOWNGRADE: no-refusal — six answers, small", ("no-refusal", None)),
        ("s2", "DOWNGRADE: LR-0a1b2c3d — one reversible decision", ("refusal", "LR-0a1b2c3d")),
        ("s3", "DOWNGRADE: none — nope", (None, None)),
    ):
        r = _cr(run_dir, *_spec_start(), cwd=repo, sid=sid)
        assert r.returncode == 0, r.stdout + r.stderr
        r = _spec_handoff(run_dir, repo, reason, sid=sid)
        assert r.returncode == 0, r.stdout + r.stderr
        row = _rows(run_dir)[-1]
        assert (row.get("downgrade"), row.get("from_downgrade")) == want, reason


def test_spec_gate_a_lone_flag_and_a_dead_git_name_the_spec_not_the_task(
    run_dir: Path, tmp_path: Path
) -> None:
    """A-S-3/C-S-3: `--why` or `--appetite` without `--file/--declare` on a spec is refused and
    the refusal says how they ride; A-S-1: an exception inside the gate names the command that
    started."""
    repo = _repo(tmp_path, lane=2)
    for flag, val in (("--why", "x"), ("--appetite", "30")):
        r = _cr(run_dir, *_spec_start(flag, val), cwd=repo)
        assert r.returncode == 1, r.stdout + r.stderr
        assert "belong to --command fabrik-task" in r.stdout
        assert "ride with --file/--declare" in r.stdout
    nobin = tmp_path / "nobin"
    nobin.mkdir()
    r = _cr(
        run_dir,
        *_spec_start("--file", "src/a.py", "--declare", _V2),
        cwd=repo,
        extra_env={"PATH": str(nobin)},
    )
    assert r.returncode == 1
    assert "REFUSED — fabrik-spec: start could not complete (FileNotFoundError)" in r.stdout
    assert "fabrik-task" not in r.stdout
