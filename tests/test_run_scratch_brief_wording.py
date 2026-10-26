"""D7 of the scratch-lifecycle spec (W-8bbd9538): every seat folder lives under the run's RUN-SCRATCH path.

`command_run.py start` prints `RUN-SCRATCH: <path>`, the run's disposable folder, removed once the run is consumed
(`docs/reference/command-run-protocol.md` § A run's disposable folder). Until the briefs named it, seats wrote their
copies, pins and probes to the bare session scratchpad, which no run owns and nothing removes (73 GB measured
2026-10-14). The rule is stated ONCE, in `subagents-core.md` (the fragment 21 command sources include); the probe
catalogue and fabrik-execute-plan point at it and name `<run scratch>` where they used to name `<scratchpad>`
(fabrik-review and fabrik-review-scoped carry infra's `scratch_dir` wording, D-886, pinned in
test_review_loop_workflow.py). Each test pins one site, so a revert of any one, or a second statement of the
rule, fails here.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "commands" / "_fragments" / "subagents-core.md"
CAT = ROOT / "commands" / "_fragments" / "review-probe-catalogue.md"
EXEC = ROOT / "commands" / "_sources" / "fabrik-execute-plan.md"

RULE = (
    "The scratch dir a brief names is a SEAT FOLDER under the run's disposable folder — `<run scratch>/seat-<n>/`,"
    " `<run scratch>` being the path this run's `start` printed as `RUN-SCRATCH:` (kept as `run_scratch` in the run"
    " record; `docs/reference/command-run-protocol.md` § A run's disposable folder) — never the session scratchpad"
    " root, which no run owns and nothing removes."
)


def _norm(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text())


def _section(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_the_seat_folder_rule_is_stated_once_in_subagents_core() -> None:
    """The rule's home: the D8 paragraph, which already bounds where a read-only seat may write. Mutants: drop the
    sentence; drop `seat-<n>`; drop `RUN-SCRATCH:`; drop 'never the session scratchpad root'; state it twice."""
    core = _norm(CORE)
    d8 = _section(
        core,
        "**Every seat's brief carries the git-verb prohibition (D8):**",
        "<!-- POOL OFF (D-181, 2026-09-07)",
    )
    assert d8.count(RULE) == 1
    # the three consequences ride the same paragraph: nothing durable, the pins dir, the only staging
    assert "so nothing durable is written there (resume artifacts go to `SCRATCH:`)" in d8
    assert (
        "a start that printed `RUN-SCRATCH: none — <why>` names a folder under the session scratchpad instead"
        in d8
    )
    assert (
        "the pins dir (the PIN paragraph below) sits under the same root, unless the including command puts it"
        " under the run's durable `SCRATCH:` folder (D-836), as `/fabrik-review`, `/fabrik-plan-review`,"
        " `/fabrik-spec-review` and `/fabrik-repo-review` do so an interrupted pass keeps its pins;"
        in d8
    )
    assert (
        "a tree is staged in a seat folder only as the probe catalogue's § Seat isolation says — an archive of the"
        " pinned SHA, or a `clone --shared --no-checkout` — never a copy of the live checkout" in d8
    )
    # stated once in the fragment: the rule's key phrase appears in no other paragraph
    assert core.count("under the run's disposable folder") == 1
    assert core.count("`<run scratch>/seat-<n>/`") == 1


def test_the_pin_paragraph_defers_the_pins_dir_root_to_d8() -> None:
    """The pin command points at D8 for the pins dir's root, so the root and its review-loop exception are stated
    once (W-7bd671f6: a second statement here said `<run scratch>` while three including review loops say
    `SCRATCH:`)."""
    pin = _section(
        _norm(CORE),
        "**PIN the subject before you dispatch",
        "<!-- POOL OFF (D-181) — pool-grounder",
    )
    assert "--pins-dir <a NEW dir per pass>" in pin
    assert "the pins dir sits where the D8 paragraph puts it" in pin
    assert "<run scratch>" not in pin and "SCRATCH:" not in pin and "disposable" not in pin


def test_the_review_loops_d8_names_put_their_pins_under_scratch() -> None:
    """D8 names the commands that put the pins dir under `SCRATCH:`; each includes the fragment and says so itself,
    and every includer whose own text names `pins_dir` or `--pins-dir` is in D8's list, so no rendered command states two roots.
    Mutants: drop a source's sentence; drop its include; add an includer naming `pins_dir` but missing from D8."""
    core = _norm(CORE)
    m = re.search(
        r"durable `SCRATCH:` folder \(D-836\), as (.+?) do so an interrupted pass keeps its pins;",
        core,
    )
    assert m, "D8's list of SCRATCH: commands"
    named = set(re.findall(r"`/(fabrik-[a-z-]+)`", m.group(1)))
    assert named == {
        "fabrik-review",
        "fabrik-plan-review",
        "fabrik-spec-review",
        "fabrik-repo-review",
    }, named
    sources = ROOT / "commands" / "_sources"
    includers = {
        p.stem
        for p in sources.glob("*.md")
        if "{{include:subagents-core}}" in (src := _norm(p))
        and ("pins_dir" in src or "--pins-dir" in src)
    }
    assert includers == named, includers ^ named
    loop = (
        "(`pins_dir`, and `<scratch>` in this command's `review_loop_ledger.py` calls, go under the run's"
        " `SCRATCH:` folder"
    )
    for name in sorted(named - {"fabrik-repo-review"}):
        assert loop in _norm(sources / f"{name}.md"), name
    # W-27a0dc32: repo-review has no `<scratch>` ledger calls; its batch launch names the same root and scratch_dir
    batch = _section(
        _norm(sources / "fabrik-repo-review.md"),
        "a slice batch IS a round",
        "contract and fallback",
    )
    assert (
        "`scratch_dir` (this run's `RUN-SCRATCH:` folder — the path after `RUN-SCRATCH: ` up to the next space on"
        " the line `start` printed (a trailing `(adopted from …)` is not part of it), or the session scratchpad when it printed `none` or nothing)"
    ) in batch
    assert (
        "(`pins_dir` goes under the run's `SCRATCH:` folder — the path on the line `start` printed that begins"
        " `SCRATCH:`, kept on disk across a WSL shutdown (D-836) — or the session scratchpad when `start` printed"
        " no line that begins `SCRATCH:`);"
    ) in batch


def test_seat_isolation_names_the_seat_folder_and_the_only_staging() -> None:
    """The catalogue's copy rule is the only way to stage a tree; `<scratch>` in its commands is the seat folder."""
    iso = _section(_norm(CAT), "## Seat isolation", "## Loop bookkeeping")
    assert iso.count("RUN-SCRATCH") == 1, "the catalogue points at the rule; it does not restate it"


def test_execute_plan_brief_and_report_files_live_under_the_run_scratch() -> None:
    """Brief and report files go under `<run scratch>`; the durable salvage sentence keeps its scratchpad warning."""
    text = EXEC.read_text()
    norm = re.sub(r"\s+", " ", text)
    assert "`<run scratch>/phase-<X>-brief.md`" in norm
    assert "`<run scratch>/phase-<X>-task-<N>-report.md`" in norm
    assert (
        "`<run scratch>` is the path this run's `start` printed as `RUN-SCRATCH:`"
        " (`/opt/fabrik/commands/_fragments/subagents-core.md`, the D8 paragraph);"
        " the folder goes when the run is consumed, which is why the salvage diff above is written elsewhere, and why"
        " a review in a later run (a resume's acceptance review of salvaged work) re-derives the brief from the plan"
        " and the ticket, never from a folder another run owned." in norm
    )
    assert "<scratchpad>" not in text
    # kept as it was: durable state is never a scratchpad's (mail 01M4Y86A9R said so)
    assert (
        "(durable — a scratchpad is session-private and a resume may be a DIFFERENT session;"
        in norm
    )


def test_the_d8_pointer_resolves_wherever_it_is_read() -> None:
    """Wave 2 of the review: `§ Subagents, the D8 paragraph` resolves only in a command that renders the fragment.
    A source that does not include `subagents-core` (or the catalogue, read by hub path) points by the hub path."""
    for path in (CAT, EXEC):
        text = _norm(path)
        if path != CAT:
            assert "{{include:subagents-core" not in path.read_text(), (
                f"{path.name} now includes the fragment"
            )
        assert "§ Subagents, the D8 paragraph" not in text, (
            f"{path.name} cites a section it does not render"
        )
        assert "`/opt/fabrik/commands/_fragments/subagents-core.md`, the D8 paragraph" in text
