"""Behavior Contract — the doc↔script coupling renderer
(`scripts/render_doc_script_links.py`).

The operator's ask is bidirectional: every doc names its scripts, every script names the doc
it must keep current. The SECOND half already existed (`# AFTER-EDIT:`, gate-WARN'd by
`check_script_headers.py`); the first half did not.

⚠️ THE DESIGN CONSTRAINT THESE TESTS EXIST TO PROTECT: the two directions are ONE source of
truth, not two. The header is the declaration; the doc-side block is DERIVED from it. A
hand-maintained list on each side would be two things to keep in sync — which is the exact
defect this repo fixed hours earlier, when a doc restating `caps.json`'s values drifted from
the live file in both of the values it named. So: the block is generated, never authored, and
`--check` is what makes "always up to date" mechanical rather than aspirational.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "render_doc_script_links.py"

spec = importlib.util.spec_from_file_location("render_doc_script_links", SCRIPT)
rdsl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rdsl)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A miniature repo: two scripts, one shared doc, one doc with hand-written prose."""
    (tmp_path / "scripts" / "sysadmin").mkdir(parents=True)
    (tmp_path / "docs" / "workstation").mkdir(parents=True)
    (tmp_path / "scripts" / "sysadmin" / "rotate.py").write_text(
        '#!/usr/bin/env python3\n# AFTER-EDIT: docs/workstation/rotation.md\n"""Rotate."""\n'
    )
    (tmp_path / "scripts" / "sysadmin" / "board.py").write_text(
        "#!/usr/bin/env python3\n"
        "# AFTER-EDIT: docs/workstation/rotation.md | docs/workstation/board.md\n"
        '"""Board."""\n'
    )
    (tmp_path / "docs" / "workstation" / "rotation.md").write_text(
        "# Rotation\n\nProse about rotation.\n\n## Related\n\n- `PORTS.md` — port 5051\n"
    )
    (tmp_path / "docs" / "workstation" / "board.md").write_text("# Board\n\nProse.\n")
    return tmp_path


def test_inverts_the_after_edit_graph_into_each_doc(repo: Path):
    """The core behavior: a script declaring a doc makes that doc name the script back."""
    assert rdsl.run(["--repo", str(repo)]) == 0
    rotation = (repo / "docs" / "workstation" / "rotation.md").read_text()
    assert "scripts/sysadmin/rotate.py" in rotation
    assert "scripts/sysadmin/board.py" in rotation, "a doc named by TWO scripts must list both"
    board = (repo / "docs" / "workstation" / "board.md").read_text()
    assert "scripts/sysadmin/board.py" in board
    assert "scripts/sysadmin/rotate.py" not in board, "rotate.py never declared board.md"


def test_hand_written_prose_outside_the_markers_survives_verbatim(repo: Path):
    """The renderer writes into a marked region ONLY. Docs carry hand-written `## Related`
    sections listing sibling DOCS; clobbering them would trade one missing link for a lost one."""
    doc = repo / "docs" / "workstation" / "rotation.md"
    before = doc.read_text()
    rdsl.run(["--repo", str(repo)])
    after = doc.read_text()
    assert before in after, "existing content was modified, not appended to"
    assert "- `PORTS.md` — port 5051" in after


def test_render_is_idempotent(repo: Path):
    """A second run must be byte-identical. A renderer that churns its own output turns every
    unrelated commit into a diff against these docs, and the block stops being read."""
    rdsl.run(["--repo", str(repo)])
    once = (repo / "docs" / "workstation" / "rotation.md").read_text()
    assert rdsl.run(["--repo", str(repo)]) == 0
    assert (repo / "docs" / "workstation" / "rotation.md").read_text() == once


def test_check_mode_fails_on_a_stale_block_and_writes_nothing(repo: Path):
    """THE GUARD THAT MAKES THE COUPLING PERMANENT. Without a --check that FAILS, the block is
    just more prose that rots — which is the whole failure mode being fixed."""
    rdsl.run(["--repo", str(repo)])
    # a THIRD script now declares rotation.md — the rendered block is stale
    (repo / "scripts" / "sysadmin" / "third.py").write_text(
        "#!/usr/bin/env python3\n# AFTER-EDIT: docs/workstation/rotation.md\n"
    )
    doc = repo / "docs" / "workstation" / "rotation.md"
    before = doc.read_text()
    assert rdsl.run(["--repo", str(repo), "--check"]) == 1, "--check must fail on a stale block"
    assert doc.read_text() == before, "--check must never mutate the tree"


def test_a_declared_doc_that_does_not_exist_is_reported_not_created(repo: Path, capsys):
    """Fail-CLOSED on a typo'd header. Creating `docs/typo.md` because a header named it would
    manufacture an empty page and make the typo look correct forever."""
    (repo / "scripts" / "sysadmin" / "typo.py").write_text(
        "#!/usr/bin/env python3\n# AFTER-EDIT: docs/workstation/rotaton.md\n"
    )
    rc = rdsl.run(["--repo", str(repo)])
    out = capsys.readouterr().out
    assert not (repo / "docs" / "workstation" / "rotaton.md").exists(), "a missing doc was created"
    assert "rotaton.md" in out and "MISSING" in out, out
    assert rc == 0, "a typo'd header is reported, not a hard failure of the render"


def test_directory_and_glob_tokens_are_reported_not_rendered(repo: Path, capsys):
    """`docs/orchestrator/` and `docs/**` satisfy the header check but cannot be inverted into a
    single page. Silently dropping them would hide a real coupling from the doc side."""
    (repo / "scripts" / "sysadmin" / "wide.py").write_text(
        "#!/usr/bin/env python3\n# AFTER-EDIT: docs/workstation/\n"
    )
    rdsl.run(["--repo", str(repo)])
    out = capsys.readouterr().out
    assert "wide.py" in out and "NOT-A-PAGE" in out, out
    rotation = (repo / "docs" / "workstation" / "rotation.md").read_text()
    assert "wide.py" not in rotation, "a directory token was rendered into a page anyway"


def test_never_writes_into_corpus_governance_or_frozen_artifacts(tmp_path: Path, capsys):
    """THE BLAST-RADIUS GUARD, and the reason this test exists at all: `# AFTER-EDIT:` answers
    "what must I update when this changes", so its targets include surfaces a generated block
    must never reach.

      * `commands/_sources/**` is RENDERED box-wide — a block here ships into every installed
        command and skill on the machine;
      * `templates/**` is fleet-synced into ~46 project repos by the post-commit sync;
      * a CONVERGED spec/plan's status is an md5 of its content — appending voids the claim AND
        the shape `check_convergence.py` reads;
      * CHANGELOG/INDEX/PORTS/DECISIONS are Doc Sync Matrix targets named by dozens of scripts
        each; "the related scripts of CHANGELOG.md" is every script there is.

    Nine scripts declare a `commands/_sources/*.md` file in this repo today. Without this guard
    the first render would have written into all nine."""
    (tmp_path / "scripts").mkdir()
    for name, target in [
        ("corpus.py", "commands/_sources/fabrik-review.md"),
        ("gov.py", "templates/governance/CLAUDE.md"),
        ("spec.py", "docs/superpowers/specs/2026-01-01-x-design.md"),
        ("plan.py", "docs/development/plans/2026-01-01-plan-1-x.md"),
        ("ledger.py", "docs/DECISIONS.md"),
        ("root.py", "CHANGELOG.md"),
        ("ok.py", "docs/reference/real-subsystem.md"),
    ]:
        (tmp_path / "scripts" / name).write_text(
            f"#!/usr/bin/env python3\n# AFTER-EDIT: {target}\n"
        )
        t = tmp_path / target
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(f"# {target}\n\nProse.\n")

    assert rdsl.run(["--repo", str(tmp_path)]) == 0
    for forbidden in (
        "commands/_sources/fabrik-review.md",
        "templates/governance/CLAUDE.md",
        "docs/superpowers/specs/2026-01-01-x-design.md",
        "docs/development/plans/2026-01-01-plan-1-x.md",
        "docs/DECISIONS.md",
        "CHANGELOG.md",
    ):
        assert rdsl.BEGIN not in (tmp_path / forbidden).read_text(), (
            f"a generated block was written into {forbidden}"
        )
    # and the one legitimate page still gets its block — an exclusion that excluded everything
    # would pass every assertion above while doing nothing at all
    assert rdsl.BEGIN in (tmp_path / "docs/reference/real-subsystem.md").read_text()
    assert "scripts/ok.py" in (tmp_path / "docs/reference/real-subsystem.md").read_text()


def test_a_symlinked_script_is_skipped_entirely(tmp_path: Path, capsys):
    """A symlink's `# AFTER-EDIT:` targets are resolved in its TARGET's world. The hub symlinks
    `scripts/verify_prod_parity.py` at a scaffold template that names `docs/DEPLOYMENT.md` — a
    file every seeded PROJECT has and the hub does not. Reporting it MISSING on every run is a
    finding that is always wrong, and always-wrong findings are how a report stops being read."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "templates").mkdir()
    real = tmp_path / "templates" / "stub.py"
    real.write_text("#!/usr/bin/env python3\n# AFTER-EDIT: docs/DEPLOYMENT.md\n")
    (tmp_path / "scripts" / "stub.py").symlink_to(real)
    assert rdsl.run(["--repo", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "MISSING" not in out, out


def test_an_uncommitted_script_is_already_coupled(tmp_path: Path):
    """`git ls-files` lists TRACKED files, and a new script is not tracked until its first commit
    — so a tracked-only enumeration makes a new coupling invisible to the gate that runs BEFORE
    that commit, landing the doc side one commit late. Caught by running this renderer on itself:
    it wrote no block into its own reference doc, because it could not see itself."""
    import subprocess as sp

    sp.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "docs" / "reference").mkdir(parents=True)
    (tmp_path / "docs" / "reference" / "thing.md").write_text("# Thing\n")
    (tmp_path / "scripts" / "brand_new.py").write_text(
        "#!/usr/bin/env python3\n# AFTER-EDIT: docs/reference/thing.md\n"
    )
    assert (
        sp.run(
            ["git", "-C", str(tmp_path), "ls-files", "scripts"], capture_output=True, text=True
        ).stdout.strip()
        == ""
    ), "fixture invalid: the script must be UNtracked"
    assert rdsl.run(["--repo", str(tmp_path)]) == 0
    assert "scripts/brand_new.py" in (tmp_path / "docs" / "reference" / "thing.md").read_text()


def test_a_half_deleted_block_is_reported_not_duplicated(repo: Path, capsys):
    """A page whose END marker was hand-deleted (or lost to a merge resolution) must NOT get a
    second block appended: that leaves two BEGINs and one END, and every later render appends
    another copy, so the page grows per run and no reader can tell which list is current.

    Reachable without malice — the block sits at the end of a file people edit."""
    doc = repo / "docs" / "workstation" / "board.md"
    rdsl.run(["--repo", str(repo)])
    doc.write_text(doc.read_text().replace(rdsl.END, ""))  # END hand-deleted
    assert rdsl.run(["--repo", str(repo)]) == 0
    out = capsys.readouterr().out
    assert "MALFORMED" in out and "board.md" in out, out
    assert doc.read_text().count(rdsl.BEGIN) == 1, "a second block was appended onto a half-block"


@pytest.fixture
def ratchet_repo(tmp_path: Path) -> Path:
    import subprocess as sp

    sp.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "a.py").write_text("#!/usr/bin/env python3\n# AFTER-EDIT: none\n")
    return tmp_path


def test_coverage_ratchet_seeds_then_blocks_a_rise(ratchet_repo: Path):
    """THE BACKFILL TEETH (operator ruling 2026-09-06). `check_script_headers` is touch-on-change
    by design — "a script gains its header the next time it is edited" — which grandfathers every
    script nobody touches (427 across 36 of 44 repos at the last audit). The ratchet makes the
    debt one-directional: seed today's number blocking nothing, then never let it rise."""
    code, msg = rdsl.ratchet(ratchet_repo, write=True)
    assert code == 0 and "SEEDED" in msg, msg
    assert (ratchet_repo / rdsl.BASELINE).is_file(), "the baseline must travel with the repo"

    (ratchet_repo / "scripts" / "b.py").write_text("print(1)\n")  # a new HEADERLESS script
    code, msg = rdsl.ratchet(ratchet_repo, write=True)
    assert code == 1, "a rise in headerless scripts must FAIL"
    assert "ROSE" in msg and "scripts/b.py" in msg, msg


def test_coverage_ratchet_tightens_and_locks_at_zero(ratchet_repo: Path):
    """A run that backfills must TIGHTEN the floor, so the debt cannot be re-borrowed later."""
    (ratchet_repo / "scripts" / "b.py").write_text("print(1)\n")
    rdsl.ratchet(ratchet_repo, write=True)  # seeds at 1
    (ratchet_repo / "scripts" / "b.py").write_text("# AFTER-EDIT: none\nprint(1)\n")  # backfilled
    code, msg = rdsl.ratchet(ratchet_repo, write=True)
    assert code == 0 and "LOCKED at zero" in msg, msg
    (ratchet_repo / "scripts" / "c.py").write_text("print(1)\n")  # try to re-borrow
    assert rdsl.ratchet(ratchet_repo, write=True)[0] == 1, "zero must lock permanently"


def test_an_after_edit_line_inside_a_docstring_is_not_a_declaration(ratchet_repo: Path):
    """It must count as headerless. Three hub scripts carried their `# AFTER-EDIT:` INSIDE the
    module docstring; a naive `grep '#\\s*AFTER-EDIT'` reads them as headered, the real parser
    (comment tokens only) does not — so a backfill driven by grep skips exactly the files that
    need it, and reports 212/212 when the truth is 209/212. That happened."""
    (ratchet_repo / "scripts" / "d.py").write_text(
        '#!/usr/bin/env python3\n"""Docs.\n\n# AFTER-EDIT: docs/x.md\n"""\n'
    )
    assert "scripts/d.py" in rdsl.uncoupled(ratchet_repo), (
        "a declaration inside a docstring was counted as a real header"
    )


# --- review pass 1 (2026-09-06), E1/E2/E3 ----------------------------------------------------------
def _git_repo(tmp_path: Path) -> Path:
    import subprocess as sp

    sp.run(["git", "init", "-q", str(tmp_path)], check=True)
    sp.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], check=True)
    sp.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "docs" / "reference").mkdir(parents=True)
    (tmp_path / "docs" / "reference" / "thing.md").write_text("# Thing\n")
    (tmp_path / "scripts" / "a.py").write_text("# AFTER-EDIT: docs/reference/thing.md\n")
    sp.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    sp.run(["git", "-C", str(tmp_path), "commit", "-qm", "base"], check=True)
    return tmp_path


def test_gate_modes_ignore_a_siblings_untracked_unstaged_script(tmp_path):
    """E1/E2: on a three-session tree a sibling's untracked scratch script under scripts/ entered
    the graph and could red the BLOCKING --check (a stale block) or raise the ratchet for everyone.
    Gate modes see tracked + STAGED files only; a plain render may still include untracked."""
    repo = _git_repo(tmp_path)
    rdsl.run(["--repo", str(repo)])
    assert rdsl.run(["--repo", str(repo), "--check"]) == 0
    (repo / "scripts" / "sibling_scratch.py").write_text(
        "# AFTER-EDIT: docs/reference/thing.md\nprint(1)\n"
    )
    assert rdsl.run(["--repo", str(repo), "--check"]) == 0, (
        "an unstaged sibling scratch script must not red --check"
    )
    (repo / "scripts" / "sibling_headerless.py").write_text("print(2)\n")
    rdsl.run(["--repo", str(repo), "--coverage"])  # seeds at the TRACKED+STAGED count: 0
    code, _ = rdsl.ratchet(repo, write=False)
    assert code == 0, "an unstaged headerless scratch file must not raise the ratchet"


def test_gate_modes_do_see_a_staged_new_script(tmp_path):
    """The other half: a script YOU staged is about to be committed — its coupling counts."""
    import subprocess as sp

    repo = _git_repo(tmp_path)
    rdsl.run(["--repo", str(repo)])
    (repo / "scripts" / "mine.py").write_text("# AFTER-EDIT: docs/reference/thing.md\n")
    sp.run(["git", "-C", str(repo), "add", "scripts/mine.py"], check=True)
    assert rdsl.run(["--repo", str(repo), "--check"]) == 1, (
        "a staged new coupling must be visible to --check"
    )


def test_crlf_doc_round_trips_and_stays_idempotent(tmp_path):
    """E3 (PLAUSIBLE → discharged): marker_state/apply_block on a CRLF page."""
    doc = "# D\r\n\r\nProse.\r\n"
    a = rdsl.apply_block(doc, ["scripts/x.py"])
    assert rdsl.marker_state(a) == "ok"
    assert rdsl.apply_block(a, ["scripts/x.py"]) == a
    assert rdsl.apply_block(a, []).rstrip("\r\n") == "# D\r\n\r\nProse.".rstrip("\r\n")
