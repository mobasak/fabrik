"""/fabrik-spec feedback queue answered in one pass (D-735, D-760).

Each test pins one sentence in the section that owns it; the 1a wording is also run through the
convergence check's own pattern, so the recipe the command gives is one the check accepts.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-spec.md"
RESEARCHER = ROOT / "commands" / "_agents" / "fabrik-researcher.md"
sys.path.insert(0, str(ROOT / "scripts" / "enforcement"))

import check_spec_convergence  # noqa: E402


def _flat(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text())


def _section(start: str, end: str) -> str:
    text = _flat(SRC)
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_an_amendment_states_no_external_facts_in_words_the_check_reads() -> None:
    """Row 1789399457: the recipe sentence clears SILENT-1a; the 'no NEW external facts' wording does not."""
    s1a = _section("### 1a", "### 1b")
    m = re.search(r"`(This amendment adds no external facts beyond [^`]+)`", s1a)
    assert m, "1a gives no amendment recipe"
    assert check_spec_convergence.NO_EXTERNAL_RE.search(m.group(1))
    assert not check_spec_convergence.NO_EXTERNAL_RE.search(
        "This amendment adds no new external facts."
    )


def test_a_best_practice_seat_carries_the_1a_facts() -> None:
    """Row 1791761722."""
    s1c = _section("### 1c", "## Phase 2")
    assert (
        "A 1c (best-practice) seat is dispatched after the 1a facts it rests on are grounded or executed"
        in s1c
    )
    assert "the 1a wave and the 1c wave are two dispatches" in s1c


def test_self_review_grades_a_converged_copy_of_the_draft() -> None:
    """Row 1789139668: the script never grades a DRAFT, so the self-review grades a flipped copy."""
    p5 = _section("## Phase 5", "## Phase 6")
    assert "set the copy's Status line to `CONVERGED`" in p5
    assert "scripts/enforcement/check_spec_convergence.py <the copy>" in p5
    assert "a DRAFT is not graded" in p5
    assert "`/fabrik-plan-review` for a `Size: small` spec" in p5


def _grade(tmp_path: Path, body: str, capsys) -> str:
    spec = tmp_path / "2026-10-12-amend-design.md"
    spec.write_text(body)
    check_spec_convergence.main([str(spec)])
    return capsys.readouterr().out


def test_the_check_skips_a_draft_and_grades_its_flipped_copy(tmp_path: Path, capsys) -> None:
    """The Phase 5 and 1a sentences, executed: the DRAFT is skipped; the copy prints the findings named."""
    draft = "# Amend\n\n**Status:** DRAFT\n\nThis amendment adds no new external facts.\n"
    assert "a DRAFT is not graded" in _grade(tmp_path, draft, capsys)
    flipped = _grade(tmp_path, draft.replace("DRAFT", "CONVERGED"), capsys)
    for finding in ("SILENT-1a", "APPROACH-FLOOR", "NO-PERSONAS", "NO-LIFECYCLE", "NO-INTAKE"):
        assert finding in flipped, finding
    recipe = draft.replace("DRAFT", "CONVERGED").replace(
        "adds no new external facts.",
        "adds no external facts beyond docs/x-design.md, last verified live 2026-09-01.",
    )
    graded = _grade(tmp_path, recipe, capsys)
    assert "SILENT-1a" not in graded and "APPROACH-FLOOR" in graded


def test_researcher_quotes_schema_and_versions_from_a_raw_fetch() -> None:
    """Row 1791275601."""
    text = _flat(RESEARCHER)
    assert (
        "on an HTML docs page a schema field or a parameter name is quoted from the raw arm" in text
    )
    assert "JSON/XML and version claims keep rule 3's routing" in text


def test_the_skip_line_routes_an_as_built_revision_to_an_amendment() -> None:
    """Row 1791859866: a CONVERGED spec's as-built re-freeze had no named home in the description."""
    desc = next(line for line in SRC.read_text().splitlines() if line.startswith("description:"))
    assert (
        "an as-built revision of a CONVERGED spec stays here as an amendment (`Profile: delta`)"
        in desc
    )


def test_local_claim_output_describes_key_material_never_pastes_it() -> None:
    """Row 1791966633: the spec cites each local claim's output, and the commit hook refuses a private-key PEM header."""
    text = re.sub(r"\s+", " ", SRC.read_text(encoding="utf-8"))
    assert (
        "its command and output cited in the spec (a key, token or credential in that output is described by its"
        " kind, length and a non-secret prefix, never pasted, its BEGIN line included: the `detect-private-key`"
        " commit hook refuses a private-key PEM header)"
    ) in text


def test_a_build_tool_setting_is_probed_by_a_build_or_its_source() -> None:
    """Row 1792191153, a recurrence of held execute-pack-config-before-relying: a design relied on a build-tool
    option its docs page described, and the build behaved otherwise."""
    phase = _section("### 1a — External facts", "### 1b — Internal capability")
    assert (
        "A build-tool setting the design relies on (any bundler, compiler, test-runner, package-manager or CI option, a"
        " config file's default included) is settled by a build you run or by the tool's own source read through `gh`"
        " — its docs page locates the setting but never settles it — else it is a named BLOCKING unknown."
    ) in phase


def test_the_orchestrator_runs_every_shell_only_check_the_grounder_cannot() -> None:
    """Row 1792241971, a recurrence of held researcher-no-shell-counts: a seat quote could not be byte-checked with
    the raw-fetch tools down, and fabrik-researcher has no shell. Review round 1: the WebFetch fallback stays bound to
    the status probe, since the quote rule forbids quoting a WebFetch reply; /fabrik-spec-review carries the same
    division of labour."""
    rule = (
        "Every other shell-only check is yours from the shell too, with no `WebFetch` fallback — for example a count over"
        " a fetched file, which you download and count yourself, and a seat's quote matched — whitespace normalised"
        " first, as"
    )
    tail = "against your own raw fetch when the raw-fetch tools are down."
    spec = _flat(SRC)
    assert (
        "it answers about a page rather than reporting a code. "
        + rule
        + " the quote rule says — "
        + tail
    ) in spec
    assert (
        "When the raw-fetch tools are down, you make that fetch from the shell (the division of labour below)."
        in spec
    )
    review = _flat(ROOT / "commands" / "_sources" / "fabrik-spec-review.md")
    assert rule + " the quote rule above says — " + tail in review


def _load(name: str, rel: str):
    import importlib.util

    spec_obj = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec_obj)
    spec_obj.loader.exec_module(mod)
    return mod


def test_a_research_brief_names_each_arms_verdict(tmp_path: Path, capsys) -> None:
    """Rows 1792472452, 1792465862, 1792412700: seats spent calls on dead arms the lead already knew about."""
    para = _section("**Parallelism — UNCONDITIONAL", "**Never solo")
    assert (
        "the seats of one wave go in one message. Each research seat's brief names the search and fetch arms with"
        " this session's verdict on each — every `<server>: <verdict>` line and every `MCP-HEALTH:` line the"
        " ORIENT `mcp_health.py` run printed, and every arm a seat of an earlier wave reported failing: a `DEAD`,"
        " `TIMEOUT` or `UNAUTHORIZED` server is down; a `CONNECTED` one with no `key check` line, or one whose key"
        " check reads `unverified`, is reachable but its key is unknown; and an arm with no verdict (a `SKIPPED`"
        " entry, the built-in `WebSearch` and `WebFetch`, and every server when the repo has no `.mcp.json`) is"
        " unknown. A seat whose arm fails as an arm (auth, credit, quota, transport — never one page's 404 or host"
        " block) says so in a line after its verdicts, which the brief asks for, and stops calling that arm. "
    ) in para
    # the two line shapes the sentence tells the lead to carry, from the probe's own main()
    health = _load("mcp_health_for_spec", "scripts/sysadmin/mcp_health.py")
    (tmp_path / ".mcp.json").write_text("{}")

    def fake_check(repo, timeout, notes):
        notes["exa"] = "unverified (HTTP 403)"
        return {"exa": "CONNECTED", "brave-search": "TIMEOUT"}

    health.check = fake_check
    health.main(["--repo", str(tmp_path)])
    out = capsys.readouterr().out
    assert "brave-search: TIMEOUT" in out
    assert "MCP-HEALTH: exa key check — unverified (HTTP 403)" in out
    source = (ROOT / "scripts" / "sysadmin" / "mcp_health.py").read_text()
    for verdict in ('"DEAD"', '"TIMEOUT"', '"CONNECTED"', '"SKIPPED (', '"UNAUTHORIZED ('):
        assert verdict in source, verdict


def test_the_draft_and_the_judge_brief_run_the_citation_checker(tmp_path: Path) -> None:
    """Rows 1792447087, 1792346710, 1792450363: the self-review's grep left drifted cites for the grader to miss."""
    review = _section("**Spec self-review", "Fix all before proceeding.")
    assert (
        "does every backticked `path:line` resolve (grep it)? Run `python3"
        " /opt/fabrik/scripts/enforcement/check_citations_resolve.py --root <repo> --doc <the spec>` too (its"
        " `--changed` reads `git diff`, so it never sees an untracked draft), confirm it printed `--doc examined 1"
        " file(s)` (a path it cannot open prints a clean zero), and fix every cite it reports. It grades only a"
        " line past the end of its file or a blank target, and never an absolute path as itself: the plain"
        " `/opt/fabrik/…` form is skipped, and one with a `.` or `-` in a segment is cut there and its tail graded"
        " against `<repo>`. So write a cite into `<repo>` repo-relative, open a cite into another repo, which stays"
        " absolute, by hand (a finding on it is the cut tail, not the cite), and still open each cite a design"
        " step rests on. Then grade"
    ) in review
    judge = _section("{{include:judge-panel}}", "If the research direction")
    assert judge == (
        "{{include:judge-panel}} Before the judge brief goes out, write it to a file in the run's `RUN-SCRATCH:`"
        " folder and run `python3 /opt/fabrik/scripts/enforcement/check_citations_resolve.py --root <repo> --doc"
        " <that file>` over it; a cite it reports is corrected first. "
    )
    # the checker's own behaviour, which the sentences state
    import check_citations_resolve as ccr

    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.py").write_text("x = 1\n")
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "README.md").write_text("a\nb\n")
    seen, _bare, _amb, _outside, findings = ccr.check_text_full(
        "`sub/a.py:9` and `/opt/fabrik/scripts/command_run.py:9`", tmp_path
    )
    assert seen == 1 and len(findings) == 1 and "BEYOND-EOF sub/a.py:9" in findings[0]
    seen, _bare, _amb, _outside, findings = ccr.check_text_full(
        "`/opt/fabrik-lib/README.md:40`", tmp_path
    )
    assert seen == 1 and "BEYOND-EOF lib/README.md:40" in findings[0]


def test_the_downgrade_check_names_the_lane_ledger_path(monkeypatch, tmp_path: Path) -> None:
    """Row 1792496306: 'beside the run-record state dir' sent a reader into command_run.py for the path."""
    bullet = _section("**DOWNGRADE check", "**WRITE the seed file")
    assert (
        "lane-refusal ledger (`lane-refusals.jsonl`, beside the run-record state dir:"
        " `~/.claude/state/lane-refusals.jsonl`, or `lane-refusals.jsonl` in the parent of `$COMMAND_RUN_DIR`"
        " when that is set — `command_run.py::_lane_ledger`) whose declared `--file` list" in bullet
    )
    cr = _load("cr_lane_ledger", "scripts/command_run.py")
    monkeypatch.delenv("COMMAND_RUN_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert cr._lane_ledger() == tmp_path / ".claude" / "state" / "lane-refusals.jsonl"
    monkeypatch.setenv("COMMAND_RUN_DIR", str(tmp_path / "x" / "runs"))
    assert cr._lane_ledger() == tmp_path / "x" / "lane-refusals.jsonl"
