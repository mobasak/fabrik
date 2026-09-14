#!/usr/bin/env python3
# AFTER-EDIT: scripts/final_gate.py, docs/TROUBLESHOOTING.md, tests/enforcement/test_check_corpus_weight.py
"""Corpus weight — a BYTE trend signal on the governance surfaces this repo OWNS.

WHAT IT MEASURES. Six hub surfaces, in bytes: ``CLAUDE.md``, ``templates/governance/CLAUDE.md``,
``commands/_sources``, ``commands/_fragments``, ``commands/_agents`` and ``.windsurf/rules`` — every
regular file under a directory surface, no extension filter (``.windsurf/rules/CLAIMS.yaml`` is
governance too). Symlinks are counted on NEITHER side: ``git ls-tree`` stores a link as a blob whose
size is the length of its target path, so following one on the tree side would invent a delta no
change could ever clear. These are the files an agent reads on every session or every invocation, so
their size is the cost the whole fleet pays; nothing else measures it.

OWNERSHIP. The positive marker is ``commands/_sources/``: the hub holds it, and so does every
registered worktree of the hub. A synced project's ``CLAUDE.md`` and ``.windsurf/rules/`` are
byte-identical copies the hub overwrites on every governance commit, so a project owns NOTHING here
and this check says exactly that and stops — a WARN about a file no project agent wrote and none may
fix is wallpaper, and wallpaper is how enforcement dies.

WHAT TRIGGERS THE WARN. The DELTA this tree carries above the base branch (``@{upstream}`` →
``origin/master`` → ``origin/main``). On a shared tree that delta includes a sibling session's
uncommitted and committed-but-unpushed work in those surfaces — the line says what it measured, not
who wrote it. The committed baseline never triggers anything: it is the trend record, and it only
ever tightens. Measured before shipping: a warn-on-every-rise-since-baseline would have fired on
16.8 of 29 days per surface (D-240 (b)), which is wallpaper.

EXIT CODES. **0 on every path the completion gate can reach**, an unexpected internal exception
included. ``run_optional_check`` reds the gate on ANY non-zero exit, ``warn_only`` or not, in ~46
synced repos, and it invokes this script with ``--check`` or with no flags at all, never with an
unknown one. ``--strict`` (which the gate never passes) exits 1 when a surface grew against the base
and 0 otherwise, and an internal error stays 0 even under it. An unparsable command line is
argparse's own exit 2, as in every other check. ⚠️ ``--strict`` changes only the EXIT CODE — it is
NOT a read-only mode, and on its own it still takes every write path a bare run takes. Pair it with
``--check`` for a diagnostic that touches nothing.

WHAT IT WRITES, AND WHEN. Exactly one file, ``.fabrik/corpus-weight-baseline.json``, on three paths:
``--seed`` (when none exists), ``--reseed`` (always), and a plain run that finds a surface BELOW its
baseline value (the ratchet tightening). Each write also ``git add``s that one path, so the tightened
trend record rides along with the change that moved it — the lint ratchet's behaviour, and the only
index mutation this script makes. ``--check`` reports in full and writes and stages nothing whatever
else is passed. Nothing is ever deleted — a surface that cannot be MEASURED this run is never ratcheted and keeps the baseline value
it already had, rather than being dropped from the record by a transient permission error; and a
worktree checkout reports and never writes — a tightening ``git add`` inside a sibling's worktree is
a collision, not a ratchet. The ONE thing a write removes is a key for a surface no longer in
``SURFACES`` (a retired or renamed one): ``--reseed`` drops it and names it, because a trend record
nothing measures is a number nobody can ever move.

Pattern and helpers follow ``scripts/enforcement/check_lint_ratchet.py``; the base-ref read follows
``scripts/enforcement/check_convergence.py::_head_text``; the ref ladder follows
``scripts/final_gate.py::_diff_base``.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
from pathlib import Path
from typing import Any

SURFACES: tuple[str, ...] = (
    "CLAUDE.md",
    "templates/governance/CLAUDE.md",
    "commands/_sources",
    "commands/_fragments",
    "commands/_agents",
    ".windsurf/rules",
)

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / ".fabrik" / "corpus-weight-baseline.json"
REL_BASELINE = ".fabrik/corpus-weight-baseline.json"

NOT_HUB = "corpus-weight: not the hub — every governance surface here is a copy; nothing to budget"


def is_owner(root: Path) -> bool:
    """Does *root* OWN its governance surfaces? The hub and its worktrees do; a sync copy does not."""
    return (root / "commands" / "_sources").is_dir()


def is_main_checkout(root: Path) -> bool:
    """A linked worktree's ``.git`` is a FILE. Every write in this script is gated on this."""
    return (root / ".git").is_dir()


def owned_surfaces(root: Path) -> list[str]:
    """The surfaces PRESENT in *root*'s tree, when *root* owns them at all.

    The report widens this to anything the baseline or the base ref also knows about, so a surface
    DELETED from the tree is still reported rather than vanishing silently — see ``_report``.
    """
    return [s for s in SURFACES if (root / s).exists()] if is_owner(root) else []


def measure(root: Path, surface: str) -> int | None:
    """Bytes of a file surface, or Σ bytes of every regular file under a directory surface.

    ``None`` means COULD NOT MEASURE — an unreadable directory, a stat that failed, a symlink, or a
    surface that is neither a regular file nor a directory. That distinction is load-bearing:
    ``Path.rglob`` swallows ``PermissionError``, so an unreadable subtree read as a SMALLER surface,
    and a plain run took that for a genuine shrink and tightened the committed trend record to a
    bogus value the ratchet can never walk back. An unmeasurable surface is reported and skipped.
    """
    target = root / surface
    try:
        if target.is_symlink():
            return None
        if target.is_file():
            return target.stat().st_size
        if not target.is_dir():
            return None
    except OSError:
        return None

    failed = False

    def _onerror(_exc: OSError) -> None:
        nonlocal failed
        failed = True

    total = 0
    for dirpath, _dirnames, filenames in os.walk(target, onerror=_onerror, followlinks=False):
        for name in filenames:
            path = Path(dirpath) / name
            try:
                if path.is_symlink():
                    continue  # ls-tree stores a link's TARGET PATH length — counted on neither side
                total += path.stat().st_size
            except OSError:
                failed = True
    return None if failed else total


def surface_state(root: Path, surface: str, size: int | None) -> str:
    """Why a surface carries no measurement — the cell an agent reads instead of a byte count.

    A symlink is checked FIRST: ``Path.exists()`` is False for a dangling one, and a link to a
    readable directory is skipped by policy (``git ls-tree`` sizes a link by its target path), not
    because anything failed — calling that "UNREADABLE" sends the reader hunting a permission
    problem that does not exist. A DANGLING link is the opposite error and gets its own cell: the
    surface is GONE, and a benign "counted on neither side" would hide a problem that is real.
    """
    if size is not None:
        return "ok"
    target = root / surface
    if target.is_symlink():
        # a DANGLING link is the surface being gone, not a policy skip — never the same cell
        return (
            "a symlink — counted on neither side"
            if target.exists()
            else "a DANGLING symlink — the surface it pointed at is gone"
        )
    if not target.exists():
        return "absent from the tree"
    if not target.is_dir() and not target.is_file():
        return "not a regular file or directory"
    return "UNREADABLE"


def diff_base(root: Path) -> str | None:
    """``final_gate.py::_diff_base``'s ladder — what this change will publish against.

    The ladder is that function's, rung for rung; the RETURN is deliberately the ref NAME on every
    rung. ``_diff_base``'s first rung already yields a name (``--abbrev-ref``) while its fallbacks
    yield a bare SHA, and a SHA in a warning tells an agent nothing they can diff — the line names
    what it measured against, per I5.
    """
    try:
        proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:  # git missing — no base is knowable
        return None
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip().splitlines()[0]
    for name in ("origin/master", "origin/main"):
        try:
            probe = subprocess.run(  # noqa: S603 — fixed argv, no shell
                ["git", "rev-parse", "--verify", "--quiet", name],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None
        if probe.returncode == 0 and probe.stdout.strip():
            return name
    return None


def base_sizes(root: Path, ref: str) -> dict[str, int | None] | None:
    """Σ blob sizes per surface at *ref* — ``None`` PER SURFACE for one with no blob there.

    Absent is not the same as present-and-empty: a surface this change CREATED has nothing to be
    measured against and is never reported as an addition. The WHOLE result is ``None`` when git
    itself could not answer, so a failed read degrades to "no base measured" rather than claiming
    every surface is absent.
    """
    out: dict[str, int | None] = {}
    for surface in SURFACES:
        try:
            proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
                ["git", "ls-tree", "-r", "-l", ref, "--", surface],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None
        if proc.returncode != 0:
            return None
        total = 0
        seen = False
        for line in proc.stdout.splitlines():
            meta, _, _path = line.partition("\t")
            fields = meta.split()
            if len(fields) < 4 or not fields[3].isdigit():
                continue  # a submodule (mode 160000) carries no size — not governance bytes
            if fields[0] == "120000":
                continue  # a symlink blob's size is its target path — skipped on the tree side too
            total += int(fields[3])
            seen = True
        out[surface] = total if seen else None
    return out


def baseline_is_usable_path() -> bool:
    """Is the baseline path a regular file (or absent)? A directory there kills every write."""
    return not BASELINE.exists() or BASELINE.is_file()


def read_baseline() -> tuple[dict[str, Any] | None, bool]:
    """``(payload, corrupt)`` — *corrupt* is True when the file EXISTS but is not readable JSON.

    A corrupted trend record used to render as "no baseline": the ratchet silently stopped
    ratcheting and said nothing was there. The two states now print differently.
    """
    if not BASELINE.exists():
        return None, False
    try:
        data = json.loads(BASELINE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, True
    return (data, False) if isinstance(data, dict) else (None, True)


def baseline_surfaces(payload: dict[str, Any] | None) -> dict[str, int] | None:
    """The payload's ``surfaces`` map with its values validated as ints, or ``None``."""
    if not payload:
        return None
    raw = payload.get("surfaces")
    if not isinstance(raw, dict):
        return None
    out: dict[str, int] = {}
    for key, value in raw.items():
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        out[str(key)] = value
    return out


def write_baseline(sizes: dict[str, int], ref: str | None) -> None:
    """Write the trend record and ``git add`` it — the only index mutation this script makes."""
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "surfaces": dict(sizes),
        "ref": ref,
        "seeded_at": datetime.datetime.now(datetime.UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
    }
    # compact, like the lint ratchet's baseline: one line means one diff line on a shared file
    BASELINE.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    # Stage it so the trend record rides along with the change that moved it (the lint ratchet's
    # staging; disclosed in --help). Best-effort: if git is unavailable the write above still stands.
    try:
        subprocess.run(  # noqa: S603 — fixed argv, no shell
            ["git", "add", "--", REL_BASELINE], cwd=ROOT, capture_output=True, check=False
        )
    except OSError:
        pass


def _baseline_is_gitignored(root: Path) -> bool:
    """Is the baseline excluded from the repo? Then it never reaches CI or a fresh clone.

    ⚠️ CI-PARITY DEPENDS ON THIS, exactly as it does for the lint ratchet: a repo that ignores
    ``.fabrik/`` can never commit the trend record, so the ratchet degrades to local-only. Surface it
    loudly rather than fail open in silence. (A TRACKED path is not ignored, and ``git check-ignore``
    is silent for one — which is the right answer here: a tracked baseline does travel.)
    """
    try:
        return (
            subprocess.run(  # noqa: S603 — fixed argv, no shell
                ["git", "check-ignore", "-q", REL_BASELINE],
                cwd=root,
                capture_output=True,
                check=False,
            ).returncode
            == 0
        )
    except OSError:  # git missing — can't tell; never crash the report over a warning
        return False


def _delta(now: int, then: int | None) -> str:
    if then is None:
        return "—"
    diff = now - then
    return "—" if diff == 0 else f"{diff:+d}"


def _surface_lines(
    root: Path,
    sizes: dict[str, int | None],
    baseline: dict[str, int] | None,
    base: dict[str, int | None] | None,
    ref: str | None,
) -> list[str]:
    lines: list[str] = []
    for surface, size in sizes.items():
        prior = baseline.get(surface) if baseline else None
        b_cell = str(prior) if prior is not None else "—"
        if size is None:
            # never compared, never ratcheted — the cell names which of the three reasons applies
            state = surface_state(root, surface, size)
            lines.append(
                f"corpus-weight: {surface} {state} · baseline {b_cell} (—) · base {ref or '—'} (—)"
            )
            continue
        b_delta = _delta(size, prior)
        if base is None:
            base_cell = "—"
        elif base.get(surface) is None:
            base_cell = "absent — not budgeted"
        else:
            base_cell = _delta(size, base[surface])
        lines.append(
            f"corpus-weight: {surface} {size} B · baseline {b_cell} ({b_delta}) "
            f"· base {ref or '—'} ({base_cell})"
        )
    return lines


def verdict(
    sizes: dict[str, int | None],
    baseline: dict[str, int] | None,  # noqa: ARG001 — the baseline NEVER triggers a verdict
    base: dict[str, int | None] | None,
    ref: str | None,
) -> tuple[bool, list[str]]:
    """``(grew, lines)`` — growth is the tree ABOVE the base ref, per surface, and nothing else."""
    if base is None:
        return False, ["corpus-weight: no base ref — growth vs base not measured"]
    lines = [
        f"⚠ corpus-weight: this change ADDS {size - (base[s] or 0)} B to {s} "
        f"(base {ref} → tree) — a governance surface grew; the review that accepts it cites the "
        f"D-row naming what the growth retires"
        for s, size in sizes.items()
        if size is not None and base.get(s) is not None and size > (base[s] or 0)
    ]
    if not lines:
        return False, [f"corpus-weight: OK — no owned surface grew vs {ref}"]
    return True, lines


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="check_corpus_weight.py",
        description=(
            "Byte trend signal on the governance surfaces this repo OWNS. Reports; it never blocks."
        ),
        epilog=(
            "WHAT IT WRITES: exactly one file, .fabrik/corpus-weight-baseline.json, on three paths —\n"
            "  --seed     writes it when none exists (a no-op, with a hint, when one does)\n"
            "  --reseed   writes today's sizes whether or not one exists\n"
            "  (plain)    tightens it for any surface now BELOW its baseline value\n"
            "Each write also `git add`s that ONE path, so the tightened record rides with the change\n"
            "that moved it — the only index mutation this script makes. --check reports in full and\n"
            "writes and stages nothing, whatever else is passed. A worktree checkout reports and\n"
            "never writes. A surface that cannot be measured is never ratcheted and keeps the\n"
            "value it already had. The one thing a write removes is a key for a surface no longer\n"
            "in SURFACES: --reseed drops it and names it.\n\n"
            "EXIT CODES: 0 on every path the gate can reach, an unexpected internal error included.\n"
            "--strict exits 1 when a surface grew against the base ref and 0 otherwise; the gate\n"
            "never passes it. An unparsable command line is argparse's own exit 2.\n\n"
            "--strict CHANGES ONLY THE EXIT CODE. It is NOT a read-only mode: on its own it still\n"
            "takes every write path a bare run takes. Pair it with --check to touch nothing."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--check", action="store_true", help="report only — writes and stages nothing")
    ap.add_argument("--seed", action="store_true", help="write the baseline when none exists")
    ap.add_argument(
        "--reseed", action="store_true", help="overwrite the baseline with today's sizes"
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when a surface grew vs the base ref — exit code only, NOT a read-only mode",
    )
    return ap


def _not_written_because(check: bool, usable: bool, main_checkout: bool) -> str:
    """Why this run wrote nothing — the ONE ladder every skip line reads.

    ``writable`` is False for three causes and the seed/reseed skip lines used to name only one of
    them, so an export with no ``.git`` and a baseline path that is a directory both reported
    "a worktree never writes" two lines under a message saying otherwise.
    """
    if check:
        return "--check writes nothing"
    if not usable:
        return "the baseline path is not a regular file"
    if not main_checkout:
        return (
            "a worktree never writes the baseline"
            if (ROOT / ".git").exists()
            else "this tree is not a git checkout"
        )
    return "nothing was writable"


def _report(args: argparse.Namespace) -> int:
    root = ROOT
    if not is_owner(root):
        print(NOT_HUB)
        return 0

    ref = diff_base(root)
    base = base_sizes(root, ref) if ref else None
    if base is None:
        ref = None  # git could not answer: say "no base ref", never "every surface is absent"
    payload, unreadable = read_baseline()
    baseline = baseline_surfaces(payload)
    # a file that parses but whose `surfaces` map is unusable (a string value, a list) is corrupt
    # too: it used to render as "no baseline", so the ratchet stopped and said nothing was there
    corrupt = unreadable or (baseline is None and BASELINE.exists())

    present = owned_surfaces(root)
    # A surface the baseline or the base ref knows about is reported even when the tree has lost it:
    # a DELETED governance surface is the largest possible regression and must never vanish silently.
    # a dangling link: exists() is False, so `present` misses it, but the surface is not GONE
    linked = {s for s in SURFACES if (root / s).is_symlink()}
    known = [
        s
        for s in SURFACES
        if s in present
        or s in linked
        or (baseline and s in baseline)
        or (base and base.get(s) is not None)
    ]
    sizes: dict[str, int | None] = {s: (measure(root, s) if s in present else None) for s in known}

    for line in _surface_lines(root, sizes, baseline, base, ref):
        print(line)

    grew, lines = verdict(sizes, baseline, base, ref)
    for line in lines:
        print(line)

    main_checkout = is_main_checkout(root)
    if not main_checkout:
        where = "worktree" if (root / ".git").exists() else "not a git checkout"
        print(f"corpus-weight: {where} — reporting only, nothing written")
    if _baseline_is_gitignored(root):
        print(f"⚠ corpus-weight: {REL_BASELINE} is gitignored here — the ratchet is local-only")
    usable = baseline_is_usable_path()
    if not usable:
        print(
            f"⚠ corpus-weight: {REL_BASELINE} is not a regular file — no trend can be kept or "
            "rebuilt until that path is cleared by hand; --seed and --reseed both refuse"
        )
    elif corrupt:
        print(
            f"⚠ corpus-weight: {REL_BASELINE} is unreadable or malformed — no trend is being kept; "
            "--reseed rebuilds it"
        )

    writable = main_checkout and not args.check and usable
    ref_cell = ref or "—"
    measured = {s: v for s, v in sizes.items() if v is not None}
    unmeasured = [s for s, v in sizes.items() if v is None and (baseline or {}).get(s) is not None]
    # a write preserves a surface it could not measure, but only one the registry still HAS: a key
    # for a retired or renamed surface would otherwise be immortal, and nothing would ever name it
    kept = {k: v for k, v in (baseline or {}).items() if k in SURFACES}
    retired = [k for k in (baseline or {}) if k not in SURFACES]
    count = len(measured)

    if args.reseed:
        if args.check:
            print(
                f"corpus-weight: would reseed {count} surface(s) at {ref_cell} (--check: not written)"
            )
            for surface in retired:
                print(
                    f"corpus-weight: would drop {surface} from the baseline (--check: not written)"
                )
            for surface in unmeasured:
                print(
                    f"corpus-weight: would keep {surface} at its previous baseline — not measurable "
                    "this run (--check: not written)"
                )
        elif writable:
            write_baseline({**kept, **measured}, ref)
            print(f"corpus-weight: reseeded {count} surface(s) at {ref_cell} → {REL_BASELINE}")
            for surface in retired:
                print(
                    f"corpus-weight: dropped {surface} from the baseline — not a surface this "
                    "check measures; --reseed is the only path that removes a stale key"
                )
            for surface in unmeasured:
                print(
                    f"corpus-weight: {surface} kept at its previous baseline — not measurable this "
                    "run, and a write never drops a surface's trend record"
                )
        else:
            why = _not_written_because(args.check, usable, main_checkout)
            print(f"corpus-weight: --reseed skipped — {why}")
    elif args.seed:
        if not usable:
            # never send the reader to --reseed when --reseed refuses too: the ⚠ above says why
            print(
                f"corpus-weight: --seed skipped — {_not_written_because(args.check, usable, main_checkout)}"
            )
        elif BASELINE.exists():
            # the FILE, not a usable map: --help says "when none exists", and a corrupt one exists
            print("corpus-weight: baseline exists — use --reseed")
        elif args.check:
            print(
                f"corpus-weight: would seed {count} surface(s) at {ref_cell} (--check: not written)"
            )
        elif writable:
            write_baseline(measured, ref)
            print(f"corpus-weight: seeded {count} surface(s) at {ref_cell} → {REL_BASELINE}")
        else:
            why = _not_written_because(args.check, usable, main_checkout)
            print(f"corpus-weight: --seed skipped — {why}")
    elif baseline is None:
        if not corrupt:
            print("corpus-weight: no baseline — run --seed at a corpus state you accept")
    else:
        for surface in measured:
            if surface not in baseline:
                print(
                    f"corpus-weight: {surface} is not in the baseline — --reseed to include it in "
                    "the trend record"
                )
        tighter = {s: v for s, v in measured.items() if s in baseline and v < baseline[s]}
        for surface, size in tighter.items():
            if writable:
                print(f"corpus-weight: ratcheted DOWN {surface} {baseline[surface]} → {size}")
            else:
                why = _not_written_because(args.check, usable, main_checkout)
                print(
                    f"corpus-weight: would ratchet DOWN {surface} {baseline[surface]} → {size} "
                    f"— {why}"
                )
        if tighter and writable:
            write_baseline({**baseline, **tighter}, ref)

    return 1 if (grew and args.strict) else 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return _report(args)
    except Exception as exc:  # noqa: BLE001 — a traceback here would red ~46 repos' completion gates
        print(f"corpus-weight: internal error — {type(exc).__name__}: {exc} (reporting only)")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
