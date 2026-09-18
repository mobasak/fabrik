"""Graders for `commands/_sources/fabrik-task.md` — the `/fabrik-task` command source.

Three facts about the source, each mechanically decidable (spec
`docs/superpowers/specs/2026-09-17-fabrik-task-lane-design.md` § Constraints C2, § Chosen approach;
ticket T03 Behavior Contract):

1. SIZE + INCLUDES — the source is at most `fabrik-features.md`'s 8,847 bytes (the smallest source
   in the corpus, C2's cap) and its only `{{include:}}` is `run-record`. The include half is C2's
   cobra counter (cobra 8): the cheapest way to satisfy a source-byte cap is to move the prose into
   a fragment, so a second include is refused whatever the byte count says.
2. RENDER — the source renders: a temp-dir `render()` (never the installed corpus — the renderer
   PRUNES, and this suite runs from worktrees) emits `fabrik-task.md`, and the source carries the
   frontmatter the corpus check and the skill wrapper read: `description:` with a `TRIGGER —`
   clause and a `Stage:`, plus `argument-hint:`.
3. RUNNABLE LINES — every fenced `python3 scripts/command_run.py …` line in the source is ACCEPTED
   by that script's own argparse, AND every printed close carries the flags the lane refuses without
   (`--feedback` on all three close verbs, `--commit` on `fabrik-task`'s `done`). A line an agent
   cannot paste is a line nobody runs; a close the tool refuses leaves the record `running` and the
   Stop hook holding the turn open.

⚠️ The cheapest way to satisfy grader 1 without producing the outcome is to move prose into a
reference doc the source points at — UNCOUNTERED by machinery (spec C3 cobra 8), named here so the
next reader greps it rather than discovering it.
"""

from __future__ import annotations

import importlib.util
import re
import shlex
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "commands" / "_sources" / "fabrik-task.md"
# `fabrik-features.md`, the smallest source in the corpus the day the cap was set (spec C2).
SIZE_CAP = 8847
_INCLUDE_RE = re.compile(r"\{\{include:([\w-]+)\}\}")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_RUN_LINE_RE = re.compile(r"command_run\.py\s")


def _load(path: Path, name: str):
    """Import a repo script by path — neither `commands/` nor `scripts/` is a package."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _source_text() -> str:
    assert SOURCE.exists(), f"{SOURCE} does not exist — T03's primary path"
    return SOURCE.read_text(encoding="utf-8")


def _run_lines(text: str) -> list[str]:
    """Every fenced `command_run.py …` logical line, backslash continuations joined."""
    out: list[str] = []
    fence = ""
    pending = ""
    for raw in text.splitlines():
        m = _FENCE_RE.match(raw)
        if m:
            token = m.group(1)
            if not fence:
                fence = token
            elif raw.strip().startswith(fence):
                fence = ""
            continue
        if not fence:
            continue
        line = raw.strip()
        if pending:
            pending = pending + " " + line.rstrip("\\").strip()
        elif _RUN_LINE_RE.search(line):
            pending = line.rstrip("\\").strip()
        else:
            continue
        if raw.rstrip().endswith("\\"):
            continue
        out.append(pending)
        pending = ""
    if pending:
        out.append(pending)
    return out


def test_source_size_and_single_include() -> None:
    """C2: at most 8,847 bytes, and `run-record` is the only include."""
    data = SOURCE.read_bytes() if SOURCE.exists() else b""
    assert SOURCE.exists(), f"{SOURCE} does not exist — T03's primary path"
    assert len(data) <= SIZE_CAP, (
        f"{SOURCE.name} is {len(data)} B, over C2's {SIZE_CAP} B cap "
        f"(fabrik-features.md, the smallest source) by {len(data) - SIZE_CAP} B"
    )
    includes = set(_INCLUDE_RE.findall(data.decode("utf-8")))
    assert includes == {"run-record"}, (
        f"includes are {sorted(includes)}; C2 allows exactly ['run-record'] — "
        "`close-feedback` is auto-appended by the assembler and `term-coverage`/`term-edit` "
        "are the weight this cap exists to keep out"
    )


def test_source_renders_with_the_frontmatter_the_corpus_reads() -> None:
    """The source renders to `fabrik-task.md` and carries its frontmatter contract."""
    text = _source_text()
    head = text.split("\n---", 1)[0] if text.startswith("---") else ""
    assert head.startswith("---"), (
        "no frontmatter — the renderer and the skill wrapper both read it"
    )
    desc = re.search(r"^description:\s*(.+)$", head, flags=re.M)
    assert desc, "frontmatter declares no `description:` — the skill router selects on it"
    value = desc.group(1)
    assert "TRIGGER —" in value, "the `description:` carries no `TRIGGER —` clause"
    assert "SKIP" in value, "the `description:` carries no SKIP clause"
    assert "Stage:" in value, "the `description:` names no Stage"
    assert re.search(r"^argument-hint:", head, flags=re.M), (
        "frontmatter declares no `argument-hint:`"
    )

    asm = _load(REPO / "commands" / "assemble_commands.py", "assemble_commands_under_test")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        asm.render(tmp, tmp / "_skills", agents_dest=tmp / "_agents")
        rendered = tmp / "fabrik-task.md"
        assert rendered.exists(), "the render emitted no fabrik-task.md"
        body = rendered.read_text(encoding="utf-8")
        assert "{{include:" not in body, "an unresolved include survived the render"
        assert (tmp / "_skills" / "fabrik-task" / "SKILL.md").exists(), "no SKILL.md wrapper"


def test_every_command_run_line_is_accepted_by_the_real_parser(monkeypatch, tmp_path) -> None:
    """Spec § Chosen approach: a printed line the tool refuses is a line nobody runs."""
    monkeypatch.setenv("COMMAND_RUN_DIR", str(tmp_path / "command-runs"))
    text = _source_text()
    lines = _run_lines(text)
    assert lines, "the source prints no `command_run.py` line — it opens no run record"
    mod = _load(REPO / "scripts" / "command_run.py", "command_run_under_test")
    parser = mod._build_parser()
    for line in lines:
        argv = shlex.split(line)
        while argv and not argv[0].endswith("command_run.py"):
            argv.pop(0)
        assert argv, f"no script token in: {line}"
        argv = argv[1:]
        try:
            args = parser.parse_args(argv)
        except SystemExit as exc:  # argparse exits 2 on an unknown or malformed flag
            pytest.fail(f"the parser REFUSED (rc {exc.code}): {line}")
        # argparse acceptance is not the whole contract: the lane REFUSES a close at RUNTIME
        # for flags the parser is happy with (`command_run.py` `_task_close_fields`). A printed
        # close the tool refuses leaves the record `running` and the Stop hook holding the turn.
        # EVERY line must name THIS lane. Without this, replacing `--command fabrik-task` with
        # another command's name on all four lines left the grader green — and the `--commit`
        # assertion below is keyed on that literal, so the typo would disable the very refusal
        # this test exists to catch (T03 review, seat C).
        if args.cmd in {"start", "done", "blocked", "handoff"}:
            assert getattr(args, "command", "") == "fabrik-task", (
                f"a printed line names another command: {line}"
            )
        if args.cmd in {"done", "blocked", "handoff"}:
            assert getattr(args, "feedback", None), f"close without --feedback: {line}"
            if args.cmd == "done" and getattr(args, "command", "") == "fabrik-task":
                assert getattr(args, "commit", None), (
                    "`done --command fabrik-task` is REFUSED without --commit "
                    f"(scripts/command_run.py `_task_close_fields`): {line}"
                )


def test_the_printed_phase_count_matches_the_headings() -> None:
    """The source PRINTS `--phases 5` and the assembler DERIVES a phase count from the headings;
    nothing tied the two together, so mutating the printed number to 3 left every grader green.
    The sibling `fabrik-deploy-checklist` has exactly this cross-check
    (`tests/test_check_command_corpus.py`, "8 phases derived from the headings") — this is that
    precedent applied here.

    The agreement is not cosmetic: `command_run.py` renders `phase <c>/<t>` from `--phases` into
    the pinned RUN line every response carries, so a wrong total misreports progress for the whole
    run. Found by T03's review, seat C."""
    import importlib.util

    text = _source_text()
    spec = importlib.util.spec_from_file_location(
        "assemble_under_test", REPO / "commands" / "assemble_commands.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    derived = mod._phase_count(text)
    assert f"--phases {derived}" in text, (
        f"the source prints a phase count that disagrees with its own headings "
        f"(_phase_count derived {derived})"
    )
