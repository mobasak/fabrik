"""/fabrik-review queue — the text defects (D-711: a verdict showing the command text WRONG is edited).

Each test asserts the corrected sentence through its closing delimiter (an appended qualifier is a mutation), in
every file that carries it, and where the sentence describes a tool, drives that tool to show the behaviour the
sentence now states (the old text promised more than the tool does).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "commands" / "_sources" / "fabrik-review.md"
FRAG = REPO / "commands" / "_fragments"


def _norm(p: Path) -> str:
    return " ".join(p.read_text(encoding="utf-8").split())


def test_the_closing_pass_confirms_zero_defects_present_not_claims_executed_true() -> None:
    """Ledger claims state DEFECTS (STILL_TRUE = the defect persists), so 'every claim executed true' read as
    'every defect still there' (rows 1791354017, 1791146542) — in term-coverage and its term-edit mirror."""
    tc = _norm(FRAG / "term-coverage.md")
    te = _norm(FRAG / "term-edit.md")
    assert (
        "in which those seats RE-EXECUTED every claim of their slice ledgers and CONFIRMED zero code or doc "
        "defects present (none persisting, none the fix introduced) (D-206, D-335)."
    ) in tc
    assert (
        "the pass in which the round-1 seats re-executed every claim of their OWN slice ledgers and confirmed "
        "zero code or doc defects present — the same seat per slice"
    ) in te
    for t in (tc, te):
        assert "ledgers executed true" not in t


def test_a_fix_touched_slice_with_no_candidate_is_added_by_hand(tmp_path: Path) -> None:
    """Row 1791235921, then intel mail 01M54XR3QS (D-933): `next` reads no diff — it carries the ids passed and,
    with the run file, the claims the run left open, but never makes a row for this pass's fix hunk, so a slice
    whose file a fix edited but which raised nothing is added by the lead (with `--args`, printed `not carried`)."""
    import json

    tc = _norm(FRAG / "term-coverage.md")
    assert (
        "a slice a fix hunk touched holds one even when it raised no candidate, and "
        "`review_loop_ledger.py next` reads no diff: it carries the `--ids` passed and, with `--args <the workflow's "
        "run file>`, the claims the run's verdicts or launch-ledger rows leave open, but never a row for a hunk "
        "this pass's fix added, so add that slice's ledger by hand (under `--args`, copy the slice's whole "
        "launch entry from the run file's `args.slices`, which stderr then names `not carried`), one row per "
        "hunk — "
        '`{id: "<slice>-X<n>", file, line, claim: "the fix hunk at <file:line> introduced a defect"}`), or any '
        "claim"
    ) in tc
    assert "builds slices only from the `--ids` passed" not in tc
    pass_file = tmp_path / "pass.json"
    pass_file.write_text(
        json.dumps(
            {
                "candidates": [
                    {"id": "A-S1", "file": "a.py", "line": 1, "claim": "a", "seat": "find:A:sonnet"},
                    {"id": "A-S2", "file": "a.py", "line": 2, "claim": "b", "seat": "find:A:sonnet"},
                ],
                "verdicts": [],
                "ledger_status": [],
            }
        )
    )
    run = tmp_path / "run.json"
    cand = {"file": "a.py", "failure_class": "logic", "seat": "sonnet"}
    run.write_text(
        json.dumps(
            {
                "runId": "wf_t",
                "args": {"slices": [{"name": "A", "files": ["a.py"]}, {"name": "B", "files": ["b.py"]}]},
                "result": {
                    "slices": [
                        {
                            "name": "A",
                            "candidates": [
                                {**cand, "id": "A-S1", "line": 1, "claim": "a"},
                                {**cand, "id": "A-S2", "line": 2, "claim": "b"},
                            ],
                            "verdicts": [
                                {"id": "A-S1", "verdict": "confirmed", "command": "c", "output": "o"},
                                {"id": "A-S2", "verdict": "unverified", "command": "c", "output": "o"},
                            ],
                        },
                        {"name": "B"},
                    ]
                },
            }
        )
    )
    tool = REPO / "scripts" / "review_loop_ledger.py"
    r = subprocess.run(
        [sys.executable, str(tool), "next", str(pass_file), "--ids", "A-S1", "--args", str(run)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    got = {sl["name"]: [row["id"] for row in sl["ledger"]] for sl in json.loads(r.stdout)}
    assert got == {"A": ["A-S1", "A-S2"]}, got
    assert "CARRIED A-S2" in r.stderr, r.stderr
    assert "not carried: B" in r.stderr, "a fix-touched slice with nothing to carry is left to the lead"
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import review_loop_ledger as rl
    finally:
        sys.path.pop(0)
    doc = {
        "candidates": [
            {"id": "A-1", "file": "a.py", "line": 3, "claim": "x"},
            {"id": "B-1", "file": "b.py", "line": 9, "claim": "y"},
        ]
    }
    assert [s["name"] for s in rl.next_ledger(doc, ["A-1"])] == ["A"], (
        "slice B is built only when its id is passed"
    )


def test_the_pre_pin_sweep_lists_the_pinned_literal_term_only(tmp_path: Path) -> None:
    """Rows 1790688796, 1790913510, 1791083066: `--claim` lists the literal term (case- and wrap-tolerant) in
    the --surface files, a directory walking only .md/.py — so a reworded mirror or another file type is not
    listed; the text now says so (term-coverage and its term-edit mirror) and orders the repo grep."""
    want = (
        "lists every line of the pinned surface where a rewritten claim's literal term occurs (case- and "
        "wrap-tolerant; a directory surface walks only its `.md` and `.py` files); a mirror outside the pin or "
        "in other words is not in that list, so also grep the repo for the term and two rewordings of the "
        "claim, and read each site before the pin"
    )
    assert want in _norm(FRAG / "term-coverage.md")
    assert want in _norm(FRAG / "term-edit.md")
    for t in (_norm(FRAG / "term-coverage.md"), _norm(FRAG / "term-edit.md")):
        assert "lists every mirror site" not in t
    d = tmp_path / "pin"
    d.mkdir()
    (d / "a.md").write_text("alpha\nthe STOP\nkey fires here\n", encoding="utf-8")  # case + wrap
    (d / "b.py").write_text("# the stop key\n", encoding="utf-8")
    (d / "c.yaml").write_text("the stop key: 1\n", encoding="utf-8")
    (d / "e.md").write_text("the halt key triggers\n", encoding="utf-8")
    p = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "enforcement" / "check_review_hygiene.py"),
            "--surface",
            "pin",
            "--claim",
            "stop key",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "a.md:2" in p.stdout and "b.py:1" in p.stdout, p.stdout
    assert "c.yaml" not in p.stdout and "e.md" not in p.stdout, p.stdout


def test_a_trimmed_round_one_sweeps_its_unread_slices_before_any_delta_pass() -> None:
    """Row 1790926480: round 1 is the only full pass, so unread slices were never 'next round' work —
    subagents-core and its term-edit mirror."""
    sc = _norm(FRAG / "subagents-core.md")
    te = _norm(FRAG / "term-edit.md")
    assert (
        "then the union is NOT the full pass: the receipt names the unread slices, and further full-pass waves "
        "over those slices alone run before any delta pass, since round 1 is not complete until every slice is "
        "read."
    ) in sc
    assert (
        "then the union is NOT the full pass, the ledger names the unread slices and further full-pass waves "
        "over those slices alone run before any delta pass;"
    ) in te
    assert "re-sweeps them next round" not in sc and "the next round sweeps them first" not in te


def test_a_synced_path_matching_its_lock_entry_is_a_sync_write_never_reverted(
    tmp_path: Path,
) -> None:
    """Row 1790455114: on a re-vendor diff every synced file is in the diff by design. The lock entry tells a
    sync's write from a local edit; the check also passes with NO lock, so the text never says 'passes'."""
    import hashlib
    import json

    chk = [
        sys.executable,
        str(REPO / "scripts" / "enforcement" / "check_synced_unmodified.py"),
        "--project-root",
        str(tmp_path),
    ]
    (tmp_path / "AGENTS.md").write_text("synced\n", encoding="utf-8")
    assert subprocess.run(chk, capture_output=True, text=True, check=False).returncode == 0, (
        "no lock: passes"
    )
    (tmp_path / ".fabrik").mkdir()
    md5 = hashlib.md5(b"synced\n", usedforsecurity=False).hexdigest()
    (tmp_path / ".fabrik" / "synced.lock").write_text(
        json.dumps({"AGENTS.md": md5}), encoding="utf-8"
    )
    assert subprocess.run(chk, capture_output=True, text=True, check=False).returncode == 0, (
        "matches its entry"
    )
    (tmp_path / "AGENTS.md").write_text("edited\n", encoding="utf-8")
    assert subprocess.run(chk, capture_output=True, text=True, check=False).returncode == 1, (
        "a local edit reds"
    )


def test_the_gate_writes_and_lints_only_staged_and_unpushed_work(tmp_path: Path) -> None:
    """W-b63ffe1a: CLAUDE.md (hub and template) say the fixers and ruff take only STAGED changes plus unpushed
    commits, and that a bare run re-stages only what was staged at its start. Drive get_writable_files on a
    scratch repo with an upstream: a staged file and an unpushed commit's file are in it; an unstaged edit to a
    tracked file is not (it stays in the READ scope)."""
    for rel in ("CLAUDE.md", "templates/governance/CLAUDE.md"):
        assert (
            "a bare run auto-fixes **only the files your change touched** — every fixer + `ruff` is scoped to "
            "your STAGED changes plus your committed-but-unpushed commits, and an unstaged edit is left alone "
            "until you stage it — and re-stages only what was staged when it started, so a committed file it "
            "fixes is left unstaged for you to commit."
        ) in _norm(REPO / rel), rel
    flow = _norm(REPO / "docs" / "workflows" / "FINAL_GATE_WORKFLOW.md")
    assert (
        "its fixers and `ruff` to the narrower WRITE scope, staged + committed-but-unpushed"
    ) in flow
    remote, work = tmp_path / "remote.git", tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    g = [
        "git",
        "-C",
        str(work),
        "-c",
        "user.email=t@t",
        "-c",
        "user.name=t",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "commit.gpgsign=false",
    ]  # a developer's global hook or signing key must not fail the probe
    subprocess.run(["git", "init", "-q", str(work)], check=True)
    (work / "tracked.py").write_text("a = 1\n", encoding="utf-8")
    subprocess.run([*g, "add", "tracked.py"], check=True)
    subprocess.run([*g, "commit", "-q", "-m", "base"], check=True)
    subprocess.run([*g, "remote", "add", "origin", str(remote)], check=True)
    subprocess.run([*g, "push", "-q", "-u", "origin", "HEAD"], check=True, capture_output=True)
    (work / "unpushed.py").write_text("c = 1\n", encoding="utf-8")
    subprocess.run([*g, "add", "unpushed.py"], check=True)
    subprocess.run([*g, "commit", "-q", "-m", "local"], check=True)
    (work / "tracked.py").write_text("a = 2\n", encoding="utf-8")  # unstaged edit to a tracked file
    (work / "staged.py").write_text("b = 1\n", encoding="utf-8")
    subprocess.run([*g, "add", "staged.py"], check=True)
    probe = (
        f"import sys; sys.path.insert(0, {str(REPO / 'scripts')!r}); import final_gate as fg; "
        "print(sorted(fg.get_writable_files())); print(sorted(fg.get_changed_files()))"
    )
    p = subprocess.run(
        [sys.executable, "-c", probe], cwd=work, capture_output=True, text=True, check=True
    )
    writable, changed = p.stdout.splitlines()[-2:]
    assert writable == "['staged.py', 'unpushed.py']", p.stdout
    assert "tracked.py" in changed, "the READ scope still sees the unstaged edit"


def test_the_subagents_pack_closing_pass_confirms_zero_defects_present() -> None:
    """W-b63ffe1a: 62-using-subagents.md mirrored the retired 'confirming every claim executed true'."""
    t = _norm(REPO / ".windsurf" / "rules" / "core" / "62-using-subagents.md")
    assert (
        "The closing pass is those same seats re-executing every claim of their slice ledgers and confirming "
        "zero code or doc defects present** —"
    ) in t
    assert "confirming every claim executed true" not in t
    perf = _norm(REPO / "docs" / "reference" / "command-loop-performance.md")
    assert "slice's ledger of claims is re-executed with zero defects confirmed present" in perf


def test_each_next_recipe_points_at_args_and_the_scripts_doc() -> None:
    """Intel mail 01M54XR3QS (D-933): each review recipe that runs `next … --ids <the confirmed ids>` adds
    `--args <a scratch copy of the run file>` whenever the run file exists and has the lead read its stderr,
    pointing at the script's doc, inside the same recipe sentence; the scoped one also trims `models`."""
    srcs = REPO / "commands" / "_sources"
    pointer = "`/opt/fabrik/docs/reference/review-loop-workflow.md`"
    for name in ("fabrik-review", "fabrik-review-scoped", "fabrik-spec-review", "fabrik-plan-review"):
        text = _norm(srcs / f"{name}.md")
        at = text.index("--ids <the confirmed ids>`")
        window = text[at : at + 700]
        assert "`--args <a scratch copy of the run file>`" in window, name
        assert "whenever that file exists" in window, name
        assert "read its stderr either way" in window, name
        assert pointer in window, name
    scoped = _norm(srcs / "fabrik-review-scoped.md")
    at = scoped.index("--ids <the confirmed ids>`")
    assert "which you trim to those seats and stamp at the trimmed count" in scoped[at : at + 700]
    review = _norm(srcs / "fabrik-review.md")
    at = review.index("which keeps its `files`)")
    assert "so its stdout, plus each `not carried` slice a fix hunk touched, is the next launch's `slices`" in (
        review[at : at + 400]
    )
