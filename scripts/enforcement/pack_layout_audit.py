#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_pack_layout_audit.py
"""Pack-layout audit engine — which `.windsurf/rules` packs CLAIM to govern a scaffold
type but match ZERO paths that type actually emits.

WHY THIS EXISTS: rule-pack `globs:` were written for a DIRECTORY-per-concern layout
(`workers/`, `jobs/`, `auth/`) while the fabrik scaffolds emit a FILE-per-concern layout
(`worker.py`, `billing_routes.py`). A pack can therefore be silently inert in every
project it governs, and nothing detected it — `select_rules.py` derives ACTIVE/AVAILABLE
from the very same globs, so a broken glob just drops the pack to AVAILABLE and looks
like ordinary "not touched yet" behavior. Measured live against `/opt/transdoc`
(2026-08-25): `core/75-workers-jobs.md` and `core/app-audit-log.md` — ALL of their globs
matched zero paths, while `transdoc/server/src/transdoc/worker.py` and
`billing_routes.py` (exactly what those packs govern) sat right there.

WHAT IT PROVES: `audit_layout(root, types)` cross-references, for every GLOB-ACTIVATED
pack under `root/.windsurf/rules`, its declared `applies_to:` frontmatter list against
the paths a FRESH scaffold of each claimed type actually emits (the honest denominator —
see `_emitted_paths_for_type`). A (pack, type) pair is a Finding when the pack claims
that type and its globs match nothing the scaffold produces.

THREE RULES (Behavior Contract — `tests/enforcement/test_pack_layout_audit.py`):
1. Applicability comes from the pack's `applies_to:` frontmatter, NEVER from the globs
   under test — deriving it from the globs is circular (see `select_rules.py`, which
   already derives ACTIVE this way; a broken pack silently drops to AVAILABLE there and
   this check could never fire if it used the same signal).
2. `activation: manual` packs are excluded entirely — not reported, not counted inert,
   never re-globbed. The four `00-domain-*` packs are manual ON PURPOSE (see
   `.windsurf/rules/saas/00-domain-saas.md` lines 1-20): their consumers load them BY
   PATH, not by glob, and a glob would inject business-formation prose into every
   coding session that happens to touch a matching file.
3. One Finding per (pack, type) pair the pack's `applies_to` claims AND that matches
   zero emitted paths — never per-glob (a pack can carry several globs; only the
   aggregate verdict for that type matters).

⚠️ THE DENOMINATOR IS CONTAMINATED IN BOTH DIRECTIONS — a Finding here is a STRONG
signal, and the ABSENCE of one is a WEAK signal. Measured, not theorised (2026-08-25):

  * OVER-states reachability. A fresh scaffold contains everything the scaffolder COPIES
    from the hub — `.windsurf/rules/**`, `scripts/enforcement/**`, `libs/subagents/`,
    `db/schema.sql`, `tests/`, `Dockerfile`, `compose.yaml`, `.env.example`. Packs can
    therefore be "reachable" via boilerplate alone, never via type-specific source. For
    `docusaurus`: `core/30-ops.md` clears on `Dockerfile`/`compose.yaml`;
    `core/62-using-subagents.md` clears on `libs/subagents` — i.e. it satisfies its own
    reachability claim with its OWN copied file. That is a FALSE CLEAR.
  * UNDER-states reachability. `rules_match._EXCLUDE` prunes `templates/`, `output/`,
    `backups/`, `.droid/`, `.tmp/` during the walk, so a glob aimed at any of them can
    never match. Real example: `core/86-email-templates.md` globs `**/templates/*email*`
    — annotating that pack would yield a FALSE INERT finding.

`check_pack_reachability` therefore prints WHICH path satisfied each claim, so a
boilerplate-only clear is visible to the reader rather than silent. Fixing the
denominator properly needs a scaffolder-side manifest of "type source vs copied
governance", which does not exist today; this is the honest interim. (D7 finding.)

DENOMINATOR: "paths the scaffolder actually emits" for a type, NOT its raw template
directory contents — the two provably diverge (`file-worker`'s template ships
`worker/__init__.py` + `worker/main.py`; the real `create_project()` output additionally
synthesizes `worker/logger.py` + `worker/pause_state.py` and drops `__init__.py`). Using
the template would under- or over-state what a real project actually has on disk.
`_emitted_paths_for_type` scaffolds for real (via `src.fabrik.scaffold.create_project`,
throwaway `base=`) and walks the result with `rules_match`'s own tree-walk primitives —
this is the ONE place in the codebase that needs to run scaffolds to answer a governance
question, and it only works from the hub (`fabrik` — the CLI package — is not shipped to
synced projects).
"""

from __future__ import annotations

import argparse
import functools
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

_ENFORCEMENT_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _ENFORCEMENT_DIR.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import rules_match  # noqa: E402 - the shared glob-normalization primitives (reused, not reimplemented)
import select_rules  # noqa: E402 - _parse_frontmatter (globs + description) + the frontmatter regex

# Two extra frontmatter fields select_rules._parse_frontmatter doesn't read (it only
# needs globs+description for its own ACTIVE/AVAILABLE split) — parsed the same way
# (same `_FM` frontmatter block regex), so a pack authored today needs no rewrite.
_ACTIVATION_RE = re.compile(r"^activation:\s*(\S+)", re.MULTILINE)
_APPLIES_TO_RE = re.compile(r"^applies_to:\s*\[(.*?)\]", re.MULTILINE | re.DOTALL)


@dataclass(frozen=True)
class Finding:
    """One (pack, scaffold type) pair: the pack's `applies_to` claims this type, and
    none of its globs match anything a fresh scaffold of that type emits."""

    pack: str  # relative to `.windsurf/rules/`, posix (e.g. "core/75-workers-jobs.md")
    scaffold_type: str  # e.g. "file-worker"
    globs: tuple[str, ...]  # the pack's globs, for the report — NOT what drove applicability


def _parse_extra_frontmatter(text: str) -> tuple[str, list[str]]:
    """(activation, applies_to) from a pack's frontmatter block. Absent fields are the
    empty string / empty list — a pack with no `applies_to:` claims nothing and can
    never generate a Finding (rule 1: applicability is opt-in, never inferred)."""
    m = select_rules._FM.search(text)
    fm = m.group(1) if m else ""
    am = _ACTIVATION_RE.search(fm)
    activation = am.group(1).strip() if am else ""
    tm = _APPLIES_TO_RE.search(fm)
    if tm is None:
        # BLOCK-SEQUENCE form — the one a YAML author is MOST likely to write for a
        # multi-item list, and the flow-style regex above silently yields [] for it:
        #     applies_to:
        #       - file-worker
        #       - saas-skeleton
        # Same fail-silent-green class as the quotes-only bug fixed earlier today, in a
        # second legal form that fix did not cover (D7 finding, 2026-08-25).
        bm = re.search(r"^applies_to:\s*$\n((?:[ \t]+-[ \t]*\S.*\n?)+)", fm, re.MULTILINE)
        if bm:
            items = [
                ln.strip().lstrip("-").strip().strip("\"'")
                for ln in bm.group(1).splitlines()
                if ln.strip().lstrip("-").strip().strip("\"'")
            ]
            return activation, items
    # ⚠️ Accept BOTH quoted and bare items. `applies_to: [file-worker]` is legal YAML and an
    # author will write it; a quotes-only regex silently yielded [] for it, so the pack was
    # skipped and could never produce a Finding — this check's OWN fail-silent-green, inside
    # the check built to close that class (review finding, 2026-08-25). Split on commas and
    # strip optional quotes per item rather than requiring them.
    applies_to = (
        [item.strip().strip("\"'") for item in tm.group(1).split(",") if item.strip().strip("\"'")]
        if tm
        else []
    )
    return activation, applies_to


def _packs_with_meta(root: Path) -> list[tuple[str, list[str], str, list[str]]]:
    """[(relative pack path, globs, activation, applies_to)] for every pack under
    `root/.windsurf/rules`. Reuses `select_rules._parse_frontmatter` for globs — the
    canonical corpus loader (`review_rubric.py::_packs` does the same)."""
    rules_dir = root / ".windsurf" / "rules"
    out: list[tuple[str, list[str], str, list[str]]] = []
    if rules_dir.exists():
        for pack in sorted(rules_dir.rglob("*.md")):
            text = pack.read_text(encoding="utf-8", errors="replace")
            globs, _desc = select_rules._parse_frontmatter(text)
            activation, applies_to = _parse_extra_frontmatter(text)
            out.append((pack.relative_to(rules_dir).as_posix(), globs, activation, applies_to))
    return out


def _import_create_project():
    """Locate `src.fabrik.scaffold.create_project` — the fabrik hub's own scaffolder
    (never a project's copy; scaffolding is hub-only tooling). Tries the repo this
    script lives in first (the hub itself, or a hub worktree), then `/opt/fabrik` (this
    script's file is governance-synced to ~46 projects; a project has no `src/fabrik/`
    and must fall back to the real hub, mirroring `check_synced_unmodified.py`'s
    `FABRIK_ROOT` pattern)."""
    for candidate in (_SCRIPTS_DIR.parent, Path("/opt/fabrik")):
        if (candidate / "src" / "fabrik" / "scaffold.py").exists():
            if str(candidate) not in sys.path:
                sys.path.insert(0, str(candidate))
            from src.fabrik.scaffold import create_project  # type: ignore[import-not-found]

            return create_project
    raise RuntimeError(
        "fabrik scaffolder not found (checked the local repo root and /opt/fabrik) — "
        "pack_layout_audit only runs at the hub"
    )


@functools.cache
def _emitted_paths_for_type(project_type: str) -> tuple[str, ...] | None:
    """Every relative file/dir path (posix) a FRESH `create_project(project_type=...)`
    emits — the honest denominator (see module docstring: the scaffold path diverges
    from the raw template directory). Throwaway `base=`, cleaned up immediately; cached
    per type since several packs can claim the same type in one `audit_layout` call.
    Extracted to its own function so tests can monkeypatch it and stay hermetic (no real
    scaffold invocation, no dependency on the live corpus or the scaffolder's runtime)."""
    try:
        create_project = _import_create_project()
    except RuntimeError:
        # The scaffolder is HUB-ONLY and this file is governance-synced to ~46 repos. main()
        # guards this — but ONLY on the `--types` DEFAULT branch. Pass `--types` explicitly
        # (exactly what docs/reference/rule-pack-reachability.md tells a pack author to do to
        # confirm an annotation) and the guard is skipped, the RuntimeError escapes main()
        # uncaught, and `run_optional_check(..., warn_only=True)` turns that traceback into a
        # HARD gate failure in every repo that cannot see the hub. Same class as the
        # `wordpress` NotImplementedError, different entry point. Proven by execution: with
        # _import_create_project stubbed to raise, `--types file-worker` crashed.
        # A type we cannot scaffold contributes NO paths — never a crash.
        # ⚠️ Returns None, NOT (). They mean different things and conflating them is a
        # SECOND defect: with () every annotated pack matches zero paths and is reported
        # UNREACHABLE — false findings on every repo that cannot see the hub. None means
        # "cannot evaluate"; audit_layout SKIPS those types rather than condemning them.
        # (Caught while fixing finding 13 — the first fix introduced it.)
        return None
    # ⚠️ SUPPRESS the scaffolder's post-scaffold sync for this THROWAWAY probe.
    # `create_project` ends with `_post_scaffold_sync()`, which shells out to
    # `scripts/sync_projects.py` with `cwd=FABRIK_ROOT` and REWRITES three tracked hub
    # files: PORTS.md, data/projects.yaml, docs/PROJECT_CATALOG.md. That is catastrophic
    # for an ADVISORY, supposedly read-only check that ships to ~46 repos:
    #   * `final_gate.py --check` is contractually READ-ONLY and would mutate the tree;
    #   * three concurrent hub sessions share this tree — every gate run dirties files
    #     that then get swept into somebody else's commit;
    #   * a PROJECT's gate run would reach into /opt/fabrik and rewrite hub files, i.e.
    #     the "files outside project tree" HARD STOP executed by machinery, not an agent.
    # Proven live before this fix: one `--types file-worker` run changed PORTS.md's md5.
    # We want the scaffold's OUTPUT, never its registry side effects. (D7 finding, 2026-08-25.)
    scaffold_mod = sys.modules[create_project.__module__]
    _real_sync = getattr(scaffold_mod, "_post_scaffold_sync", None)
    if _real_sync is not None:
        scaffold_mod._post_scaffold_sync = lambda *_a, **_kw: None
    try:
        return _scaffold_and_walk(create_project, project_type)
    except (NotImplementedError, ValueError):
        # TWO cases, one sentinel. NotImplementedError: a registry type with no scaffolder
        # (e.g. `wordpress`). ValueError: `create_project` rejecting a type it does not know
        # — reachable because `--types` is USER-SUPPLIED and never validated against the
        # registry before use. A round-6 finder considered this exact path and dismissed it
        # ("audit_layout only calls this for types in SCAFFOLD_TYPES, pre-validated"); that
        # reasoning was wrong, and a direct probe crashed the check with an uncaught
        # ValueError -> non-zero exit -> warn_only turns it into a gate failure. Third
        # instance of "an uncaught exception escapes an ADVISORY check" (cf. findings 2, 13).
        # Some registry types have no scaffolder (e.g. `wordpress` is out of fabrik) but
        # ARE in SCAFFOLD_TYPES, which is what the docs tell pack authors to choose from.
        # Uncaught, this propagated out of an ADVISORY check -> non-zero exit -> and
        # run_optional_check's warn_only contract fails the gate on ANY non-zero exit,
        # i.e. a hard gate failure in ~46 repos the moment one pack annotated that type.
        # ⚠️ Returns None, NOT (). A type with no scaffolder cannot be EVALUATED; it does
        # not "emit nothing". With () every pack claiming that type matches zero paths and
        # is reported UNREACHABLE — a FALSE finding, at fleet scale. Proven live: a pack
        # claiming `wordpress` was printed as "globs match ZERO paths that type emits" when
        # the truth is the type cannot be built here at all. The RuntimeError branch above
        # already returned None; this branch did not, so the sentinel was only half-applied.
        # (D7 round 6, finding 14 — the SECOND half of finding 13's own fix.)
        return None
    finally:
        if _real_sync is not None:
            scaffold_mod._post_scaffold_sync = _real_sync


def _scaffold_and_walk(create_project, project_type: str) -> tuple[str, ...]:
    """Scaffold into a throwaway dir and return its path tuple. Split out so the
    side-effect suppression above wraps the whole scaffold, not just part of it."""
    with tempfile.TemporaryDirectory(prefix="pack-layout-audit-") as tmp:
        project_dir = create_project(
            f"probe-{project_type}",
            "pack layout audit probe (throwaway)",
            base=Path(tmp),
            project_type=project_type,
            generate_spec=False,
        )
        return rules_match._tree_paths(project_dir)


def _satisfying_path(paths: tuple[str, ...] | None, globs: list[str]) -> str | None:
    """The FIRST emitted path any glob matches, or None. Same logic as
    `_matches_any_emitted`, but returns the evidence instead of a bare bool — so a caller
    can show the reader WHY a pack was cleared. That matters because the denominator
    over-states reachability (see module docstring): a clear on `Dockerfile` or
    `libs/subagents` is a boilerplate-only clear, and only the path reveals it."""
    if paths is None:
        return None  # cannot evaluate — never a clear
    for glob in globs:
        pat = rules_match._strip_wildcards(glob)
        if pat is None:
            continue
        for expanded in rules_match._expand_braces(pat):
            for rel in paths:
                if rules_match._tail_matches(rel, expanded):
                    return rel
    return None


def _matches_any_emitted(paths: tuple[str, ...] | None, globs: list[str]) -> bool:
    """Does ANY of `globs` match ANY of `paths`? Built from `rules_match`'s own
    normalization primitives (`_strip_wildcards` / `_expand_braces` / `_tail_matches`) —
    the same three steps `any_path_matches` composes, just fed a pre-fetched path tuple
    instead of walking a live directory (there is no directory to walk after the
    scaffold's `TemporaryDirectory` closes).

    ⚠️ The wildcard-only story is NOT uniform, and an earlier version of this docstring
    claimed it was ("a wildcard-only glob is treated as NON-matching, mirroring
    select_rules' empty_matches_all=False"). That holds for `**/` ONLY. `_strip_wildcards`
    does `lstrip("/")` FIRST, so `/**` and `**` survive as `'**'`, reach `_tail_matches`,
    and match EVERYTHING. Measured against ("worker/main.py", "Dockerfile"):

        glob='**/'  this=False  rules_match(empty_matches_all=True)=True   select_rules=False
        glob='/**'  this=True   rules_match=True                            select_rules=True
        glob='**'   this=True   rules_match=True                            select_rules=True

    Two consequences, both latent: (a) a pack globbing `/**` is auto-declared reachable for
    every type, having proven nothing; (b) for `**/` this audit reports UNREACHABLE while
    `review_rubric` injects that same pack as MATCHED for EVERY changed path — a genuine
    disagreement between this engine and the shared matcher. The cross-ticket seam proof
    could not observe it: it used only the two live packs, neither carrying a wildcard-only
    glob, and no pack in the corpus carries one today (verified). Recorded rather than
    silently "mirrored". (D7 whole-plan validation, 2026-08-25.)

    MECHANISM for `**/`, stated precisely because two review rounds read the previous wording
    as a stronger guarantee than the code gives: `_strip_wildcards("**/")` returns None and
    the loop SKIPS that glob — it contributes nothing either way. A pack whose ONLY glob is
    `**/` therefore ends with no matches and is reported unreachable; a pack that also has
    real globs is decided entirely by those. So the effect matches "wildcard-only proves
    nothing about this type", but it is a consequence of the skip, not a special case anyone
    wrote. Do not restate it as a deliberate policy."""""
    if paths is None:
        # SYMMETRY with _satisfying_path, which already tolerates the sentinel. Every call
        # site guards `is None` today, so this is latent — but two sibling helpers with
        # DIFFERENT None-tolerance is precisely the trap that produced finding 13's cascade
        # (a fix returned () where None was meant, and every pack was condemned). "Cannot
        # evaluate" is never "matched". (Self-probe during the round-6 confirming pass.)
        return False
    for glob in globs:
        pat = rules_match._strip_wildcards(glob)
        if pat is None:
            continue
        for expanded in rules_match._expand_braces(pat):
            if any(rules_match._tail_matches(rel, expanded) for rel in paths):
                return True
    return False


def audit_layout(root: Path, types: list[str]) -> list[Finding]:
    """For the pack corpus under `root/.windsurf/rules` x `types`: every (pack, type)
    pair where the pack's `applies_to:` claims `type` and none of its globs match
    anything a fresh scaffold of `type` emits."""
    findings: list[Finding] = []
    for rel, globs, activation, applies_to in _packs_with_meta(root):
        if activation == "manual":  # rule 2 — excluded entirely, never re-globbed
            continue
        for scaffold_type in types:
            if scaffold_type not in applies_to:  # rule 1 — applicability is declared, not derived
                continue
            emitted = _emitted_paths_for_type(scaffold_type)
            if emitted is None:
                # Cannot evaluate this type here (no scaffolder, or none for this type).
                # Skipping is the honest answer: "I could not ask" is NOT "the pack is
                # unreachable". Returning () instead would report every claiming pack as
                # UNREACHABLE on every repo that cannot see the hub — false findings at
                # fleet scale. (D7 confirming round, finding 13's second half.)
                continue
            if not _matches_any_emitted(emitted, globs):  # rule 3 — one row per claimed pair
                findings.append(Finding(pack=rel, scaffold_type=scaffold_type, globs=tuple(globs)))
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Audit .windsurf/rules pack applies_to claims against real scaffold-emitted layout."
    )
    ap.add_argument("--project-root", type=Path, default=Path.cwd())
    ap.add_argument(
        "--types",
        nargs="+",
        default=None,
        help="scaffold types to check (default: all types from the live SCAFFOLD_TYPES registry)",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = args.project_root.resolve()

    types = args.types
    if types is None:
        try:
            _import_create_project()  # ensures the hub's `src.fabrik` is on sys.path
            from src.fabrik.scaffold import SCAFFOLD_TYPES  # type: ignore[import-not-found]

            types = sorted(SCAFFOLD_TYPES)
        except (RuntimeError, ImportError) as e:
            print(
                f"ERROR: could not resolve the live SCAFFOLD_TYPES registry: {e}", file=sys.stderr
            )
            return 1

    findings = audit_layout(root, types)
    denominator = (
        f"{len(types)} scaffold type(s) x the pack corpus under {root / '.windsurf' / 'rules'}"
    )

    if args.json:
        print(
            json.dumps(
                {
                    "denominator": denominator,
                    "findings": [
                        {"pack": f.pack, "scaffold_type": f.scaffold_type, "globs": list(f.globs)}
                        for f in findings
                    ],
                },
                indent=2,
            )
        )
    else:
        print(f"Checked {denominator}.")
        if not findings:
            print(
                "OK — every glob-activated pack's applies_to claim matches at least one emitted path."
            )
        else:
            for f in findings:
                print(
                    f"  INERT: {f.pack} claims applies_to includes {f.scaffold_type!r} "
                    f"but globs {list(f.globs)} match ZERO paths that type emits"
                )
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
