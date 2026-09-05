"""Behaviour tests for the command-corpus integrity check.

Each test names a defect class the 2026-08-16 corpus audit found LIVE, and proves
the check goes red on it. The path-look-alike test is the important negative: a
naive matcher "finds" four broken chains in `/opt/fabrik-lib`, `/run/fabrik-autoheal`
and `docs/reference/fabrik-mail.md` that were never broken, and a check that cries
wolf gets ignored — which is how a real break then ships.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "enforcement"))
sys.path.insert(0, str(REPO / "commands"))

from check_command_corpus import audit  # noqa: E402


@pytest.fixture
def corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A minimal two-command corpus; the callable writes the file under test."""
    import check_command_corpus as _ccc  # noqa: PLC0415

    # `repo` stays the REAL hub (predicates 2/6 resolve script paths against it), so predicate 4
    # would read the live, sibling-mutable CLAUDE.md — the class `_CLAUDE_MD` closed elsewhere (FC1)
    monkeypatch.setattr(_ccc, "_canonical_trailer_model", lambda *a, **k: "Claude Fable 5.1")
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
            src,
            frag,
            tmp_path / "no-assembler.py",
            REPO,
            agents=tmp_path
            / "no-agents",  # never the LIVE _agents/: a peer's half-saved definition red every `assert not corpus(...)` (FD4)
        )

    return write


def test_a_digit_bearing_command_name_is_a_chain_reference(corpus, tmp_path):
    """`/fabrik-oauth2-setup` matched NOTHING under `[a-z-]*` (the lookahead refused the partial
    match), so a dangling digit-bearing reference was invisible to predicates 2 and 8 (FB7); a
    `.md` filename is still a file, never a chain reference."""
    problems = corpus("run /fabrik-oauth2-setup, then read /fabrik-real.md and /fabrik-nope.md\n")
    assert any("/fabrik-oauth2-setup does not exist" in p for p in problems), problems
    problems = corpus(
        "run /fabrik-2fa\n"
    )  # a digit-FIRST segment was still invisible after FB7 (FC1)
    assert any("/fabrik-2fa does not exist" in p for p in problems), problems
    assert not any("fabrik-nope" in p for p in problems), problems
    (tmp_path / "_sources" / "fabrik-oauth2-setup.md").write_text("{{include:run-record}}\n")
    assert not corpus("run /fabrik-oauth2-setup\n")


def test_a_bare_line_break_between_the_script_and_start_is_not_a_run_record(corpus):
    """`\\s*` spanned newlines without a backslash: prose naming `command_run.py` at a line's end
    followed by a sentence starting with `start` opened a run record (FC1)."""
    problems = corpus(
        "Records live in scripts/command_run.py\nstart every phase by reading the ledger\n",
        with_record=False,
    )
    assert any("opens no run record" in p for p in problems), problems


def test_a_wrapped_or_respaced_run_record_start_opens_a_run_record(corpus):
    """`command_run.py \\` + newline + `start` and `command_run.py   start` both open a record;
    the bare substring test called each "opens no run record" — a BLOCKING false positive on
    ordinary shell wrapping (FB7)."""
    for body in (
        "```bash\npython3 scripts/command_run.py \\\n  start --command fabrik-probe --phases 4\n```\n",
        "python3 scripts/command_run.py   start --command fabrik-probe\n",
    ):
        problems = corpus(body, with_record=False)
        assert not any("opens no run record" in p for p in problems), (body, problems)
    problems = corpus("python3 scripts/command_run.py restart --command x\n", with_record=False)
    assert any("opens no run record" in p for p in problems), problems


def test_a_fenced_caller_claim_is_an_example_and_a_claim_ends_at_the_sentence(corpus):
    """A fenced `auto-called by /fabrik-real` is illustration, as the heading form already
    treats a fenced `#` (FB7); and the verb capture stops at the sentence — the next sentence's
    `/fabrik-real` is not a claimed caller (the `([^.;]*)` bound, ungraded until now)."""
    assert not corpus("```\ndescription: auto-called by /fabrik-real reactively\n```\n")
    problems = corpus("it is invoked by the operator. See /fabrik-real for the successor.\n")
    assert not any("claims caller" in p for p in problems), problems
    problems = corpus("it is invoked by /fabrik-real; see also the successor\n")
    assert any("claims caller /fabrik-real" in p for p in problems), problems


def test_a_prefix_sibling_never_honours_a_caller_claim(corpus, tmp_path):
    """`/fabrik-review-scoped` CONTAINS `/fabrik-review`: the substring back-reference honoured a
    false claim through a prefix sibling — 9 such pairs live (FC1)."""
    (tmp_path / "_sources" / "fabrik-probe-scoped.md").write_text("{{include:run-record}}\n")
    (tmp_path / "_sources" / "fabrik-real.md").write_text(
        "{{include:run-record}}\nsee /fabrik-probe-scoped\n"
    )  # names only the claimant's PREFIX SIBLING — a substring test finds `/fabrik-probe` inside it
    problems = corpus("description: auto-called by /fabrik-real reactively.\n")
    assert any("claims caller /fabrik-real" in p for p in problems), problems


def test_real_fences_and_indented_headings_in_caller_claims(corpus):
    """`~~~` and a 4-backtick fence holding a 3-backtick one fabricated claims under a bare ```
    toggle; a fenced bullet under a call-sites heading was harvested before the fence guard; a
    heading may carry up to three leading spaces (FC1)."""
    assert not corpus("~~~\ndescription: auto-called by /fabrik-real reactively\n~~~\n")
    assert not corpus("````\n```\ndescription: auto-called by /fabrik-real reactively\n```\n````\n")
    assert not corpus(
        "## Where this auto-fires (0 call sites)\n```\n# example: /fabrik-real\n```\n"
    )
    problems = corpus(
        "   ## Where this auto-fires (1 call site)\n- **`/fabrik-real` (reactive):** x\n"
    )
    assert any("claims caller /fabrik-real" in p for p in problems), problems


def test_a_quoted_or_annotated_agent_name_and_a_bom_are_valid_definitions(tmp_path):
    """`name: "good"` and `name: good  # note` are valid YAML that resolves to `good`; a BOM
    is not "no frontmatter" — each was a BLOCKING false positive on a fleet-synced check (FC1)."""
    src, frag = tmp_path / "_sources", tmp_path / "_fragments"
    src.mkdir()
    frag.mkdir()
    (src / "fabrik-real.md").write_text("{{include:run-record}}\n")
    agents = tmp_path / "_agents"
    agents.mkdir()
    (agents / "quoted.md").write_text('---\nname: "quoted"\ndescription: d\n---\n')
    (agents / "noted.md").write_text("---\nname: noted  # the reviewer\ndescription: d\n---\n")
    (agents / "bom.md").write_text("\ufeff---\nname: bom\ndescription: d\n---\n")
    problems = audit(
        src,
        frag,
        tmp_path / "no-assembler.py",
        tmp_path,
        agents=agents,
    )
    assert not problems, problems


def test_a_truncated_web_tools_literal_is_said(corpus):
    """The 2 000-char perf bound silently stopped checking names beyond it — a bad name past
    the bound was invisible (FC1)."""
    import check_command_corpus as ccc

    body = 'fanout("r", web_tools=[' + '"web_search",' * 180 + '"exa"])\n'
    corpus(body)
    assert any("literal was checked to 2 000 chars" in a for a in ccc.ADVISORIES), ccc.ADVISORIES
    ccc.ADVISORIES.clear()


def test_the_recorder_leaves_no_wrapper_and_no_environment_behind(tmp_path, monkeypatch):
    """The wrappers went on `spec.loader` and stayed in `sys.modules` for the process — a
    `copy`/`pickle` of any wrapped spec recursed to death and 128 modules carried a foreign
    loader for a pytest session; the probe also left `SUBAGENTS_NO_AUTOLOAD` set (FC1)."""
    import copy
    import pickle

    import check_command_corpus as ccc

    monkeypatch.delenv("SUBAGENTS_NO_AUTOLOAD", raising=False)
    hub = _probe_hub(tmp_path, 'import json\nWEB_TOOL_NAMES = frozenset({"web_search"})\n')
    saved_mods = {
        k: sys.modules.pop(k) for k in list(sys.modules) if k == "libs" or k.startswith("libs.")
    }
    try:
        assert ccc._live_web_tool_names(hub) == frozenset({"web_search"})
        assert "SUBAGENTS_NO_AUTOLOAD" not in os.environ
        for name, mod in list(sys.modules.items()):
            loader = getattr(getattr(mod, "__spec__", None), "loader", None)
            assert not isinstance(loader, ccc._RecordingLoader), name
            assert not isinstance(getattr(mod, "__loader__", None), ccc._RecordingLoader), name
        spec = sys.modules["libs.subagents.web_tools"].__spec__
        copy.deepcopy(spec)
        pickle.loads(pickle.dumps(spec))
    finally:
        for k in [k for k in sys.modules if k == "libs" or k.startswith("libs.")]:
            del sys.modules[k]
        sys.modules.update(
            saved_mods
        )  # the REAL libs.* modules come back: deleting them split identities for every later importer (L64-10, FD8)
        while str(hub) in sys.path:
            sys.path.remove(
                str(hub)
            )  # the probe pins the hub on sys.path (DS1): a later REAL import must not resolve to this fake


def test_the_recorder_stack_is_per_thread_and_its_loader_is_copyable():
    """A concurrent import interleaved another thread's pushes; a half-built wrapper recursed
    forever in `__getattr__` (FC1)."""
    import copy
    import threading

    import check_command_corpus as ccc

    rec = ccc._ImportRecorder()
    rec.stack.append("main-thread-module")
    seen: list[list[str]] = []
    t = threading.Thread(target=lambda: seen.append(list(rec.stack)))
    t.start()
    t.join()
    assert seen == [[]] and rec.stack == ["main-thread-module"]

    class _L:
        def exec_module(self, m):
            pass

    wrapper = ccc._RecordingLoader(_L(), "x", rec)
    assert (
        copy.copy(wrapper)._name == "x"
    )  # `copy` probes `__reduce_ex__`/`__setstate__` through __getattr__ first
    with pytest.raises(AttributeError):
        wrapper.__setstate__  # noqa: B018 - a dunder probe must never recurse


def test_a_lowercase_trailer_key_is_the_same_trailer(tmp_path):
    """git parses trailer keys case-insensitively: `co-authored-by: OldModel` lands a real (wrong)
    trailer, and the case-sensitive regex let it through (FB7)."""
    src, frag = tmp_path / "_sources", tmp_path / "_fragments"
    src.mkdir()
    frag.mkdir()
    (tmp_path / "CLAUDE.md").write_text(_CLAUDE_MD, encoding="utf-8")
    (src / "fabrik-probe.md").write_text(
        "{{include:run-record}}\nco-authored-by: Claude Opus 4.8 <noreply@anthropic.com>\n"
    )
    problems = audit(src, frag, tmp_path / "no-assembler.py", tmp_path)
    assert any("commit template says Co-Authored-By" in p for p in problems), problems


def test_a_vanished_repo_file_is_listed_once_and_an_unreadable_agent_def_never_crashes(
    tmp_path, monkeypatch
):
    """`_read` deduped on the RAW path and stored the SCRUBBED one, so a file inside the repo was
    listed once per caller and "attempted N" inflated with it; and the wrapper + agent-definition
    reads bypassed `_read` — a sibling's mid-render wrapper was a traceback out of a BLOCKING
    gate (FB7)."""
    import check_command_corpus as ccc

    monkeypatch.setattr(ccc, "REPO", tmp_path)
    src, frag = tmp_path / "commands" / "_sources", tmp_path / "commands" / "_fragments"
    src.mkdir(parents=True)
    frag.mkdir()
    (src / "fabrik-real.md").write_text("{{include:run-record}}\n")
    (src / "fabrik-probe.md").write_text("{{include:run-record}}\nauto-called by /fabrik-real\n")
    agents = tmp_path / "commands" / "_agents"
    agents.mkdir()
    (agents / "fabrik-reviewer.md").write_text("---\nname: fabrik-reviewer\ndescription: d\n---\n")
    real_read = Path.read_text

    def exploding_read(self, *a, **kw):
        if self.name in ("fabrik-real.md", "fabrik-reviewer.md"):
            raise OSError("vanished mid-audit")
        return real_read(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", exploding_read)
    problems = audit(
        src,
        frag,
        tmp_path / "no-assembler.py",
        tmp_path,
        agents=agents,
    )
    assert not any("Traceback" in p for p in problems)
    assert [s for s in ccc.SKIPPED if "fabrik-real.md" in s] == [
        "commands/_sources/fabrik-real.md: OSError"
    ], ccc.SKIPPED
    assert any("fabrik-reviewer.md" in s for s in ccc.SKIPPED), ccc.SKIPPED
    ccc.SKIPPED.clear()


def test_the_advisory_line_is_printed_and_a_multiline_message_is_one_row(
    tmp_path, monkeypatch, capsys
):
    """`⚠ advisory —` reaches stdout on both exits (the whole point of the ADVISORIES list was
    ungraded); an exception message with newlines rendered as several gate rows (FC1)."""
    import check_command_corpus as ccc

    monkeypatch.setattr(ccc, "audit", lambda *a, **kw: [])
    ccc.ADVISORIES.append("web-tool names: a module wrote 9 bytes to stdout/stderr at import")
    assert ccc.main(["--quiet"]) == 0
    assert "⚠ advisory — web-tool names: a module wrote 9 bytes" in capsys.readouterr().out
    ccc.ADVISORIES.clear()
    assert ccc._safe_str(
        RuntimeError("Missing configuration:\n  set EXA_API_KEY\n  set BRAVE_KEY")
    ) == ("Missing configuration: set EXA_API_KEY set BRAVE_KEY")


def test_the_selftest_never_grades_the_live_agent_definitions(tmp_path, monkeypatch, capsys):
    """The canary and good-fixture audits fell back to the module-level `_agents/` dir: a real
    defect in a LIVE agent definition read as "FALSE POSITIVE on known-good input" — the
    anti-vacuity harness misdiagnosing the repo as its own breakage (FB7)."""
    import check_command_corpus as ccc

    bad = tmp_path / "_agents"
    bad.mkdir()
    (bad / "fabrik-reviewer.md").write_text("---\nname: WRONG-NAME\ndescription: d\n---\n")
    monkeypatch.setattr(ccc, "AGENTS_SRC", bad)
    assert ccc._selftest() == 0, capsys.readouterr().out


def test_a_live_agent_definition_never_satisfies_a_selftest_canary(tmp_path, monkeypatch):
    """The CANARY audits fell back to the live `_agents/` too: a live definition whose problem
    text happened to contain a canary's signature would satisfy a VACUOUS predicate — the
    anti-vacuity harness passing on contamination. With predicate 2 neutered, a contaminated
    live `_agents/` must still read VACUOUS (FB7's canary-site half, graded in pass 62)."""
    import check_command_corpus as ccc

    bad = tmp_path / "_agents"
    bad.mkdir()
    (bad / "fabrik-reviewer.md").write_text(
        "---\nname: scripts/enforcement/check_no_such_thing.py does not exist\ndescription: d\n---\n"
    )
    monkeypatch.setattr(ccc, "AGENTS_SRC", bad)
    monkeypatch.setattr(
        ccc, "_SCRIPT_RE", __import__("re").compile(r"(?!x)x")
    )  # predicate 3 — the ONLY predicate its canary exercises — can never fire
    assert ccc._selftest() == 1  # VACUOUS, never satisfied by the live definition's text


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
    problems = audit(src, frag, tmp_path / "absent.py", REPO)
    assert problems and "nothing to audit" in problems[0]


def test_live_corpus_is_clean():
    """The shipped corpus itself must satisfy the check."""
    assert audit() == []
    ccc_mod = sys.modules[audit.__module__]
    ccc_mod.AUDITED.clear()  # the real audit fills the module global; reversed collection order leaked it (pass 49)


def test_command_without_a_run_record_is_caught(corpus):
    """CLAUDE.md makes the record the first act; 24 of 27 commands never opened one."""
    problems = corpus("a command body that never opens a run record\n", with_record=False)
    assert any("no run record" in p for p in problems)


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


def test_template_shipped_scripts_resolve(tmp_path: Path):
    """A hub command's script ref is hub-rooted: a template-only script is a dead hub ref.

    History in two turns: hub-rooting alone called five live orchestrator references dead
    (they shipped via templates/i18n-kit), so a templates/** fallback was added — corpus-wide,
    which the next review showed masks a genuinely deleted HUB script whose name survives in
    a scaffold template. The fallback was then scoped to the orchestrator docs and retired
    with them (T08a): command sources never received it, so both refs below stay flagged.
    """
    src, frag = tmp_path / "_sources", tmp_path / "_fragments"
    src.mkdir(), frag.mkdir()
    t = tmp_path / "templates" / "kit" / "scripts" / "shipped_by_scaffold.py"
    t.parent.mkdir(parents=True)
    t.write_text("#\n")
    (src / "fabrik-real.md").write_text(
        "run scripts/shipped_by_scaffold.py\nrun scripts/never_anywhere.py\n{{include:run-record}}\n"
    )
    problems = audit(src, frag, tmp_path / "absent.py", tmp_path)
    assert any("shipped_by_scaffold" in p for p in problems), (
        "a HUB command referencing a template-only script is a dead hub ref — must stay flagged"
    )
    assert any("never_anywhere" in p for p in problems)


def test_project_without_a_corpus_stays_silent_and_does_not_crash(tmp_path: Path):
    """The fleet hazard: a project-shaped tree (no `commands/_sources/`) must be silently N/A.

    Honesty note (closing-sweep finding): this fixture cannot reproduce v1's actual crash —
    v1's `_live_web_tool_names()` read the module-level REPO (the real hub, which has
    libs/subagents), so the ModuleNotFoundError only fired in a genuinely separate repo. What
    this test DOES pin: (a) a tree with no corpus yields zero problems and no crash; (b) the
    None-sentinel below, which is the guard that would stop the crash in a repo without the
    pool vendored.
    """
    problems = audit(
        tmp_path / "_sources", tmp_path / "_fragments", tmp_path / "absent.py", tmp_path
    )
    assert problems == [], f"a project-shaped tree must be silently N/A, got: {problems[:3]}"
    from check_command_corpus import _live_web_tool_names  # noqa: PLC0415

    assert _live_web_tool_names(tmp_path) is None, (
        "the crash guard: a repo without libs/subagents must yield the skip-sentinel, "
        "never an import attempt (None, not an empty set — empty inverts predicate 1)"
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
    problems = audit(src, frag, tmp_path / "absent.py", tmp_path)
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


@pytest.mark.parametrize("name", ["fabrik-epics.md", "fabrik-epics-review.md", "fabrik-vision.md"])
def test_a_former_orchestrator_command_is_audited_like_any_other_source(
    tmp_path, monkeypatch, name
):
    """The three commands that shipped as orchestrator wrappers are plain sources since T08a: the
    per-source predicates read them with no special case. Proven by IDENTITY, not presence — the
    same close in the mega source and in an ordinary `fabrik-probe.md` yields the same finding
    text modulo the filename (a check that special-cased the three names with a message of its
    own would pass a mere "some --feedback problem exists"), and the same close WITH
    `--feedback` is clean for both."""
    import check_command_corpus as ccc

    monkeypatch.setattr(ccc, "_canonical_trailer_model", lambda *a, **k: "Claude Fable 5.1")
    src, frag = tmp_path / "_sources", tmp_path / "_fragments"
    src.mkdir()
    frag.mkdir()
    (src / "fabrik-real.md").write_text("{{include:run-record}}\n")

    def findings(filename: str, feedback: str) -> list[str]:
        """The SAME fixture under `filename`, alone in `src`, its own path normalised away."""
        for stale in src.glob("fabrik-*.md"):
            if stale.name != "fabrik-real.md":
                stale.unlink()
        (src / filename).write_text(
            "{{include:run-record}}\n"
            f"close it: `python3 scripts/command_run.py done --command {filename.removesuffix('.md')}"
            f' --evidence "e"{feedback}`\n'
        )
        problems = audit(
            src, frag, tmp_path / "no-assembler.py", REPO, agents=tmp_path / "no-agents"
        )
        return [p.replace(str(src / filename), "<file>") for p in problems]

    mega, plain = findings(name, ""), findings("fabrik-probe.md", "")
    assert mega and "--feedback" in mega[0], mega
    assert mega == plain, (mega, plain)
    with_flag = " --feedback 'none — probe'"
    assert findings(name, with_flag) == [] == findings("fabrik-probe.md", with_flag)


def test_all_three_close_verbs_are_policed(corpus):
    """`blocked` and `handoff` refuse identically — policing only `done` would leave the two
    dispositions a stuck run actually uses. `handoff` is what the certification gauntlets close
    NOT-QUIET runs with, so it is the likeliest close to carry machinery friction."""
    for verb, arg in (("done", "--evidence"), ("blocked", "--reason"), ("handoff", "--reason")):
        problems = corpus(
            f'`python3 scripts/command_run.py {verb} --command fabrik-probe {arg} "x"`\n'
        )
        assert any("--feedback" in p for p in problems), f"{verb} not policed: {problems}"


def test_the_prose_that_documents_the_flag_never_excuses_a_close_without_it(corpus):
    """The flat 4-line window admitted the sentence explaining the requirement — the run-record
    fragment's own close passed with its flag deleted, and so did 21 of 47 live close sites; a
    neighbouring close's flag excused a feedback-less one too (FB7)."""
    problems = corpus(
        '- `python3 scripts/command_run.py done --command fabrik-probe --evidence "<what proves the terminal\n'
        '  condition was met>"` — the evidence is the point. ⚠️ **`--feedback` is REQUIRED: the close\n'
        "  REFUSES without it**\n"
    )
    assert any("--feedback" in p for p in problems), problems
    problems = corpus(
        '`python3 scripts/command_run.py done --command fabrik-probe --evidence "e"`\n'
        '`python3 scripts/command_run.py blocked --command fabrik-probe --reason "r" --feedback "none"`\n'
    )
    assert sum("--feedback" in p for p in problems) == 1, problems


def test_a_close_whose_flag_wraps_inside_its_own_span_or_continuation_is_compliant(corpus):
    """The false-positive side of the new window: the fragment's real shape (an inline-code span
    running on to the next line) and a fenced `\\` continuation both carry the flag on the
    continuation line (FB7)."""
    problems = corpus(
        '- `python3 scripts/command_run.py done --command fabrik-probe --evidence "<proof>"\n'
        '  --feedback "<what you filed | none>"` — the evidence is the point.\n'
        "```bash\n"
        "python3 scripts/command_run.py blocked --command fabrik-probe --reason r \\\n"
        "  --feedback none\n"
        "```\n"
    )
    assert not any("--feedback" in p for p in problems), problems


def test_prose_after_the_close_span_on_the_same_line_never_excuses_it(corpus):
    """The window was seeded with the WHOLE close line: prose after the span's closer — or a
    neighbouring table cell — on the same line still excused a feedback-less close (FC1)."""
    problems = corpus(
        'run `python3 scripts/command_run.py done --command fabrik-probe --evidence "e"` — remember `--feedback` is required\n'
    )
    assert any("--feedback" in p for p in problems), problems
    problems = corpus("| `done --command fabrik-probe --evidence e` | `--feedback none` |\n")
    assert any("--feedback" in p for p in problems), problems
    # the next close STOPS the window even when the first left its span open
    problems = corpus(
        '- `python3 scripts/command_run.py done --command fabrik-probe --evidence "e"\n'
        "  python3 scripts/command_run.py blocked --command fabrik-probe --reason r --feedback none`\n"
    )
    assert any("--feedback" in p for p in problems), problems
    # prose on the NEXT line, outside any span or continuation, never excuses either
    problems = corpus(
        '`python3 scripts/command_run.py done --command fabrik-probe --evidence "e"`\n'
        "remember `--feedback` is required\n"
    )
    assert any("--feedback" in p for p in problems), problems
    # a continuation that STOPS (a line without `\\`) ends the window before a later flag
    problems = corpus(
        "```bash\npython3 scripts/command_run.py done --command fabrik-probe --evidence e \\\n  --reason r\n  --feedback none\n```\n"
    )
    assert any("--feedback" in p for p in problems), problems
    # `--command=x` is argparse-legal and a runnable close the tool then refuses
    problems = corpus("`command_run.py done --command=fabrik-probe --evidence=e`\n")
    assert any("--feedback" in p for p in problems), problems


def test_a_long_fenced_continuation_that_carries_the_flag_is_compliant(corpus):
    """A `\\` continuation runs while lines end in `\\` — a flat 3-line cap red a fenced
    six-line command whose flag sat on the last line (FC1)."""
    body = "```bash\npython3 scripts/command_run.py done --command fabrik-probe \\\n"
    body += "".join(f"  --opt{i} v \\\n" for i in range(6))
    body += "  --evidence e --feedback none\n```\n"
    assert not any("--feedback" in p for p in corpus(body)), corpus(body)


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
    """The success line said "55 corpus file(s)" while the predicates read 93 (the agent
    definitions, among others, never counted) — a denominator the line's own comment warned
    about (DS2). Every read site is exercised by a DISJOINT file, so dropping the agent site
    reds this test; the two corpus-loop sites read the same files and cover each other by
    design (DU1). The audited set holds the corpus and the agent definitions and nothing else:
    the orchestrator docs and wrappers left it by design when T08a retired that path, so an
    extra name here is a read site the check grew back, not a denominator to update."""
    import check_command_corpus as ccc

    src = tmp_path / "_sources"
    frag = tmp_path / "_fragments"
    agents = tmp_path / "_agents"
    for d in (src, frag, agents):
        d.mkdir(parents=True)
    (src / "fabrik-a.md").write_text("{{include:run-record}}\n", encoding="utf-8")
    (src / "fabrik-b.md").write_text("{{include:run-record}}\n", encoding="utf-8")
    (agents / "agent-z.md").write_text(
        "---\nname: agent-z\ndescription: d\n---\n", encoding="utf-8"
    )
    ccc.audit(src, frag, tmp_path / "absent.py", REPO, agents=agents)
    names = {Path(p).name for p in ccc.AUDITED}
    assert names == {"fabrik-a.md", "fabrik-b.md", "agent-z.md"}, names


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
    ccc.SKIPPED_PREDICATES.clear()  # module state — never leave it for the next test (pass 48)


def test_a_failing_run_still_prints_its_coverage_warnings(monkeypatch, capsys):
    """The failing exit is the run that most needs to say the verdict was computed over an
    incomplete corpus; the ⚠ lines were printed on success only (EA1)."""
    import check_command_corpus as ccc

    def fake_audit(*a, **kw):
        ccc.SKIPPED[:] = ["commands/_sources/unreadable.md"]
        ccc.SKIPPED_PREDICATES[:] = [
            "web-tool names: libs/subagents/web_tools.py absent — predicate 1 did not run"
        ]
        return ["commands/_sources/x.md: chain target /fabrik-nope does not exist"]

    monkeypatch.setattr(ccc, "audit", fake_audit)
    ccc.AUDITED.clear()
    assert ccc.main(["--quiet"]) == 1
    out = capsys.readouterr().out
    assert out.startswith("✗ command corpus: 1 broken reference(s)"), out
    assert (
        "⚠ 1 file(s) could NOT be read" in out and "⚠ predicate skipped — web-tool names" in out
    ), out
    ccc.SKIPPED.clear()
    ccc.SKIPPED_PREDICATES.clear()


def _fake_hub(
    root: Path,
    web_tools_body: str | None,
    init_body: str = "",
    tools_body: str | None = None,
    extra: dict[str, str] | None = None,
) -> Path:
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
        (root / "libs" / "subagents" / "__init__.py").write_text(init_body, encoding="utf-8")
        (root / "libs" / "subagents" / "web_tools.py").write_text(web_tools_body, encoding="utf-8")
        if tools_body is not None:
            (root / "libs" / "subagents" / "tools.py").write_text(tools_body, encoding="utf-8")
        for rel, body in (extra or {}).items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(body, encoding="utf-8")
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
    # a SIBLING module broken (a peer's half-saved WIP on the shared tree): web_tools.py itself
    # is fine, the package __init__ raises — not this check's surface (EA1)
    _fake_hub(
        tmp_path / "sibling",
        'WEB_TOOL_NAMES = frozenset({"web_search"})\n',
        init_body="raise RuntimeError('sibling WIP')\n",
    )
    # the half-saved-file shape ITSELF: a SyntaxError in web_tools.py carries no `path` and the
    # import frames are stripped, so the last frame is the importer — it must still BLOCK (EC1)
    _fake_hub(tmp_path / "syntax", "def broken(:\n")
    # a renamed constant: the ImportError's `path` is web_tools.py — BLOCK (the exc.path preference)
    _fake_hub(tmp_path / "renamed", 'WEB_TOOL_NAMES_V2 = frozenset({"web_search"})\n')
    # a SyntaxError in the sibling web_tools imports DIRECTLY: blamed on tools.py, an advisory
    _fake_hub(
        tmp_path / "sibtools",
        'from .tools import H\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        tools_body="def x(:\n",
    )
    # a dependency OUTSIDE the repo raising on import: an advisory naming the file, never an
    # absolute path (EC1)
    _fake_hub(tmp_path / "extdep", "import broken_dep_xyz\nWEB_TOOL_NAMES = frozenset()\n")
    (tmp_path / "site").mkdir()
    (tmp_path / "site" / "broken_dep_xyz.py").write_text(
        "raise ImportError('broken wheel')\n", encoding="utf-8"
    )
    # an out-of-repo PACKAGE: the common shape (httpx, every dependency) — named with its package,
    # never a bare `__init__.py` (EE1)
    _fake_hub(tmp_path / "extpkg", "import broken_pkg\nWEB_TOOL_NAMES = frozenset()\n")
    (tmp_path / "site" / "broken_pkg").mkdir()
    (tmp_path / "site" / "broken_pkg" / "__init__.py").write_text(
        "raise ImportError('broken pkg')\n", encoding="utf-8"
    )
    # the constant's SHAPE: a bare str is a set of characters, None crashes, a non-str member
    # crashes the remediation join — every one a hub problem naming the shape (EE1)
    _fake_hub(tmp_path / "strconst", 'WEB_TOOL_NAMES = "web_search"\n')
    _fake_hub(tmp_path / "noneconst", "WEB_TOOL_NAMES = None\n")
    _fake_hub(tmp_path / "badmember", "WEB_TOOL_NAMES = frozenset({1})\n")
    # a RUNTIME SyntaxError (compile() of a string): `exc.filename` is `<string>`, the frames are
    # kept — the blame must fall through to the frame, web_tools.py, and BLOCK (EE1)
    _fake_hub(
        tmp_path / "rtsyntax",
        'compile("def (:", "<string>", "exec")\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    # a suffix collision: `deep_web_tools.py` ends with the name — identity, not suffix (EE1)
    _fake_hub(
        tmp_path / "suffix",
        'from .deep_web_tools import X\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        extra={"libs/subagents/deep_web_tools.py": "raise RuntimeError('deep WIP')\n"},
    )
    # the SAME basename, a different file: `libs/web_tools.py` is a real standalone module in
    # this tree — a failure there must be an advisory naming it, never a block under
    # `libs/subagents/web_tools.py`'s name (identity, not basename — pass 51)
    _fake_hub(
        tmp_path / "parentwt",
        'from ..web_tools import X\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        extra={"libs/web_tools.py": "raise RuntimeError('standalone WIP')\n"},
    )
    # the target's OWN health is asked of the FILE, not inferred from a traceback (EG1): NUL
    # bytes (a SyntaxError with NO filename — the importer would have been blamed), an
    # unreadable file (a PermissionError raised inside the import machinery), a directory at
    # the module path (a ModuleNotFoundError in the importer)
    _fake_hub(tmp_path / "nulbytes", "WEB_TOOL_NAMES = frozenset()\n")
    (tmp_path / "nulbytes" / "libs" / "subagents" / "web_tools.py").write_bytes(
        b"WEB_TOOL_NAMES = frozenset()\n\x00\x00"
    )
    _fake_hub(tmp_path / "noperm", 'WEB_TOOL_NAMES = frozenset({"web_search"})\n')
    _fake_hub(tmp_path / "dirmod", None)
    (tmp_path / "dirmod" / "libs" / "subagents" / "web_tools.py").mkdir(parents=True)
    (tmp_path / "dirmod" / "libs" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "dirmod" / "libs" / "subagents" / "__init__.py").write_text("", encoding="utf-8")
    # a DANGLING symlink at the module path is PRESENT and broken — never "absent" (EI1)
    _fake_hub(tmp_path / "dangling", None)
    (tmp_path / "dangling" / "libs" / "subagents").mkdir(parents=True)
    (tmp_path / "dangling" / "libs" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "dangling" / "libs" / "subagents" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "dangling" / "libs" / "subagents" / "web_tools.py").symlink_to(
        "/nonexistent/gone.py"
    )
    # an unreadable PARENT directory: `exists()` itself raises — the target's own defect (EI1)
    _fake_hub(tmp_path / "nopermdir", 'WEB_TOOL_NAMES = frozenset({"web_search"})\n')
    # a corrupt bytecode cache with a healthy source: EOFError inside frozen importlib, no path,
    # no filename — the last real frame is the checker itself, so it is the target's (EI1)
    _fake_hub(tmp_path / "corruptpyc", 'WEB_TOOL_NAMES = frozenset({"web_search"})\n')
    import importlib.util
    import py_compile

    src = tmp_path / "corruptpyc" / "libs" / "subagents" / "web_tools.py"
    pyc = Path(importlib.util.cache_from_source(str(src)))
    py_compile.compile(str(src), cfile=str(pyc), doraise=True)
    pyc.write_bytes(pyc.read_bytes()[:20])
    # a SIBLING's torn bytecode cache with a healthy target: the same frameless EOFError — it
    # must NOT block under web_tools.py's name; the caches are asked and the owner named (EK1)
    _fake_hub(tmp_path / "sibpyc", 'WEB_TOOL_NAMES = frozenset({"web_search"})\n')
    sib = tmp_path / "sibpyc" / "libs" / "subagents" / "__init__.py"
    sibpyc = Path(importlib.util.cache_from_source(str(sib)))
    py_compile.compile(str(sib), cfile=str(sibpyc), doraise=True)
    sibpyc.write_bytes(sibpyc.read_bytes()[:20])
    # a ZERO-BYTE target cache (Python ignores it and recompiles) beside a torn PARENT cache:
    # the parent is the owner — the target's harmless cache must not be blamed first (EM1)
    _fake_hub(tmp_path / "zerotarget", 'WEB_TOOL_NAMES = frozenset({"web_search"})\n')
    zt = tmp_path / "zerotarget" / "libs" / "subagents" / "web_tools.py"
    Path(importlib.util.cache_from_source(str(zt))).parent.mkdir(exist_ok=True)
    Path(importlib.util.cache_from_source(str(zt))).write_bytes(b"")
    par = tmp_path / "zerotarget" / "libs" / "__init__.py"
    parpyc = Path(importlib.util.cache_from_source(str(par)))
    py_compile.compile(str(par), cfile=str(parpyc), doraise=True)
    parpyc.write_bytes(parpyc.read_bytes()[:20])
    # a torn cache of a sibling web_tools.py imports DIRECTLY (`from .tools import` — the
    # production shape): the target's own import line is a real frame, so the frame rule would
    # blame the target; the failure ended inside the import machinery, so the caches decide (EM1)
    _fake_hub(
        tmp_path / "sibtoolspyc",
        'from .tools import H\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        tools_body="H = 1\n",
    )
    tp = tmp_path / "sibtoolspyc" / "libs" / "subagents" / "tools.py"
    tppyc = Path(importlib.util.cache_from_source(str(tp)))
    py_compile.compile(str(tp), cfile=str(tppyc), doraise=True)
    tppyc.write_bytes(tppyc.read_bytes()[:20])
    # a sibling RAISING at import beside a coincidentally torn cache of ANOTHER sibling: the
    # failure has a real innermost frame (the raising sibling), so the caches are NOT consulted
    # and the raising sibling is named — the trigger guard is load-bearing (pass 55)
    _fake_hub(
        tmp_path / "raiseplustorn",
        'from .tools import H\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        tools_body="raise RuntimeError('tools WIP')\n",
        extra={"libs/subagents/other.py": "X = 1\n"},
    )
    oth = tmp_path / "raiseplustorn" / "libs" / "subagents" / "other.py"
    othpyc = Path(importlib.util.cache_from_source(str(oth)))
    py_compile.compile(str(oth), cfile=str(othpyc), doraise=True)
    othpyc.write_bytes(othpyc.read_bytes()[:20])
    # a NUL-padded SIBLING (a SyntaxError with no filename, frames stripped → the importer is the
    # last frame): the sibling's SOURCE is asked, compile-first, and named — never the target (EO1)
    _fake_hub(
        tmp_path / "nulsib",
        'from .tools import H\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        tools_body="H = 1\n",
    )
    (tmp_path / "nulsib" / "libs" / "subagents" / "tools.py").write_bytes(b"H = 1\n\x00\n")
    # a DIRECTORY where a sibling belongs (a half-finished checkout): the sibling is named (EO1)
    _fake_hub(
        tmp_path / "dirsib", 'from .tools import H\nWEB_TOOL_NAMES = frozenset({"web_search"})\n'
    )
    (tmp_path / "dirsib" / "libs" / "subagents" / "tools.py").mkdir()
    # an UNREADABLE sibling: a PermissionError inside the machinery (frames kept, innermost
    # frozen) with no torn cache — the frame's attribution must be KEPT (the round-54 `elif`) (EO1)
    _fake_hub(
        tmp_path / "nopermsib",
        'from .tools import H\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        tools_body="H = 1\n",
    )
    # a STALE-header target cache (recompiled by Python) beside a torn parent cache: the parent
    # is named — the header clause end-to-end, not only the zero-byte one (EO1)
    _fake_hub(tmp_path / "staletarget", 'WEB_TOOL_NAMES = frozenset({"web_search"})\n')
    stt = tmp_path / "staletarget" / "libs" / "subagents" / "web_tools.py"
    stpyc = Path(importlib.util.cache_from_source(str(stt)))
    py_compile.compile(str(stt), cfile=str(stpyc), doraise=True)
    hdr = bytearray(stpyc.read_bytes()[:20])
    hdr[8:12] = (1).to_bytes(4, "little")
    stpyc.write_bytes(bytes(hdr))
    stpar = tmp_path / "staletarget" / "libs" / "__init__.py"
    stparpyc = Path(importlib.util.cache_from_source(str(stpar)))
    py_compile.compile(str(stpar), cfile=str(stparpyc), doraise=True)
    stparpyc.write_bytes(stparpyc.read_bytes()[:20])
    # a target cache whose body unmarshals to a NON-code object (CPython: ImportError "Non-code
    # object", `path` = the pyc): the target's own cache is torn — a BLOCK (EO1)
    _fake_hub(tmp_path / "noncode", 'WEB_TOOL_NAMES = frozenset({"web_search"})\n')
    nct = tmp_path / "noncode" / "libs" / "subagents" / "web_tools.py"
    ncpyc = Path(importlib.util.cache_from_source(str(nct)))
    py_compile.compile(str(nct), cfile=str(ncpyc), doraise=True)
    import marshal

    ncpyc.write_bytes(ncpyc.read_bytes()[:16] + marshal.dumps(42))
    # BOTH the parent's and the target's caches torn: a BLOCK naming both dirs — the remedy
    # must fix the failure in one step (EO1)
    _fake_hub(tmp_path / "bothtorn", 'WEB_TOOL_NAMES = frozenset({"web_search"})\n')
    for src in (
        tmp_path / "bothtorn" / "libs" / "__init__.py",
        tmp_path / "bothtorn" / "libs" / "subagents" / "web_tools.py",
    ):
        pc = Path(importlib.util.cache_from_source(str(src)))
        py_compile.compile(str(src), cfile=str(pc), doraise=True)
        pc.write_bytes(pc.read_bytes()[:20])
    # an UNRELATED broken sibling (never imported) beside a target that raises at import: the
    # target's own blame must not be stolen — a BLOCK, never an advisory naming other.py (EQ1)
    _fake_hub(
        tmp_path / "unrelatedsib",
        "raise RuntimeError('real hub defect')\n",
        extra={"libs/subagents/other.py": "X = 1\n"},
    )
    (tmp_path / "unrelatedsib" / "libs" / "subagents" / "other.py").write_bytes(b"X = 1\n\x00\n")
    # the same, with a renamed constant (an ImportError whose own `path` IS the target)
    _fake_hub(
        tmp_path / "unrelatedsib2",
        'WEB_TOOL_NAMES_V2 = frozenset({"web_search"})\n',
        extra={"libs/subagents/other.py": "X = 1\n"},
    )
    (tmp_path / "unrelatedsib2" / "libs" / "subagents" / "other.py").write_bytes(b"X = 1\n\x00\n")
    # a NESTED subpackage the target imports, NUL-padded: the population is recursive (EQ1)
    _fake_hub(
        tmp_path / "deepnul",
        'from .sub.deep import H\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        extra={"libs/subagents/sub/__init__.py": "", "libs/subagents/sub/deep.py": "H = 1\n"},
    )
    (tmp_path / "deepnul" / "libs" / "subagents" / "sub" / "deep.py").write_bytes(b"H = 1\n\x00\n")
    # a nested module's cache torn: named with its cache remedy, never the target
    _fake_hub(
        tmp_path / "deeppyc",
        'from .sub.deep import H\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        extra={"libs/subagents/sub/__init__.py": "", "libs/subagents/sub/deep.py": "H = 1\n"},
    )
    dp = tmp_path / "deeppyc" / "libs" / "subagents" / "sub" / "deep.py"
    dppyc = Path(importlib.util.cache_from_source(str(dp)))
    py_compile.compile(str(dp), cfile=str(dppyc), doraise=True)
    dppyc.write_bytes(dppyc.read_bytes()[:20])
    # the CLOSURE, not the directory: a target that raises ImportError / opens a missing file /
    # imports a missing sibling, beside an UNRELATED NUL-padded file nobody imports (in the
    # package or in the parent package) — every one stays the target's BLOCK (ES1)
    for name, body in (
        ("raiseimp_nul", "raise ImportError('vendor sync broke')\n"),
        (
            "oserr_nul",
            'open("definitely_missing_cfg_xyz.yaml")\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        ),
        ("missingsib_nul", 'from .nope import x\nWEB_TOOL_NAMES = frozenset({"web_search"})\n'),
    ):
        _fake_hub(tmp_path / name, body, extra={"libs/subagents/other.py": "X = 1\n"})
        (tmp_path / name / "libs" / "subagents" / "other.py").write_bytes(b"X = 1\n\x00\n")
    _fake_hub(
        tmp_path / "parentbroken",
        "raise ImportError('vendor sync broke')\n",
        extra={"libs/cost_budget.py": "X = 1\n"},
    )
    (tmp_path / "parentbroken" / "libs" / "cost_budget.py").write_bytes(b"X = 1\n\x00\n")
    # a SOURCELESS sibling `.pyc` (tools.py deleted): a non-code body → CPython names the pyc in
    # exc.path — an advisory naming the file itself as the artifact; a torn body → the frameless
    # EOFError — the closure holds the sourceless module (ES1)
    for name in ("noncode_sourceless", "sourceless_torn"):
        _fake_hub(
            tmp_path / name,
            'from .tools import H\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
            tools_body="H = 1\n",
        )
        tsrc = tmp_path / name / "libs" / "subagents" / "tools.py"
        tpyc = tsrc.with_suffix(".pyc")
        py_compile.compile(str(tsrc), cfile=str(tpyc), doraise=True)
        tsrc.unlink()
        raw = tpyc.read_bytes()
        tpyc.write_bytes(
            raw[:16] + marshal.dumps([1, 2, 3]) if name == "noncode_sourceless" else raw[:20]
        )
    # two nested same-named modules, both caches torn: both named repo-relatively, both dirs (ES1)
    _fake_hub(
        tmp_path / "twinutil",
        'from .a.util.mod import A\nfrom .b.util.mod import B\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        extra={f"libs/subagents/{d}/__init__.py": "" for d in ("a", "a/util", "b", "b/util")},
    )
    for d in ("a", "b"):
        modp = tmp_path / "twinutil" / "libs" / "subagents" / d / "util" / "mod.py"
        modp.write_text(f"{d.upper()} = 1\n", encoding="utf-8")
        mp = Path(importlib.util.cache_from_source(str(modp)))
        py_compile.compile(str(modp), cfile=str(mp), doraise=True)
        mp.write_bytes(mp.read_bytes()[:20])
    # a NUL-padded imported sibling beside a FIFO / a second NUL file that sort first but are not
    # in the closure: the imported one is named (ES1)
    _fake_hub(
        tmp_path / "fifofirst",
        'from .tools import H\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        tools_body="H = 1\n",
    )
    (tmp_path / "fifofirst" / "libs" / "subagents" / "tools.py").write_bytes(b"H = 1\n\x00\n")
    os.mkfifo(tmp_path / "fifofirst" / "libs" / "subagents" / "aaa_fifo.py")
    _fake_hub(
        tmp_path / "twobroken",
        'from .tools import H\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        tools_body="H = 1\n",
        extra={"libs/subagents/aaa.py": "A = 1\n"},
    )
    (tmp_path / "twobroken" / "libs" / "subagents" / "tools.py").write_bytes(b"H = 1\n\x00\n")
    (tmp_path / "twobroken" / "libs" / "subagents" / "aaa.py").write_bytes(b"A = 1\n\x00\n")
    # TWO imported modules broken: both named, so fixing the first never runs into the second (ES1)
    _fake_hub(
        tmp_path / "twoimported",
        'from .tools import H\nfrom .bbb import B\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        tools_body="H = 1\n",
        extra={"libs/subagents/bbb.py": "B = 1\n"},
    )
    (tmp_path / "twoimported" / "libs" / "subagents" / "tools.py").write_bytes(b"H = 1\n\x00\n")
    (tmp_path / "twoimported" / "libs" / "subagents" / "bbb.py").write_bytes(b"B = 1\n\x00\n")
    # pass 60 (EY8): a submodule the package __init__ SHADOWS is never imported; a PACKAGE wins over
    # a same-stem module; a taken runtime branch's broken module is NAMED beside the block
    _fake_hub(
        tmp_path / "attrshadow",
        'from .pkg import x\nraise ImportError("vendor sync broke")\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        extra={"libs/subagents/pkg/__init__.py": "x = 1\n", "libs/subagents/pkg/x.py": "X = 1\n"},
    )
    (tmp_path / "attrshadow" / "libs" / "subagents" / "pkg" / "x.py").write_bytes(b"X = 1\n\x00\n")
    _fake_hub(
        tmp_path / "stemtwin",
        'from .x import X\nraise ImportError("vendor sync broke")\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        extra={"libs/subagents/x/__init__.py": "X = 1\n", "libs/subagents/x.py": "X = 1\n"},
    )
    (tmp_path / "stemtwin" / "libs" / "subagents" / "x.py").write_bytes(
        b"X = 1\n\x00\n"
    )  # the stale module nobody loads
    _fake_hub(
        tmp_path / "stemtwin2",
        'from .x import X\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        extra={"libs/subagents/x/__init__.py": "X = 1\n", "libs/subagents/x.py": "X = 1\n"},
    )
    (tmp_path / "stemtwin2" / "libs" / "subagents" / "x" / "__init__.py").write_bytes(
        b"X = 1\n\x00\n"
    )  # the loaded package IS the broken one
    _fake_hub(
        tmp_path / "vertaken",
        'import sys\nif sys.version_info >= (3, 0):\n    from .compat import X\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        extra={"libs/subagents/compat.py": "X = 1\n"},
    )
    (tmp_path / "vertaken" / "libs" / "subagents" / "compat.py").write_bytes(b"X = 1\n\x00\n")
    # pass 60 (EY9): a runtime OSError is the target's OWN; find_spec raising; sys.exit at import; a bogus exc.path
    _fake_hub(
        tmp_path / "oserr_impnul",
        'open("definitely_missing_cfg_xyz.yaml")\nfrom .tools import H\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',  # the target's OWN OSError first; the NUL sibling is in the closure but never reached
        tools_body="H = 1\n",
    )
    (tmp_path / "oserr_impnul" / "libs" / "subagents" / "tools.py").write_bytes(b"H = 1\n\x00\n")
    _fake_hub(
        tmp_path / "stubdep",
        'import sys, types\nsys.modules.setdefault("fakedep_xyz", types.ModuleType("fakedep_xyz"))\nfrom fakedep_xyz.sub import x\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    _fake_hub(
        tmp_path / "sysexit0",
        'import sys\nsys.exit(0)\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    _fake_hub(
        tmp_path / "bogus_path",
        'raise ImportError("vendor sync broke", path="/etc")\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    # pass 61 (EZ8): a module that PRINTS at import (the check's stdout must stay ⚠-first); an absent
    # distribution under an installed NAMESPACE root (`google.protobuf`) is an advisory, not a block
    _fake_hub(
        tmp_path / "chatty",
        'print("[subagents] loading provider registry")\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    _fake_hub(
        tmp_path / "nsdist",
        'from nsdist_xyz.core import Thing\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    # pass 62 (FB7): a PEP 562 `__getattr__` that raises leaves the import STATEMENT with nothing
    # on the recorder — blank blame was a fail-OPEN advisory for the target's own defect
    _fake_hub(
        tmp_path / "lazygetattr",
        'def __getattr__(name):\n    raise RuntimeError("provider registry unavailable: " + name)\n',
    )
    # a loader whose create_module raises (an extension module's init): the IMPORTER took the
    # blame and the gate blocked under web_tools.py's name for a sibling's broken extension
    _fake_hub(
        tmp_path / "createfail",
        'from . import speedup\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        init_body=(
            "import importlib.abc, importlib.machinery, os, sys\n"
            "class _L(importlib.abc.Loader):\n"
            "    def create_module(self, spec):\n"
            "        raise ImportError('wrong ELF class: ELFCLASS32')\n"
            "    def exec_module(self, module):\n"
            "        pass\n"
            "class _F:\n"
            "    def find_spec(self, name, path=None, target=None):\n"
            "        if name == __name__ + '.speedup':\n"
            "            return importlib.machinery.ModuleSpec(name, _L(), origin=os.path.join(os.path.dirname(__file__), 'speedup.so'))\n"
            "        return None\n"
            "sys.meta_path.append(_F())\n"
        ),
    )
    # a HEALTHY sourceless .pyc that merely raises is not a torn cache — "replace the .pyc" sent
    # the operator to fix an artifact CPython loaded fine
    _fake_hub(
        tmp_path / "pycraises",
        'from .tools import H\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        tools_body='raise RuntimeError("vendored WIP")\nH = 1\n',
    )
    _pyc_src = tmp_path / "pycraises" / "libs" / "subagents" / "tools.py"
    py_compile.compile(str(_pyc_src), cfile=str(_pyc_src.with_suffix(".pyc")), doraise=True)
    _pyc_src.unlink()
    # a write to FD 1 / FD 2 bypasses redirect_stdout: it led the check's stdout (breaking the
    # ⚠-first --json contract) and a stderr banner rode into the gate row unscrubbed
    _fake_hub(
        tmp_path / "fdchatty",
        'import os, sys\nos.write(1, b"[subagents] fd1 banner\\n")\nsys.stderr.write("[subagents] stderr banner\\n")\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    # the LAST module to ask for a missing distribution is the one that required it: a sibling
    # swallows the optional import, the target then requires it — the target is named, not the
    # sibling (and vice versa)
    _fake_hub(
        tmp_path / "swallowreq",
        'from . import tools\nimport optdep_absent_xyz\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        tools_body="try:\n    import optdep_absent_xyz\nexcept ImportError:\n    pass\n",
    )
    # a missing submodule of a REPO-ROOT PACKAGE (`db/`) is ours — the importer's own defect,
    # never "a distribution not installed"
    _fake_hub(
        tmp_path / "rootpkg",
        'import db.nope\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    (tmp_path / "rootpkg" / "db").mkdir()
    (tmp_path / "rootpkg" / "db" / "schema.sql").write_text("", encoding="utf-8")
    # pass 63 (FC1): a raw fd-2 write and a `sys.__stdout__` write bypass every Python-level
    # redirect — only the fd-level sink sees them, and their byte counts are exact
    _fake_hub(
        tmp_path / "fd2raw",
        'import os\nos.write(2, b"[subagents] raw fd2 banner\\n")\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    _fake_hub(
        tmp_path / "dunder",
        'import sys\nsys.__stdout__.write("[subagents] dunder banner\\n")\nsys.__stdout__.flush()\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    # a module's LEGITIMATE stream-API use at import (`sys.stderr.buffer`) raised inside the
    # module under a StringIO redirect — a false block under its own name
    _fake_hub(
        tmp_path / "stderr_buffer",
        'import sys\nsys.stderr.buffer.write(b"[subagents] buffered\\n")\nsys.stderr.flush()\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    # a PEP 562 raise AFTER a swallowed optional import: `rec.missing` is non-empty, so the
    # "nothing failed or went missing" test read the target's own defect as an advisory
    _fake_hub(
        tmp_path / "lazygetattr_swallowmissing",
        'try:\n    import optdep_absent_zzz\nexcept ImportError:\n    pass\ndef __getattr__(name):\n    raise RuntimeError("provider registry unavailable: " + name)\n',
    )
    _fake_hub(tmp_path / "healthy", 'WEB_TOOL_NAMES = frozenset({"web_search"})\n')
    # pass 64 (FD3): a sibling installs a non-module PROXY in sys.modules whose __getattr__ raises
    # on `__loader__` — the unwind raised before the fd restore and the gate exited 1 with no output
    _fake_hub(
        tmp_path / "proxy_sibling",
        'from . import lazy\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        extra={
            "libs/subagents/lazy.py": "import sys\nclass _P:\n    def __getattr__(self, a):\n        raise ImportError('backend unavailable: ' + a)\nsys.modules[__name__] = _P()\n"
        },
    )
    # a module that REBINDS sys.stdout kept the binding after the probe
    _fake_hub(
        tmp_path / "stdout_rebind",
        'import io, sys\nsys.stdout = io.StringIO()\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    # a finder that raises for the target's name — the import machinery's failure, never the target's
    _fake_hub(
        tmp_path / "finder_raises",
        'WEB_TOOL_NAMES = frozenset({"web_search"})\n',
        init_body="import sys\nclass _F:\n    def find_spec(self, name, path=None, target=None):\n        if name == 'libs.subagents.web_tools' and path and 'finder_raises' in str(list(path)[0]):\n            raise RuntimeError('editable-install finder broke')\n        return None\nsys.meta_path.insert(0, _F())\n",
    )
    # pass 65 (FE2): the pre-`reconfigure()` UTF-8 idiom re-wraps the ORIGINAL buffer; dropping the
    # wrapper on the binding restore let its finalizer close the buffer — no verdict, exit 1
    _fake_hub(
        tmp_path / "rewrap_stdout",
        'import io, sys\nsys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    # an unflushed `sys.__stdout__` write made BEFORE a rebind stayed pending and led the verdict on
    # the restored fd with no advisory (FE2)
    _fake_hub(
        tmp_path / "dunder_rebind",
        'import io, sys\nsys.__stdout__.write("BANNER-VIA-DUNDER\\n")\nsys.stdout = io.StringIO()\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    (
        tmp_path / "site" / "nsdist_xyz"
    ).mkdir()  # a namespace package: present for every sibling distribution
    # an exception whose __str__ RAISES: the verdict must still be one line, never a traceback (EZ8)
    _fake_hub(
        tmp_path / "lazystr",
        'class _LazyError(Exception):\n    def __str__(self):\n        raise ValueError("boom in __str__")\nraise _LazyError()\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    # a NUL module named only inside a FUNCTION BODY / an `if TYPE_CHECKING:` block is never
    # executed at import: the target's own SOURCE-SHAPED raise (an ImportError with no path — the
    # shape that opens the sibling redirect) stays the target's BLOCK (EU4)
    _fake_hub(
        tmp_path / "lazysteal",
        'raise ImportError("vendor sync broke")\n\ndef f():\n    from .typ import X\n    return X\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        extra={"libs/subagents/typ.py": "X = 1\n"},
    )
    (tmp_path / "lazysteal" / "libs" / "subagents" / "typ.py").write_bytes(b"X = 1\n\x00\n")
    _fake_hub(
        tmp_path / "typesteal",
        'from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from .typ import X\nraise ImportError("vendor sync broke")\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        extra={"libs/subagents/typ.py": "X = 1\n"},
    )
    (tmp_path / "typesteal" / "libs" / "subagents" / "typ.py").write_bytes(b"X = 1\n\x00\n")
    # a FIFO at an IMPORTED sibling's path: in the closure, named, never OPENED (a read blocks forever) (EU4)
    _fake_hub(
        tmp_path / "fifoimported",
        'from .missing import x\nfrom .fifo import y\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    os.mkfifo(tmp_path / "fifoimported" / "libs" / "subagents" / "fifo.py")
    # the break one hop away from a HEALTHY importer: the package __init__ imports a NUL agent.py —
    # the frame names __init__.py, the closure names agent.py (EU4)
    _fake_hub(
        tmp_path / "indirectnul",
        'WEB_TOOL_NAMES = frozenset({"web_search"})\n',
        init_body="from .agent import Runner\n",
        extra={"libs/subagents/agent.py": "class Runner:\n    pass\n"},
    )
    (tmp_path / "indirectnul" / "libs" / "subagents" / "agent.py").write_bytes(
        b"class Runner:\n    pass\n\x00\n"
    )
    # a DANGLING symlink at an imported sibling's path is in the closure and named (EU4)
    _fake_hub(
        tmp_path / "danglingsib",
        'from .tools import H\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    os.symlink(
        "/nonexistent/vendored/tools.py",
        tmp_path / "danglingsib" / "libs" / "subagents" / "tools.py",
    )
    # a distribution this interpreter lacks: the module is not broken — an advisory naming it (EU4)
    _fake_hub(
        tmp_path / "absentdep",
        'import httpx_not_installed_xyz\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    # two torn caches: named in the order CPython LOADS them — depth-first, `deep` before `b` (EU4)
    _fake_hub(
        tmp_path / "dfsorder",
        'from .a import A\nfrom .b import B\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        extra={
            "libs/subagents/a.py": "from .deep import D\nA = 1\n",
            "libs/subagents/b.py": "B = 1\n",
            "libs/subagents/deep.py": "D = 1\n",
        },
    )
    for name in ("deep", "b"):
        modp = tmp_path / "dfsorder" / "libs" / "subagents" / f"{name}.py"
        mp = Path(importlib.util.cache_from_source(str(modp)))
        py_compile.compile(str(modp), cfile=str(mp), doraise=True)
        mp.write_bytes(mp.read_bytes()[:20])
    # pass 59 (EW7): a NUL module named only in a branch nothing static proves runs — a never-taken
    # `except ImportError:`, a version check, a `TYPE_CHECKING or …` test — never takes the blame
    for hub, body in (
        (
            "trysteal",
            'try:\n    import fcntl\nexcept ImportError:\n    from .typ import X\nraise ImportError("vendor sync broke")\n',
        ),
        (
            "versteal",
            'import sys\nif sys.version_info >= (3, 99):\n    from .typ import X\nraise ImportError("vendor sync broke")\n',
        ),
        (
            "boolsteal",
            'from typing import TYPE_CHECKING\nif TYPE_CHECKING or False:\n    from .typ import X\nraise ImportError("vendor sync broke")\n',
        ),
    ):
        _fake_hub(
            tmp_path / hub,
            body + 'WEB_TOOL_NAMES = frozenset({"web_search"})\n',
            extra={"libs/subagents/typ.py": "X = 1\n"},
        )
        (tmp_path / hub / "libs" / "subagents" / "typ.py").write_bytes(b"X = 1\n\x00\n")
    # the TYPE_CHECKING `else` and a `with` body DO run: a NUL module there is named
    for hub, body in (
        (
            "typeelse",
            "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    pass\nelse:\n    from .tools import H\n",
        ),
        (
            "nestedimports",
            "import contextlib\nwith contextlib.nullcontext():\n    from .tools import H\n",
        ),
    ):
        _fake_hub(
            tmp_path / hub,
            body + 'WEB_TOOL_NAMES = frozenset({"web_search"})\n',
            tools_body="H = 1\n",
        )
        (tmp_path / hub / "libs" / "subagents" / "tools.py").write_bytes(b"H = 1\n\x00\n")
    # a typo'd ROOT of our own package and a missing SUBMODULE of an installed distribution are
    # module defects (a BLOCK), never "a dependency is not installed" (EW7)
    _fake_hub(
        tmp_path / "typoimport",
        'from subagents.impl import Z\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        extra={"libs/subagents/impl.py": "Z = 1\n"},
    )
    _fake_hub(
        tmp_path / "subdepmissing",
        'from json.nope import z\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    # a NUL module at the REPO ROOT is a broken file of ours, not a missing distribution
    _fake_hub(tmp_path / "rootmod", 'import rootmod\nWEB_TOOL_NAMES = frozenset({"web_search"})\n')
    (tmp_path / "rootmod" / "rootmod.py").write_bytes(b"R = 1\n\x00\n")
    # a SIBLING's missing distribution keeps the sibling's name in the advisory
    _fake_hub(
        tmp_path / "sibdep",
        'from .tools import H\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        tools_body="import httpx_not_installed_xyz\nH = 1\n",
    )
    # a failure raised OUTSIDE the closure (a site-packages module) keeps its own blame even when
    # a NUL sibling sits one import later
    _fake_hub(
        tmp_path / "extthenthird",
        'import extmod_xyz\nfrom .third import T\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
        extra={"libs/subagents/third.py": "T = 1\n"},
    )
    (tmp_path / "extthenthird" / "libs" / "subagents" / "third.py").write_bytes(b"T = 1\n\x00\n")
    (tmp_path / "site" / "extmod_xyz.py").write_text(
        'raise ImportError("optional extra missing")\n', encoding="utf-8"
    )
    # the module fails opening a DATA file at import: the FileNotFoundError names a non-.py, so
    # the frame — web_tools.py — is the truth: a BLOCK (EI1)
    _fake_hub(
        tmp_path / "missingcfg",
        'open("definitely_missing_cfg_xyz.yaml")\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    # a real collection that is not a set literal — dict keys — is ACCEPTED: predicate 1 runs
    # and flags the bait (EG1; the consumer's `name in WEB_TOOL_NAMES` accepts it too)
    _fake_hub(tmp_path / "dictkeys", '_REG = {"web_search": 1}\nWEB_TOOL_NAMES = _REG.keys()\n')
    # a SYMLINKED libs/ (the vendored tree lives elsewhere): an in-repo file must still read
    # repo-relative, never "(outside the repo)" (EE1)
    vend = tmp_path / "vendored"
    _fake_hub(tmp_path / "symlibs", None)
    (vend / "subagents").mkdir(parents=True)
    (vend / "__init__.py").write_text("", encoding="utf-8")
    (vend / "subagents" / "__init__.py").write_text(
        "raise RuntimeError('sibling WIP')\n", encoding="utf-8"
    )
    (vend / "subagents" / "web_tools.py").write_text(
        'WEB_TOOL_NAMES = frozenset({"web_search"})\n', encoding="utf-8"
    )
    (tmp_path / "symlibs" / "libs").symlink_to(vend, target_is_directory=True)
    driver = tmp_path / "driver.py"
    driver.write_text(
        "import json, sys\n"
        f"sys.path.insert(0, {str(REPO / 'scripts' / 'enforcement')!r})\n"
        "from pathlib import Path\n"
        "import check_command_corpus as c\n"
        "out = {}\n"
        f"for name in ('broken', 'empty', 'absent', 'sibling', 'syntax', 'renamed', 'sibtools', 'extdep', 'extpkg', 'strconst', 'noneconst', 'badmember', 'rtsyntax', 'suffix', 'symlibs', 'parentwt', 'nulbytes', 'noperm', 'dirmod', 'dictkeys', 'dangling', 'nopermdir', 'corruptpyc', 'missingcfg', 'sibpyc', 'zerotarget', 'sibtoolspyc', 'raiseplustorn', 'nulsib', 'dirsib', 'nopermsib', 'staletarget', 'noncode', 'bothtorn', 'unrelatedsib', 'unrelatedsib2', 'deepnul', 'deeppyc', 'raiseimp_nul', 'oserr_nul', 'missingsib_nul', 'parentbroken', 'noncode_sourceless', 'sourceless_torn', 'twinutil', 'fifofirst', 'twobroken', 'twoimported', 'lazysteal', 'typesteal', 'fifoimported', 'indirectnul', 'danglingsib', 'absentdep', 'dfsorder', 'trysteal', 'versteal', 'boolsteal', 'typeelse', 'nestedimports', 'typoimport', 'subdepmissing', 'rootmod', 'sibdep', 'extthenthird', 'attrshadow', 'stemtwin', 'stemtwin2', 'vertaken', 'oserr_impnul', 'stubdep', 'sysexit0', 'bogus_path', 'chatty', 'nsdist', 'lazystr', 'lazygetattr', 'createfail', 'pycraises', 'fdchatty', 'swallowreq', 'rootpkg', 'fd2raw', 'dunder', 'stderr_buffer', 'lazygetattr_swallowmissing', 'healthy', 'proxy_sibling', 'stdout_rebind', 'finder_raises', 'rewrap_stdout', 'dunder_rebind'):\n"
        f"    hub = Path({str(tmp_path)!r}) / name\n"
        "    for k in [k for k in sys.modules if k == 'libs' or k.startswith('libs.')]:\n"
        "        del sys.modules[k]\n"
        f"    site = {str(tmp_path / 'site')!r}\n"
        "    if site in sys.path:\n"
        "        sys.path.remove(site)\n"
        "    if name in ('extdep', 'extpkg', 'extthenthird', 'nsdist'):\n"  # the dependency dir reaches ONLY the hubs that need it — a `libs` package there would beat a namespace-shaped hub (pass 50)
        "        sys.path.append(site)\n"
        "    probs = c.audit(hub / 'commands' / '_sources', hub / 'commands' / '_fragments', hub / 'commands' / 'assemble_commands.py', hub, agents=hub / 'no-agents')\n"
        "    out[name] = {'problems': probs, 'skipped': list(c.SKIPPED_PREDICATES), 'failure': list(c._IMPORT_FAILURE), 'advisories': list(c.ADVISORIES)}\n"
        "print(json.dumps(out))\n",
        encoding="utf-8",
    )
    # the unreadable fixtures are armed LAST: 500 lines of fixture construction sat between the
    # chmod(0) and the finally that restores it — a raise in between left pytest's tmp dir
    # undeletable (L64-3/9, FD8) — and MEASURED after arming: the FD8 move measured the modes
    # before they were applied, so all three "unreadable" branches below were dead (B65-1, FF1)
    (tmp_path / "noperm" / "libs" / "subagents" / "web_tools.py").chmod(0)
    (tmp_path / "nopermdir" / "libs" / "subagents").chmod(0)
    (tmp_path / "nopermsib" / "libs" / "subagents" / "tools.py").chmod(0)
    noperm_unreadable = not os.access(
        tmp_path / "noperm" / "libs" / "subagents" / "web_tools.py", os.R_OK
    )
    nopermdir_unreadable = not os.access(tmp_path / "nopermdir" / "libs" / "subagents", os.R_OK)
    nopermsib_unreadable = not os.access(
        tmp_path / "nopermsib" / "libs" / "subagents" / "tools.py", os.R_OK
    )
    try:
        r = subprocess.run(
            [sys.executable, str(driver)], capture_output=True, text=True, timeout=120
        )
    finally:
        (tmp_path / "nopermdir" / "libs" / "subagents").chmod(
            0o755
        )  # pytest's tmp cleanup must be able to remove it
        (tmp_path / "nopermsib" / "libs" / "subagents" / "tools.py").chmod(0o644)
        (tmp_path / "noperm" / "libs" / "subagents" / "web_tools.py").chmod(0o644)
    assert r.returncode == 0, r.stdout + r.stderr
    # the driver prints ONE line: any module banner that reached fd 1 during an import is a leak
    # the old `json.loads(lines[-1])` silently tolerated — the grader could not see the invariant (FB7)
    assert len(r.stdout.strip().splitlines()) == 1, r.stdout
    assert not r.stderr, (
        "STDERR LEAK: " + r.stderr[:500]
    )  # an fd-2 write rides into the gate row unscrubbed (FC1)
    out = json.loads(r.stdout.strip().splitlines()[-1])
    # a first failing hub aborts the other verdicts; pytest shows captured stdout on failure, so
    # one red run prints every hub's state instead of only the one that broke (L)
    print(json.dumps(out, indent=1))
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
    # a broken SIBLING: no problem under web_tools.py's name, an advisory naming the real file
    assert not any(
        "web_tools.py is present but unusable" in p for p in out["sibling"]["problems"]
    ), out["sibling"]
    assert len(out["sibling"]["skipped"]) == 1, out["sibling"]
    assert (
        "__init__.py failed to import (RuntimeError: sibling WIP)" in out["sibling"]["skipped"][0]
    ), out["sibling"]
    assert "predicate 1 did not run" in out["sibling"]["skipped"][0]
    # the half-saved web_tools.py itself: BLOCK, blamed on web_tools.py (EC1)
    assert any(
        "web_tools.py is present but unusable (SyntaxError" in p for p in out["syntax"]["problems"]
    ), out["syntax"]
    assert out["syntax"]["skipped"] == [], out["syntax"]
    # a renamed constant: BLOCK via `exc.path`
    assert any(
        "present but unusable (ImportError: cannot import name 'WEB_TOOL_NAMES'" in p
        for p in out["renamed"]["problems"]
    ), out["renamed"]
    # a half-saved SIBLING that web_tools imports directly: an advisory naming tools.py, no block
    assert not any(
        "web_tools.py is present but unusable" in p for p in out["sibtools"]["problems"]
    ), out["sibtools"]
    assert (
        len(out["sibtools"]["skipped"]) == 1
        and "tools.py failed to import (SyntaxError" in out["sibtools"]["skipped"][0]
    ), out["sibtools"]
    assert "__init__" not in out["sibtools"]["skipped"][0]
    # a dependency outside the repo: an advisory naming the file, never an absolute path
    assert (
        len(out["extdep"]["skipped"]) == 1
        and "broken_dep_xyz.py (outside the repo) failed to import (ImportError: broken wheel)"
        in out["extdep"]["skipped"][0]
    ), out["extdep"]
    assert (
        "broken_pkg/__init__.py (outside the repo) failed to import (ImportError: broken pkg)"
        in out["extpkg"]["skipped"][0]
    ), out["extpkg"]
    # the constant's shape — each a hub PROBLEM naming the shape, never a traceback or an inverted check
    assert any(
        "present but unusable (WEB_TOOL_NAMES is not a collection of str (str))" in p
        for p in out["strconst"]["problems"]
    ), out["strconst"]
    assert not any("is not a real tool" in p for p in out["strconst"]["problems"]), out["strconst"]
    assert any(
        "present but unusable (WEB_TOOL_NAMES is not a collection of str (NoneType))" in p
        for p in out["noneconst"]["problems"]
    ), out["noneconst"]
    assert any(
        "present but unusable (WEB_TOOL_NAMES has a member that is not a non-empty str)" in p
        for p in out["badmember"]["problems"]
    ), out["badmember"]
    # a runtime SyntaxError: BLOCK, blamed on web_tools.py by its frame
    assert any(
        "web_tools.py is present but unusable (SyntaxError" in p
        for p in out["rtsyntax"]["problems"]
    ), out["rtsyntax"]
    assert out["rtsyntax"]["skipped"] == [], out["rtsyntax"]
    # a suffix collision: an advisory naming deep_web_tools.py, never a block under web_tools.py's name
    assert not any(
        "web_tools.py is present but unusable" in p for p in out["suffix"]["problems"]
    ), out["suffix"]
    assert (
        len(out["suffix"]["skipped"]) == 1
        and "deep_web_tools.py failed to import (RuntimeError: deep WIP)"
        in out["suffix"]["skipped"][0]
    ), out["suffix"]
    # a symlinked libs/: repo-relative, never "(outside the repo)"
    assert (
        len(out["symlibs"]["skipped"]) == 1
        and "libs/subagents/__init__.py failed to import (RuntimeError: sibling WIP)"
        in out["symlibs"]["skipped"][0]
    ), out["symlibs"]
    assert "outside" not in out["symlibs"]["skipped"][0], out["symlibs"]
    # the same basename elsewhere: an advisory naming libs/web_tools.py, never a block
    assert not any("is present but unusable" in p for p in out["parentwt"]["problems"]), out[
        "parentwt"
    ]
    assert (
        len(out["parentwt"]["skipped"]) == 1
        and "libs/web_tools.py failed to import (RuntimeError: standalone WIP)"
        in out["parentwt"]["skipped"][0]
    ), out["parentwt"]
    # the file's own health — each a BLOCK naming the cause, no traceback, no misattribution
    assert any(
        "web_tools.py is present but unusable (SyntaxError: source code string cannot contain null bytes"
        in p
        for p in out["nulbytes"]["problems"]
    ), out["nulbytes"]
    assert out["nulbytes"]["skipped"] == [], out["nulbytes"]
    if noperm_unreadable:  # root reads anything — the shape is unreachable there
        assert any(
            "web_tools.py is present but unusable (PermissionError" in p
            for p in out["noperm"]["problems"]
        ), out["noperm"]
        assert out["noperm"]["skipped"] == [], out["noperm"]
        unusable_file = [p for p in out["noperm"]["problems"] if "present but unusable" in p]
        assert unusable_file and not any(str(tmp_path) in p for p in unusable_file), out[
            "noperm"
        ]  # the target-check branch scrubs too (EK1)
    assert any(
        "web_tools.py is present but unusable (not a regular file)" in p
        for p in out["dirmod"]["problems"]
    ), out["dirmod"]
    # a dangling symlink: present and broken, never "absent"
    assert any(
        "web_tools.py is present but unusable (not a regular file)" in p
        for p in out["dangling"]["problems"]
    ), out["dangling"]
    assert out["dangling"]["skipped"] == [], out["dangling"]
    # an unreadable parent: a BLOCK naming the PermissionError, no traceback, no absolute path
    if nopermdir_unreadable:  # root reads anything — the shape is unreachable there
        assert any(
            "web_tools.py is present but unusable (PermissionError" in p
            for p in out["nopermdir"]["problems"]
        ), out["nopermdir"]
        unusable = [p for p in out["nopermdir"]["problems"] if "present but unusable" in p]
        assert unusable and not any(str(tmp_path) in p for p in unusable), out[
            "nopermdir"
        ]  # the exception's quoted path is scrubbed
    # a corrupt bytecode cache: a BLOCK on the target, blamed via the checker's own frame
    assert any(
        "web_tools.py is present but unusable (bytecode cache of libs/subagents/web_tools.py unloadable (EOFError"
        in p
        for p in out["corruptpyc"]["problems"]
    ), out["corruptpyc"]
    assert any("delete libs/subagents/__pycache__" in p for p in out["corruptpyc"]["problems"]), (
        out["corruptpyc"]
    )
    assert out["corruptpyc"]["skipped"] == [], out["corruptpyc"]
    # a missing data file opened at import: the module's own failure — a BLOCK
    assert any(
        "web_tools.py is present but unusable (FileNotFoundError" in p
        for p in out["missingcfg"]["problems"]
    ), out["missingcfg"]
    assert out["missingcfg"]["skipped"] == [], out["missingcfg"]
    # a sibling's torn cache: an advisory naming the sibling's cache, never a block
    assert not any("present but unusable" in p for p in out["sibpyc"]["problems"]), out["sibpyc"]
    assert (
        len(out["sibpyc"]["skipped"]) == 1
        and "libs/subagents/__init__.py failed to import (bytecode cache of libs/subagents/__init__.py unloadable (EOFError"
        in out["sibpyc"]["skipped"][0]
    ), out["sibpyc"]
    # a zero-byte target cache beside a torn parent cache: the PARENT is named, not the target
    assert not any("present but unusable" in p for p in out["zerotarget"]["problems"]), out[
        "zerotarget"
    ]
    assert (
        len(out["zerotarget"]["skipped"]) == 1
        and "libs/__init__.py failed to import (bytecode cache of libs/__init__.py unloadable (EOFError"
        in out["zerotarget"]["skipped"][0]
    ), out["zerotarget"]
    assert "delete libs/__pycache__" in out["zerotarget"]["skipped"][0], out["zerotarget"]
    # a torn cache of the DIRECT sibling: an advisory naming tools.py, never a block on the target
    assert not any("present but unusable" in p for p in out["sibtoolspyc"]["problems"]), out[
        "sibtoolspyc"
    ]
    assert (
        len(out["sibtoolspyc"]["skipped"]) == 1
        and "libs/subagents/tools.py failed to import (bytecode cache of libs/subagents/tools.py unloadable (EOFError"
        in out["sibtoolspyc"]["skipped"][0]
    ), out["sibtoolspyc"]
    # a raising sibling beside another sibling's torn cache: the raise is named, not the cache
    assert not any("present but unusable" in p for p in out["raiseplustorn"]["problems"]), out[
        "raiseplustorn"
    ]
    assert (
        len(out["raiseplustorn"]["skipped"]) == 1
        and "libs/subagents/tools.py failed to import (RuntimeError: tools WIP)"
        in out["raiseplustorn"]["skipped"][0]
    ), out["raiseplustorn"]
    assert "bytecode cache" not in out["raiseplustorn"]["skipped"][0], out["raiseplustorn"]
    # a NUL-padded sibling / a directory at a sibling's path: an advisory naming the sibling
    for hub in ("nulsib", "dirsib"):
        assert not any("present but unusable" in p for p in out[hub]["problems"]), (hub, out[hub])
        assert (
            len(out[hub]["skipped"]) == 1
            and "libs/subagents/tools.py failed to import" in out[hub]["skipped"][0]
        ), (hub, out[hub])
    # an unreadable sibling with no torn cache: the frame's attribution is KEPT, never "unknown"
    if nopermsib_unreadable:
        assert not any("present but unusable" in p for p in out["nopermsib"]["problems"]), out[
            "nopermsib"
        ]
        assert (
            len(out["nopermsib"]["skipped"]) == 1
            and "libs/subagents/tools.py failed to import (PermissionError"
            in out["nopermsib"]["skipped"][0]
        ), out["nopermsib"]
    # a stale-header target cache beside a torn parent: the parent is named, end to end
    assert not any("present but unusable" in p for p in out["staletarget"]["problems"]), out[
        "staletarget"
    ]
    assert (
        len(out["staletarget"]["skipped"]) == 1
        and "bytecode cache of libs/__init__.py unloadable" in out["staletarget"]["skipped"][0]
    ), out["staletarget"]
    # a non-code body in the target's own cache: a BLOCK, never an advisory on the pyc's path
    assert any(
        "web_tools.py is present but unusable (bytecode cache of libs/subagents/web_tools.py unloadable"
        in p
        for p in out["noncode"]["problems"]
    ), out["noncode"]
    # both caches torn: CPython fails on the PACKAGE first — named with its remedy (an advisory);
    # the target's own torn cache is the next run's block (the recorder names what CPython hit, EZ5)
    assert any(
        "bytecode cache of libs/__init__.py unloadable" in s and "delete libs/__pycache__" in s
        for s in out["bothtorn"]["skipped"]
    ), out["bothtorn"]
    # an unrelated broken sibling never steals the target's own blame: still a BLOCK on the target
    for hub in ("unrelatedsib", "unrelatedsib2"):
        assert any("web_tools.py is present but unusable" in p for p in out[hub]["problems"]), (
            hub,
            out[hub],
        )
        assert out[hub]["skipped"] == [], (hub, out[hub])
    # a nested subpackage: the population is recursive — the deep module is named, not the target
    assert not any("present but unusable" in p for p in out["deepnul"]["problems"]), out["deepnul"]
    assert (
        len(out["deepnul"]["skipped"]) == 1
        and "libs/subagents/sub/deep.py failed to import" in out["deepnul"]["skipped"][0]
    ), out["deepnul"]
    assert not any("present but unusable" in p for p in out["deeppyc"]["problems"]), out["deeppyc"]
    assert (
        len(out["deeppyc"]["skipped"]) == 1
        and "bytecode cache of libs/subagents/sub/deep.py unloadable"
        in out["deeppyc"]["skipped"][0]
        and "delete libs/subagents/sub/__pycache__" in out["deeppyc"]["skipped"][0]
    ), out["deeppyc"]
    # the closure: an unrelated NUL file (package or parent package) never takes the target's blame
    for hub in ("raiseimp_nul", "oserr_nul", "missingsib_nul", "parentbroken"):
        assert any("web_tools.py is present but unusable" in p for p in out[hub]["problems"]), (
            hub,
            out[hub],
        )
        assert out[hub]["skipped"] == [], (hub, out[hub])
    # a sourceless sibling pyc: named as the artifact itself, with a remedy that fits
    assert (
        len(out["noncode_sourceless"]["skipped"]) == 1
        and "bytecode cache of libs/subagents/tools.pyc unloadable"
        in out["noncode_sourceless"]["skipped"][0]
        and "replace libs/subagents/tools.pyc" in out["noncode_sourceless"]["skipped"][0]
    ), out["noncode_sourceless"]
    assert not any("present but unusable" in p for p in out["sourceless_torn"]["problems"]), out[
        "sourceless_torn"
    ]
    assert (
        len(out["sourceless_torn"]["skipped"]) == 1
        and "bytecode cache of libs/subagents/tools.pyc unloadable"
        in out["sourceless_torn"]["skipped"][0]
    ), out["sourceless_torn"]
    # two same-named nested modules: both named, both cache dirs, repo-relative
    tw = (
        out["twinutil"]["skipped"][0]
        if out["twinutil"]["skipped"]
        else " ".join(out["twinutil"]["problems"])
    )
    assert (  # the first torn cache CPython loads, named repo-relatively with its own dir (EZ5)
        "libs/subagents/a/util/mod.py unloadable" in tw
        and "delete libs/subagents/a/util/__pycache__" in tw
    ), out["twinutil"]
    # the imported broken sibling is named, never a FIFO or NUL file outside the closure
    for hub in ("fifofirst", "twobroken"):
        assert (
            len(out[hub]["skipped"]) == 1
            and "libs/subagents/tools.py failed to import" in out[hub]["skipped"][0]
        ), (hub, out[hub])
        assert "aaa" not in out[hub]["skipped"][0], (hub, out[hub])
    assert (  # the first broken module CPython reached; the second is the next run's (EZ5)
        len(out["twoimported"]["skipped"]) == 1
        and "libs/subagents/tools.py failed to import" in out["twoimported"]["skipped"][0]
    ), out["twoimported"]
    # pass 58 (EU4): a lazily / TYPE_CHECKING-imported NUL module never steals the target's blame
    for hub in ("lazysteal", "typesteal"):
        assert any(
            "web_tools.py is present but unusable (ImportError: vendor sync broke" in p
            for p in out[hub]["problems"]
        ), (hub, out[hub])
        # named only INSIDE the "also broken" note — never the blamed file, never an advisory (EY8)

        assert not out[hub]["skipped"] and not any(
            p.startswith("libs/subagents/typ.py") for p in out[hub]["problems"]
        ), (hub, out[hub])
    # a FIFO one import away: the driver returned (no hang — nothing static opens it, EZ5); the
    # failure CPython hit first is the MISSING module the target imports — its own defect, a block
    assert any(
        "web_tools.py is present but unusable" in p and "libs.subagents.missing" in p
        for p in out["fifoimported"]["problems"]
    ), out["fifoimported"]
    # the healthy importer is never blamed for the NUL module it imports
    assert (
        len(out["indirectnul"]["skipped"]) == 1
        and "libs/subagents/agent.py failed to import" in out["indirectnul"]["skipped"][0]
    ), out["indirectnul"]
    assert "libs/subagents/tools.py" in " ".join(
        out["danglingsib"]["skipped"] + out["danglingsib"]["problems"]
    ), out["danglingsib"]
    assert not any("present but unusable" in p for p in out["absentdep"]["problems"]) and any(
        "httpx_not_installed_xyz" in s and "not installed in this interpreter" in s
        for s in out["absentdep"]["skipped"]
    ), out["absentdep"]
    dfs = " ".join(out["dfsorder"]["skipped"] + out["dfsorder"]["problems"])
    assert "bytecode cache of libs/subagents/deep.py unloadable" in dfs and "b.py" not in dfs, (
        out["dfsorder"]
    )  # `deep` is what CPython loads first (a → deep before b) — the recorder needs no order model (EZ5)
    # pass 59 (EW7)
    for hub in ("trysteal", "versteal", "boolsteal"):
        assert any(
            "web_tools.py is present but unusable (ImportError: vendor sync broke" in p
            for p in out[hub]["problems"]
        ), (hub, out[hub])
        assert not out[hub]["skipped"] and not any(
            p.startswith("libs/subagents/typ.py") for p in out[hub]["problems"]
        ), (hub, out[hub])
    for hub in ("typeelse", "nestedimports"):
        assert (
            len(out[hub]["skipped"]) == 1
            and "libs/subagents/tools.py failed to import" in out[hub]["skipped"][0]
        ), (hub, out[hub])
    for hub in ("typoimport", "subdepmissing", "rootmod"):
        joined = " ".join(out[hub]["problems"] + out[hub]["skipped"])
        assert "not installed in this interpreter" not in joined, (hub, out[hub])
        assert (
            any("present but unusable" in p for p in out[hub]["problems"]) or "rootmod.py" in joined
        ), (hub, out[hub])
    assert not any("present but unusable" in p for p in out["sibdep"]["problems"]) and any(
        s.startswith("web-tool names: libs/subagents/tools.py failed to import")
        and "not installed in this interpreter" in s
        for s in out["sibdep"]["skipped"]
    ), out["sibdep"]
    ext = " ".join(out["extthenthird"]["skipped"] + out["extthenthird"]["problems"])
    assert "extmod_xyz" in ext and "third.py" not in ext, out["extthenthird"]
    # pass 60 (EY8/EY9)
    for hub in ("attrshadow", "stemtwin", "bogus_path", "oserr_impnul", "stubdep", "sysexit0"):
        assert any("web_tools.py is present but unusable" in p for p in out[hub]["problems"]), (
            hub,
            out[hub],
        )
        assert not out[hub]["skipped"], (hub, out[hub])
    assert "x.py" not in " ".join(out["attrshadow"]["problems"]) and "x.py" not in " ".join(
        out["stemtwin"]["problems"]
    ), (out["attrshadow"], out["stemtwin"])
    assert "libs/subagents/x/__init__.py failed to import" in " ".join(
        out["stemtwin2"]["skipped"]
    ), out["stemtwin2"]
    # a TAKEN runtime branch's broken module is what CPython executed: named, an advisory —
    # the healthy target is never blamed (EZ5)
    assert "libs/subagents/compat.py failed to import" in " ".join(out["vertaken"]["skipped"]), out[
        "vertaken"
    ]
    assert not any("present but unusable" in p for p in out["vertaken"]["problems"]), out[
        "vertaken"
    ]
    assert any("SystemExit" in p for p in out["sysexit0"]["problems"]), out["sysexit0"]
    # pass 61 (EZ8)
    assert not any("present but unusable" in p for p in out["chatty"]["problems"]), out["chatty"]
    assert not out["chatty"]["skipped"] and any(
        "wrote" in s and "bytes to stdout/stderr at import" in s
        for s in out["chatty"]["advisories"]
    ), (
        out["chatty"]
    )  # an ADVISORY — the predicate RAN; "predicate skipped" claimed incomplete coverage of a complete audit (FB7)
    assert not any("present but unusable" in p for p in out["nsdist"]["problems"]), out["nsdist"]
    # pass 62 (FB7)
    assert any(
        "present but unusable" in p and "RuntimeError: provider registry unavailable" in p
        for p in out["lazygetattr"]["problems"]
    ), out["lazygetattr"]
    assert not any("present but unusable" in p for p in out["createfail"]["problems"]) and any(
        "speedup.so" in s and "ELFCLASS32" in s for s in out["createfail"]["skipped"]
    ), out["createfail"]
    assert any(
        "tools.pyc failed to import (RuntimeError: vendored WIP)" in s and "bytecode cache" not in s
        for s in out["pycraises"]["skipped"]
    ), out["pycraises"]
    assert not any("present but unusable" in p for p in out["fdchatty"]["problems"]) and any(
        "bytes to stdout/stderr" in s for s in out["fdchatty"]["advisories"]
    ), out["fdchatty"]
    assert any(
        "web_tools.py imports a distribution not installed" in s and "/tools.py" not in s
        for s in out["swallowreq"]["skipped"]
    ), out["swallowreq"]
    assert any(
        "present but unusable" in p and "imports it" in p for p in out["rootpkg"]["problems"]
    ), out["rootpkg"]
    # pass 63 (FC1)
    assert any(
        re.search(r"wrote 2[4-8] bytes to stdout/stderr", s) for s in out["fd2raw"]["advisories"]
    ), out[
        "fd2raw"
    ]  # the raw fd-2 banner, counted by the fd-level sink (no Python-level layer sees it)
    assert any(re.search(r"wrote 2[3-7] bytes", s) for s in out["dunder"]["advisories"]), out[
        "dunder"
    ]
    assert not any("present but unusable" in p for p in out["stderr_buffer"]["problems"]) and any(
        "bytes to stdout/stderr" in s for s in out["stderr_buffer"]["advisories"]
    ), out["stderr_buffer"]
    assert any(
        "present but unusable" in p and "provider registry unavailable" in p
        for p in out["lazygetattr_swallowmissing"]["problems"]
    ), out["lazygetattr_swallowmissing"]
    assert out["healthy"]["advisories"] == [] and out["healthy"]["skipped"] == [], out[
        "healthy"
    ]  # cleared per audit
    # pass 64 (FD3): the driver printed its JSON line at all — a raising unwind had left fd 1 on the sink
    assert not any("present but unusable" in p for p in out["proxy_sibling"]["problems"]), out[
        "proxy_sibling"
    ]
    assert not any("present but unusable" in p for p in out["stdout_rebind"]["problems"]), out[
        "stdout_rebind"
    ]
    assert any(
        "editable-install finder broke" in s
        for s in out["finder_raises"]["skipped"] + out["finder_raises"]["problems"]
    ), out["finder_raises"]
    assert (
        out["rewrap_stdout"]["problems"] == list(out["healthy"]["problems"])
        and out["rewrap_stdout"]["failure"] == []
    ), out["rewrap_stdout"]  # the driver printed its verdict at all (FE2)
    assert any("bytes to stdout/stderr" in s for s in out["dunder_rebind"]["advisories"]), out[
        "dunder_rebind"
    ]
    assert "BANNER-VIA-DUNDER" not in r.stdout, "the banner led the verdict on the restored fd"
    assert any(
        s.startswith("web-tool names: importing libs/subagents/web_tools.py failed (")
        for s in out["nsdist"]["skipped"]
    ), out[
        "nsdist"
    ]  # the blank-blame render no longer names web_tools.py as the failing file and then disowns it
    assert any(
        "nsdist_xyz" in s and "not installed in this interpreter" in s
        for s in out["nsdist"]["skipped"]
    ), out["nsdist"]

    assert any(
        "present but unusable (_LazyError: <str() failed>)" in p for p in out["lazystr"]["problems"]
    ), out["lazystr"]
    # dict keys ACCEPTED: the predicate ran and flagged the bait
    assert not any("present but unusable" in p for p in out["dictkeys"]["problems"]), out[
        "dictkeys"
    ]
    assert any("'exa' is not a real tool" in p for p in out["dictkeys"]["problems"]), out[
        "dictkeys"
    ]


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


@pytest.mark.parametrize(
    ("value", "expect"),
    [
        (frozenset({"web_search"}), None),
        (("web_search", "web_search"), None),
        ({"web_search": 1}.keys(), None),
        ({"web_search": 1}, None),
        ("web_search", "not a collection of str (str)"),
        (b"web_search", "not a collection of str (bytes)"),
        (None, "not a collection of str (NoneType)"),
        (7, "not a collection of str (int)"),
        ((n for n in ["web_search"]), "not a collection of str (generator)"),
        (frozenset(), "is empty"),
        (frozenset({"web_search", ""}), "member that is not a non-empty str"),
        ([1, 2], "member that is not a non-empty str"),
    ],
)
def test_shape_problem_names_every_bad_shape_and_accepts_every_real_collection(value, expect):
    """Direct unit grading of the shape rule — the driver grades it only through one 20-hub
    assertion chain (pass 51)."""
    import check_command_corpus as ccc

    got = ccc._shape_problem(value)
    assert (got is None) if expect is None else (got and expect in got), (value, got)


def test_display_path_is_cwd_independent_and_never_absolute(tmp_path, monkeypatch):
    """A pseudo path (`<frozen importlib._bootstrap>`, `<string>`) or a relative one must not
    resolve against the cwd and read as a repo file; an out-of-repo package keeps its package;
    an empty blame is named as unknown (EG1)."""
    import check_command_corpus as ccc

    repo = tmp_path / "repo"
    (repo / "libs").mkdir(parents=True)
    inside = repo / "libs" / "x.py"
    inside.write_text("", encoding="utf-8")
    for cwd in (repo, tmp_path):
        monkeypatch.chdir(cwd)
        assert ccc._display_path(str(inside), repo) == "libs/x.py"
        assert (
            ccc._display_path("<frozen importlib._bootstrap>", repo)
            == "<frozen importlib._bootstrap> (not a file)"
        )
        assert ccc._display_path("<string>", repo) == "<string> (not a file)"
        assert ccc._display_path("", repo) == "an unknown file"
        assert (
            ccc._display_path(str(tmp_path / "site" / "pkg" / "__init__.py"), repo)
            == "pkg/__init__.py (outside the repo)"
        )
        assert (
            ccc._display_path(str(tmp_path / "site" / "dep.py"), repo)
            == "dep.py (outside the repo)"
        )
    # the RESOLVED branch: a blame given through a symlinked alias of the repo, the repo given
    # resolved — the literal `relative_to` fails, the resolved one places it (pass 52)
    alias = tmp_path / "alias"
    alias.symlink_to(repo, target_is_directory=True)
    assert ccc._display_path(str(alias / "libs" / "x.py"), repo.resolve()) == "libs/x.py"


def test_same_file_is_identity_and_survives_an_unresolvable_blame(tmp_path):
    """`libs/web_tools.py` and `libs/subagents/web_tools.py` share a basename and are different
    files; a symlink loop (pathlib raises RuntimeError, not OSError) or an embedded NUL is never
    the target (EG1)."""
    import check_command_corpus as ccc

    (tmp_path / "libs" / "subagents").mkdir(parents=True)
    target = tmp_path / "libs" / "subagents" / "web_tools.py"
    target.write_text("", encoding="utf-8")
    other = tmp_path / "libs" / "web_tools.py"
    other.write_text("", encoding="utf-8")
    assert ccc._same_file(str(target), target)
    assert not ccc._same_file(str(other), target)
    loop = tmp_path / "loop"
    loop.symlink_to(loop)
    assert not ccc._same_file(str(loop / "web_tools.py"), target)
    assert not ccc._same_file("bad\0name", target)


def test_target_is_broken_asks_the_file(tmp_path):
    """NUL bytes, a directory, an unreadable file and a syntax error are settled by reading and
    compiling the target — never by a traceback (EG1); a file that compiles is not broken."""
    import check_command_corpus as ccc

    t = tmp_path / "web_tools.py"
    t.write_text("WEB_TOOL_NAMES = frozenset()\n", encoding="utf-8")
    assert ccc._target_is_broken(t) is None
    t.write_bytes(b"x = 1\n\x00")
    assert "null bytes" in (ccc._target_is_broken(t) or "")
    t.write_text("def broken(:\n", encoding="utf-8")
    assert (ccc._target_is_broken(t) or "").startswith("SyntaxError")
    d = tmp_path / "dir.py"
    d.mkdir()
    assert ccc._target_is_broken(d) == "not a regular file"


def test_the_manual_rules_select_the_hash_branch_on_bit_zero_like_cpython(tmp_path):
    """CPython's `hash_based` is bit 0; bit 1 is only `check_source`. The manual fallback keyed
    the hash compare on bit 1, so a `flags=0b10` cache (timestamp-validated by CPython) read
    "not accepted" and a torn body under it was missed (EU4)."""
    import importlib.util

    import check_command_corpus as ccc

    src = tmp_path / "m.py"
    src.write_text("x = 1\n", encoding="utf-8")
    st = src.stat()
    stamp = (int(st.st_mtime) & 0xFFFFFFFF).to_bytes(4, "little") + (
        st.st_size & 0xFFFFFFFF
    ).to_bytes(4, "little")
    magic = importlib.util.MAGIC_NUMBER
    good_hash = importlib.util.source_hash(src.read_bytes())
    assert ccc._manual_cache_accepted(magic + (0b10).to_bytes(4, "little") + stamp, st, src) is True
    assert (
        ccc._manual_cache_accepted(magic + (0b10).to_bytes(4, "little") + b"\x00" * 8, st, src)
        is False
    )
    assert (
        ccc._manual_cache_accepted(magic + (0b01).to_bytes(4, "little") + b"\xff" * 8, st, src)
        is True
    )
    assert (
        ccc._manual_cache_accepted(magic + (0b11).to_bytes(4, "little") + b"\xff" * 8, st, src)
        is False
    )
    assert (
        ccc._manual_cache_accepted(magic + (0b11).to_bytes(4, "little") + good_hash, st, src)
        is True
    )


def test_the_failure_text_is_safe_and_bounded():
    """`str(exc)` may raise (a lazy message) or run to megabytes: neither is a traceback out of a
    gate nor a 10 MB gate row (EZ8)."""
    import check_command_corpus as ccc

    class _LazyError(Exception):
        def __str__(self):
            raise ValueError("boom in __str__")

    assert ccc._safe_str(_LazyError()) == "<str() failed>"
    big = ccc._safe_str(RuntimeError("x" * 10_000_000))
    assert len(big) < 600 and "+9999500 chars" in big, big[-40:]


def test_an_unread_corpus_file_is_reported_repo_relative(tmp_path, monkeypatch):
    """The unread-file list bypassed `_scrub`: every other stdout path is scrubbed (EZ8)."""
    import check_command_corpus as ccc

    monkeypatch.setattr(ccc, "REPO", tmp_path)
    ccc.SKIPPED.clear()
    gone = tmp_path / "commands" / "_sources" / "fabrik-gone.md"
    assert ccc._read(gone) is None
    assert ccc.SKIPPED and str(tmp_path) not in ccc.SKIPPED[-1], ccc.SKIPPED


_CLAUDE_MD = (
    "# fixture contract\n\nExample:\n```\nfix(x): y\n\nAgent-Role: primary\n"
    "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\n```\n"
)  # a FIXED trailer example — copying the live CLAUDE.md made predicate 4's verdict depend on whatever a sibling session was mid-editing (FB7)


def _probe_hub(tmp_path, web_tools_body, init_body=""):
    import shutil

    hub = tmp_path / "hub"
    (hub / "scripts" / "enforcement").mkdir(parents=True)
    (hub / "libs" / "subagents").mkdir(parents=True)
    (hub / "libs" / "__init__.py").write_text(init_body, encoding="utf-8")
    (hub / "libs" / "subagents" / "__init__.py").write_text("", encoding="utf-8")
    (hub / "libs" / "subagents" / "web_tools.py").write_text(web_tools_body, encoding="utf-8")
    shutil.copy(
        REPO / "scripts" / "enforcement" / "check_command_corpus.py",
        hub / "scripts" / "enforcement" / "check_command_corpus.py",
    )
    (hub / "CLAUDE.md").write_text(_CLAUDE_MD, encoding="utf-8")
    (hub / "commands" / "_sources").mkdir(parents=True)
    (hub / "commands" / "_sources" / "fabrik-x.md").write_text(
        "{{include:run-record}}\n", encoding="utf-8"
    )  # an empty corpus exits before the probe
    return hub


def test_the_import_probe_neither_loads_the_cwd_env_nor_lets_a_module_print(tmp_path):
    """The import runs in the gate's process: the package autoloaded the CWD's `.env` (20 curated
    secrets) into `os.environ`, and a module's print led the check's stdout — `--json` reads
    only ⚠-first output (EZ8). A fresh interpreter, cwd = a dir holding a sentinel `.env`."""
    import subprocess

    seen = tmp_path / "seen.txt"
    hub = _probe_hub(
        tmp_path,
        f"import os\nopen({str(seen)!r}, 'w').write(str(os.environ.get('EXA_API_KEY')))\nprint('[subagents] loading')\nWEB_TOOL_NAMES = frozenset({{'web_search'}})\n",
        "import os\nfrom dotenv import load_dotenv\nif os.getenv('SUBAGENTS_NO_AUTOLOAD') != '1':\n    load_dotenv(os.path.join(os.getcwd(), '.env'))\n",
    )
    (hub / ".env").write_text("EXA_API_KEY=SENTINEL_FROM_CWD\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("EXA_API_KEY", "SUBAGENTS_NO_AUTOLOAD")}
    env.update(
        {"ALERT_ENABLED": "0", "FABRIK_NO_AUTOLOAD": "1"}
    )  # an explicit env cannot inherit the conftest mute (B67-9)
    proc = subprocess.run(
        [
            sys.executable,
            str(hub / "scripts" / "enforcement" / "check_command_corpus.py"),
            "--quiet",
        ],
        cwd=hub,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    assert seen.read_text(encoding="utf-8") == "None", seen.read_text(encoding="utf-8")
    first = proc.stdout.lstrip().splitlines()[:1]
    assert not first or first[0].startswith("⚠"), proc.stdout[:200]
    assert "[subagents] loading" not in proc.stdout, proc.stdout[:200]


def test_a_keyboard_interrupt_at_import_is_never_a_verdict(tmp_path):
    """`except BaseException` must let Ctrl-C through: an interrupt during the import propagates
    instead of becoming "present but unusable (KeyboardInterrupt)" (EZ8)."""
    import subprocess

    hub = _probe_hub(tmp_path, "raise KeyboardInterrupt\n")
    proc = subprocess.run(
        [
            sys.executable,
            str(hub / "scripts" / "enforcement" / "check_command_corpus.py"),
            "--quiet",
        ],
        cwd=hub,
        env={
            k: os.environ[k] for k in ("PATH", "HOME", "LANG") if k in os.environ
        },  # never the whole parent environment into an import probe (B-10, FD8)
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert (
        proc.returncode != 0
        and "KeyboardInterrupt" in proc.stderr
        and "present but unusable" not in proc.stdout
    ), (proc.returncode, proc.stdout[:200])


def test_the_selftest_keeps_its_web_tool_canaries_when_the_hub_module_is_present_but_broken(
    tmp_path,
):
    """A hub whose `web_tools.py` RAISES is not a project: the six canaries stay and fail loudly
    (exit 1), never "N/A … (a project)" and exit 0 (EW7). A fresh interpreter, so the hub's own
    `libs` package is not already imported."""
    import shutil
    import subprocess

    hub = tmp_path / "hub"
    (hub / "scripts" / "enforcement").mkdir(parents=True)
    (hub / "libs" / "subagents").mkdir(parents=True)
    (hub / "libs" / "__init__.py").write_text("", encoding="utf-8")
    (hub / "libs" / "subagents" / "__init__.py").write_text("", encoding="utf-8")
    (hub / "libs" / "subagents" / "web_tools.py").write_text(
        'raise ImportError("vendor sync broke")\n', encoding="utf-8"
    )
    shutil.copy(
        REPO / "scripts" / "enforcement" / "check_command_corpus.py",
        hub / "scripts" / "enforcement" / "check_command_corpus.py",
    )
    (hub / "CLAUDE.md").write_text(_CLAUDE_MD, encoding="utf-8")
    (hub / "scripts" / "command_run.py").write_text("", encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(hub / "scripts" / "enforcement" / "check_command_corpus.py"),
            "--selftest",
        ],
        cwd=hub,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 1 and "N/A" not in proc.stdout, (proc.stdout, proc.stderr)


def test_the_selftest_in_a_project_without_the_trailer_example_marks_that_canary_not_applicable(
    tmp_path, monkeypatch, capsys
):
    """A project whose CLAUDE.md carries no Co-Authored-By example turns predicate 4 off by design;
    the canary said VACUOUS and exited 1 (EW7). The success line names what was N/A."""
    import check_command_corpus as ccc

    repo = tmp_path / "project"
    (repo / "scripts" / "enforcement").mkdir(parents=True)
    (repo / "CLAUDE.md").write_text(
        "# a project contract with no trailer example\n", encoding="utf-8"
    )
    (repo / "scripts" / "command_run.py").write_text("", encoding="utf-8")
    (repo / "scripts" / "enforcement" / "check_command_corpus.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(ccc, "REPO", repo)
    monkeypatch.setattr(ccc, "_live_web_tool_names", lambda *a, **k: None)
    assert ccc._selftest() == 0
    out = capsys.readouterr().out
    assert "N/A: the trailer-model canary skipped" in out and "VACUOUS" not in out, out
    assert (
        "8 canaries over 6 of the eight predicates" in out
        and "(N/A: web-tool names, trailer model)" in out
    ), out


def _pkg(tmp_path):
    pkg = tmp_path / "libs" / "subagents"
    pkg.mkdir(parents=True)
    (pkg.parent / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    return pkg


def test_an_unreadable_claude_md_turns_the_trailer_predicate_off_without_a_traceback(tmp_path):
    """`_canonical_trailer_model` read `CLAUDE.md` after a bare `exists()`; mode 000 or a directory
    at that path was a PermissionError/IsADirectoryError out of a blocking gate — and the home
    path in stderr (EY9)."""
    import os

    import check_command_corpus as ccc

    repo = tmp_path / "repo"
    (repo / "CLAUDE.md").mkdir(parents=True)
    assert ccc._canonical_trailer_model(repo) is None
    repo2 = tmp_path / "repo2"
    repo2.mkdir()
    (repo2 / "CLAUDE.md").write_text("Co-Authored-By: Claude X <x@y>\n", encoding="utf-8")
    (repo2 / "CLAUDE.md").chmod(0)
    if os.access(repo2 / "CLAUDE.md", os.R_OK):
        pytest.skip("running as root")
    try:
        assert ccc._canonical_trailer_model(repo2) is None
    finally:
        (repo2 / "CLAUDE.md").chmod(0o644)


def test_the_selftest_names_a_broken_module_cites_no_synced_only_path_and_derives_its_tool_names(
    tmp_path,
):
    """Three selftest shapes in fresh interpreters: a hub whose module RAISES prints the failure
    before the VACUOUS lines (the module is broken, not the check); a bare tree without
    `scripts/command_run.py` is not a FALSE POSITIVE; a live set of ONE tool name still passes
    (the fixture derives its names from the live set) (EY9)."""
    import shutil
    import subprocess

    def tree(name, web_tools_body):
        hub = tmp_path / name
        (hub / "scripts" / "enforcement").mkdir(parents=True)
        shutil.copy(
            REPO / "scripts" / "enforcement" / "check_command_corpus.py",
            hub / "scripts" / "enforcement" / "check_command_corpus.py",
        )
        (hub / "CLAUDE.md").write_text(_CLAUDE_MD, encoding="utf-8")
        if web_tools_body is not None:
            (hub / "libs" / "subagents").mkdir(parents=True)
            (hub / "libs" / "__init__.py").write_text("", encoding="utf-8")
            (hub / "libs" / "subagents" / "__init__.py").write_text("", encoding="utf-8")
            (hub / "libs" / "subagents" / "web_tools.py").write_text(
                web_tools_body, encoding="utf-8"
            )
        return subprocess.run(
            [
                sys.executable,
                str(hub / "scripts" / "enforcement" / "check_command_corpus.py"),
                "--selftest",
            ],
            cwd=hub,
            capture_output=True,
            text=True,
            timeout=120,
        )

    broken = tree("broken", 'raise RuntimeError("half-saved vendor sync")\n')
    assert (
        broken.returncode == 1
        and "predicate 1 cannot run: RuntimeError: half-saved vendor sync" in broken.stdout
    ), broken.stdout
    bare = tree("bare", None)
    assert bare.returncode == 0 and "FALSE POSITIVE" not in bare.stdout, (bare.stdout, bare.stderr)
    one = tree(
        "one", 'WEB_TOOL_NAMES = frozenset({"web_probe"})\n'
    )  # NOT web_search: the pad must come from the live set (EZ8)
    assert one.returncode == 0 and "15 canaries over 8" in one.stdout, (one.stdout, one.stderr)
    quoted = tree("quoted", 'WEB_TOOL_NAMES = frozenset({"web_search", \'docs"_lookup\'})\n')
    tree("pinned", 'WEB_TOOL_NAMES = frozenset({"web_search"})\n')
    (tmp_path / "pinned" / "CLAUDE.md").write_text(
        "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>\n", encoding="utf-8"
    )
    import subprocess as _sp

    pinned2 = _sp.run(
        [
            sys.executable,
            str(tmp_path / "pinned" / "scripts" / "enforcement" / "check_command_corpus.py"),
            "--selftest",
        ],
        cwd=tmp_path / "pinned",
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert pinned2.returncode == 0 and "VACUOUS" not in pinned2.stdout, (
        pinned2.stdout,
        pinned2.stderr,
    )  # the bad trailer derives from the canonical model — a repo pinning Opus 4.8 is not VACUOUS (EZ8)
    assert quoted.returncode == 0, (
        quoted.stdout,
        quoted.stderr,
    )  # a non-identifier name never enters the fixture's own syntax (EZ8)
    dangling = tmp_path / "dangling"
    (dangling / "scripts" / "enforcement").mkdir(parents=True)
    shutil.copy(
        REPO / "scripts" / "enforcement" / "check_command_corpus.py",
        dangling / "scripts" / "enforcement" / "check_command_corpus.py",
    )
    (dangling / "CLAUDE.md").write_text(_CLAUDE_MD, encoding="utf-8")
    (dangling / "libs" / "subagents").mkdir(parents=True)
    (dangling / "libs" / "subagents" / "web_tools.py").symlink_to(
        "/nonexistent/vendored/web_tools.py"
    )
    d = subprocess.run(
        [
            sys.executable,
            str(dangling / "scripts" / "enforcement" / "check_command_corpus.py"),
            "--selftest",
        ],
        cwd=dangling,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert d.returncode == 1 and "N/A" not in d.stdout, (
        d.stdout
    )  # a dangling link is PRESENT-and-broken, never "a project"


def test_the_selftest_in_a_project_marks_the_web_tool_canaries_not_applicable(
    tmp_path, monkeypatch, capsys
):
    """The script is synced to every project, the vendored pool module is not: there the six
    web-tool canaries printed VACUOUS and the selftest exited 1 (EU4)."""
    import check_command_corpus as ccc

    repo = tmp_path / "project"
    (repo / "scripts" / "enforcement").mkdir(parents=True)
    (repo / "CLAUDE.md").write_text(_CLAUDE_MD, encoding="utf-8")
    (repo / "scripts" / "command_run.py").write_text("", encoding="utf-8")
    (repo / "scripts" / "enforcement" / "check_command_corpus.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(ccc, "REPO", repo)
    monkeypatch.setattr(ccc, "_live_web_tool_names", lambda *a, **k: None)
    assert ccc._selftest() == 0
    out = capsys.readouterr().out
    assert "N/A: 6 web-tool canaries skipped" in out and "VACUOUS" not in out, out
    assert "9 canaries over 7 of the eight predicates" in out and "(N/A: web-tool names)" in out, (
        out
    )


def test_the_manual_fallback_accepts_a_sourceless_module_by_header_alone(tmp_path, monkeypatch):
    """With CPython's validators absent (`_be` None) a SOURCELESS `.pyc` has no source to compare
    an mtime or size against: the manual rules accept it by magic + flags alone. Without that
    shortcut the module's own stat is compared to its header and a good cache reads torn (EU2)."""
    import importlib.util

    import check_command_corpus as ccc

    monkeypatch.setattr(ccc, "_be", None)
    pyc = tmp_path / "sourceless.pyc"
    pyc.write_bytes(importlib.util.MAGIC_NUMBER + b"\x00" * 12 + b"body")
    assert ccc._cache_accepted(pyc.read_bytes(), pyc.stat(), pyc) is True
    torn = (
        importlib.util.MAGIC_NUMBER + (0b1000).to_bytes(4, "little") + b"\x00" * 8
    )  # reserved bit
    assert ccc._cache_accepted(torn, pyc.stat(), pyc) is False


def test_cpythons_validators_are_bound_on_this_interpreter_and_a_drifted_api_falls_back(
    tmp_path, monkeypatch
):
    """The primary path must be LIVE on CPython (pinning `_be = None` forever kept the suite
    green); a private validator whose signature drifted on a future CPython falls back to the
    manual rules instead of taking the gate down (ES1)."""
    import importlib.util
    import py_compile
    import types as _t

    import check_command_corpus as ccc

    assert (
        ccc._be is not None
        and callable(getattr(ccc._be, "_classify_pyc", None))
        and callable(getattr(ccc._be, "_validate_timestamp_pyc", None))
    )
    (tmp_path / "libs" / "subagents").mkdir(parents=True)
    src = tmp_path / "libs" / "subagents" / "web_tools.py"
    src.write_text("WEB_TOOL_NAMES = frozenset()\n", encoding="utf-8")
    pyc = Path(importlib.util.cache_from_source(str(src)))
    py_compile.compile(str(src), cfile=str(pyc), doraise=True)
    pyc.write_bytes(pyc.read_bytes()[:20])
    drifted = _t.SimpleNamespace(
        _classify_pyc=lambda data, name, details: 0,
        _validate_timestamp_pyc=lambda data, stats, name: None,
    )
    monkeypatch.setattr(ccc, "_be", drifted)
    assert ccc._cache_would_fail(src) is True  # the manual rules still see the torn body


def test_the_probe_restores_the_stream_bindings_and_survives_its_own_setup_failing(
    tmp_path, monkeypatch
):
    """A module that rebinds `sys.stdout` kept the binding (the verdict then printed into its
    object); a cached target plus a setup failure (ENOSPC on the sink) read as the target's own
    defect; the fd from `os.dup(1)` leaked when `os.dup(2)` raised (FD3)."""
    import tempfile

    import check_command_corpus as ccc

    hub = _probe_hub(
        tmp_path,
        'import io, sys\nsys.stdout = io.StringIO()\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    saved_mods = {
        k: sys.modules.pop(k) for k in list(sys.modules) if k == "libs" or k.startswith("libs.")
    }
    out0, err0 = sys.stdout, sys.stderr
    try:
        assert ccc._live_web_tool_names(hub) == frozenset({"web_search"})
        assert sys.stdout is out0 and sys.stderr is err0
        ccc._IMPORT_FAILURE.clear()
        ccc._IMPORT_BLAME.clear()

        def enospc():
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(tempfile, "TemporaryFile", enospc)
        fds_before = len(os.listdir("/proc/self/fd"))
        assert ccc._live_web_tool_names(hub) is None
        assert ccc._IMPORT_BLAME == [""] and "could not set up" in ccc._IMPORT_FAILURE[0], (
            ccc._IMPORT_FAILURE,
            ccc._IMPORT_BLAME,
        )
        assert len(os.listdir("/proc/self/fd")) == fds_before  # nothing leaked on the failed setup
        assert sys.stdout is out0
    finally:
        ccc._IMPORT_FAILURE.clear()
        ccc._IMPORT_BLAME.clear()
        for k in [k for k in sys.modules if k == "libs" or k.startswith("libs.")]:
            del sys.modules[k]
        sys.modules.update(saved_mods)
        while str(hub) in sys.path:
            sys.path.remove(str(hub))


def test_two_recorders_never_recurse_and_a_spec_is_wrapped_once():
    """The recorder walked the WHOLE meta_path: a second recorder called it back — RecursionError
    on the first import; a caching finder handing the same spec back twice was wrapped twice and
    the outer wrapper hid the inner from unwind (FD3)."""
    import importlib.machinery

    import check_command_corpus as ccc

    r1, r2 = ccc._ImportRecorder(), ccc._ImportRecorder()
    sys.meta_path.insert(0, r1)
    sys.meta_path.insert(0, r2)
    cache = None
    try:
        assert (
            r2.find_spec("json") is not None
        )  # resolves through r1 and PathFinder without recursion
        cached = importlib.machinery.ModuleSpec(
            "x.cached", importlib.machinery.SourceFileLoader("x.cached", "/dev/null")
        )
        first = ccc._RecordingLoader(cached.loader, "x.cached", r1)
        cached.loader = first
        r1.wrappers.append((cached, first))

        class _Cache:
            def find_spec(self, name, path=None, target=None):
                return cached if name == "x.cached" else None

        cache = _Cache()
        sys.meta_path.insert(sys.meta_path.index(r1) + 1, cache)
        assert r1.find_spec("x.cached") is cached and cached.loader is first  # ONE wrapper
        r1.unwind()
        assert not isinstance(cached.loader, ccc._RecordingLoader)
    finally:
        sys.meta_path[:] = [
            f for f in sys.meta_path if f is not r1 and f is not r2 and f is not cache
        ]
        r2.unwind()
        r1.unwind()


def test_two_closes_on_one_line_and_fenced_backticks_and_comments(corpus):
    """The second of two closes on a line was never windowed; inside a fence a backtick in an
    argument cut the window; a trailing shell comment carried the flag (FD4)."""
    problems = corpus(
        "`done --command fabrik-probe --feedback f` or `blocked --command fabrik-probe --reason r`\n"
    )
    assert sum("--feedback" in p for p in problems) == 1, problems
    body = '```bash\npython3 scripts/command_run.py done --command fabrik-probe --evidence "see `docs`" --feedback f\n```\n'
    assert not any("--feedback" in p for p in corpus(body)), corpus(body)
    body = "```bash\npython3 scripts/command_run.py done --command fabrik-probe --evidence e   # refuses without --feedback\n```\n"
    assert any("--feedback" in p for p in corpus(body)), corpus(body)
    # an UNCLOSED span absorbed twelve lines of prose — the close is graded on its own line (I-C6)
    problems = corpus(
        "`done --command fabrik-probe --evidence e\nprose says --feedback is required here\n"
    )
    assert any("--feedback" in p for p in problems), problems
    # the same-line closer half of the seed: prose after the closer on the NEXT line, no backtick there
    problems = corpus(
        "`python3 scripts/command_run.py done --command fabrik-probe --evidence e` prose\n--feedback is documented here\n"
    )
    assert any("--feedback" in p for p in problems), problems


def test_a_closing_fence_never_carries_an_info_string_and_a_tab_comment_is_a_comment(
    corpus, tmp_path
):
    """```bash inside an open fence is CONTENT (a nested-markdown demo fabricated a claim); a TAB
    before `#` in `name:` is a YAML comment; `command_run.py \\` + a BLANK line + `start` is two
    commands, not a run-record start (FD4)."""
    assert not corpus("```markdown\n```bash\nauto-called by /fabrik-real\n```\n```\n")
    src, frag = tmp_path / "_s", tmp_path / "_f"
    src.mkdir()
    frag.mkdir()
    (src / "fabrik-real.md").write_text("{{include:run-record}}\n")
    agents = tmp_path / "_a"
    agents.mkdir()
    (agents / "tabbed.md").write_text("---\nname: tabbed\t# the reviewer\ndescription: d\n---\n")
    assert not audit(
        src,
        frag,
        tmp_path / "no-assembler.py",
        tmp_path,
        agents=agents,
    )
    problems = corpus("python3 scripts/command_run.py \\\n\nstart --command x\n", with_record=False)
    assert any("opens no run record" in p for p in problems), problems
    problems = corpus("python3 scripts/command_run.py\tstart --command x\n", with_record=False)
    assert not any("opens no run record" in p for p in problems), problems


def test_a_fenced_or_commented_start_and_an_unclosed_frontmatter_and_a_quoted_hash(
    corpus, tmp_path
):
    """Predicate 5 was satisfied by a `start` inside a fence, an HTML comment, or `start-run`;
    predicate 6 fell back to the WHOLE file on an unclosed frontmatter and truncated a quoted
    `name:` at its `#` (FD4)."""
    for body in (
        "<!-- python3 scripts/command_run.py start --command x -->\nbody\n",
        "python3 scripts/command_run.py start-run --command x\n",
    ):
        problems = corpus(body, with_record=False)
        assert any("opens no run record" in p for p in problems), (body, problems)
    src, frag = tmp_path / "_s6", tmp_path / "_f6"
    src.mkdir()
    frag.mkdir()
    agents = tmp_path / "_a6"
    agents.mkdir()
    (src / "fabrik-real.md").write_text(
        "{{include:run-record}}\n"
    )  # an EMPTY sources dir is refused before the agents predicate runs
    (agents / "probe.md").write_text("---\n\nprose\nname: probe\ndescription: d\n")
    problems = audit(
        src,
        frag,
        tmp_path / "no-assembler.py",
        tmp_path,
        agents=agents,
    )
    assert any("never closed" in p for p in problems), problems
    (agents / "probe.md").write_text('---\nname: "probe"  # a note\ndescription: d\n---\n')
    assert not audit(
        src,
        frag,
        tmp_path / "no-assembler.py",
        tmp_path,
        agents=agents,
    )
    (agents / "probe.md").write_text('---\nname: "pro # be"\ndescription: d\n---\n')
    problems = audit(
        src,
        frag,
        tmp_path / "no-assembler.py",
        tmp_path,
        agents=agents,
    )
    assert any("declares `name: pro # be`" in p for p in problems), problems


def test_a_caller_naming_the_claimant_only_inside_a_fence_honours_nothing(corpus, tmp_path):
    """The claim side skips fences; the honour side did not — a fenced example in the caller
    honoured a false claim (FD4)."""
    (tmp_path / "_sources" / "fabrik-real.md").write_text(
        "{{include:run-record}}\n```\nexample: /fabrik-probe\n```\n"
    )
    problems = corpus("description: auto-called by /fabrik-real reactively.\n")
    assert any("claims caller /fabrik-real" in p for p in problems), problems


def _ast_emitters(ccc) -> int:
    """The grader's OWN count of `problems.append(…)` calls — never the function under test (FF1)."""
    import ast

    tree = ast.parse(Path(ccc.__file__).read_text(encoding="utf-8"))
    return len(
        {
            n.lineno
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "append"
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "problems"
        }
    )


def test_safe_str_keeps_only_printable_text():
    """A NUL or an ANSI escape in an import failure's message rode into the gate row (FD3)."""
    import check_command_corpus as ccc

    assert ccc._safe_str(RuntimeError("a\x00b\x1b[0m c\n d")) == "a b [0m c d"


def test_the_probe_survives_a_rewrapped_stream_flushes_the_originals_and_blames_the_same_way_twice(
    tmp_path, monkeypatch, capfd
):
    """`sys.stdout = io.TextIOWrapper(sys.stdout.buffer)` at import closed the SHARED buffer when the
    FD3 restore dropped the wrapper (the gate's own print then raised); an unflushed `sys.__stdout__`
    write made before a rebind led the verdict on the restored fd with no advisory; a cached PEP 562
    target was blamed on the first probe and silently skipped on the second (`was_loaded`, FE2)."""
    import check_command_corpus as ccc

    saved_mods = {
        k: sys.modules.pop(k) for k in list(sys.modules) if k == "libs" or k.startswith("libs.")
    }
    out0 = sys.stdout
    hub = _probe_hub(
        tmp_path,
        'import io, sys\nsys.__stdout__.write("BANNER-VIA-DUNDER\\n")\nsys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")\nWEB_TOOL_NAMES = frozenset({"web_search"})\n',
    )
    try:
        ccc.ADVISORIES.clear()
        assert ccc._live_web_tool_names(hub) == frozenset({"web_search"})
        assert sys.stdout is out0 and not sys.stdout.closed
        print("verdict-still-printable")
        captured = capfd.readouterr()
        assert (
            "verdict-still-printable" in captured.out and "BANNER-VIA-DUNDER" not in captured.out
        ), captured.out
    finally:
        ccc.ADVISORIES.clear()
        for k in [k for k in sys.modules if k == "libs" or k.startswith("libs.")]:
            del sys.modules[k]
        sys.modules.update(saved_mods)
        while str(hub) in sys.path:
            sys.path.remove(str(hub))
    # the same PEP 562 target probed twice is blamed the same way twice
    hub2 = _probe_hub(
        tmp_path / "second",
        "def __getattr__(name):\n    raise RuntimeError('provider registry unavailable: ' + name)\n",
    )
    saved_mods = {
        k: sys.modules.pop(k) for k in list(sys.modules) if k == "libs" or k.startswith("libs.")
    }
    try:
        blames = []
        for _ in range(2):
            ccc._IMPORT_FAILURE.clear()
            ccc._IMPORT_BLAME.clear()
            assert ccc._live_web_tool_names(hub2) is None
            blames.append(list(ccc._IMPORT_BLAME))
        assert blames[0] == blames[1] and blames[0] != [""], blames
    finally:
        ccc._IMPORT_FAILURE.clear()
        ccc._IMPORT_BLAME.clear()
        for k in [k for k in sys.modules if k == "libs" or k.startswith("libs.")]:
            del sys.modules[k]
        sys.modules.update(saved_mods)
        while str(hub2) in sys.path:
            sys.path.remove(str(hub2))


def test_a_second_dup_failure_leaks_no_fd_and_a_proxy_sibling_leaves_no_wrapper(
    tmp_path, monkeypatch
):
    """`saved = [os.dup(1), os.dup(2)]` leaked the first fd when the second raised; the unwind's
    `getattr(mod, "__loader__", None)` form left two modules carrying a `_RecordingLoader` after a
    proxy sibling — both FD3 claims had no grader (FE2)."""
    import check_command_corpus as ccc

    hub = _probe_hub(
        tmp_path, 'from . import lazy\nimport json\nWEB_TOOL_NAMES = frozenset({"web_search"})\n'
    )
    (hub / "libs" / "subagents" / "lazy.py").write_text(
        "import sys\nclass _P:\n    def __getattr__(self, a):\n        raise ImportError('backend unavailable: ' + a)\nsys.modules[__name__] = _P()\n"
    )
    saved_mods = {
        k: sys.modules.pop(k) for k in list(sys.modules) if k == "libs" or k.startswith("libs.")
    }
    try:
        assert ccc._live_web_tool_names(hub) == frozenset({"web_search"})

        def _wrapped(mod):
            try:
                d = getattr(mod, "__dict__", None)
                loader = d.get("__loader__") if isinstance(d, dict) else None
                spec = d.get("__spec__") if isinstance(d, dict) else None
                return isinstance(loader, ccc._RecordingLoader) or isinstance(
                    getattr(spec, "loader", None), ccc._RecordingLoader
                )
            except Exception:  # noqa: BLE001
                return False

        assert [n for n, m in list(sys.modules.items()) if _wrapped(m)] == []
        real_dup = os.dup
        calls = {"n": 0}

        def flaky_dup(fd):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError(24, "Too many open files")
            return real_dup(fd)

        for k in [k for k in sys.modules if k == "libs" or k.startswith("libs.")]:
            del sys.modules[k]
        ccc._IMPORT_FAILURE.clear()
        ccc._IMPORT_BLAME.clear()
        monkeypatch.setattr(os, "dup", flaky_dup)
        before = len(os.listdir("/proc/self/fd"))
        assert ccc._live_web_tool_names(hub) is None
        assert len(os.listdir("/proc/self/fd")) == before and ccc._IMPORT_BLAME == [""], (
            ccc._IMPORT_FAILURE,
            ccc._IMPORT_BLAME,
        )
    finally:
        ccc._IMPORT_FAILURE.clear()
        ccc._IMPORT_BLAME.clear()
        for k in [k for k in sys.modules if k == "libs" or k.startswith("libs.")]:
            del sys.modules[k]
        sys.modules.update(saved_mods)
        while str(hub) in sys.path:
            sys.path.remove(str(hub))


def test_a_quoted_hash_a_nested_fence_and_a_caller_comment(corpus, tmp_path):
    """A `#` inside a QUOTED argument of a fenced close was a shell comment (a blocking false positive);
    predicate 7's fence tracker was a bare toggle (one nested/info-string fence inverted it for the
    rest of the file); a caller naming the claimant only inside an HTML comment honoured it (FE2)."""
    for body in (
        '```bash\npython3 scripts/command_run.py done --command fabrik-probe --evidence "PR #42 merged" --feedback "none"\n```\n',
        "```bash\npython3 scripts/command_run.py done --command fabrik-probe --evidence '3 of 5 # files' --feedback f\n```\n",
    ):
        assert not any("--feedback" in p for p in corpus(body)), corpus(body)
    # a nested fence: the outer ```` holds an inner ``` — the inner closer does not close the outer,
    # so the close after it is still fenced and its comment is still cut
    body = "````markdown\n```bash\npython3 scripts/command_run.py done --command fabrik-probe --evidence e   # documents --feedback\n```\n````\n"
    assert any("--feedback" in p for p in corpus(body)), corpus(body)
    # a `~~~` inside an open ``` fence is content, not a closer: the span AFTER the real closer is prose
    body = "```\n~~~\n```\n\n`done --command fabrik-probe --evidence e` — note `--feedback` is required\n"
    assert any("--feedback" in p for p in corpus(body)), corpus(body)
    (tmp_path / "_sources" / "fabrik-real.md").write_text(
        "{{include:run-record}}\n<!-- calls /fabrik-probe -->\n"
    )
    problems = corpus("description: auto-called by /fabrik-real reactively.\n")
    assert any("claims caller /fabrik-real" in p for p in problems), problems
    (tmp_path / "_sources" / "fabrik-real.md").write_text(
        "{{include:run-record}}\n```\n```bash\n/fabrik-probe\n```\n"
    )
    problems = corpus("description: auto-called by /fabrik-real reactively.\n")
    assert any("claims caller /fabrik-real" in p for p in problems), (
        "a ```bash inside an open fence in the CALLER is content — the honour side must not close on it"
    )


def test_the_selftest_counts_the_emitter_lines_it_executed(capsys):
    """`13 distinct signatures` credited two signatures to one emitter and none to an unexercised
    one; the count is now the emitter LINES the canaries executed, measured independently here (FE2)."""
    import check_command_corpus as ccc

    assert ccc._selftest() == 0  # its own tracer replaces ours — it publishes the lines it saw
    hit = set(ccc._SELFTEST_HIT)
    line = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("✓ selftest")][-1]
    m = re.search(r"\((\d+) of (\d+) problem emitters in this file executed\)", line)
    assert m, line
    covered, emitters = int(m.group(1)), int(m.group(2))
    assert emitters == len(ccc._emitter_lines()) == _ast_emitters(ccc) and covered == len(
        hit & ccc._emitter_lines()
    ), (
        line,
        sorted(hit & ccc._emitter_lines()),
    )
    assert 0 < covered <= emitters


def test_a_yaml_name_with_a_space_before_the_colon(tmp_path):
    """`name : probe` is YAML-legal and was "declares no `name:`" (FE2)."""
    src, frag = tmp_path / "_s8", tmp_path / "_f8"
    src.mkdir()
    frag.mkdir()
    (src / "fabrik-real.md").write_text("{{include:run-record}}\n")
    agents = tmp_path / "_a8"
    agents.mkdir()
    (agents / "probe.md").write_text("---\nname : probe\ndescription: d\n---\n")
    assert not audit(
        src,
        frag,
        tmp_path / "no-assembler.py",
        tmp_path,
        agents=agents,
    )


def test_the_probe_flushes_the_callers_pending_stdout_before_it_captures(tmp_path):
    """The FE2 finally flushed `sys.__stdout__` INTO the sink: an in-process caller's block-buffered
    bytes (every test runs under a redirected `sys.stdout`) vanished and were blamed on the module
    as an N-byte leak (FF1)."""
    hub = _probe_hub(tmp_path, 'WEB_TOOL_NAMES = frozenset({"web_search"})\n')
    driver = tmp_path / "driver.py"
    driver.write_text(
        "import contextlib, io, json, sys\n"
        f"sys.path.insert(0, {str(REPO / 'scripts' / 'enforcement')!r})\n"
        "import check_command_corpus as c\n"
        "print('HEADER-BEFORE-PROBE')\n"
        "with contextlib.redirect_stdout(io.StringIO()):\n"
        f"    names = c._live_web_tool_names(__import__('pathlib').Path({str(hub)!r}))\n"
        "print('AFTER-PROBE', json.dumps(sorted(names)), json.dumps(c.ADVISORIES))\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(driver)], capture_output=True, text=True, timeout=60
    )  # a PIPE: block-buffered, so the header is pending when the probe moves the fds
    assert proc.returncode == 0, proc.stderr
    assert "HEADER-BEFORE-PROBE" in proc.stdout, proc.stdout
    assert 'AFTER-PROBE ["web_search"] []' in proc.stdout, proc.stdout


def test_the_cli_survives_a_detached_original_and_a_wrapper_that_owns_the_fd(tmp_path):
    """`io.TextIOWrapper(sys.stdout.detach())` restored a DETACHED wrapper (the verdict print raised,
    exit 120, nothing printed); `open(sys.stdout.fileno(), "w")` closed fd 1 when its wrapper was
    finalized; a detached stderr failed the exit-time flush — a green verdict with exit 120 (FF1)."""
    idioms = {
        "detach_rewrap": 'import io, sys\nsys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8")\n',
        "codecs_writer": 'import codecs, sys\nsys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())\n',
        "fdopen_rewrap": 'import sys\nsys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)\n',
        "stderr_detach": 'import io, sys\nsys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding="utf-8")\n',
        "keep_wrapper_atexit": 'import atexit, io, sys\nW = sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")\natexit.register(lambda: W.write("bye\\n"))\n',
        # a module that DETACHES or CLOSES a stream and rebinds NOTHING: FF1 assumed a live wrapper and restored the dead original — exit 120 / no verdict (A67-1)
        "detach_only": "import sys\nsys.stdout.detach()\n",
        "dunder_rebind_only": 'import io, sys\nsys.__stdout__ = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8")\n',
        "close": "import sys\nsys.stdout.close()\n",
        "buffer_detach": "import sys\nsys.stdout.buffer.detach()\n",
        "detach_then_none": "import sys\nsys.stdout.detach()\nsys.stdout = None\n",
        "stderr_detach_only": "import sys\nsys.stderr.detach()\n",
        "stderr_close": "import sys\nsys.stderr.close()\n",
        "healthy": "",
    }
    script = REPO / "scripts" / "enforcement" / "check_command_corpus.py"
    for name, body in idioms.items():
        root = tmp_path / name
        (root / "scripts" / "enforcement").mkdir(parents=True)
        shutil.copy(script, root / "scripts" / "enforcement" / "check_command_corpus.py")
        (root / "libs" / "subagents").mkdir(parents=True)
        (root / "libs" / "__init__.py").write_text("")
        (root / "libs" / "subagents" / "__init__.py").write_text("")
        (root / "libs" / "subagents" / "web_tools.py").write_text(
            body + 'WEB_TOOL_NAMES = frozenset({"web_search"})\n'
        )
        (root / "CLAUDE.md").write_text(
            "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\n"
        )
        (root / "commands" / "_sources").mkdir(parents=True)
        (root / "commands" / "_fragments").mkdir()
        (root / "commands" / "assemble_commands.py").write_text("")
        (root / "commands" / "_sources" / "fabrik-a.md").write_text("{{include:run-record}}\n")
        proc = subprocess.run(
            [sys.executable, "scripts/enforcement/check_command_corpus.py"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert "command corpus:" in proc.stdout, (name, proc.stdout, proc.stderr)
        assert proc.returncode in (0, 1), (name, proc.returncode, proc.stderr)
        assert "Traceback" not in proc.stderr and "Bad file descriptor" not in proc.stderr, (
            name,
            proc.stderr,
        )
        assert "Exception ignored" not in proc.stderr, (name, proc.stderr)
        if name == "healthy":
            assert proc.returncode == 0 and proc.stdout.startswith("✓"), (proc.stdout, proc.stderr)
        if name in ("detach_only", "dunder_rebind_only", "close", "buffer_detach"):
            assert "left the process's stdout unusable" in proc.stdout, (name, proc.stdout)
        if name == "detach_rewrap":
            assert "a module detached the process" in proc.stdout, (
                name,
                proc.stdout,
            )  # the FF1 advisory, ungraded (A67-5 M4)


def test_shell_escapes_a_column_zero_comment_a_carried_quote_and_a_backticked_info_string(
    corpus,
):
    """`'it'\\''s # done'` and `"a \\" # b"` fired BLOCKING false positives (no escape handling); a
    column-0 `#` on a continuation line satisfied the window; a quoted argument spanning a
    continuation reset its quote state per line; a backtick inside a backtick-fence info string
    opened a fence (FF1)."""
    import check_command_corpus as ccc

    close = "python3 scripts/command_run.py done --command fabrik-probe"
    for body in (
        f"```bash\n{close} --evidence 'it'\\''s # done' --feedback f\n```\n",
        f'```bash\n{close} \\\n  --evidence "PR #42 merged" --feedback "none"\n```\n',  # the CONTINUATION window's quoted `#` — single-line closes went through `finditer`, this path had no grader (B66-C2)
        f'```bash\n{close} --evidence "a \\" # b" --feedback f\n```\n',
        f'```bash\n{close} --evidence "multi \\\nline # text" --feedback f\n```\n',
        f"```bash\n{close} --evidence a\\#b --feedback f\n```\n",
    ):
        assert not any("--feedback" in p for p in corpus(body)), (body, corpus(body))
    for body in (
        f"```bash\n{close} --evidence e \\\n# --feedback is required\n```\n",
        f"```bash\n{close} --evidence e \\\n  # --feedback is required\n```\n",
        f"```a`b\n`{close} --evidence e` says --feedback\n",
    ):
        assert any("--feedback" in p for p in corpus(body)), (body, corpus(body))
    assert ccc._cut_shell_comment("a \\# b # c") == ("a \\# b ", "")
    assert ccc._cut_shell_comment('x "open # not', "") == ('x "open # not', '"')
    assert ccc._cut_shell_comment('still # not" now # cut', '"') == ('still # not" now ', "")
    assert ccc._fence_step("```a`b", "", 0) == ("", 0, False)


def test_a_commented_claim_is_a_note_and_a_fence_inside_a_comment_opens_nothing(corpus, tmp_path):
    """The claim side stripped fences but not HTML comments (a commented-out note fired a BLOCKING
    claim); the honour side unfenced BEFORE it stripped comments, so `<!--\n```\n-->` in the caller
    swallowed its real reference (FF1)."""
    import check_command_corpus as ccc

    assert ccc._claimed_callers("<!-- auto-called by /fabrik-real -->\n") == {}
    assert ccc._claimed_callers("<!--\nauto-called by /fabrik-real\n-->\n") == {}
    assert ccc._claimed_callers("<!-- ``` -->\nauto-called by /fabrik-real.\n") == {
        "fabrik-real": 2
    }
    assert not any("claims caller" in p for p in corpus("<!-- auto-called by /fabrik-real -->\n"))
    (tmp_path / "_sources" / "fabrik-real.md").write_text(
        "{{include:run-record}}\n<!--\n```\n-->\nI invoke /fabrik-probe here.\n"
    )
    problems = corpus("description: auto-called by /fabrik-real reactively.\n")
    assert not any("claims caller /fabrik-real" in p for p in problems), problems
    (tmp_path / "_sources" / "fabrik-real.md").write_text(
        "{{include:run-record}}\n```\n<!-- x\n```\ncall /fabrik-probe\n-->\n"
    )
    problems = corpus("description: auto-called by /fabrik-real reactively.\n")
    assert not any("claims caller /fabrik-real" in p for p in problems), (
        "a `<!--` inside a fence is content: the fenced block ends at its closer and the call after it is honoured"
    )
    assert (
        ccc._blank_html_comments("a <!-- b\nc --> d\n```\n<!-- e\n```\nf")
        == "a \n d\n```\n<!-- e\n```\nf"
    )


def test_the_three_fence_readers_share_the_one_tracker():
    """FE2 claimed `_fence_step` is the ONE CommonMark tracker for the claim side, the honour side
    and predicate 7 while `_claimed_callers` kept an inline copy (G66-C8, F66-3, FF1)."""
    import check_command_corpus as ccc

    src = Path(ccc.__file__).read_text(encoding="utf-8")
    assert src.count("_fence_step(") == 5, (
        src.count("_fence_step(")
    )  # the def + FOUR call sites (`_unfenced`, `_blank_html_comments`, the claim side, predicate 7) — `>= 4` tolerated deleting exactly the one the comment forgot (B67-12)
    assert src.count('re.match(r"(`{3,}|~{3,})(.*)$"') == 1  # inside _fence_step only
    assert ccc._claimed_callers("````\n```\nauto-called by /fabrik-x\n````\n") == {}


def test_the_second_round_of_predicate_shapes_a_found(corpus):
    """A67-2: predicate 5 stripped comments with the naive regex — a `<!--` inside a fence paired
    with a later `-->` and blanked the real start (2 of 98 live files carry a fenced `<!--`).
    A67-3: `\\ ` is an escaped space, not a continuation. A67-6: an OPEN quote spans lines without
    a `\\`. A67-5: `_fence_step` on a tilde fence with a backtick in its info string, an escape
    inside single quotes, a comment closing line re-stripped, and the emitter SET (FG1)."""
    import check_command_corpus as ccc

    close = "python3 scripts/command_run.py done --command fabrik-probe"
    body = (
        "```bash\necho '<!--'\n```\npython3 scripts/command_run.py start --command x\nprose -->\n"
    )
    assert not any("opens no run record" in p for p in corpus(body, with_record=False)), corpus(
        body, with_record=False
    )
    body = f"```bash\n{close} --evidence e \\ \necho --feedback\n```\n"
    assert any("--feedback" in p for p in corpus(body)), corpus(body)
    body = f"```bash\n{close} --evidence 'multi\nline' --feedback f\n```\n"
    assert not any("--feedback" in p for p in corpus(body)), corpus(body)
    assert ccc._fence_step("~~~a`b", "", 0) == ("~", 3, True)
    assert ccc._cut_shell_comment("x 'a\\' # --feedback f") == ("x 'a\\' ", "")
    assert ccc._blank_html_comments("<!-- a\nb --> <!-- c --> d") == "\n  d"
    import ast

    tree = ast.parse(Path(ccc.__file__).read_text(encoding="utf-8"))
    own = frozenset(
        n.lineno
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "append"
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "problems"
    )
    assert (
        ccc._emitter_lines() == own
    )  # SET equality: `end_lineno` survived a count-only grader while the selftest printed "2 of 18"


def test_a_semicolon_comment_is_a_comment(corpus):
    """bash: `set -- x;# --feedback f` has argc 1 — the whitespace-only rule kept the close whole
    and predicate 7 accepted a close that lacks `--feedback` (G67-6, FG1)."""
    close = "python3 scripts/command_run.py done --command fabrik-probe"
    body = f"```bash\n{close} --evidence e;# --feedback f\n```\n"
    assert any("--feedback" in p for p in corpus(body)), corpus(body)


def test_pass_68_corpus_shapes(corpus, tmp_path):
    """A68: `>&-` launches (below, in the CLI grader); `<!-->` is a complete comment; `$'it\\'s'`
    is one word; an escaped trailing backslash is not a continuation; `)#`/`>#` start a comment;
    an open quote never crosses the closing fence; `description:` is a KEY; the four round-67
    hunks that had no grader (`&#`, the orch-wrapper comment strip, both continuation rules) (FH1)."""
    import check_command_corpus as ccc

    close = "python3 scripts/command_run.py done --command fabrik-probe"
    assert ccc._blank_html_comments("<!-->\nx") == "\nx"
    assert ccc._blank_html_comments("<!--->\nx") == "\nx"
    assert not any(
        "opens no run record" in p
        for p in corpus(
            "<!-->\npython3 scripts/command_run.py start --command x\n", with_record=False
        )
    )
    for body in (  # these FIRE
        f"```bash\n{close} --evidence $'it\\'s' # --feedback f\n```\n",
        f"```bash\n{close} --evidence e \\\\\n--feedback f\n```\n",
        f"```bash\n{close} --evidence e )# --feedback f\n```\n",
        f"```bash\n{close} --evidence e ># --feedback f\n```\n",
        f"```bash\n{close} --evidence e &# --feedback f\n```\n",
        f"```bash\n{close} --evidence e \\\n  --evidence f \\ \n--feedback f\n```\n",
        f'```bash\n{close} --evidence "oops\n```\nThe flag `--feedback` is REQUIRED.\n',
    ):
        assert any("--feedback" in p for p in corpus(body)), (body, corpus(body))
    for body in (  # these are SILENT
        f'```bash\n{close} --evidence "multi \\\nline\nmore" --feedback f\n```\n',
    ):
        assert not any("--feedback" in p for p in corpus(body)), (body, corpus(body))
    assert ccc._continues("a \\") and not ccc._continues("a \\\\") and ccc._continues("a \\\\\\")
    # the IN-LOOP recompute (line 1305), which the round-67 cases never reached — both directions
    # were vacuous: a quote spanning TWO continuation lines, and an escaped space on a continuation
    # line (B68-1, FH1)
    assert not any(
        "--feedback" in p
        for p in corpus(f"```bash\n{close} --evidence 'a\nb\nc' --feedback f\n```\n")
    )
    assert any(
        "--feedback" in p
        for p in corpus(f"```bash\n{close} \\\n --evidence e \\ \necho --feedback\n```\n")
    )


def test_pass_68_agent_description_is_a_key_and_a_closed_stdout_launch_is_green(tmp_path, corpus):
    """`#description:` passed (a YAML comment), `description :` fired (A68-8); a launch with stdout
    or stderr CLOSED tracebacked on a green corpus and printed a false `unusable` advisory (A68-1);
    `detach()` alone printed the FF1 wrapper advisory with no wrapper (A68-7) (FH1)."""
    import check_command_corpus as ccc

    agents = tmp_path / "agents68"
    agents.mkdir()
    (agents / "one.md").write_text("---\nname: one\n#description: d\n---\n")
    (agents / "two.md").write_text("---\nname: two\ndescription : d\n---\n")
    (agents / "three.md").write_text("---\nname: three\ndescription:d\n---\n")
    probs = ccc.audit(
        tmp_path / "_sources",
        tmp_path / "_fragments",
        tmp_path / "no-assembler.py",
        REPO,
        agents=agents,
    )
    assert any("_agents/one.md: no `description:`" in p for p in probs), probs
    assert not any("_agents/two.md" in p for p in probs), probs
    assert not any("_agents/three.md" in p and "description" in p for p in probs), probs
    root = tmp_path / "closedfd"
    (root / "scripts" / "enforcement").mkdir(parents=True)
    shutil.copy(
        REPO / "scripts" / "enforcement" / "check_command_corpus.py",
        root / "scripts" / "enforcement" / "check_command_corpus.py",
    )
    (root / "libs" / "subagents").mkdir(parents=True)
    (root / "libs" / "__init__.py").write_text("")
    (root / "libs" / "subagents" / "__init__.py").write_text("")
    (root / "libs" / "subagents" / "web_tools.py").write_text(
        'WEB_TOOL_NAMES = frozenset({"web_search"})\n'
    )
    (root / "CLAUDE.md").write_text("Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\n")
    (root / "commands" / "_sources").mkdir(parents=True)
    (root / "commands" / "_fragments").mkdir()
    (root / "commands" / "assemble_commands.py").write_text("")
    (root / "commands" / "_sources" / "fabrik-a.md").write_text("{{include:run-record}}\n")
    for redirect in (">&-", "2>&-"):
        proc = subprocess.run(
            [
                "bash",
                "-c",
                f"exec {redirect}; exec {sys.executable} scripts/enforcement/check_command_corpus.py --quiet",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, (redirect, proc.returncode, proc.stdout, proc.stderr)
        assert "Traceback" not in proc.stderr and "unusable" not in proc.stdout, (
            redirect,
            proc.stdout,
            proc.stderr,
        )
    (root / "libs" / "subagents" / "web_tools.py").write_text(
        'import sys\nsys.stdout.detach()\nWEB_TOOL_NAMES = frozenset({"web_search"})\n'
    )
    proc = subprocess.run(
        [sys.executable, "scripts/enforcement/check_command_corpus.py", "--quiet"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "its own wrapper is now the binding" not in proc.stdout, proc.stdout
    assert "left the process's stdout unusable" in proc.stdout, proc.stdout
