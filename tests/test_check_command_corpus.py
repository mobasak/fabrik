"""Behaviour tests for the command-corpus integrity check.

Each test names a defect class the 2026-08-16 corpus audit found LIVE, and proves
the check goes red on it. The path-look-alike test is the important negative: a
naive matcher "finds" four broken chains in `/opt/fabrik-lib`, `/run/fabrik-autoheal`
and `docs/reference/fabrik-mail.md` that were never broken, and a check that cries
wolf gets ignored — which is how a real break then ships.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "enforcement"))
sys.path.insert(0, str(REPO / "commands"))

from check_command_corpus import audit  # noqa: E402


@pytest.fixture
def corpus(tmp_path: Path):
    """A minimal two-command corpus; the callable writes the file under test."""
    src, frag = tmp_path / "_sources", tmp_path / "_fragments"
    src.mkdir()
    frag.mkdir()
    # Every fixture command carries a run record unless a test opts out: predicate 5
    # applies to the whole corpus, so a bare sibling would pollute every other test.
    (src / "fabrik-real.md").write_text("a real sibling command\n{{include:run-record}}\n")

    def write(body: str, *, with_record: bool = True) -> list[str]:
        prefix = "{{include:run-record}}\n" if with_record else ""
        (src / "fabrik-probe.md").write_text(prefix + body)
        return audit(
            src, frag, tmp_path / "no-assembler.py", REPO, traycer_skills=tmp_path / "no-orch"
        )

    return write


def test_provider_name_in_web_tools_is_caught(corpus):
    """The founding defect: provider names where tool names belong ⇒ agent runs blind."""
    problems = corpus('fanout("research", web_tools=["exa","brave","firecrawl","context7"])\n')
    assert problems, "the provider-name defect must be caught"
    joined = " ".join(problems)
    assert "'exa'" in joined and "'context7'" in joined, joined
    assert "runs blind" in joined


def test_real_web_tool_names_pass(corpus):
    assert corpus('fanout("research", web_tools=["web_search","web_scrape","docs_lookup"])\n') == []


def test_dangling_chain_reference_is_caught(corpus):
    problems = corpus("when done run /fabrik-nonexistent to continue\n")
    assert any("/fabrik-nonexistent" in p for p in problems)


def test_path_lookalikes_are_not_chain_references(corpus):
    """`/opt/fabrik-lib` is a directory, not a dead command — never flag it."""
    assert (
        corpus(
            "vendor from /opt/fabrik-lib, the pause marker is /run/fabrik-autoheal/pause,\n"
            "and the mailbox doc is docs/reference/fabrik-mail.md — then run /fabrik-real\n"
        )
        == []
    )


def test_missing_script_path_is_caught(corpus):
    problems = corpus("run `scripts/enforcement/check_totally_absent.py --json`\n")
    assert any("check_totally_absent.py" in p for p in problems)


def test_existing_script_path_passes(corpus):
    assert corpus("run `scripts/enforcement/check_command_corpus.py`\n") == []


def test_stale_trailer_model_is_caught(corpus):
    """Six live templates stamped a retired model into provenance trailers."""
    problems = corpus("Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>\n")
    assert any("Opus 4.8" in p for p in problems)


def test_empty_corpus_is_reported_not_silently_green(tmp_path: Path):
    """A check that finds nothing to audit must say so — silence would be vacuous."""
    src, frag = tmp_path / "_sources", tmp_path / "_fragments"
    src.mkdir()
    frag.mkdir()
    problems = audit(src, frag, tmp_path / "absent.py", REPO, traycer_skills=tmp_path / "no-orch")
    assert problems and "nothing to audit" in problems[0]


def test_live_corpus_is_clean():
    """The shipped corpus itself must satisfy the check."""
    assert audit() == []


def test_command_without_a_run_record_is_caught(corpus):
    """CLAUDE.md makes the record the first act; 24 of 27 commands never opened one."""
    problems = corpus("a command body that never opens a run record\n", with_record=False)
    assert any("opens no run record" in p for p in problems)


def test_bespoke_start_block_satisfies_the_run_record(corpus):
    """A command with its own `start` block needs no fragment — both forms count."""
    assert (
        corpus(
            "run `python3 scripts/command_run.py start --command x --phases 3`\n", with_record=False
        )
        == []
    )


def test_phase_count_prefers_explicit_phase_headings():
    from assemble_commands import _phase_count  # noqa: PLC0415

    assert _phase_count("## Phase 0 — a\n## Phase 1 — b\n## Phase 2 — c\n") == 3
    assert _phase_count("## PHASE 0 — a\n## PHASE 1 — b\n") == 2


def test_phase_count_ignores_a_lone_phase_heading_among_real_sections():
    """A single `Phase 0` plus branch sections is not a one-phase command (fabrik-release)."""
    from assemble_commands import _phase_count  # noqa: PLC0415

    text = "## Termination\n## Phase 0 — resolve\n## VPS path\n## MOBILE path\n## Output\n"
    assert _phase_count(text) == 5


def test_phase_count_never_returns_zero():
    """`--phases 0` would make a record that can never show progress."""
    from assemble_commands import _phase_count  # noqa: PLC0415

    assert _phase_count("prose with no headings at all\n") == 1


# --- The orchestrator corpus (docs/orchestrator/_traycer-skills wrappers + their docs) ---------


def _orch_fixture(tmp_path: Path, *, wrapper_extra: str = "", doc_body: str = "step body\n"):
    """One generated-style wrapper + its canonical doc, isolated from the real tree."""
    skills = tmp_path / "_traycer-skills" / "fab-mega-99-probe"
    skills.mkdir(parents=True, exist_ok=True)
    doc = tmp_path / "docs" / "orchestrator" / "probe" / "99-probe.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(doc_body)
    skills.joinpath("SKILL.md").write_text(
        "<!-- GENERATED by /opt/fabrik/commands/assemble_commands.py -->\n"
        "`/opt/fabrik/docs/orchestrator/probe/99-probe.md`\n" + wrapper_extra
    )
    return tmp_path / "_traycer-skills"


def test_generated_orch_wrapper_without_a_run_record_is_a_defect(tmp_path: Path):
    """The whole reason the wrappers are generated now: the record must ride them.

    Measured 2026-08-16: zero of the four mega wrappers opened a run record, so the pinned
    RUN: line and the Stop hook's fifth cause were disarmed on the widest-blast-radius chain.
    """
    src, frag = tmp_path / "_sources", tmp_path / "_fragments"
    src.mkdir(), frag.mkdir()
    (src / "fabrik-real.md").write_text("x\n{{include:run-record}}\n")
    orch = _orch_fixture(tmp_path)
    problems = audit(src, frag, tmp_path / "absent.py", tmp_path, traycer_skills=orch)
    assert any("opens no run record" in p for p in problems)
    # and the same wrapper WITH the record is clean
    orch2 = _orch_fixture(tmp_path, wrapper_extra="command_run.py start --command x\n")
    problems2 = audit(src, frag, tmp_path / "absent.py", tmp_path, traycer_skills=orch2)
    assert not any("opens no run record" in p for p in problems2)


def test_orch_wrapper_pointing_at_a_missing_doc_is_a_defect(tmp_path: Path):
    """A wrapper aiming agents at nothing is the corpus's founding failure shape."""
    src, frag = tmp_path / "_sources", tmp_path / "_fragments"
    src.mkdir(), frag.mkdir()
    (src / "fabrik-real.md").write_text("x\n{{include:run-record}}\n")
    orch = _orch_fixture(tmp_path, wrapper_extra="command_run.py start\n")
    (tmp_path / "docs" / "orchestrator" / "probe" / "99-probe.md").unlink()
    problems = audit(src, frag, tmp_path / "absent.py", tmp_path, traycer_skills=orch)
    assert any("does not exist — the wrapper points agents at nothing" in p for p in problems)


def test_template_shipped_scripts_resolve(tmp_path: Path):
    """Template delivery resolves ORCH-doc refs only; a hub command's ref stays hub-rooted.

    History in two turns: hub-rooting alone called five live orchestrator references dead
    (they ship via templates/i18n-kit), so a templates/** fallback was added — corpus-wide,
    which the next review showed masks a genuinely deleted HUB script whose name survives in
    a scaffold template. The fallback is now scoped to orchestrator docs (project context);
    `test_templates_fallback_is_orch_scoped_and_files_only` covers the full matrix.
    """
    src, frag = tmp_path / "_sources", tmp_path / "_fragments"
    src.mkdir(), frag.mkdir()
    t = tmp_path / "templates" / "kit" / "scripts" / "shipped_by_scaffold.py"
    t.parent.mkdir(parents=True)
    t.write_text("#\n")
    (src / "fabrik-real.md").write_text(
        "run scripts/shipped_by_scaffold.py\nrun scripts/never_anywhere.py\n{{include:run-record}}\n"
    )
    problems = audit(
        src, frag, tmp_path / "absent.py", tmp_path, traycer_skills=tmp_path / "no-orch"
    )
    assert any("shipped_by_scaffold" in p for p in problems), (
        "a HUB command referencing a template-only script is a dead hub ref — must stay flagged"
    )
    assert any("never_anywhere" in p for p in problems)


def test_every_wrapper_must_open_a_run_record_banner_or_not(tmp_path: Path):
    """Deleting the GENERATED banner exempted a wrapper from the one thing the predicate proves.

    Reproduced 2026-08-18; the carve-out died when the whole set (mega + ettw) came under
    generation — a hand-written wrapper now fails until added to ORCH_SOURCES, which is the fix.
    """
    src, frag = tmp_path / "_sources", tmp_path / "_fragments"
    src.mkdir(), frag.mkdir()
    (src / "fabrik-real.md").write_text("x\n{{include:run-record}}\n")
    orch = _orch_fixture(tmp_path)  # GENERATED banner, no record
    # strip the banner — v1 read that as an exemption
    w = orch / "fab-mega-99-probe" / "SKILL.md"
    w.write_text(
        w.read_text().replace(
            "<!-- GENERATED by /opt/fabrik/commands/assemble_commands.py -->\n", ""
        )
    )
    problems = audit(src, frag, tmp_path / "absent.py", tmp_path, traycer_skills=orch)
    assert any("opens no run record" in p for p in problems), (
        "an unbannered wrapper with no record slipped the requirement — banner-stripping is an exemption again"
    )


def test_traversal_in_the_doc_pointer_is_refused(tmp_path: Path):
    src, frag = tmp_path / "_sources", tmp_path / "_fragments"
    src.mkdir(), frag.mkdir()
    (src / "fabrik-real.md").write_text("x\n{{include:run-record}}\n")
    skills = tmp_path / "_traycer-skills" / "fab-mega-98-esc"
    skills.mkdir(parents=True)
    outside = tmp_path / "secrets.md"
    outside.write_text("outside\n")
    skills.joinpath("SKILL.md").write_text(
        "`/opt/fabrik/docs/orchestrator/../../secrets.md`\ncommand_run.py start\n"
    )
    problems = audit(
        src, frag, tmp_path / "absent.py", tmp_path, traycer_skills=tmp_path / "_traycer-skills"
    )
    assert any("escapes docs/orchestrator" in p for p in problems)


def test_project_with_orch_dir_but_no_corpus_stays_silent_and_does_not_crash(tmp_path: Path):
    """The fleet hazard: a project acquiring _traycer-skills/ must be silently N/A.

    Honesty note (closing-sweep finding): this fixture cannot reproduce v1's actual crash —
    v1's `_live_web_tool_names()` read the module-level REPO (the real hub, which has
    libs/subagents), so the ModuleNotFoundError only fired in a genuinely separate repo. What
    this test DOES pin: (a) the ordering fix — the orch section never runs without a hub
    corpus, so the 28 bogus chain-ref problems v1 emitted here are gone; (b) the None-sentinel
    below, which is the guard that would stop the crash in a repo without the pool vendored.
    """
    _orch_fixture(tmp_path, wrapper_extra="command_run.py start\n")
    problems = audit(
        tmp_path / "_sources",
        tmp_path / "_fragments",
        tmp_path / "absent.py",
        tmp_path,
        traycer_skills=tmp_path / "_traycer-skills",
    )
    assert problems == [], f"a project-shaped tree must be silently N/A, got: {problems[:3]}"
    from check_command_corpus import _live_web_tool_names  # noqa: PLC0415

    assert _live_web_tool_names(tmp_path) is None, (
        "the crash guard: a repo without libs/subagents must yield the skip-sentinel, "
        "never an import attempt (None, not an empty set — empty inverts predicate 1)"
    )


def test_hub_with_assembler_but_missing_wrapper_tree_is_a_defect(tmp_path: Path):
    src, frag = tmp_path / "_sources", tmp_path / "_fragments"
    src.mkdir(), frag.mkdir()
    (src / "fabrik-real.md").write_text("x\n{{include:run-record}}\n")
    asm = tmp_path / "assemble_commands.py"
    asm.write_text("# assembler\n")
    problems = audit(src, frag, asm, tmp_path, traycer_skills=tmp_path / "never-rendered")
    assert any("wrapper tree missing in the hub" in p for p in problems)


def test_templates_fallback_is_orch_scoped_and_files_only(tmp_path: Path):
    """A hub COMMAND naming a template-only script stays dead; an ORCH doc naming it is live;
    a DIRECTORY named like a script is not a delivery."""
    src, frag = tmp_path / "_sources", tmp_path / "_fragments"
    src.mkdir(), frag.mkdir()
    t = tmp_path / "templates" / "kit" / "scripts" / "only_in_template.py"
    t.parent.mkdir(parents=True)
    t.write_text("#\n")
    d = tmp_path / "templates" / "kit2" / "scripts" / "dir_not_file.py"
    d.mkdir(parents=True)  # a DIRECTORY with a script-shaped name
    (src / "fabrik-real.md").write_text("run scripts/only_in_template.py\n{{include:run-record}}\n")
    orch = _orch_fixture(
        tmp_path,
        wrapper_extra="command_run.py start\n",
        doc_body="run scripts/only_in_template.py\nrun scripts/dir_not_file.py\n",
    )
    problems = audit(src, frag, tmp_path / "absent.py", tmp_path, traycer_skills=orch)
    joined = "\n".join(problems)
    assert "fabrik-real.md" in joined and "only_in_template" in joined, (
        "a hub command's template-only ref must stay flagged — the fallback is orch-scoped"
    )
    assert any("dir_not_file" in p for p in problems), (
        "a directory named like a script satisfied the fallback — must be files only"
    )
    assert not any("99-probe.md" in p and "only_in_template" in p for p in problems), (
        "the orch doc's template-shipped ref must resolve"
    )


def test_hub_absolute_script_citations_are_audited(tmp_path: Path):
    """Round-5 defeat: /opt/fabrik/scripts/x.py citations were invisible to predicate 3 —
    the orchestrator docs cite almost exclusively in that form."""
    src, frag = tmp_path / "_sources", tmp_path / "_fragments"
    src.mkdir(), frag.mkdir()
    live = tmp_path / "scripts" / "really_here.py"
    live.parent.mkdir()
    live.write_text("#\n")
    (src / "fabrik-real.md").write_text(
        "run `/opt/fabrik/scripts/definitely_absent_xyz.py` then "
        "`/opt/fabrik/scripts/really_here.py`\n{{include:run-record}}\n"
    )
    problems = audit(
        src, frag, tmp_path / "absent.py", tmp_path, traycer_skills=tmp_path / "no-orch"
    )
    assert any("definitely_absent_xyz" in p for p in problems), "absolute dead citation missed"
    assert not any("really_here" in p for p in problems), "absolute LIVE citation false-flagged"


# ── Predicate 7: an advertised close must be a RUNNABLE close ────────────────────────────────


def test_an_advertised_close_without_feedback_is_caught(corpus):
    """`command_run.py done|blocked|handoff` REFUSES without `--feedback`, so a printed close
    missing it instructs a command the tool cannot accept — the record stays `running` and the
    Stop hook holds the turn open. Found live: 36 such sites (the run-record fragment, the 17
    generated orchestrator wrappers, the Stop hook) the day the refusal landed."""
    problems = corpus(
        'close it: `python3 scripts/command_run.py done --command fabrik-probe --evidence "e"`\n'
    )
    assert any("--feedback" in p for p in problems), problems


def test_all_three_close_verbs_are_policed(corpus):
    """`blocked` and `handoff` refuse identically — policing only `done` would leave the two
    dispositions a stuck run actually uses. `handoff` is what the certification gauntlets close
    NOT-QUIET runs with, so it is the likeliest close to carry machinery friction."""
    for verb, arg in (("done", "--evidence"), ("blocked", "--reason"), ("handoff", "--reason")):
        problems = corpus(
            f'`python3 scripts/command_run.py {verb} --command fabrik-probe {arg} "x"`\n'
        )
        assert any("--feedback" in p for p in problems), f"{verb} not policed: {problems}"


def test_a_compliant_close_is_silent(corpus):
    """The false-positive side. Without this, the predicate could pass by flagging everything."""
    problems = corpus(
        '`python3 scripts/command_run.py done --command fabrik-probe --evidence "e" '
        '--feedback "none — swept the corpus"`\n'
    )
    assert not any("--feedback" in p for p in problems), problems


def test_the_flag_may_wrap_to_a_continuation_line(corpus):
    """The real fragment wraps: the command opens on one line and `--feedback` lands on the next.
    A single-line window would have called every correctly-fixed site a defect."""
    problems = corpus(
        '`python3 scripts/command_run.py blocked --command fabrik-probe --reason "<what>"\n'
        '  --feedback "<what you filed, to whom | none — surfaces>"`\n'
    )
    assert not any("--feedback" in p for p in problems), problems


# ── Predicate 8: a CLAIMED caller must actually call ───────────────────────────────────────────
# Found live at cmd 13/31 (2026-08-29): `/fabrik-generate-tests` advertised itself as
# "auto-called by ... /fabrik-review reactively" while fabrik-review.md contained ZERO references
# to it. The advertised wiring did not exist — and it was concealing the real defect, that
# /fabrik-review had reproduced the whole pipeline inline instead of invoking it. A reader who
# trusts the claim believes a call happens that never does.


def test_claimed_caller_that_never_calls_is_caught(corpus):
    """The founding defect, reduced: X says Y calls it; Y never names X."""
    problems = corpus("description: auto-called by /fabrik-real per phase.\n")
    assert any("fabrik-real" in p and "wiring" in p for p in problems), problems


def test_claimed_caller_that_really_calls_is_silent(corpus, tmp_path: Path):
    """The false-positive side: a claim the alleged caller honours must stay silent."""
    (tmp_path / "_sources" / "fabrik-real.md").write_text(
        "{{include:run-record}}\nI invoke /fabrik-probe when a behavior has no test.\n"
    )
    problems = corpus("description: auto-called by /fabrik-real per phase.\n")
    assert not any("wiring" in p for p in problems), problems


def test_a_call_sites_section_makes_every_bullet_a_claim(corpus):
    """The corpus's OTHER claim form. `/fabrik-generate-tests` states its callers under a
    `## Where this auto-fires (3 call sites ...)` heading, not in a `called by` sentence — a
    predicate reading only the verb form would have passed the exact file that was wrong."""
    problems = corpus(
        "## Where this auto-fires (2 call sites)\n"
        "- **`/fabrik-real` (reactive):** when a review finds an untested behavior.\n"
    )
    assert any("fabrik-real" in p and "wiring" in p for p in problems), problems


def test_the_call_sites_section_ends_at_the_next_heading(corpus):
    """Scope discipline. If the section never closed, every command named anywhere BELOW it
    would become a fabricated 'claim' — the predicate would then invent defects at the bottom
    of every long source, which is how a check earns its way into being ignored."""
    problems = corpus(
        "## Where this auto-fires (1 call site)\n"
        "- Standalone only.\n"
        "\n## Related\n"
        "See /fabrik-real for adversarial review.\n"
    )
    assert not any("wiring" in p for p in problems), problems


def test_a_bare_mention_is_not_a_caller_claim(corpus):
    """The important negative: cross-references, SKIP routes and successor pointers name other
    commands constantly (439 such mentions across the live corpus). Treating those as claims
    would fire on 17.5% of them — measured — and a check that cries wolf gets ignored."""
    problems = corpus(
        "SKIP: adversarial code review (-> /fabrik-real).\n"
        "**Next in the pipeline:** /fabrik-real.\n"
    )
    assert not any("wiring" in p for p in problems), problems


def test_a_fenced_comment_does_not_close_the_call_sites_section(corpus):
    """Found by the review of predicate 8 itself. `_claimed_callers` treated any line starting
    with `#` as a heading, so a `# comment` inside a fenced block CLOSED the section and every
    claim below it became invisible — the check reporting success because it stopped asking."""
    problems = corpus(
        "## Where this auto-fires (2 call sites)\n"
        "- Standalone.\n"
        "\n```bash\n# a comment inside a fence\npython3 scripts/x.py\n```\n\n"
        "- **`/fabrik-real` (reactive):** when a review finds an untested behavior.\n"
    )
    assert any("fabrik-real" in p and "wiring" in p for p in problems), problems


def test_where_this_runs_is_not_a_call_sites_section(corpus):
    """`## Where this runs` in /fabrik-deploy-plan{,-review} is about which REPO you run the
    command from — hub vs project — not about who calls it. Reading its command mentions as
    caller claims fabricates a finding the day one of those pipeline neighbours stops naming
    the other; it was silent only by coincidence."""
    problems = corpus(
        "## Where this runs\n"
        "Same split as `/fabrik-real`: VPS surfaces are hub-side, store surfaces project-side.\n"
    )
    assert not any("wiring" in p for p in problems), problems


def test_an_unreadable_caller_source_does_not_crash_the_gate(corpus, monkeypatch):
    """This check is BLOCKING and runs on a tree with three concurrent sessions. `caller in
    known_commands` proves the file existed when the set was BUILT, not when it is READ — a
    sibling's rename in between raises OSError out of the gate for every session. Predicate 7,
    twenty lines above, already guards its read; predicate 8 shipped without one.

    Deleting the file up front would NOT reproduce this: `known_commands` would simply not
    contain it and the caller would be skipped. The race is strictly between those two moments,
    so the read itself is what has to fail."""
    real_read = Path.read_text

    def exploding_read(self, *a, **kw):
        if self.name == "fabrik-real.md":
            raise OSError("vanished mid-audit (sibling rename)")
        return real_read(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", exploding_read)
    problems = corpus("description: auto-called by /fabrik-real per phase.\n")
    assert isinstance(problems, list)  # the point is that it RETURNS rather than raising


def test_an_unreadable_file_is_reported_not_counted_as_audited(corpus, monkeypatch):
    """The fix for the OSError crash introduced its own fail-silent-green: `_read` skips the
    file, `audit` returns clean, and `main` prints 'all sound across N corpus file(s)' with N
    counting files COLLECTED, not files READ. A check must never claim coverage it did not have.
    """
    import check_command_corpus as ccc

    real_read = Path.read_text

    def exploding_read(self, *a, **kw):
        if self.name == "fabrik-real.md":
            raise OSError("vanished mid-audit")
        return real_read(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", exploding_read)
    corpus("a body with nothing wrong in it\n")
    assert any("fabrik-real.md" in s for s in ccc.SKIPPED), (
        f"an unread file left no trace: {ccc.SKIPPED}"
    )


def test_one_unreadable_file_is_counted_once(corpus, monkeypatch):
    """`_read` is called from four sites, so a single vanished file appended three SKIPPED
    entries and `main`'s `audited - len(SKIPPED)` over-subtracted — a denominator-honesty fix
    that lied about the denominator. Dedupe by path, and never report a negative count."""
    import check_command_corpus as ccc

    real_read = Path.read_text

    def exploding_read(self, *a, **kw):
        if self.name == "fabrik-real.md":
            raise OSError("vanished mid-audit")
        return real_read(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", exploding_read)
    corpus("description: auto-called by /fabrik-real per phase.\n")
    hits = [s for s in ccc.SKIPPED if "fabrik-real.md" in s]
    assert len(hits) == 1, f"one file, {len(hits)} entries: {ccc.SKIPPED}"


def test_the_audited_count_never_goes_negative(monkeypatch, capsys):
    """SKIPPED can name files outside `_corpus_files` (orchestrator docs), so the
    `audited - len(SKIPPED)` arithmetic can underflow into a nonsense negative denominator —
    a summary line claiming a negative number of files audited."""
    import check_command_corpus as ccc

    monkeypatch.setattr(ccc, "audit", lambda *a, **kw: [])
    monkeypatch.setattr(ccc, "_corpus_files", lambda *a, **kw: [Path("one.md")])
    ccc.SKIPPED.clear()
    ccc.SKIPPED.extend(["a.md: OSError", "b.md: OSError", "c.md: OSError"])
    ccc.AUDITED.clear()  # the denominator is what the predicates OPENED, never collected-minus-skipped (DS2)
    ccc.SKIPPED_PREDICATES.clear()  # the patched-out audit() would otherwise leave an earlier test's advisory (DW1)
    ccc.main([])
    out = capsys.readouterr().out
    assert "across 0 file(s) read" in out, out
    assert "-2 " not in out, out
    assert "(attempted 3)" in out, (
        out
    )  # the population = read + unreadable, never the read count alone (DU1/DW3)


def test_a_scriptless_close_is_still_policed(corpus):
    """Found at cmd 24/31: prose closes like `done --command x --evidence "…"` (no
    `command_run.py` on the line) were INVISIBLE to predicate 7 — and the blindness hid six
    real feedback-less closes across four commands, each instructing a close the tool refuses."""
    problems = corpus(
        '`done --command fabrik-probe --evidence "<proof>"` at the TERMINAL verdict\n'
    )
    assert any("--feedback" in p for p in problems), f"script-less close escaped: {problems}"


def test_a_scriptless_close_with_feedback_is_silent(corpus):
    problems = corpus(
        '`done --command fabrik-probe --evidence "<proof>" --feedback "<line>"` at the verdict\n'
    )
    assert not any("--feedback" in p for p in problems), problems


# ── plan 2026-09-01-plan-1-deployment-verification, Phase A: the rewritten runner's anatomy ──────


def test_deploy_verify_source_carries_parity_phase():
    """The runner's contract-driven parity phase, the UNVERIFIED vocabulary and the run-time-derived
    registrar table must be in the LIVE source — grep'd, not assumed (Phase A gate lines)."""
    src = (REPO / "commands" / "_sources" / "fabrik-deploy-verify.md").read_text(encoding="utf-8")
    assert src.count("## Phase 6 — Parity") == 1
    assert src.count("UNVERIFIED") >= 2, "Phase 0 rule + Output vocabulary"
    assert src.count("_REGISTRAR_ORDER") >= 2, "Layer 3 derived at RUN time from the live registry"
    assert "## Phase 1b — Identity" in src
    assert "verify_prod_parity.py --verdict" in src, (
        "the verdict algebra is EXECUTED, never applied in prose"
    )


def _render_corpus(tmp_path: Path):
    """Render the LIVE corpus into a temp dir through the real assembler (never the installed dir)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "asm_for_test", REPO / "commands" / "assemble_commands.py"
    )
    asm = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(asm)
    out = tmp_path / "render"
    asm.render(out, out / "_skills")
    return out


def test_deploy_checklist_renders_to_the_anatomy(tmp_path: Path):
    """Phase B (plan 2026-09-01-plan-1): the rendered authoring command carries the see-every-row-red phase,
    the header rule and the fixed Output block — the anatomy § Corpus conformance 1 prescribes."""
    out = _render_corpus(tmp_path)
    cmd = (out / "fabrik-deploy-checklist.md").read_text(encoding="utf-8")
    assert "## Phase 5 — SEE EVERY ROW RED" in cmd
    assert (
        "Status: DRAFT | FROZEN" in cmd
        and "Frozen — no agent adds, removes or re-derives a row" in cmd
    )
    assert (
        "## Output (always, last thing)" in cmd
        and "DEPLOY-CHECKLIST:" in cmd
        and "RED-SEEN:" in cmd
    )
    assert "command_run.py start --command fabrik-deploy-checklist --phases 8" in cmd, (
        "8 phases derived from the headings"
    )
    assert "{{" not in cmd, "an unresolved include/PARAMS token shipped"


def test_deploy_checklist_skill_description_within_limit(tmp_path: Path):
    """`_emit_skill` refuses a composed description over 1024 chars — the first draft composed to 1366."""
    out = _render_corpus(tmp_path)
    skill = (out / "_skills" / "fabrik-deploy-checklist" / "SKILL.md").read_text(encoding="utf-8")
    desc = next(line for line in skill.splitlines() if line.startswith("description:"))
    assert len(desc) - len("description: ") <= 1024, len(desc)
    assert "NEXT: /fabrik-release" in desc


def test_deploy_commands_name_the_pre_existing_project_paths():
    """Review 2026-09-02: the stub is seeded at SCAFFOLD time only (SCRIPT_FILES) and deliberately never
    synced (a synced copy would be gitignored and overwritten — the contract is project-owned), so every
    project scaffolded before 2026-09-02 has NO `scripts/verify_prod_parity.py` and NO fleet-AI doc
    sections. Both commands must say what to do about that, or the first real run stalls."""
    checklist = (REPO / "commands" / "_sources" / "fabrik-deploy-checklist.md").read_text()
    verify = (REPO / "commands" / "_sources" / "fabrik-deploy-verify.md").read_text()
    assert "If `scripts/verify_prod_parity.py` is absent" in checklist
    assert "templates/scaffold/scripts/verify_prod_parity.py" in checklist  # where to copy it from
    assert "never synced" in checklist  # the design reason, stated where the agent reads it
    assert (
        "sections are absent" in checklist
    )  # Phase 6: ADD the fleet-AI sections on a pre-existing project
    assert "scaffolded before 2026-09-02" in verify  # absent is the NORMAL state, routed not feared


def test_deploy_commands_carry_the_multi_site_execution_model():
    """Review 2026-09-02 (after tryton-crm's first real freeze): executed from the hub, 15 of its 27 rows
    were unreachable (every DB row, redis, the filestore, the internal renderer), so the runner's
    'run it from the project's checkout' could never reach CONFIRMED. Rows now declare a SITE and the
    runner runs one leg per site (hub · host · container), ships the gitignored vendored comparator into
    the container for its leg, keeps an unreachable leg in the denominator, and merges with --rows-from."""
    checklist = (REPO / "commands" / "_sources" / "fabrik-deploy-checklist.md").read_text()
    verify = (REPO / "commands" / "_sources" / "fabrik-deploy-verify.md").read_text()
    for needle in ('@site("container")', "--rows-from", "--unreachable", "docker cp"):
        assert needle in verify, needle
    for needle in ("@site(", "self-referential", "snapshot fallback", "floor"):
        assert needle in checklist, needle


def test_deploy_commands_declare_the_container_leg_and_test_comparators_not_examples():
    """tryton-crm's v2/v3 run: (1) the runner assumed 'the app container' — their bridge is DB-free by
    design and the DB-reaching container is `trytond`; the contract declares `CONTAINER_LEG_SERVICE` and
    the runner reads it from `--header`. (2) The comparator rule listed examples (filestore = exact,
    attachments = floor) that grow on the SAME event; the rule is the TEST — does this number change when
    a user does their job? — and coupled derived stores switch together."""
    # whitespace-normalised: the sources wrap prose at ~100 columns, so a phrase can straddle a newline
    checklist = " ".join(
        (REPO / "commands" / "_sources" / "fabrik-deploy-checklist.md").read_text().split()
    )
    verify = " ".join(
        (REPO / "commands" / "_sources" / "fabrik-deploy-verify.md").read_text().split()
    )
    assert "CONTAINER_LEG_SERVICE" in verify and "container_leg_service" in verify
    assert "CONTAINER_LEG_SERVICE" in checklist
    assert "does this number change when a user does their job" in checklist
    assert "switch together" in checklist
    assert (
        "python-dotenv" in verify or "dotenv" in verify
    )  # the comparator's runtime dependency, named


def test_the_selftest_is_not_vacuous():
    """`--selftest` is the predicates' ONLY grader and nothing on the box ran it: three regex
    mutations that its canaries catch left this whole suite green (review 2026-09-03, DS2)."""
    import subprocess

    r = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "enforcement" / "check_command_corpus.py"),
            "--selftest",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0 and "selftest:" in r.stdout, r.stdout + r.stderr


def test_the_audited_denominator_counts_every_file_a_predicate_opened(tmp_path):
    """The success line said "55 corpus file(s)" while the predicates read 93 (the orchestrator
    docs, the wrappers and the agent definitions never counted) — a denominator the line's own
    comment warned about (DS2). Every read site is exercised by a DISJOINT file, so dropping any
    one of the wrapper/agent sites reds this test; the two corpus-loop sites read the same files
    and cover each other by design (DU1)."""
    import check_command_corpus as ccc

    src = tmp_path / "_sources"
    frag = tmp_path / "_fragments"
    skills = tmp_path / "_traycer-skills" / "fab-x"
    agents = tmp_path / "_agents"
    for d in (src, frag, skills, agents):
        d.mkdir(parents=True)
    (src / "fabrik-a.md").write_text("{{include:run-record}}\n", encoding="utf-8")
    (src / "fabrik-b.md").write_text("{{include:run-record}}\n", encoding="utf-8")
    (skills / "SKILL.md").write_text(
        "`/opt/fabrik/docs/orchestrator/epic-to-ticket-workflow/00-trigger-fabrik.md`\n{{include:run-record}}\n",
        encoding="utf-8",
    )
    (agents / "agent-z.md").write_text(
        "---\nname: agent-z\ndescription: d\n---\n", encoding="utf-8"
    )
    ccc.audit(src, frag, tmp_path / "absent.py", REPO, traycer_skills=skills.parent, agents=agents)
    names = {Path(p).name for p in ccc.AUDITED}
    # the wrapper's canonical doc is REQUIRED too — a regression dropping orchestrator docs from
    # the audited set must red this, not only its sibling test (DW1)
    assert names == {
        "fabrik-a.md",
        "fabrik-b.md",
        "SKILL.md",
        "agent-z.md",
        "00-trigger-fabrik.md",
    }, names


def test_a_hub_without_its_web_tools_module_says_the_predicate_did_not_run(tmp_path):
    """With `libs/subagents/web_tools.py` absent the founding predicate ran zero times and the
    success line still named it (executed at pass 45: the provider-name defect it exists for
    passed green). In the hub — the assembler present — that is an advisory, never silence (DU1)."""
    import check_command_corpus as ccc

    repo = tmp_path / "hub"
    (repo / "commands").mkdir(parents=True)
    (repo / "commands" / "assemble_commands.py").write_text("# assembler\n", encoding="utf-8")
    src = repo / "commands" / "_sources"
    frag = repo / "commands" / "_fragments"
    src.mkdir()
    frag.mkdir()
    (src / "fabrik-a.md").write_text(
        '{{include:run-record}}\nfanout("r", web_tools=["exa"])\n', encoding="utf-8"
    )
    probs = ccc.audit(
        src,
        frag,
        repo / "commands" / "assemble_commands.py",
        repo,
        traycer_skills=tmp_path / "no-orch",
        agents=tmp_path / "no-agents",
    )
    assert ccc.SKIPPED_PREDICATES and "predicate 1 did not run" in ccc.SKIPPED_PREDICATES[0]
    # the silence is DELIBERATE and pinned: the bait `["exa"]` raises no web-tool finding here (DW1)
    assert not any("is not a real tool" in p for p in probs), probs
    # a SPOKE (no assembler) skips by design and stays silent
    spoke = tmp_path / "spoke"
    (spoke / "commands" / "_sources").mkdir(parents=True)
    (spoke / "commands" / "_fragments").mkdir()
    (spoke / "commands" / "_sources" / "fabrik-a.md").write_text(
        "{{include:run-record}}\n", encoding="utf-8"
    )
    ccc.audit(
        spoke / "commands" / "_sources",
        spoke / "commands" / "_fragments",
        spoke / "commands" / "assemble_commands.py",
        spoke,
        traycer_skills=tmp_path / "no-orch",
        agents=tmp_path / "no-agents",
    )
    assert ccc.SKIPPED_PREDICATES == []  # cleared per audit, and never raised for a spoke (DW1)


def test_the_skipped_predicate_advisory_reaches_stdout(monkeypatch, capsys):
    """DU1 recorded the skip; only `main` prints it — the print half was ungraded (DW1)."""
    import check_command_corpus as ccc

    def fake_audit(*a, **kw):
        ccc.SKIPPED_PREDICATES[:] = [
            "web-tool names: libs/subagents/web_tools.py absent — predicate 1 did not run"
        ]
        return []

    monkeypatch.setattr(ccc, "audit", fake_audit)
    ccc.SKIPPED.clear()
    ccc.AUDITED.clear()
    assert ccc.main([]) == 0
    out = capsys.readouterr().out
    assert "⚠ predicate skipped — web-tool names" in out, out


def _fake_hub(root: Path, web_tools_body: str | None) -> Path:
    """A hub-shaped tree: the assembler (so predicate 1's hub branch runs), one source carrying
    the bait `["exa"]`, and a `libs/subagents/web_tools.py` whose body the test chooses — or no
    module at all when `web_tools_body` is None."""
    (root / "commands" / "_sources").mkdir(parents=True)
    (root / "commands" / "_fragments").mkdir()
    (root / "commands" / "assemble_commands.py").write_text("", encoding="utf-8")
    (root / "commands" / "_sources" / "fabrik-a.md").write_text(
        '{{include:run-record}}\nfanout("r", web_tools=["exa"])\n', encoding="utf-8"
    )
    if web_tools_body is not None:
        (root / "libs" / "subagents").mkdir(parents=True)
        (root / "libs" / "__init__.py").write_text("", encoding="utf-8")
        (root / "libs" / "subagents" / "__init__.py").write_text("", encoding="utf-8")
        (root / "libs" / "subagents" / "web_tools.py").write_text(web_tools_body, encoding="utf-8")
    return root


def test_a_present_but_unusable_web_tools_module_is_a_hub_problem_and_an_absent_one_an_advisory(
    tmp_path,
):
    """Round 46 guarded the import and turned a REAL hub defect (a module that raises, a renamed
    or empty constant after a vendor sync) from a BLOCKING red into a green with an advisory the
    `--json` mode never showed (DY1). In the hub: unusable ⇒ a problem; absent ⇒ the DU1 advisory
    — and `_IMPORT_FAILURE` is cleared per audit, so an absent module after a broken one says
    `absent`, never the previous repo's exception. Three hubs, one fresh interpreter (the package
    import is cached in `sys.modules`; the driver purges it between hubs, as one process per repo
    would)."""
    import json
    import subprocess

    _fake_hub(tmp_path / "broken", "raise RuntimeError('broken vendor sync')\n")
    _fake_hub(tmp_path / "empty", "WEB_TOOL_NAMES = frozenset()\n")
    _fake_hub(tmp_path / "absent", None)
    driver = tmp_path / "driver.py"
    driver.write_text(
        "import json, sys\n"
        f"sys.path.insert(0, {str(REPO / 'scripts' / 'enforcement')!r})\n"
        "from pathlib import Path\n"
        "import check_command_corpus as c\n"
        "out = {}\n"
        f"for name in ('broken', 'empty', 'absent'):\n"
        f"    hub = Path({str(tmp_path)!r}) / name\n"
        "    for k in [k for k in sys.modules if k == 'libs' or k.startswith('libs.')]:\n"
        "        del sys.modules[k]\n"
        "    probs = c.audit(hub / 'commands' / '_sources', hub / 'commands' / '_fragments', hub / 'commands' / 'assemble_commands.py', hub, traycer_skills=hub / 'no-orch', agents=hub / 'no-agents')\n"
        "    out[name] = {'problems': probs, 'skipped': list(c.SKIPPED_PREDICATES), 'failure': list(c._IMPORT_FAILURE)}\n"
        "print(json.dumps(out))\n",
        encoding="utf-8",
    )
    r = subprocess.run([sys.executable, str(driver)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    # the hub with a raising module: a BLOCKING problem naming the exception, no skip, and the
    # bait never reaches the "is not a real tool" verdict (the predicate did not run)
    assert out["broken"]["failure"] == ["RuntimeError: broken vendor sync"], out["broken"]
    assert any(
        "present but unusable (RuntimeError: broken vendor sync)" in p
        for p in out["broken"]["problems"]
    ), out["broken"]
    assert out["broken"]["skipped"] == [], out["broken"]
    assert not any("is not a real tool" in p for p in out["broken"]["problems"]), out["broken"]
    # an EMPTY constant would otherwise flag every name in the corpus — it is the same defect
    assert out["empty"]["failure"] == ["WEB_TOOL_NAMES is empty"], out["empty"]
    assert any(
        "present but unusable (WEB_TOOL_NAMES is empty)" in p for p in out["empty"]["problems"]
    ), out["empty"]
    assert not any("is not a real tool" in p for p in out["empty"]["problems"]), out["empty"]
    # an ABSENT module after a broken one: the advisory says absent (the failure list was
    # cleared per audit), and nothing blocks
    assert out["absent"]["failure"] == [], out["absent"]
    assert out["absent"]["skipped"] == [
        "web-tool names: libs/subagents/web_tools.py absent — predicate 1 did not run"
    ], out["absent"]
    assert not any("web_tools.py" in p for p in out["absent"]["problems"]), out["absent"]


def test_quiet_drops_the_clean_denominator_line_and_keeps_every_warning(monkeypatch, capsys):
    """The gate passes `--quiet` (as it does the sibling header check): the ✓ line would otherwise
    ship into every green gate run fleet-wide as a content-free advisory row, and the `--json`
    `warnings` array admits only ⚠-FIRST output — so the ⚠ lines must print under `--quiet`, and
    print FIRST (DY1)."""
    import check_command_corpus as ccc

    def fake_audit(*a, **kw):
        ccc.SKIPPED_PREDICATES[:] = [
            "web-tool names: libs/subagents/web_tools.py absent — predicate 1 did not run"
        ]
        ccc.SKIPPED[:] = ["commands/_sources/x.md"]
        return []

    monkeypatch.setattr(ccc, "audit", fake_audit)
    ccc.AUDITED.clear()
    assert ccc.main(["--quiet"]) == 0
    out = capsys.readouterr().out
    assert "✓" not in out, out
    assert out.lstrip().startswith("⚠"), out  # the runner's --json filter: ⚠-first or invisible
    assert (
        "⚠ 1 file(s) could NOT be read" in out and "⚠ predicate skipped — web-tool names" in out
    ), out
    ccc.SKIPPED.clear()
    ccc.SKIPPED_PREDICATES.clear()
    monkeypatch.setattr(ccc, "audit", lambda *a, **kw: [])
    assert ccc.main(["--quiet"]) == 0
    assert capsys.readouterr().out == ""  # a clean quiet run prints nothing at all


def test_the_deploy_triad_reads_the_frozen_contract_before_the_deploy_not_after():
    """After tryton-crm's v3 run (2026-09-03): the checklist and the runner knew the contract, but
    `/fabrik-deploy-plan` and `/fabrik-deploy` did not mention it at all — a plan could be authored and
    a deploy dispatched against a DRAFT contract, and the leg container's missing interpreter/dotenv was
    only ever discovered at verify time. Now: the plan reads `--header` as a precondition and proves the
    container leg can run the comparator in Phase 2; the deploy re-reads the header pre-flip and refuses
    DRAFT or a re-frozen version; checklist + verify name the no-interpreter (Node image) class."""
    src = REPO / "commands" / "_sources"
    norm = lambda name: " ".join((src / name).read_text().split())  # noqa: E731
    plan, deploy = norm("fabrik-deploy-plan.md"), norm("fabrik-deploy.md")
    checklist, verify = norm("fabrik-deploy-checklist.md"), norm("fabrik-deploy-verify.md")
    for text in (plan, deploy):
        assert "verify_prod_parity.py --header" in text
        assert "BLOCKED: parity contract DRAFT" in text
    assert "import dotenv" in plan  # Phase 2 proves the leg image can run the comparator
    assert (
        "parity contract re-frozen" in deploy
    )  # plan-version ≠ checkout-version is a review re-entry
    assert (
        "not in the plan header" in deploy
    )  # pre-2026-09-03 plans carry no version: WARN, never BLOCK
    assert "no `python` at all" in checklist
    assert "executable file not found" in verify


def test_every_deploy_chain_command_carries_the_shared_order_and_repo_block():
    """Operator, 2026-09-03: "in which order and in which repo (hub or project) these commands run must
    be indicated IN the commands, and the order must be inside them so agents know the next command."
    One fragment (`_fragments/deploy-chain.md`) names all six steps with their repo; every command in
    the chain includes it and states its own step + previous + next above the include."""
    src = REPO / "commands" / "_sources"
    frag = (REPO / "commands" / "_fragments" / "deploy-chain.md").read_text()
    for needle in (
        "/fabrik-deploy-checklist",
        "/fabrik-release",
        "/fabrik-deploy-plan",
        "/fabrik-deploy-plan-review",
        "/fabrik-deploy`",
        "/fabrik-deploy-verify",
        "**PROJECT**",
        "**HUB**",
        "Gate 2",
    ):
        assert needle in frag, needle
    for name, step in (
        ("fabrik-deploy-checklist.md", 1),
        ("fabrik-deploy-plan.md", 3),
        ("fabrik-deploy-plan-review.md", 4),
        ("fabrik-deploy.md", 5),
        ("fabrik-deploy-verify.md", 6),
    ):
        text = (src / name).read_text()
        assert "{{include:deploy-chain}}" in text, name
        assert f"You are at step {step} of the chain" in text, name
