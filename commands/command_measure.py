# AFTER-EDIT: docs/reference/command-corpus-check.md
"""The lean program's size measure and L1 ceiling: what a rendered command costs its reader.

Spec: the lean command corpus design (W-96f36043) § Target, § The measure, § Loop changes L1.
``measure()`` splits a command's cost into its OWN text (the render, every file under ``commands/``
the render names, and the rendered definition of every seat it names) and its READS (every other
repo file it names, plus the decision rows it cites). ``commands/_size_ceiling.json`` freezes, per
command, a ceiling over the own text (own +3%, ``HEADROOM``), the seats and the reads;
``assemble_commands.py --check`` exits 5 on a breach (``findings()``), after the LOSS gate's 4 and
before drift's 1. ``ratchet()`` (``--ratchet``, run by the coordinator on every merged tree) only
lowers; a raise is a hand edit carrying ``raised_by: D-<n>``.

Detection is mechanical and each row FREEZES what was detected: a path counts when the render names
it and it is a file, a seat when the render names it as a bare token outside the appended
fragments (identical in every render, so they carry no dispatch information), a decision row when
the render cites its id. A departure — a seat no longer named, a read not in the frozen set — is a
breach until a D-row in the row (``released`` / ``added``) names it. A hand-declared list would be
the cheapest evasion, and the corpus has no dispatch grammar to check it against.

COBRA (D-253), the cheapest passes and what catches each: deleting the last mention of a seat or a
read (a breach until a D-row releases it); a shrink left un-ratcheted to regrow into the slack (a
report line, and the coordinator ratchets every merged tree); a raise under a thin D-row (kaizen
counts ``raised_by`` changes from ``git log -p -- commands/_size_ceiling.json``, per D-row). NOT
measured, so kaizen's audit pair is the catcher: text moved into a script the agent is told to READ
(scripts are excluded as run, § The measure item 1, including ``commands/*.py``), into a fragment
named only by its bare stem ("read the term-coverage fragment"), into a file under
``docs/development/reviews/`` (excluded as output), or into a script's printed output (§ The measure
item 4, out of scope); renaming a command (a fresh row; fleet-visible, the ledger moves with it).
"""

from __future__ import annotations

import fnmatch
import json
import math
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent  # commands/
CEILING = ROOT / "_size_ceiling.json"
HEADROOM = 0.03  # L1: own text plus 3%; the file stores no copy
_SCRIPT = {".py", ".sh", ".bash", ".js", ".mjs", ".cjs", ".ts"}
# files the agent WRITES, or that every session loads whatever the command says (§ The measure 1, 3)
_OUTPUTS = (
    "docs/development/reviews/*",
    ".tmp/*",
    "CHANGELOG.md",
    "INDEX.md",
    "docs/DECISIONS.md",
    "docs/LESSONS_LEARNT.md",
    "docs/STRATEGIC_BACKLOG.md",
    "CLAUDE.md",
    "templates/governance/CLAUDE.md",
)
# a repo-relative path, optionally `/opt/fabrik/`- or `./`-prefixed, zero or more directories
_PATH = re.compile(r"(?<![\w.~/$-])(?:/opt/fabrik/+|\./)?((?:\.?[\w-][\w.-]*/+)*[\w-][\w.-]*\.[A-Za-z0-9]+)")
_INCLUDE = re.compile(r"^\{\{include:([\w-]+)\}\}\s*$", re.M)
_DID = re.compile(r"(?<![\w-])D-(\d+)(?![\w-])")
_ROW = re.compile(r"\|\s*(D-\d+)\s*\|")


def words(text: str) -> int:
    return len(text.split())


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def _named_files(text: str, root: Path) -> list[str]:
    out: list[str] = []
    for m in _PATH.finditer(text):
        rel = re.sub(r"/+", "/", m.group(1))
        if rel in out or ".." in Path(rel).parts:
            continue
        p = root / rel
        if p.is_file() and p.resolve().is_relative_to(root.resolve()):
            out.append(rel)
    return out


def decision_rows(root: Path) -> dict[str, str]:
    p = root / "docs" / "DECISIONS.md"
    rows: dict[str, str] = {}
    if p.is_file():
        for ln in _read(p).splitlines():
            if m := _ROW.match(ln):
                rows.setdefault(m.group(1), ln)
    return rows


def measure(
    cmd: str,
    render_dir: Path,
    root: Path,
    src_dir: Path,
    appended: tuple[str, ...] = (),
    rows: dict[str, str] | None = None,
) -> dict[str, Any]:
    """The own text and the reads of ``cmd``'s render in ``render_dir`` (seats under ``_agents/``).
    ``appended`` names the fragments the renderer appends without an include line."""
    text = _read(render_dir / f"{cmd}.md")
    src = src_dir / f"{cmd}.md"
    frag_dir = src_dir.parent / "_fragments"
    included = set(_INCLUDE.findall(_read(src))) if src.is_file() else set()
    own_src = f"commands/_sources/{cmd}.md"
    agents_dir = render_dir / "_agents"
    seat_names = sorted(p.stem for p in agents_dir.glob("*.md")) if agents_dir.is_dir() else []
    scan = text
    for name in appended:
        if (frag_dir / f"{name}.md").is_file():
            scan = scan.replace(_read(frag_dir / f"{name}.md").rstrip("\n"), "")
    agents: dict[str, int] = {}
    for name in seat_names:
        if re.search(rf"(?<![\w/-]){re.escape(name)}(?![\w-])", scan):
            agents[name] = words(_read(agents_dir / f"{name}.md"))
    own_reads: dict[str, int] = {}
    reads: dict[str, int] = {}
    for rel in _named_files(text, root):
        path = Path(rel)
        if path.suffix in _SCRIPT or rel == own_src:
            continue
        if rel.startswith("commands/"):
            if rel.startswith("commands/_fragments/") and (
                path.stem in included
                # appended to the render (close-feedback), or to every seat definition counted here
                # (agent-feedback): already read once
                or (path.stem in appended and (_read(root / rel).rstrip("\n") in text or agents))
            ):
                continue
            if rel.startswith("commands/_agents/") and path.stem in seat_names:
                agents.setdefault(path.stem, words(_read(agents_dir / f"{path.stem}.md")))
                continue
            own_reads[rel] = words(_read(root / rel))
        elif not any(fnmatch.fnmatch(rel, pat) for pat in _OUTPUTS):
            reads[rel] = words(_read(root / rel))
    rows = decision_rows(root) if rows is None else rows
    for n in dict.fromkeys(_DID.findall(text)):
        if (row := rows.get(f"D-{n}")) is not None:
            reads[f"docs/DECISIONS.md#D-{n}"] = words(row)
    render = words(text)
    return {
        "render": render,
        "own_reads": own_reads,
        "agents": agents,
        "own": render + sum(own_reads.values()) + sum(agents.values()),
        "reads": reads,
        "reads_total": sum(reads.values()),
    }


def measure_all(render_dir: Path, root: Path, src_dir: Path, appended: tuple[str, ...] = ()) -> dict[str, dict[str, Any]]:
    rows = decision_rows(root)
    return {p.stem: measure(p.stem, render_dir, root, src_dir, appended, rows) for p in sorted(render_dir.glob("*.md"))}


def ceiling_of(own: int) -> int:
    return math.ceil(own * (1 + HEADROOM))


# ── the ceiling file ──────────────────────────────────────────────────────────────────────────
def _load(path: Path) -> dict[str, Any]:
    """The whole ceiling document, validated; raises ``ValueError`` with the reason."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError("missing — run assemble_commands.py --ratchet") from None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unreadable ({type(exc).__name__})") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("commands"), dict):
        raise ValueError("no `commands` mapping")
    if not isinstance(doc.setdefault("retired", {}), dict):
        raise ValueError("`retired` is not a mapping")
    for name, row in doc["commands"].items():
        ok = (
            isinstance(row, dict)
            and all(type(row.get(k)) is int for k in ("baseline_own", "own", "render"))
            and isinstance(row.get("agents"), list)
            and isinstance(row.get("reads"), dict)
            and isinstance(row["reads"].get("paths"), dict)
            and all(isinstance(row.get(k, {}), dict) for k in ("released", "added"))
            and isinstance(row.get("raised_by", ""), str)
        )
        if not ok:
            raise ValueError(f"row {name!r} is not {{baseline_own, own, render: int, agents: [], reads: {{paths}}, …}}")
    return doc


def _cites(rows: dict[str, str], did: Any, what: str) -> str | None:
    """Why ``did`` does not license ``what``, else None (the row must exist)."""
    if not isinstance(did, str) or did not in rows:
        return f"{what} names {did!r}, which is no row in docs/DECISIONS.md"
    return None


def ceiling_findings(measured: dict[str, dict[str, Any]], path: Path, root: Path) -> tuple[list[str], list[str]]:
    """``(breaches, reports)`` for ``measured`` against the ceiling file at ``path``: a breach is an
    exit-5 line, a report never changes the exit."""
    try:
        doc = _load(path)
    except ValueError as exc:
        return [f"CEILING {path.name}: {exc}"], []
    rows = decision_rows(root)
    breaches: list[str] = []
    reports: list[str] = []
    grown: dict[str, list[str]] = {}
    for cmd, m in measured.items():
        row = doc["commands"].get(cmd)
        if row is None:
            breaches.append(f"CEILING {cmd}: no ceiling row — run assemble_commands.py --ratchet")
            continue
        if m["own"] > row["render"]:
            breaches.append(f"CEILING {cmd}: own text {m['own']} words > ceiling {row['render']} (+{m['own'] - row['render']})")
        if row["render"] > ceiling_of(row["baseline_own"]):
            why = _cites(rows, row.get("raised_by"), f"ceiling {row['render']} is raised above baseline {row['baseline_own']}+3%; raised_by")
            if why:
                breaches.append(f"CEILING {cmd}: {why}")
        if row["render"] > ceiling_of(m["own"]) and m["own"] <= row["render"]:
            reports.append(f"REPORT {cmd}: shrank to {m['own']} words, ceiling {row['render']} — lowered by assemble_commands.py --ratchet at merge")
        released = row.get("released", {})
        for seat in row["agents"]:
            if seat not in m["agents"]:
                why = _cites(rows, released.get(seat), f"seat {seat} is no longer named; released")
                if why:
                    breaches.append(f"CEILING {cmd}: {why}")
        for seat in sorted(set(m["agents"]) - set(row["agents"])):
            breaches.append(f"CEILING {cmd}: seat {seat} is named but not in the row — run assemble_commands.py --ratchet")
        frozen, added = row["reads"]["paths"], row.get("added", {})
        for key, w in m["reads"].items():
            if key not in frozen:
                why = _cites(rows, added.get(key), f"read {key} is new to the frozen set; added")
                if why:
                    breaches.append(f"CEILING {cmd}: {why}")
            elif type(frozen[key]) is int and w > frozen[key]:
                grown.setdefault(f"{key} {frozen[key]}→{w}", []).append(cmd)
    for cmd in sorted(set(doc["commands"]) - set(measured)):
        breaches.append(f"CEILING {cmd}: a row with no command — retire it with assemble_commands.py --ratchet")
    reports += [f"REPORT read grew {k} in {len(v)} command(s): {', '.join(v)}" for k, v in sorted(grown.items())]
    return breaches, reports


def findings(render_dir: Path, root: Path, src_dir: Path, appended: tuple[str, ...], path: Path | None = None) -> tuple[list[str], list[str]]:
    """``ceiling_findings`` over a fresh measure; never raises — any exception is one breach line."""
    try:
        return ceiling_findings(measure_all(render_dir, root, src_dir, appended), CEILING if path is None else path, root)
    except Exception as exc:  # noqa: BLE001 — a failed measure is a breach (exit 5), never drift's exit 1
        return [f"CEILING: measure failed — {type(exc).__name__}: {exc}"], []


def ratchet(measured: dict[str, dict[str, Any]], path: Path) -> list[str]:
    """Rewrite the ceiling file and return one line per change (none when nothing changed): each
    ceiling lowered to ceil(own*1.03) when that is lower, a newly named seat appended, a new command
    given a row (a retired name reuses its old ceiling), an orphan row retired. It never raises a
    ceiling and never rewrites ``baseline_own``, ``raised_by``, ``released``, ``added`` or a frozen
    reads set. A missing file is created; a malformed one raises ``ValueError`` (fix it by hand)."""
    try:
        doc = _load(path)
    except ValueError:
        if path.exists():
            raise
        doc = {"commands": {}, "retired": {}}
    changes: list[str] = []
    cmds, retired = doc["commands"], doc["retired"]
    for cmd, m in sorted(measured.items()):
        row = cmds.get(cmd)
        if row is None:
            ceiling = retired.pop(cmd, None)
            ceiling = ceiling_of(m["own"]) if type(ceiling) is not int else ceiling
            cmds[cmd] = {
                "baseline_own": m["own"],
                "own": m["own"],
                "render": ceiling,
                "agents": sorted(m["agents"]),
                "reads": {"total": m["reads_total"], "paths": dict(sorted(m["reads"].items()))},
            }
            changes.append(f"+ {cmd}: ceiling {ceiling} (own {m['own']})")
            continue
        new = min(row["render"], ceiling_of(m["own"]))
        if new != row["render"]:
            changes.append(f"↓ {cmd}: ceiling {row['render']} → {new} (own {m['own']})")
            row["render"], row["own"] = new, m["own"]
        if extra := sorted(set(m["agents"]) - set(row["agents"])):
            row["agents"] = row["agents"] + extra
            changes.append(f"+ {cmd}: seat(s) {', '.join(extra)}")
    for cmd in sorted(set(cmds) - set(measured)):
        retired[cmd] = cmds.pop(cmd)["render"]
        changes.append(f"- {cmd}: retired")
    if changes:
        doc["commands"] = dict(sorted(cmds.items()))
        doc["retired"] = dict(sorted(retired.items()))
        path.write_text(json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return changes
