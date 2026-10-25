"""W-51eee9fd: the seat rule for `$HOME` reads names the measured cause, not a stall.

Replayed on Claude Code 2.1.302 (2026-10-18), Read, grep and python open of `~/.claude*` files all returned at
once, so the rule allows a home read only for a file the brief names, Bash-bounded and size-checked, and keeps every
write under `~` banned. Input domain: the three seat-facing sentences, read from the tracked sources; no fixtures.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / ".windsurf" / "rules" / "core" / "62-using-subagents.md"
CRITIQUE = ROOT / "commands" / "_fragments" / "design-critique.md"


def _norm(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text())


def _between(text: str, anchor: str, start: str, end: str) -> str:
    """The clause holding `anchor`, cut at the nearest `start` before it and `end` after it."""
    i = text.index(anchor)
    return text[text.rindex(start, 0, i) + len(start) : text.index(end, i)].strip()


def test_pack_forbids_writes_and_unnamed_home_reads() -> None:
    """B2: the subagents pack tells a dispatcher to forbid writes under `~` and every home read the brief does not
    name, and carries the read bounds for a seat that is not a `fabrik-reviewer`; asserted between its neighbours."""
    assert (
        "name the question and never the expected answer, and forbid writes anywhere under `~` and reads of any home"
        " path the brief does not name by file (name each `~/.claude*` file the seat must read, to be read through Bash"
        " under `timeout 120`, its size taken first with `stat -L -c %s`, in ranges of at most 64 KiB when larger). **A"
        " seat a later pass must RESUME"
    ) in _norm(PACK)


def test_critique_house_rule_allows_only_a_named_read() -> None:
    """B3: the design-critique house rules carry the named-read form, asserted between its neighbours (its seats are
    `fabrik-reviewer` agents, whose house rule carries the bounds)."""
    assert (
        "the house rules every seat brief carries: read-only, no `$HOME` read the brief does not name by file, scratch"
        " only under"
    ) in _norm(CRITIQUE)


HOME_CLAUDE = re.compile(r"(~|\$\{?HOME\}?|/home/[^/\s`]+)`?(-rooted `?)?/?\.claude")
STALL = re.compile(r"\b(stall|stalls|stalled|stalling|hang|hangs|hung|hanging)\b", re.IGNORECASE)


def _seat_texts() -> list[Path]:
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "commands", ".windsurf/rules", ".claude/workflows"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return [ROOT / p for p in out if p.endswith((".md", ".js"))]


def _offenders(text: str) -> list[str]:
    hits = []
    for para in re.split(r"\n\s*\n|\n\s*[-*] ", text):
        for sentence in re.split(r"\. ", " ".join(para.split())):
            if HOME_CLAUDE.search(sentence) and STALL.search(sentence):
                hits.append(sentence[:160])
    return hits


def test_no_seat_text_claims_a_home_read_stalls() -> None:
    """B4: no seat-facing sentence pairs a home-rooted `.claude` path with a stall or hang (this vocabulary only — a
    paraphrase such as "freezes" passes, as the D-row says). The matcher is proven on a sample of the old wording."""
    assert _offenders(
        "never read or write any `$HOME`-rooted `.claude*` path (it stalls the seat); x"
    )
    assert _offenders("forbid home-directory reads (a seat that opens `~/.claude*` stalls). B")
    assert _offenders("opening ${HOME}/.claude/x files is stalling the seat. y")
    assert _offenders("never read any `~`-rooted `.claude*` path (it stalls the seat); x")
    assert _offenders("reading `${HOME}`-rooted `.claude*` stalls. x")
    assert _offenders("never read `~`/.claude* (it stalls)")
    assert not _offenders("re-check code.claude.com; the installed binary confirms it. C")
    assert not _offenders("- read ~/.claude/x with cat\n- the build step hangs on a lock")
    files = _seat_texts()
    assert len(files) > 50
    found = {str(p.relative_to(ROOT)): _offenders(p.read_text()) for p in files}
    assert {k: v for k, v in found.items() if v} == {}
