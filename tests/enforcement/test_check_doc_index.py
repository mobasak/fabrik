# AFTER-EDIT: scripts/enforcement/check_doc_index.py
"""Behavior contract for the INDEX↔tree drift gate (docs-truth plan Phase F)."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path("/opt/fabrik")
sys.path.insert(0, str(REPO / "scripts" / "enforcement"))

import check_doc_index as cdi  # noqa: E402


def test_live_tree_is_clean():
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts/enforcement/check_doc_index.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_selection_docs_are_excluded():
    assert cdi._SELECTION_RE.match("docs/reference/kilo/TASK_SUBAGENT_SELECTION.md")
    assert cdi._SELECTION_RE.match("docs/reference/kilo/TTS_SELECTION.md")
    assert not cdi._SELECTION_RE.match("docs/reference/kilo/AI_VENDOR_ACCESS.md")


def test_pipeline_artifacts_are_excluded():
    assert any(p.startswith("docs/development/plans/") for p in cdi.EXCLUDE_PREFIXES)
    assert any(p.startswith("docs/superpowers/") for p in cdi.EXCLUDE_PREFIXES)


def test_every_per_run_artifact_class_is_excluded_including_certifications():
    """All FOUR dated, machine-generated, per-run classes — asserted LITERALLY and together,
    because certifications arrived (2026-08-27) without this exclusion and nothing noticed: one
    synced command MANDATED `docs/development/certifications/` while this synced check penalised
    it, so every project reddened its gate on its first certification (job-agent: 16 ERRORs, then
    16 rows of per-run noise injected into a curated index as the workaround).

    INDEX.md maps DURABLE docs. Board shape, ticket naming, dispositions and evidence paths are
    already graded by check_certification_coverage.py — that is the check that owns them."""
    for prefix in (
        "docs/development/plans/",
        "docs/development/epics/",
        "docs/development/reviews/",
        "docs/development/certifications/",
    ):
        assert prefix in cdi.EXCLUDE_PREFIXES, f"{prefix} must be exempt from the INDEX map"


def test_a_certification_board_file_is_not_reported_as_unindexed():
    """The behaviour, not the constant: the path shape /fabrik-user-test actually emits."""
    board = "docs/development/certifications/2026-08-28-cert-linkedin/TC01-profiles.md"
    assert any(board.startswith(p) for p in cdi.EXCLUDE_PREFIXES), board


def test_would_fail_on_unindexed_doc(monkeypatch, tmp_path):
    """(b)-direction detection: a live doc absent from INDEX is reported.

    The doc is now written to disk rather than only named by a stdout fake: direction (b) skips
    a path git lists but the worktree does not have (a tracked-then-deleted doc, whose INDEX row
    direction (a) would immediately report as a missing target — the two directions contradicted
    each other there).
    """
    _isolated_index(monkeypatch, tmp_path)
    (tmp_path / "docs" / "operations").mkdir(parents=True)
    (tmp_path / "docs" / "operations" / "definitely-not-indexed-xyz.md").write_text("x")
    _fake_ls(monkeypatch, tracked="docs/operations/definitely-not-indexed-xyz.md\n")
    assert cdi.main() == 1


def test_ls_files_disables_quotepath(monkeypatch):
    """quotePath regression (trade-intelligence upstream 2026-08-05): the ls-files
    call must pass -c core.quotePath=false or non-ASCII doc names come back
    escaped and false-flag as missing from INDEX.md."""
    captured = {}
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        if "ls-files" in cmd:
            captured["cmd"] = cmd

            class R:
                stdout = b""
                returncode = 0

            return R()
        return real_run(cmd, **kw)

    monkeypatch.setattr(cdi.subprocess, "run", fake_run)
    cdi.main()
    assert "core.quotePath=false" in captured["cmd"], captured


def test_untracked_doc_fires_on_the_authoring_run(monkeypatch, tmp_path):
    """transdoc 01M17VA9: tracked-only scoping gave the run that CREATES a doc a false
    green — it committed on it, and the missing INDEX row surfaced as the next agent's
    red. An untracked doc under the INDEX-governed tree is live and must be reported
    to its author, on the run that wrote it."""
    _isolated_index(monkeypatch, tmp_path)
    (tmp_path / "docs" / "reference").mkdir(parents=True)
    (tmp_path / "docs" / "reference" / "brand-new-proposal.md").write_text("x")
    _fake_ls(monkeypatch, untracked="docs/reference/brand-new-proposal.md\n")
    assert cdi.main() == 1


def _fake_ls(monkeypatch, *, tracked="", untracked="", rc=0):
    """Stand in for both `git ls-files` calls — the second is the one carrying --others."""
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        if "ls-files" in cmd:

            class R:
                stdout = b"\0".join(
                    x.encode()
                    for x in (untracked if "--others" in cmd else tracked).split("\n")
                    if x
                )
                returncode = rc

            return R()
        return real_run(cmd, **kw)

    monkeypatch.setattr(cdi.subprocess, "run", fake_run)


def _isolated_index(monkeypatch, tmp_path, body="# INDEX\n\n- [README](README.md)\n"):
    """Point the check at a throwaway root whose INDEX.md names nothing under docs/.

    Without this the check reads the HUB's own INDEX.md, which DOES carry a DECISIONS.md
    row — so an exemption test run against the live tree passes identically whether or not
    the exemption exists. That vacuous shape is exactly what these three tests must avoid.
    """
    (tmp_path / "INDEX.md").write_text(body, encoding="utf-8")
    monkeypatch.setattr(cdi, "REPO", tmp_path)
    # main() reads `as_json = "--json" in sys.argv`, which under pytest is PYTEST's argv — a
    # `pytest --json ...` invocation silently flips these tests into the JSON branch (proven live
    # by an author-blind seat, 2026-09-11: dormant today, no addopts and no conftest option, but
    # `--json` is muscle memory from `final_gate.py --json`). Pin it so the branch is chosen by
    # the test, never by how the suite was launched.
    monkeypatch.setattr(cdi.sys, "argv", ["check_doc_index.py"])


def _seed(tmp_path, rel="docs/DECISIONS.md", body=None):
    """Write `rel` as the ACTUAL distributed seed unless `body` overrides it.

    The fixture reads `templates/governance/DECISIONS.md` rather than inventing content, so these
    graders move with the real seed instead of asserting against a hard-coded stand-in.
    """
    if body is None:
        body = (REPO / "templates" / "governance" / "DECISIONS.md").read_text(encoding="utf-8")
    f = tmp_path / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(body, encoding="utf-8")
    return f


def test_the_current_template_seed_is_pinned():
    """The pin cannot rot silently. `_PRISTINE_SEEDS` is a hand-maintained set of the seeds the
    sync has distributed, and the moment templates/governance/DECISIONS.md changes without the new
    hash being added, every freshly seeded repo stops being recognised as pristine and starts
    owing an INDEX row nobody in it wrote. This test is what makes that a failing build rather
    than a slow fleet-wide drift."""
    seed = REPO / "templates" / "governance" / "DECISIONS.md"
    digest = hashlib.md5(seed.read_bytes(), usedforsecurity=False).hexdigest()
    known = cdi._PRISTINE_SEEDS["docs/DECISIONS.md"]
    assert digest in known, (
        f"{seed} now hashes to {digest}, which is not in _PRISTINE_SEEDS['docs/DECISIONS.md'] — "
        "add it (the set is cumulative: older repos keep the bytes they were seeded with)"
    )
    # ANTI-SHRINK, take two. `len(known) >= 1` was the first attempt and a second seat showed it
    # cannot see the failure its own docstring describes: once the set holds two hashes, deleting
    # the OLDER one still leaves the current one present and the length non-zero, while quietly
    # turning every repo seeded from that older template red. Pinning the SET makes growth a
    # deliberate edit here and makes shrinkage fail.
    assert known == frozenset({"c9081f23d0feda07d8b24562e53f7d12"}), (
        "the distributed-seed set changed. Adding a seed is expected as the template evolves — "
        "add its md5 in BOTH places. Removing one is not: repos keep the bytes they were seeded "
        f"with, so a dropped hash reds every repo still holding it. Now: {sorted(known)}"
    )
    # A `SEEDED_UNADOPTED == frozenset(_PRISTINE_SEEDS)` assertion stood here. An author-blind
    # seat proved it constrained nothing at one key — hardcoding the constant survived every
    # mutant — so the constant was DELETED and the exemption reads the pin directly. Assert the
    # absence, which IS constrainable.
    assert not hasattr(cdi, "SEEDED_UNADOPTED"), (
        "a second name for the exempt-path set reintroduces exactly the drift the pin removed"
    )


def test_a_pristine_seeded_ledger_is_exempt(monkeypatch, tmp_path):
    """25 of the 45 git repos under /opt are in exactly this state (measured 2026-09-11): the
    governance sync wrote docs/DECISIONS.md, its bytes are still byte-identical to
    templates/governance/DECISIONS.md, and no session in that repo has written a decision. The
    gate used to bill the INDEX row to whoever ran next."""
    _isolated_index(monkeypatch, tmp_path)
    _seed(tmp_path)
    _fake_ls(monkeypatch, untracked="docs/DECISIONS.md\n")
    assert cdi.main() == 0


def test_a_ledger_the_repo_has_written_to_owes_its_index_row(monkeypatch, tmp_path, capsys):
    """THE grader that keys the exemption to PROVENANCE rather than to git bookkeeping.

    An author-blind seat broke the first version with this exact fixture: a project agent obeys
    CLAUDE.md's decision-ledger rule, appends real decision rows, and runs the gate BEFORE
    staging — the file is still untracked, so a tracked-ness exemption returned a false GREEN on
    a doc the repo itself authored. That is verbatim the transdoc 01M17VA9 regression the
    untracked-counts-as-live rule exists to prevent, re-opened for this one path.
    """
    _isolated_index(monkeypatch, tmp_path)
    f = _seed(tmp_path)  # the exact distributed seed …
    f.write_text(
        f.read_text() + "| D-001 | 2026-09-11 | this repo's own decision | x | y | z |\n",
        encoding="utf-8",
    )  # … and the repo then writes its first decision, WITHOUT staging it
    _fake_ls(monkeypatch, untracked="docs/DECISIONS.md\n")
    assert cdi.main() == 1
    out = capsys.readouterr().out
    assert "live doc not in INDEX.md: docs/DECISIONS.md" in out, out


def test_the_exemption_does_not_flip_on_git_add(monkeypatch, tmp_path):
    """`--others` means "not in the INDEX", so the first version handed a bare `git add docs/`
    over the PRISTINE seed an instant red, and `git rm --cached` took it away again — while the
    code comment, FINAL_GATE_WORKFLOW.md and D-225 all described the axis as "commits". Content
    does not move when the index does."""
    _isolated_index(monkeypatch, tmp_path)
    _seed(tmp_path)
    _fake_ls(monkeypatch, tracked="docs/DECISIONS.md\n")  # staged/committed, still pristine
    assert cdi.main() == 0


def test_an_unrecognised_ledger_gets_no_exemption(monkeypatch, tmp_path, capsys):
    """Fail CLOSED on anything whose bytes the hub cannot vouch for. A file that is neither a known
    seed nor recognisable is treated as the repo's own and owes its row — so a future template
    change, a partial write or a hand-edited header can never silently WIDEN the exemption."""
    _isolated_index(monkeypatch, tmp_path)
    _seed(tmp_path, body="# Decisions\n\nsomething else entirely\n")
    _fake_ls(monkeypatch, untracked="docs/DECISIONS.md\n")
    assert cdi.main() == 1
    assert "docs/DECISIONS.md" in capsys.readouterr().out


def test_missing_index_is_a_finding_not_a_traceback(monkeypatch, tmp_path, capsys):
    """5 of the 45 repos carry this synced check and have no INDEX.md; the unguarded read raised
    FileNotFoundError, so the gate reported a stack trace — which names no file to fix and reads
    as a broken check rather than a finding."""
    monkeypatch.setattr(cdi, "REPO", tmp_path)
    monkeypatch.setattr(cdi.sys, "argv", ["check_doc_index.py"])
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")  # there IS a docs tree, so this is a real red
    assert cdi.main() == 1
    assert "INDEX.md is missing" in capsys.readouterr().out


def test_missing_index_json_branch_reports_failure(monkeypatch, tmp_path, capsys):
    """The `--json` half of the missing-INDEX guard shipped with NO grader, and an author-blind
    seat proved the gap with a surviving mutant: a copy emitting `{"status": "success"}` — a
    fabricated all-clear for a repo with no INDEX.md — left every test green, because the
    plain-text test never sets `--json`."""
    monkeypatch.setattr(cdi, "REPO", tmp_path)
    monkeypatch.setattr(cdi.sys, "argv", ["check_doc_index.py", "--json"])
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    assert cdi.main() == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failure", payload
    assert payload["drift"] and "INDEX.md" in payload["drift"][0], payload


def test_an_index_that_is_a_directory_names_its_real_shape(monkeypatch, tmp_path, capsys):
    """`is_file()` is also False for a DIRECTORY and for a broken symlink, and telling either of
    those to "create the index" sends the reader after the wrong thing."""
    monkeypatch.setattr(cdi, "REPO", tmp_path)
    monkeypatch.setattr(cdi.sys, "argv", ["check_doc_index.py"])
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    (tmp_path / "INDEX.md").mkdir()
    assert cdi.main() == 1
    assert "is not a regular file" in capsys.readouterr().out


def test_unreadable_index_is_a_finding_not_a_traceback(monkeypatch, tmp_path, capsys):
    """FileNotFoundError was one member of a class: a mode-000 INDEX.md still tracebacked PAST
    the missing-file guard. The read now catches OSError — the class, not the instance."""
    monkeypatch.setattr(cdi, "REPO", tmp_path)
    monkeypatch.setattr(cdi.sys, "argv", ["check_doc_index.py"])
    idx = tmp_path / "INDEX.md"
    idx.write_text("# INDEX\n")
    idx.chmod(0o000)
    try:
        if os.access(idx, os.R_OK):  # running as root: the mode is not enforced, skip honestly
            pytest.skip("cannot make a file unreadable as this user")
        assert cdi.main() == 1
        assert "could not be read" in capsys.readouterr().out
    finally:
        idx.chmod(0o644)


def test_git_failure_fails_closed_instead_of_reporting_ok(monkeypatch, tmp_path, capsys):
    """`check=False` plus `.stdout` alone turned git's exit 128 ("not a git repository") into
    zero docs examined and a cheerful OK — a green with a denominator of nothing, which is the
    shape the hub contract bans outright."""
    _isolated_index(monkeypatch, tmp_path)
    _fake_ls(monkeypatch, rc=128)
    assert cdi.main() == 1
    assert "0 docs" in capsys.readouterr().out


def test_a_tracked_doc_deleted_from_the_worktree_is_not_demanded(monkeypatch, tmp_path):
    """Otherwise the two directions contradict: adding the natural `](docs/…)` link makes
    direction (a) report the target as missing, so only a link-less bare-basename mention
    satisfies both — a nonsense edit made to appease a gate."""
    _isolated_index(monkeypatch, tmp_path)
    _fake_ls(monkeypatch, tracked="docs/gone.md\n")  # git lists it; the worktree does not have it
    assert cdi.main() == 0


def test_finding_order_is_deterministic_across_hash_seeds(tmp_path):
    """`untracked` is a SET, so before `sorted()` the ERROR/drift line order varied between runs
    on identical input — and a closing author-blind seat proved the `sorted()` fix had NO grader:
    reverting it left all 19 tests green, because every other test asserts on rc or on substring
    membership, neither of which can see order.

    Asserting "the output happens to be sorted" would be probabilistic (CPython's set order for
    strings depends on PYTHONHASHSEED, which pytest does not pin), so this drives the REAL contract
    instead: the same repo, two different hash seeds, byte-identical output. Under the mutant the
    two runs disagree; the check is copied into a throwaway git repo because `_root()` resolves
    from `__file__`, which is also what makes this an end-to-end run of the shipped script.
    """
    (tmp_path / "scripts" / "enforcement").mkdir(parents=True)
    shutil.copy(
        REPO / "scripts" / "enforcement" / "check_doc_index.py",
        tmp_path / "scripts" / "enforcement" / "check_doc_index.py",
    )
    (tmp_path / "INDEX.md").write_text("# INDEX\n", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    # Enough names that set order and sorted order coincide only by accident.
    for name in ("zeta", "alpha", "mu", "omega", "beta", "kappa", "delta", "sigma"):
        (docs / f"{name}.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    def run(seed):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        return subprocess.run(
            [sys.executable, str(tmp_path / "scripts" / "enforcement" / "check_doc_index.py")],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        ).stdout

    first, second = run("0"), run("1")
    assert first == second, f"finding order is hash-seed dependent:\n{first}\n---\n{second}"
    assert first.count("live doc not in INDEX.md") == 8, first


def test_a_broken_symlink_doc_is_still_reported(monkeypatch, tmp_path, capsys):
    """`Path.exists()` FOLLOWS symlinks, so the tracked-but-deleted skip written in round 2 also
    swallowed a tracked doc whose symlink target is gone — a live finding HEAD reported and the
    rewrite dropped. `lstat` is true for a broken symlink and still false for a deleted file."""
    _isolated_index(monkeypatch, tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "dangling.md").symlink_to(tmp_path / "docs" / "nowhere.md")
    _fake_ls(monkeypatch, tracked="docs/dangling.md\n")
    assert cdi.main() == 1
    assert "docs/dangling.md" in capsys.readouterr().out


def test_an_unreadable_doc_path_is_reported_not_tracebacked(monkeypatch, tmp_path, capsys):
    """`Path.exists()` propagates EACCES, so a mode-000 docs/ subtree turned this check into the
    TRACEBACK the whole change exists to remove — the instance-not-class mistake its own comment
    warns about, committed on a line the change added. Unreadable is not absent."""
    _isolated_index(monkeypatch, tmp_path)
    sub = tmp_path / "docs" / "sub"
    sub.mkdir(parents=True)
    (sub / "hidden.md").write_text("x", encoding="utf-8")
    sub.chmod(0o000)
    try:
        if os.access(sub / "hidden.md", os.F_OK):
            pytest.skip("cannot make a directory unreadable as this user")
        _fake_ls(monkeypatch, tracked="docs/sub/hidden.md\n")
        assert cdi.main() == 1
        assert "docs/sub/hidden.md" in capsys.readouterr().out
    finally:
        sub.chmod(0o755)


def test_a_missing_git_binary_fails_closed(monkeypatch, tmp_path, capsys):
    """`_ls`'s docstring promises None "when git could not answer". A non-zero exit was handled;
    git being absent from PATH raised FileNotFoundError out of subprocess instead."""
    _isolated_index(monkeypatch, tmp_path)
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        if "ls-files" in cmd:
            raise FileNotFoundError(2, "No such file or directory: 'git'")
        return real_run(cmd, **kw)

    monkeypatch.setattr(cdi.subprocess, "run", fake_run)
    assert cdi.main() == 1
    out = capsys.readouterr().out
    # The CAUSE must be named, not just the symptom: the caller used to print "is this a git
    # repository?" for a box that simply has no git binary, sending the operator to inspect .git/.
    assert "git could not be run" in out, out
    assert "is this a git repository" not in out, out


def test_a_broken_symlink_index_names_its_real_shape(monkeypatch, tmp_path, capsys):
    """The comment claimed a broken-symlink INDEX.md was distinguished from a missing one and
    that both were reproduced. `exists()` follows the link, so it took the "is missing" branch —
    which sends the reader off to create a file that is already there, pointing nowhere."""
    monkeypatch.setattr(cdi, "REPO", tmp_path)
    monkeypatch.setattr(cdi.sys, "argv", ["check_doc_index.py"])
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x", encoding="utf-8")
    (tmp_path / "INDEX.md").symlink_to(tmp_path / "nowhere.md")
    assert cdi.main() == 1
    assert "is not a regular file" in capsys.readouterr().out


def test_the_seed_pin_is_keyed_by_path(monkeypatch, tmp_path, capsys):
    """A flat hash set would let one exempt path's seed hash exempt a DIFFERENT path the moment
    SEEDED_UNADOPTED grows past one member — a sentinel collision with no visible symptom."""
    monkeypatch.setattr(
        cdi, "_PRISTINE_SEEDS", {**cdi._PRISTINE_SEEDS, "docs/OTHER.md": frozenset()}
    )
    _isolated_index(monkeypatch, tmp_path)
    _seed(tmp_path, rel="docs/OTHER.md")  # the DECISIONS seed bytes, at a different path
    _fake_ls(monkeypatch, untracked="docs/OTHER.md\n")
    assert cdi.main() == 1, "another path's seed hash must not exempt this one"
    assert "docs/OTHER.md" in capsys.readouterr().out


def _git_repo_with(tmp_path, names, index_body="# INDEX\n", env=None):
    """A throwaway git repo holding `names` under docs/, with the real check copied in and RUN.

    Returns the CompletedProcess, and asserts no traceback itself. The earlier version returned
    `.stdout` alone with `check=False` and no assertion on `returncode` or `stderr` — so a run
    that printed the expected lines and THEN died still passed, which is precisely how a
    `UnicodeEncodeError` in the plain-text branch (the branch `final_gate.py` actually invokes)
    shipped past a grader written to catch hostile filenames. `names` may be `bytes` so a
    non-UTF-8 filename is expressible at all; `write_text(encoding="utf-8")` could not.
    """
    (tmp_path / "scripts" / "enforcement").mkdir(parents=True)
    shutil.copy(
        REPO / "scripts" / "enforcement" / "check_doc_index.py",
        tmp_path / "scripts" / "enforcement" / "check_doc_index.py",
    )
    (tmp_path / "INDEX.md").write_bytes(
        index_body if isinstance(index_body, bytes) else index_body.encode("utf-8")
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    for n in names:
        raw = n if isinstance(n, bytes) else n.encode("utf-8")
        with open(os.path.join(os.fsencode(docs), raw), "wb") as fh:
            fh.write(b"x")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    proc = subprocess.run(
        [sys.executable, str(tmp_path / "scripts" / "enforcement" / "check_doc_index.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **env} if env else None,
    )
    assert "Traceback" not in proc.stderr, proc.stderr
    assert proc.returncode in (0, 1), (proc.returncode, proc.stdout, proc.stderr)
    return proc


def test_a_c_quoted_path_is_still_reported(tmp_path):
    """`core.quotePath=false` only stops git quoting NON-ASCII bytes. git still C-quotes any path
    holding a control character, a double quote or a backslash — unconditionally — and the quoted
    literal (`"docs/a\\"b.md"`) resolves to nothing on disk. An author-blind seat proved that the
    worktree-liveness skip therefore read five such LIVE, unindexed docs as "tracked but deleted"
    and returned a clean green where the pre-fix version reported all five. `-z` is the only git
    output that is never quoted.
    """
    out = _git_repo_with(tmp_path, ['a"b.md', "a\\b.md", "plain.md"]).stdout
    for name in ('docs/a"b.md', "docs/a\\b.md", "docs/plain.md"):
        assert name in out, f"{name} missing from:\n{out}"


def test_direction_a_reports_an_unreadable_target_rather_than_crashing(
    monkeypatch, tmp_path, capsys
):
    """The EACCES traceback was fixed at ONE of three call sites. Direction (a) — "INDEX.md names
    missing path" — kept `Path.exists()`, so an INDEX link into a mode-000 subtree still killed
    the whole check with a stack trace and zero findings."""
    locked = tmp_path / "docs" / "locked"
    locked.mkdir(parents=True)
    (locked / "t.md").write_text("x", encoding="utf-8")
    _isolated_index(monkeypatch, tmp_path, body="# INDEX\n\n- [t](docs/locked/t.md)\n")
    _fake_ls(monkeypatch)
    locked.chmod(0o000)
    try:
        if os.access(locked / "t.md", os.F_OK):
            pytest.skip("cannot make a directory unreadable as this user")
        assert cdi.main() == 1
        assert "cannot be read" in capsys.readouterr().out
    finally:
        locked.chmod(0o755)


def test_a_parent_replaced_by_a_file_counts_as_absent(monkeypatch, tmp_path):
    """`Path.exists()` answers False for ENOTDIR, ELOOP and EBADF as well as ENOENT. Routing every
    OSError to "report" inverted those three, turning a genuinely-gone doc into a false red whose
    only remedy re-creates the direction (a)/(b) contradiction."""
    _isolated_index(monkeypatch, tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "sub").write_text("i am a file, not a directory", encoding="utf-8")
    _fake_ls(monkeypatch, tracked="docs/sub/x.md\n")  # lstat -> ENOTDIR
    assert cdi.main() == 0


def test_a_non_utf8_filename_is_reported_in_both_branches(tmp_path):
    """The surrogateescape decode of git's `-z` bytes had NO grader — `_fake_ls` encodes with
    strict UTF-8 and `_git_repo_with` writes only ASCII, so no fake could structurally reach it
    (an author-blind seat proved the mutant survived all 28 tests).

    Reaching it found a live crash rather than a missing test: decoding with surrogateescape lets
    a non-UTF-8 FILENAME become a finding instead of a `UnicodeDecodeError`, and then the lone
    surrogate raises `UnicodeEncodeError` at `print()`. `--json` survived (json escapes
    surrogates) while the plain-text branch died — the same defect one layer down. Both branches
    are asserted here for exactly that reason.
    """
    (tmp_path / "scripts" / "enforcement").mkdir(parents=True)
    shutil.copy(
        REPO / "scripts" / "enforcement" / "check_doc_index.py",
        tmp_path / "scripts" / "enforcement" / "check_doc_index.py",
    )
    (tmp_path / "INDEX.md").write_text("# INDEX\n", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    with open(os.path.join(os.fsencode(docs), b"caf\xe9.md"), "wb") as fh:
        fh.write(b"x")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    script = str(tmp_path / "scripts" / "enforcement" / "check_doc_index.py")

    plain = subprocess.run(
        [sys.executable, script], cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert plain.returncode == 1, plain.stdout + plain.stderr
    assert "UnicodeEncodeError" not in plain.stderr, plain.stderr
    assert "live doc not in INDEX.md" in plain.stdout, plain.stdout

    js = subprocess.run(
        [sys.executable, script, "--json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert js.returncode == 1, js.stdout + js.stderr
    assert json.loads(js.stdout)["status"] == "failure", js.stdout


def test_a_symlink_cycle_in_an_index_target_counts_as_absent(monkeypatch, tmp_path, capsys):
    """ELOOP sits in `_ABSENT_ERRNOS` and nothing tested it — removing it survived all 28 tests.

    Note where it is actually REACHABLE, which is not where it first looks: `lstat` does not
    follow links, so a cycle is `present` to direction (b) — correctly, the path is a live entry
    in the worktree. It is `stat` in direction (a) that walks the cycle and raises ELOOP, and an
    INDEX link into a cycle genuinely does not resolve. Writing this test against direction (b)
    first is what surfaced the distinction.
    """
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").symlink_to(docs / "b.md")
    (docs / "b.md").symlink_to(docs / "a.md")
    _isolated_index(monkeypatch, tmp_path, body="# INDEX\n\n- [a](docs/a.md)\n")
    _fake_ls(monkeypatch)
    assert cdi.main() == 1
    assert "INDEX.md names missing path: docs/a.md" in capsys.readouterr().out


def test_direction_a_treats_a_dangling_target_as_missing(monkeypatch, tmp_path, capsys):
    """The companion of `test_a_broken_symlink_doc_is_still_reported`, for the OTHER direction.
    Direction (a) asks whether what INDEX.md points at RESOLVES, so it must follow the link —
    swapping its `stat()` for `lstat()` survived all 28 tests, and would have quietly called a
    dangling INDEX target present."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "dangling.md").symlink_to(docs / "nowhere.md")
    _isolated_index(monkeypatch, tmp_path, body="# INDEX\n\n- [d](docs/dangling.md)\n")
    _fake_ls(monkeypatch)
    assert cdi.main() == 1
    assert "INDEX.md names missing path: docs/dangling.md" in capsys.readouterr().out


def test_an_index_link_with_an_embedded_nul_is_reported(monkeypatch, tmp_path, capsys):
    """`Path.exists()` answers False for a non-encodable path via a SECOND except arm
    (`except ValueError`), and the rewrite that replaced it reproduced only the OSError one.
    Direction (a)'s regex accepts a NUL (it is neither `)`, `#` nor whitespace), so an INDEX.md
    carrying `](docs/a<NUL>b.md)` tracebacked where the pre-rewrite version reported it — a
    regression an author-blind seat proved red-on-revert against HEAD."""
    _isolated_index(monkeypatch, tmp_path, body="# INDEX\n\n- [x](docs/a\x00b.md)\n")
    _fake_ls(monkeypatch)
    assert cdi.main() == 1
    assert "INDEX.md names missing path" in capsys.readouterr().out


def test_a_carriage_return_filename_can_actually_be_satisfied(tmp_path):
    """The `text=True` universal-newline hole was closed on the GIT side only. `read_text` is
    text mode too, so it rewrote a `\\r` INSIDE a filename to `\\n` — and the two sides of the
    membership test could then never match. The finding was a red with NO reachable remedy:
    naming the doc by full path, by bare path or by basename all still failed."""
    name = b"a\rb.md"
    red = _git_repo_with(tmp_path / "red", [name])
    assert red.returncode == 1, red.stdout
    green = _git_repo_with(
        tmp_path / "green", [name], index_body=b"# INDEX\n\n- [x](docs/a\rb.md)\n"
    )
    assert green.returncode == 0, green.stdout


def test_a_non_utf8_filename_can_actually_be_satisfied(tmp_path):
    """Same class, the other half: the path side decoded with `surrogateescape` (`\\udcXX`) while
    INDEX.md was read with `errors="replace"` (`U+FFFD`), so the strings could never be equal and
    the finding was permanently unclearable. Both sides now share one encoding contract."""
    name = b"caf\xe9.md"
    red = _git_repo_with(tmp_path / "red", [name])
    assert red.returncode == 1, red.stdout
    green = _git_repo_with(
        tmp_path / "green", [name], index_body=b"# INDEX\n\n- [x](docs/caf\xe9.md)\n"
    )
    assert green.returncode == 0, green.stdout


def test_an_index_symlinked_into_an_unreadable_dir_is_a_finding(monkeypatch, tmp_path, capsys):
    """`is_file()` stats the TARGET and re-raises EACCES, so it tracebacked one call to the right
    of the guard added to prevent exactly that — the location fixed, the class still open."""
    monkeypatch.setattr(cdi, "REPO", tmp_path)
    monkeypatch.setattr(cdi.sys, "argv", ["check_doc_index.py"])
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x", encoding="utf-8")
    hidden = tmp_path / "hidden"
    hidden.mkdir()
    (hidden / "real.md").write_text("# INDEX\n", encoding="utf-8")
    (tmp_path / "INDEX.md").symlink_to(hidden / "real.md")
    hidden.chmod(0o000)
    try:
        if os.access(hidden / "real.md", os.F_OK):
            pytest.skip("cannot make a directory unreadable as this user")
        assert cdi.main() == 1
        assert "could not be examined" in capsys.readouterr().out
    finally:
        hidden.chmod(0o755)


def test_absent_errnos_still_mirrors_pathlib():
    """`_ABSENT_ERRNOS` claims to mirror `Path.exists()`'s ignored set, and nothing asserted it —
    `command grep -rn 'IGNORED_ERRNOS'` over scripts/ and tests/ returned zero matches. An
    unaccounted errno member is the exact failure this review hit four separate times, so the
    claim gets the one grader that can catch an interpreter bump changing it underneath us.
    """
    import pathlib

    assert frozenset(pathlib._IGNORED_ERRNOS) == cdi._ABSENT_ERRNOS, (
        f"pathlib now ignores {sorted(pathlib._IGNORED_ERRNOS)}, the module ignores "
        f"{sorted(cdi._ABSENT_ERRNOS)} — the helpers' docstrings claim to mirror Path.exists()"
    )


def test_an_unreadable_seed_gets_no_exemption(monkeypatch, tmp_path, capsys):
    """The fail-CLOSED half of the provenance rule had no grader at all: an author-blind seat
    flipped `_is_pristine_seed`'s `except OSError` from `return False` to `return True` and the
    mutant survived all 35 tests. If the check cannot READ the ledger it cannot vouch for its
    bytes, so it must treat the file as the repo's own — an unreadable file is not a pristine one.
    """
    _isolated_index(monkeypatch, tmp_path)
    seed = _seed(tmp_path)  # the exact distributed seed — exempt if it can be read
    seed.chmod(0o000)
    try:
        if os.access(seed, os.R_OK):
            pytest.skip("cannot make a file unreadable as this user")
        _fake_ls(monkeypatch, untracked="docs/DECISIONS.md\n")
        assert cdi.main() == 1
        assert "docs/DECISIONS.md" in capsys.readouterr().out
    finally:
        seed.chmod(0o644)


def test_a_c_quoted_filename_can_actually_be_satisfied(tmp_path):
    """The third sibling of the satisfiability claim. CR names and non-UTF-8 names each have a
    red/green pair; C-quoted names (quote, backslash, control char) had only the RED half, which
    is the shape that twice hid a finding with no reachable remedy."""
    names = ['a"b.md', "a\\b.md", "\x01ctl.md"]
    red = _git_repo_with(tmp_path / "red", names)
    assert red.returncode == 1, red.stdout
    body = "# INDEX\n\n" + "".join(f"- [x](docs/{n})\n" for n in names)
    green = _git_repo_with(tmp_path / "green", names, index_body=body)
    assert green.returncode == 0, green.stdout


def test_the_plain_text_branch_survives_an_ascii_stdout(tmp_path):
    """`_printable` neutralises lone SURROGATES; it does nothing for a VALID non-ASCII character,
    and this module's own "OK" line contains an em dash. So on a non-UTF-8 stdout a CLEAN repo
    exited 1 with a `UnicodeEncodeError`, and a repo WITH a finding exited 1 with the finding text
    lost entirely — a red carrying no remedy at all. `final_gate.py` invokes this plain-text branch
    and inherits the gate's environment, so the env is reachable, not hypothetical.

    The fix reconfigures the STREAM, which is why it needs a grader out here rather than a unit
    test: nothing a wrapper function does can reach a bare `print()` of a literal. An author-blind
    seat proved the guard could be deleted with the whole suite still green.
    """
    ascii_env = {"PYTHONIOENCODING": "ascii"}
    clean = _git_repo_with(
        tmp_path / "clean", ["a.md"], index_body="# INDEX\n\n- [a](docs/a.md)\n", env=ascii_env
    )
    assert clean.returncode == 0, clean.stdout + clean.stderr
    # Assert the PRECONDITION, not just the outcome. A confirming seat showed this grader rests
    # entirely on one un-asserted fact — that PYTHONIOENCODING actually reached the child — and
    # that dropping the helper's env threading (the shape a future tidy-up produces) left all 40
    # tests green with the guard ALSO deleted. The discriminator is exact: under an ascii stdout
    # the em dash renders as a literal backslash-u escape; under utf-8 it is a real character.
    assert "OK \\u2014" in clean.stdout, (
        "the child did not run under an ascii stdout — PYTHONIOENCODING never reached it, so "
        "this grader is asserting nothing: " + clean.stdout
    )

    dirty = _git_repo_with(tmp_path / "dirty", ["a.md"], env=ascii_env)
    assert dirty.returncode == 1, dirty.stdout + dirty.stderr
    assert "live doc not in INDEX.md" in dirty.stdout, dirty.stdout


def test_a_control_char_in_a_filename_cannot_split_a_finding(tmp_path):
    """A `\\r` inside a filename rendered ONE finding as TWO lines, and `final_gate.py` captures
    with `text=True`, whose newline translation then makes the split permanent — so the remedy
    half of the finding was torn onto a line of its own in the branch the gate reads."""
    out = _git_repo_with(tmp_path, [b"a\rb.md"]).stdout
    assert "docs/a\\x0db.md" in out, out
    # Two vacuous assertions were tried here before this one, and naming both is the point.
    # `len(errors) == 1` is vacuous because the torn continuation line does not begin with
    # "ERROR:", so the count stays 1 either way. `"\r" not in out` is WORSE — a tautology: the
    # helper captures with `text=True`, whose universal-newline translation rewrites a raw CR to
    # "\n" before this test can ever observe it, so it passes for the mutant too and cannot fail
    # for any input at all. What IS observable through that capture is the SPLIT itself, which is
    # the real contract: one finding, one line, whatever the filename contains.
    assert len(out.rstrip("\n").splitlines()) == 1, repr(out)
    errors = [ln for ln in out.splitlines() if ln.startswith("ERROR:")]
    assert len(errors) == 1, out
    assert errors[0].rstrip().endswith("INDEX row)"), errors


def test_a_newline_in_a_filename_cannot_split_a_finding(tmp_path):
    """The sibling of the CR case, and the reason the line-count assertion above is not dead
    weight behind the `\\x0d` check: `_printable` originally escaped C0 controls EXCEPT newline,
    on the reasoning that a newline is the separator rather than content. True of the separator
    `print()` appends; false of a newline INSIDE a filename, which git reports verbatim through
    `-z`. Measured before fixing: one finding, two lines."""
    out = _git_repo_with(tmp_path, [b"a\nb.md"]).stdout
    assert len(out.rstrip("\n").splitlines()) == 1, repr(out)
    assert "docs/a\\x0ab.md" in out, out


def test_untracked_only_reports_the_creating_runs_docs_and_nothing_else(tmp_path, monkeypatch):
    """T4.6 (01M23D1BF): the untracked-doc rule billed an arbitrary LATER run at its completion
    gate; `--untracked-only` is the cheap lean-tier mode that reports only untracked live docs, so
    the authoring run sees its debt while the file is still in hand."""
    r = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts/enforcement/check_doc_index.py"),
            "--untracked-only",
            "--json",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=120,
    )
    payload = json.loads(r.stdout)
    assert payload.get("mode") == "untracked-only", payload
    assert all("untracked" in d for d in payload["drift"]), payload
