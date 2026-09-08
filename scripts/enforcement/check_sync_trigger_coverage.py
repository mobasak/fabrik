#!/usr/bin/env python3
# AFTER-EDIT: tests/test_sync_trigger_coverage.py, scripts/fabrik_synced_manifest.py
"""Gate: every FLEET-SYNCED surface must either TRIGGER the governance-sync or be declared a
deliberate non-trigger.

The bug this exists to make unreachable: `fabrik_synced_manifest.py` says WHAT is distributed to
~46 projects; the `governance-sync` `files:` filter in `.pre-commit-config.yaml` decides which
edits actually FIRE that distribution. When a path is in the first list and not the second, you
edit a fleet-wide file, commit it, and it silently never ships — the fleet keeps running the old
copy. That happened twice on 2026-08-09 (the `release_cut.py` review fix sat un-distributed until
a manual `--force` sync), which is why the filter is no longer allowed to be maintained by memory.

Deliberate non-triggers are legitimate and documented (CLAUDE.md § Sync-consciousness): RUN_SCRIPTS,
`.windsurf/workflows/`, and most reference docs ride the NEXT unrelated sync rather than paying a
fleet-wide distribution on every edit. So this gate does not demand universal coverage — it demands
that the choice was made CONSCIOUSLY: covered by the filter, or listed below. A brand-new manifest
entry matches neither and fails until someone decides which it is.

Direction: manifest → filter only. A filter alternative with no manifest entry (a path that
triggers a sync but is not itself distributed) is harmless — it costs one extra sync, it never
loses one — so it is out of scope here rather than an undetected defect.

Usage:
    python scripts/enforcement/check_sync_trigger_coverage.py          # gate (exit 1 on a gap)
    python scripts/enforcement/check_sync_trigger_coverage.py --fix    # print the regex to add
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

DEFAULT_HUB = Path("/opt/fabrik")

# Files only the hub has. Used to tell "a project copy" (skip, correct) apart from "the hub with a
# renamed/moved manifest" (fail loudly) — see hub_root().
_HUB_MARKERS = ("commands/_sources",)  # the corpus source dir — projects never have it.
# `templates/governance` was in this set and is too generic: `templates/` is an ordinary directory
# name, so a project that ever created `templates/governance/` would red its own Tier-2 gate with
# "looks like the hub" (review finding — currently clean fleet-wide, but a latent trap).


def hub_root(script: Path | None = None) -> Path | None:
    """The hub checkout this script belongs to, or None if this is a synced project copy.

    This script is itself fleet-synced with the rest of `scripts/enforcement/`, so it runs in
    ~48 repos that have no manifest to compare against. Naively deriving the root from
    `__file__` made a project copy read the PROJECT as if it were the hub and die on a
    FileNotFoundError, failing every project's Tier-2 gate. Pinning the root to a literal
    `/opt/fabrik` fixed that but broke the other direction: a `git worktree` of the hub (a
    documented workflow, CLAUDE.md § EXIT) lives at a different path, so the gate silently
    skipped itself exactly where hub work happens — a vacuous green.

    So: derive the candidate root from `__file__`, and accept it ONLY if the manifest is
    actually sitting in it. A hub worktree qualifies; a project copy cannot, and declines
    rather than reaching across into /opt/fabrik to report a hub gap as a project failure.
    """
    script = (script or Path(__file__)).resolve()
    if len(script.parents) > 2:
        candidate = script.parents[2]
        if (candidate / "scripts" / "fabrik_synced_manifest.py").is_file():
            return candidate
    return None


def hub_shaped_without_manifest(script: Path | None = None) -> Path | None:
    """A tree that IS the hub but has no manifest to read, or None.

    The one file whose absence should be LOUDEST is the file that decides whether to check at all:
    renaming or moving `scripts/fabrik_synced_manifest.py` turned this gate into a permanent silent
    no-op ON THE HUB, indistinguishable from a pass in `final_gate --json` (review finding,
    reproduced). A project copy carries none of these markers, so it still self-skips correctly.

    Deliberately NOT raised from `hub_root()` at import time — this module is fleet-synced, and an
    import-time raise would break every consumer instead of failing one check.
    """
    script = (script or Path(__file__)).resolve()
    if len(script.parents) <= 2:
        return None
    candidate = script.parents[2]
    if (candidate / "scripts" / "fabrik_synced_manifest.py").is_file():
        return None
    return candidate if any((candidate / m).exists() for m in _HUB_MARKERS) else None


FABRIK_ROOT = hub_root() or DEFAULT_HUB

# Synced, but deliberately NOT a sync trigger — each rides the next unrelated distribution.
# Prefixes, matched against the repo-relative path. Adding a row here is a CONSCIOUS decision
# that "editing this need not reach the fleet today"; that is exactly what the gate is asking for.
# SEEDED_NOT_ENFORCED entries are NOT re-listed here — they are read from the manifest itself.
DECLARED_NON_TRIGGERS = (
    "templates/scaffold/scripts/",  # RUN_SCRIPTS (rund/runc/…): dev conveniences, not governance
    ".windsurf/workflows/",  # workflow templates: consumed on the next sync
    # Reference docs are declared ONE BY ONE, never as a blanket `docs/reference/` prefix: the
    # filter individually names technology-stack-decision-guide.md, i.e. someone decided that
    # one SHOULD trigger — a blanket prefix would short-circuit it before the regex is ever
    # consulted, so dropping it from the filter would go undetected (the very bug class this
    # gate exists for, reproduced inside the gate's own exemption list).
    "docs/reference/kilo/",  # regenerated nightly by the kilo pipeline — a machine-written diff
    "docs/reference/MD/",  # authoring templates: consumed on the next sync
    "docs/reference/long-command-monitoring.md",
    "docs/reference/mobile-responsive-testing-guide.md",
    "docs/reference/convergence-prompts.md",
    "docs/operations/",  # lifecycle docs: read-on-demand, not enforcement
    # `libs/subagents` was listed here until 2026-09-08 (D-199). It was DEAD the moment D-196
    # retired the dir from VENDORED_DIRS — `synced_surfaces()` derives only from GOVERNANCE_DIRS
    # and VENDORED_DIRS, so the exemption could never be exercised again. Deleted rather than left
    # as harmless dead weight, because D-196/D-198 both classify the retirement REVERSIBLE
    # ("re-add the entry"): on that sanctioned undo the stale exemption would have SILENTLY
    # exempted the module from trigger coverage, so a hub edit to it would no longer be required
    # to trigger a fleet sync and this gate would still report OK. A dead entry on a documented
    # reversal path is a landmine, not dead weight.
    "libs/health_probe",  # vendored fabrik-lib health-probe (D-082): re-vendored deliberately, rides the next sync
    # AUTO-GENERATED by sync_projects.py and committed by automated chore(catalog) commits.
    # It was briefly a trigger; that made a ROBOT the thing that decides when the fleet gets a
    # distribution — and because the sync copies WORKING-TREE contents (shutil.copy2), an
    # unattended catalog regen would force-ship whatever half-finished .windsurf/rules/ or
    # scripts/enforcement/ edits a sibling agent happens to have uncommitted, to ~48 repos.
    # A deliberate rules/enforcement edit is made by an agent who knows the tree state; a
    # catalog regen is not. It rides the next such sync instead (hours, and it regenerates
    # anyway) — a far better trade than an unattended fleet push (native review finding).
    "docs/PROJECT_CATALOG.md",
)

# Every category the derivation depends on. A rename must fail loudly: a silently-dropped
# category stops being coverage-checked while the gate still reports green (review finding).
REQUIRED_MANIFEST_ATTRS = (
    "GOVERNANCE_FILES",
    "GOVERNANCE_TEMPLATES",
    "AGENT_HOOK_FILES",
    "REFERENCE_DOCS",
    "GOVERNANCE_DIRS",
    "VENDORED_DIRS",
    "CORE_SCRIPTS",
    "RUN_SCRIPTS",
    "RUN_SCRIPTS_SRC_DIR",
    "ENFORCEMENT_DIR",
    "SEEDED_NOT_ENFORCED",
)


class CoverageError(RuntimeError):
    """The gate could not read its inputs — fail loudly; a silent pass is worse than no gate."""


def trigger_pattern(config: Path, hook_id: str = "governance-sync") -> str:
    """The named hook's `files:` regex, read STRUCTURALLY from .pre-commit-config.yaml.

    Parsed as YAML and looked up BY HOOK ID. A string-scan for the id followed by the next
    `files:` line silently reads a LATER hook's filter when hooks are reordered, and returns
    the scalar indicator (`>-`) instead of the pattern when the filter is a block scalar —
    both validate coverage against the wrong regex, i.e. a false pass (review finding).
    """
    try:
        text = config.read_text(encoding="utf-8")
    except OSError as e:
        raise CoverageError(f"cannot read {config}: {e}") from e
    try:
        import yaml  # pre-commit's own dependency; present wherever this gate runs
    except ImportError:
        yaml = None  # type: ignore[assignment]
    if yaml is not None:
        try:
            data = yaml.safe_load(text) or {}
        except Exception as e:  # noqa: BLE001 — a malformed config must fail loudly, not pass
            raise CoverageError(f"cannot parse {config}: {e}") from e
        if not isinstance(data, dict):
            # `yes` / a bare list / a string all parse as VALID yaml but are not a config; the
            # .get() below would raise AttributeError, which is not a CoverageError and surfaces
            # as an unexplained crash (pool finder, reproduced).
            raise CoverageError(f"{config} does not parse to a mapping (got {type(data).__name__})")
        for repo in data.get("repos", []) or []:
            for hook in (repo or {}).get("hooks", []) or []:
                if (hook or {}).get("id") == hook_id:
                    pattern = (hook.get("files") or "").strip()
                    if not pattern:
                        raise CoverageError(f"hook {hook_id!r} has no files: filter")
                    return pattern
        raise CoverageError(f"no {hook_id!r} hook in {config}")
    # No PyYAML: scan ONLY this hook's own block, so a later hook's filter cannot be stolen.
    # Anchor on the real `- id: <hook>` LINE — a bare substring search also matches a comment
    # or another hook's `name:` that merely mentions the id, which then truncates the block at
    # the real hook and raises a spurious "no files: filter" (reproduced by the review).
    start = re.search(rf"^\s*-\s*id:\s*['\"]?{re.escape(hook_id)}['\"]?\s*$", text, re.M)
    if not start:
        raise CoverageError(f"no {hook_id!r} hook in {config}")
    block = text[start.start() :]
    nxt = re.search(r"^\s*- id:", block[start.end() - start.start() :], re.M)
    if nxt:
        block = block[: (start.end() - start.start()) + nxt.start()]
    m = re.search(r"^\s*files:\s*(.+)$", block, re.M)
    if not m:
        raise CoverageError(f"hook {hook_id!r} has no files: filter")
    return m.group(1).strip().strip("'\"")


def running_on_hub(script: Path | None = None) -> bool:
    """True where both lists live — any hub checkout, including a worktree. See `hub_root`."""
    return hub_root(script) is not None


def _manifest():
    """The hub's synced manifest module — the canonical WHAT-is-distributed list."""
    spec = importlib.util.spec_from_file_location(
        "fabrik_synced_manifest", FABRIK_ROOT / "scripts" / "fabrik_synced_manifest.py"
    )
    if spec is None or spec.loader is None:
        raise CoverageError("cannot load scripts/fabrik_synced_manifest.py")
    man = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(man)
    except OSError as e:
        raise CoverageError(f"cannot read scripts/fabrik_synced_manifest.py: {e}") from e
    return man


def synced_surfaces() -> set[str]:
    """Every repo-relative path the manifest distributes (files + directory prefixes)."""
    man = _manifest()
    missing = [a for a in REQUIRED_MANIFEST_ATTRS if not hasattr(man, a)]
    if missing:
        raise CoverageError(
            f"manifest is missing {', '.join(missing)} — renamed? A silently dropped category "
            "stops being coverage-checked while this gate still reports green"
        )

    out: set[str] = set()

    def add(value: object, prefix: str = "") -> None:
        name = value[0] if isinstance(value, tuple) else value
        if not isinstance(name, str) or not name:
            return
        # Prefix unless the entry already carries it — a future nested CORE_SCRIPTS entry
        # ("sub/tool.py") must become "scripts/sub/tool.py", not a bare, wrong path.
        out.add(name if not prefix or name.startswith(prefix) else f"{prefix}{name}")

    for attr in ("GOVERNANCE_FILES", "GOVERNANCE_TEMPLATES", "AGENT_HOOK_FILES", "REFERENCE_DOCS"):
        for item in getattr(man, attr, []) or []:
            add(item)
    # Directory entries are PREFIXES — normalise the trailing slash so the probe below
    # tests a child path against a prefix regex (a bare dir name never matches one).
    for attr in ("GOVERNANCE_DIRS", "VENDORED_DIRS"):
        for item in getattr(man, attr, []) or []:
            name = item[0] if isinstance(item, tuple) else item
            if isinstance(name, str) and name:
                out.add(name.rstrip("/") + "/")
    # CORE_SCRIPTS are bare filenames living under scripts/
    for item in getattr(man, "CORE_SCRIPTS", []) or []:
        add(item, prefix="scripts/")
    # RUN_SCRIPTS are bare filenames under the scaffold template dir
    run_dir = man.RUN_SCRIPTS_SRC_DIR
    for item in getattr(man, "RUN_SCRIPTS", []) or []:
        add(item, prefix=f"{run_dir.rstrip('/')}/")
    enf = getattr(man, "ENFORCEMENT_DIR", "scripts/enforcement")
    if enf:
        out.add(enf.rstrip("/") + "/")
    return out


def _declared(surface: str, seeded: frozenset[str] = frozenset()) -> bool:
    """True iff this surface is a declared non-trigger — either listed above, or SEEDED_NOT_ENFORCED
    in the manifest (distributed once, then owned by each project).

    Matching is EXACT or a real directory prefix: a bare prefix must not shadow a sibling
    (`libs/subagents` must not exempt `libs/subagents_new_thing.py`; review finding).
    """
    if surface in seeded:
        return True
    # ONE implementation, called — not restated. The first version of `_declared_matches` claimed
    # in its own docstring that writing this twice was the mirror defect, and then left this copy
    # in place; `_declared` never called it (caught by the closing seat).
    return any(_declared_matches(d, surface) for d in DECLARED_NON_TRIGGERS)


# Tolerates the spellings a shell author actually uses. The first version understood only
# `[ "$(pwd)" = "/opt/fabrik" ]`; `$PWD`, `[[ … == … ]]`, and `!=` all read as "no guard" and
# returned the exact false-green this caveat exists to kill (review finding).
_PWD_GUARD_RE = re.compile(r'(?:\$\(pwd\)|\$PWD|\$\{PWD\})"?\s*[!=]?==?\s*"?(/[^"\s\]]+)')


def _inert_is_unknown(inert: str) -> bool:
    """True when the caveat is an UNKNOWN rather than a proven-inert sync.

    ONE predicate, two call sites. The three-state fix originally landed on `main()`'s clean path
    only, so the FAILING path still glued an unknown to "fixing the gap here still distributes
    nothing" — asserting on no evidence the exact thing the fix was written to stop asserting, one
    branch away (round 8e). Two sites testing the same string separately is how that happened.
    """
    return "could not be determined" in inert


def sync_is_inert_here(config: Path, root: Path) -> str | None:
    """Why a commit from THIS checkout would distribute nothing, or None if the sync can fire.

    The governance-sync hook's body is a WRAPPER SCRIPT, and the `$(pwd)` guard lives in THAT
    script — `scripts/governance_sync_postcommit.sh` — not in `.pre-commit-config.yaml`. From a
    `git worktree` of the hub the guard exits 0 immediately, and `sync_enforcement_to_projects.py`
    hardcodes the same root, so even if it ran it would ship the MAIN checkout's files. Reporting
    "every synced surface triggers a sync" there is a FALSE GREEN about the very thing this gate
    exists to guarantee: an agent edits a rule in a worktree, commits, sees the tick, and zero
    repos receive it. Filter coverage is still genuinely complete, so this is a truthful caveat,
    not a failure (failing would red every worktree gate for a condition the filter cannot fix).

    ⚠️ This used to scan the WHOLE `.pre-commit-config.yaml` for any `$(pwd)` guard and attribute
    whatever it found to `governance-sync`. It was right only by coincidence — an unrelated hook
    (`command-corpus-check`) guards the same literal — and a fixture with the guard on a DIFFERENT
    hook made it emit a message NAMING governance-sync for a guard that was not its own (proven
    2026-09-08 by the independent closing pass). It now reads the wrapper the hook actually
    invokes, and says so when it cannot find one.
    """
    entry = _governance_sync_entry(config)
    if entry is None:
        # A hook with no readable `entry:` executes NOTHING. Returning None here asserted "the
        # sync CAN fire" — the most confident verdict this gate has, handed to the strongest
        # evidence of a broken hook. That is the same inversion round 8c fixed twenty lines down
        # (an unreadable wrapper), recurring one frame UP the call chain: the structural fix moved
        # the fail-open rather than closing it. `main()` branches on "could not be determined",
        # so the --force advice stays correctly suppressed.
        return (
            f"the governance-sync hook's entry: could not be read from {config} — whether a "
            f"commit from {root} fires a sync could not be determined"
        )
    script = _guard_script(entry, root)
    if script is None:
        # NOT None: an unidentifiable wrapper is an UNKNOWN, and returning None here would assert
        # "the sync can fire" on no evidence — the failure this function exists to prevent.
        return (
            "the governance-sync hook's entry names no readable wrapper script "
            f"({entry!r}) — whether a commit from {root} fires a sync could not be determined"
        )
    try:
        text = script.read_text(encoding="utf-8")
    except OSError:
        # A named wrapper that does NOT EXIST is the strongest evidence of a broken hook there is —
        # stronger than one we merely could not parse. Returning None here said "the sync can fire";
        # the weaker unknown above returned a caveat. The two fail directions were inverted relative
        # to their evidence, five lines apart (closing sweep).
        return (
            f"the governance-sync hook names a wrapper this checkout cannot read ({script}) — "
            "a commit from here fires no sync"
        )
    for m in _PWD_GUARD_RE.finditer(text):
        guarded = Path(m.group(1))
        if guarded != root:
            return (
                f"the governance-sync hook's wrapper ({script.name}) only runs when pwd is "
                f"{guarded}, but this checkout is {root} — a commit from here fires NO sync "
                "and distributes nothing"
            )
    return None


def _governance_sync_entry(config: Path) -> str | None:
    """The governance-sync hook's `entry:`, read with the YAML PARSER this file already imports.

    ⚠️ THE ROOT FIX, and the reason it is worth naming: the first three versions of this hand-rolled
    a regex over the same file that `trigger_pattern` (20 lines up) parses with `yaml.safe_load`.
    Every single entry-shape defect the review found here — a double-quoted entry, a single-quoted
    id, a folded `entry: >`, a trailing `# comment`, a missing key — is a shape the real parser
    handles for free, and each was fixed by adding one more special case to the regex, which is
    what kept generating the next one. Three closing sweeps, six findings, all of one class.

    So: parse it. The PyYAML-absent fallback mirrors `trigger_pattern`'s, scoped to this hook's own
    block, because a gate must still answer when the dependency is missing.
    """
    try:
        text = config.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        import yaml
    except ImportError:
        yaml = None  # type: ignore[assignment]
    if yaml is not None:
        try:
            data = yaml.safe_load(text) or {}
        except Exception:  # noqa: BLE001 — an unparseable config is an UNKNOWN, not a green
            return None
        if not isinstance(data, dict):
            return None
        for repo in data.get("repos", []) or []:
            for hook in (repo or {}).get("hooks", []) or []:
                if (hook or {}).get("id") == "governance-sync":
                    entry = (hook.get("entry") or "").strip()
                    return entry or None
        return None
    block = re.search(
        r"^\s*-\s*id:\s*['\"]?governance-sync['\"]?[^\S\n]*(?:#[^\n]*)?$(.*?)(?=^\s*-\s*id:|\Z)",
        text,
        re.M | re.S,
    )
    if block is None:
        return None
    entry = re.search(r"^\s*entry:\s*(.+)$", block.group(1), re.M)
    return entry.group(1).strip() if entry else None


def _guard_script(entry: str, root: Path) -> Path | None:
    """The wrapper script an `entry:` invokes, if it names one this checkout has.

    Quotes are STRIPPED per token. The first version split on whitespace and matched a bare
    `.sh` suffix, so `entry: "bash x.sh"`, `entry: 'bash x.sh'` and `bash -c '… x.sh'` all
    returned None — and None means "the sync can fire", the exact FALSE GREEN this function
    exists to kill. `.pre-commit-config.yaml` already carries a double-quoted entry, so that
    shape is live in this file today (caught by the closing seat, 5 of 9 shapes failing open).
    The sibling parser in `tests/test_exec_bits.py` strips quotes; two hand-rolled parsers in
    one change that disagreed with each other.
    """
    for raw in entry.split():
        token = raw.strip("\"'")
        if token.endswith(".sh"):
            p = Path(token)
            return p if p.is_absolute() else root / p
    return None


def _probe(path: str) -> str:
    """A concrete path to test the regex against (a directory entry needs a child)."""
    return f"{path}probe.py" if path.endswith("/") else path


def dead_declarations(seeded: frozenset[str] = frozenset()) -> list[str]:
    """Entries in ``DECLARED_NON_TRIGGERS`` that no longer match ANY real synced surface.

    The gate walks manifest → filter and asks "is this surface declared?". Nothing ever walked the
    other way, so an exemption whose subject has been retired stayed in the tuple forever, matching
    nothing and warning no one. That is not dead weight: D-196/D-198 both classify the vendored-dir
    retirement REVERSIBLE ("re-add the entry"), and on that sanctioned undo a stale exemption
    SILENTLY exempts the module from trigger coverage — a hub edit to it stops being required to
    fire a fleet sync while this gate still prints OK.

    `libs/subagents` was exactly that entry and was deleted by hand (D-199). The hand-deletion left
    the MECHANISM unbuilt, so the next retirement would recreate it; the independent closing pass
    (2026-09-08) built this. Advisory, never blocking: a dead entry misleads, it does not break a
    sync, and a gate that hard-fails on tidiness gets waived into uselessness.
    """
    # `seeded` names SURFACES, so it filters surfaces — testing the ENTRY against it (as the
    # first version did) is a different predicate that would have gone wrong the moment a caller
    # passed one. Latent, and fixed before it could be wired.
    surfaces = [s for s in synced_surfaces() if s not in seeded]
    return [e for e in DECLARED_NON_TRIGGERS if not any(_declared_matches(e, s) for s in surfaces)]


def _declared_matches(entry: str, surface: str) -> bool:
    """One entry's match, with `_declared`'s EXACT semantics — never a second implementation.

    `_declared` normalises with `rstrip("/")` and then matches exact-or-directory-prefix. Writing
    that logic twice is the mirror defect this same review fixed in `test_sync_worktree_adoption`:
    a copy cannot make a change fail. Kept as one expression so the two cannot drift; if
    `_declared` changes, this must change with it and the graders below say so.
    """
    base = entry.rstrip("/")
    return surface == base or surface.startswith(base + "/")


def uncovered(root: Path | None = None) -> list[str]:
    """Synced surfaces that neither trigger a sync nor are declared deliberate non-triggers."""
    root = root or FABRIK_ROOT
    pattern = trigger_pattern(root / ".pre-commit-config.yaml")
    surfaces = synced_surfaces()
    if not surfaces:
        # A broken/renamed manifest constant would yield nothing to check and the gate
        # would report success — the exact silent hole it exists to prevent, reproduced
        # inside the gate itself (review finding).
        raise CoverageError(
            "derived ZERO synced surfaces from the manifest — the derivation is broken "
            "(renamed constant? import failure?); refusing to report a vacuous pass"
        )
    seeded = frozenset(str(s) for s in (getattr(_manifest(), "SEEDED_NOT_ENFORCED", None) or ()))
    gaps = []
    for surface in sorted(surfaces):
        if _declared(surface, seeded):
            continue
        if re.search(pattern, _probe(surface)):
            continue
        gaps.append(surface)
    return gaps


def fix_suggestion(root: Path | None = None) -> str:
    """The regex alternatives to paste into the governance-sync files: filter."""
    parts = []
    for surface in uncovered(root):
        if surface.endswith("/"):
            parts.append("^" + re.escape(surface))
        else:
            parts.append("^" + re.escape(surface) + "$")
    return "|".join(parts)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    broken_hub = hub_shaped_without_manifest()
    if broken_hub is not None:
        print(
            f"✗ sync-trigger coverage: {broken_hub} looks like the hub "
            f"({', '.join(_HUB_MARKERS)} present) but scripts/fabrik_synced_manifest.py is "
            "missing — renamed or moved? Refusing to skip: that would silently disable this "
            "gate on the hub itself."
        )
        return 1
    if not running_on_hub():
        # This script syncs to ~48 projects with the rest of scripts/enforcement/; there is no
        # manifest there to compare against. Skip, never crash their Tier-2 gate.
        print("(not the hub — sync-trigger coverage check skipped)")
        return 0
    try:
        gaps = uncovered()
    except CoverageError as e:
        print(f"✗ sync-trigger coverage: {e}")
        return 1
    except Exception as e:  # noqa: BLE001 — a gate must never emit a bare traceback to the fleet
        print(f"✗ sync-trigger coverage: unexpected {type(e).__name__}: {e}")
        return 1
    if not gaps:
        # The reverse walk, ADVISORY and on the success path: a dead exemption never breaks a
        # sync, it just misleads — and a gate that hard-fails on tidiness gets waived. It is
        # printed HERE because the first version of this fix defined the function and called it
        # from nowhere: the only enforcement was pytest, and the hub's pytest leg is OFF by
        # design, so `final_gate --json` printed ✓ with the landmine back in place.
        try:
            _dead = dead_declarations()
        except Exception as exc:  # a gate must never emit a bare traceback to the fleet (:460)
            print(f"⚠ dead-exemption walk skipped ({type(exc).__name__}: {exc})")
            _dead = []
        for entry in _dead:
            print(
                f"⚠ dead exemption: {entry!r} in DECLARED_NON_TRIGGERS matches no synced surface "
                "— on the documented re-add path it would silently exempt that surface again"
            )
        inert = sync_is_inert_here(FABRIK_ROOT / ".pre-commit-config.yaml", FABRIK_ROOT)
        if inert:
            print("✓ sync-trigger coverage: the filter covers every synced surface")
            # THREE states, not two. "could not be determined" is not "CANNOT FIRE", and the
            # --force remediation must not be advised on an UNKNOWN: that command is the
            # unattended working-tree push D-202 removed as a hazard, so recommending it on no
            # evidence would have this gate advising the thing a sibling surface calls dangerous
            # (closing sweep — two hub surfaces giving opposite advice about one command).
            if _inert_is_unknown(inert):
                print(f"⚠ the sync's trigger could not be DETERMINED from this checkout — {inert}.")
            else:
                print(f"⚠ but the sync CANNOT FIRE from this checkout — {inert}.")
                print(
                    "  Commit from the main checkout, or run "
                    "scripts/sync_enforcement_to_projects.py --force yourself."
                )
            return 0
        print("✓ sync-trigger coverage: every synced surface triggers a sync or is declared")
        return 0
    inert = sync_is_inert_here(FABRIK_ROOT / ".pre-commit-config.yaml", FABRIK_ROOT)
    if inert:
        # Also on the FAILING path: an agent in a worktree who fixes the gap still ships nothing,
        # and without this would never be told (review finding).
        if _inert_is_unknown(inert):
            print(f"⚠ note: {inert} — whether fixing the gap here distributes anything is UNKNOWN.")
        else:
            print(f"⚠ note: {inert} — fixing the gap here still distributes nothing.")
    print("✗ sync-trigger coverage — these are DISTRIBUTED fleet-wide but editing them fires NO")
    print("  governance-sync, so a commit ships nothing and the fleet keeps the old copy:")
    for g in gaps:
        print(f"    · {g}")
    print("\n  Fix ONE of:")
    print("   (a) add to the governance-sync files: filter in .pre-commit-config.yaml —")
    print(f"       |{fix_suggestion()}")
    print("   (b) if it should ride the next unrelated sync by design, declare it in")
    print("       scripts/enforcement/check_sync_trigger_coverage.py::DECLARED_NON_TRIGGERS")
    if "--fix" in args:
        print(f"\n{fix_suggestion()}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
