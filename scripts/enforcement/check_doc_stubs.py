#!/usr/bin/env python3
# AFTER-EDIT: none
"""Force-fill advisory — WARN when a seeded doc is still unfilled AFTER its Doc Sync Matrix trigger
fired in the staged change: it carries a template placeholder, or it is still mostly its scaffold
template.

A freshly-scaffolded doc stub is fine — until the change that *should* have filled it ships. This
catches the stub that silently rots past the moment it became relevant: e.g. you add an API route
(QUICKSTART's trigger) but ``docs/QUICKSTART.md`` is still the pristine template.

Two signals (W-ad71f248):
- a placeholder token from ``PLACEHOLDERS`` (seeding substitutes most tokens, so this sees few docs);
- D-593's "left as its scaffold template" rule, ``fleet_doc_audit.template_verdict`` — the one
  implementation, READ from the hub and never copied here. A project carries no ``templates/``,
  so the rule is loaded from the first of ``_HUB_ROOTS`` holding both the templates and the
  script: this tree when it is the hub, else the box-local ``/opt/fabrik``. Off the box the rule
  is skipped and the output SAYS so; it never fails silently.

Design:
- The docs checked are the intersection of (a) the SSOT registry (``_doc_registry.PROJECT_DOCS``)
  and (b) the docs for which we have a *mechanical* trigger detector below — so a doc renamed or
  removed from the registry automatically drops out (no drift), and fuzzy-trigger docs
  (BUSINESS_MODEL etc., no reliable code signal) are deliberately not nudged. ``_staged`` and the
  route detector are reused from ``check_doc_sync``; the compose/env/schema filename detectors are
  local (check_doc_sync does not expose them as helpers).
- ADVISORY ONLY — always exits 0 (never blocks a project's gate). Fail-safe: ANY git / parse /
  IO / import error → exit 0 (a doc-stub nudge must never break a commit).
- Registered advisory in ``final_gate.py``.
"""

from __future__ import annotations

import functools
import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:  # same-dir siblings: check_doc_sync + _doc_registry
    sys.path.insert(0, str(_HERE))

# Placeholder sentinels a scaffolded-but-unfilled doc still carries — the FIRST signal. Deliberately
# the NAME tokens only: a date format like ``YYYY-MM-DD`` / ``[DATE]`` legitimately appears in a
# *filled* doc (e.g. data-contract documenting a DATE column), so treating dates as "unfilled"
# false-WARNs fleet-wide. Seeding substitutes ``[Project Name]`` too, so these tokens see a seeded
# doc only where seeding left one (``{PROJECT_NAME}`` cells): 16 of 174 covered docs fleet-wide on
# 2026-10-19, against 84 left as their template — hence the second signal below.
PLACEHOLDERS: tuple[str, ...] = (
    "[Project Name]",
    "[PROJECT_NAME]",
    "{PROJECT_NAME}",
)


def _has_placeholder(path: Path) -> bool:
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return False
    return any(ph in text for ph in PLACEHOLDERS)


# Where D-593's rule is read from: this tree when it is the hub (or a hub worktree), else the
# box-local hub every project sits beside — the path check_synced_unmodified/check_vps_docs use.
# A root counts only with BOTH the templates and the script, so a project tree never qualifies.
_HUB_ROOTS: tuple[Path, ...] = (_HERE.parents[1], Path("/opt/fabrik"))
_AUDIT_MODULE = "_check_doc_stubs_fleet_doc_audit"
# Every fleet_doc_audit name this check reads; tests/test_fleet_doc_audit.py pins that each exists,
# so a hub rename goes red in the hub instead of silently skipping the rule in every project.
AUDIT_NAMES: tuple[str, ...] = (
    "templated_docs",
    "template_verdict",
    "template_versions",
    "_substantive_lines",
    "template_history_complete",
    "_HISTORY_NOTE",
)


def _guarded(fn: Callable[[], Any]) -> tuple[Any, str | None]:
    """``(fn(), None)``, or ``(None, <error class>)`` when the call into hub code raises — any
    BaseException (a stray ``SystemExit`` in hub code would make this warn_only check exit
    non-zero, which final_gate fails the gate on); KeyboardInterrupt still propagates."""
    try:
        return fn(), None
    except KeyboardInterrupt:
        raise
    except BaseException as exc:
        return None, type(exc).__name__


@functools.cache
def _template_audit() -> tuple[ModuleType | None, str | None]:
    """``(fleet_doc_audit, None)`` from the first qualifying hub root, else ``(None, <reason>)``."""
    for root in _HUB_ROOTS:
        script = root / "scripts" / "fleet_doc_audit.py"
        if not ((root / "templates" / "scaffold").is_dir() and script.is_file()):
            continue

        def _load(script: Path = script) -> ModuleType:
            spec = importlib.util.spec_from_file_location(_AUDIT_MODULE, script)
            assert spec and spec.loader
            mod = importlib.util.module_from_spec(spec)
            # registered BEFORE exec: its @dataclass resolves the module through sys.modules
            sys.modules[_AUDIT_MODULE] = mod
            spec.loader.exec_module(mod)
            return mod

        mod, err = _guarded(_load)
        if err:
            sys.modules.pop(_AUDIT_MODULE, None)
            return None, f"loading {script} raised {err}"
        return mod, None
    return None, "no hub with templates/scaffold and scripts/fleet_doc_audit.py"


def _left_as_template(
    audit: ModuleType, doc: str, path: Path
) -> tuple[tuple[int, int] | None, str | None]:
    """``((pct, share), None)`` when ``doc`` is left as its scaffold template under D-593's rule —
    ``pct`` of the template still verbatim, ``share`` of the doc that is template text —
    ``(None, None)`` when it is not, ``(None, <error class>)`` when the hub code raised."""

    def _verdict() -> tuple[int, int] | None:
        template = dict(audit.templated_docs()).get(doc)
        if not template:
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
        pct = audit.template_verdict(text, template)
        if pct is None:
            return None
        lines = audit._substantive_lines(text)
        every = frozenset().union(*audit.template_versions(template))
        share = round(100 * len(lines & every) / len(lines)) if lines else 0
        return pct, share

    return _guarded(_verdict)


def _trigger_detectors() -> dict[str, object]:
    """Map registry doc name → a predicate(staged: list[str]) that is True when the doc's
    Doc-Sync trigger fired. Only docs with a *mechanical* trigger are covered (fuzzy-trigger
    docs like BUSINESS_MODEL have no reliable code signal — nudging them would be noise)."""
    import check_doc_sync as ds  # same-dir sibling (the proven Doc-Sync detectors)

    def _compose(staged: list[str]) -> bool:
        return any(Path(f).name in {"compose.yaml", "compose.yml"} for f in staged)

    def _env(staged: list[str]) -> bool:
        return any(Path(f).name in {".env.example", ".env"} for f in staged)

    def _schema(staged: list[str]) -> bool:
        return any(
            f.lower().endswith(".sql") or "migration" in f.lower() or "alembic" in f.lower()
            for f in staged
        )

    return {
        "docs/QUICKSTART.md": ds._has_route_change,
        "docs/CONFIGURATION.md": _env,
        "docs/data-contract.md": _schema,
        "docs/SERVICES.md": _compose,
        "docs/OPERATIONS.md": _compose,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Doc-stub force-fill advisory.")
    ap.add_argument(
        "--range",
        dest="rng",
        metavar="BASE..HEAD",
        help="scan a git range's CUMULATIVE diff instead of the staged diff (whole-plan receipt)",
    )
    # argv=None (bare main() call) → parse NO args (staged mode), never the host's sys.argv.
    args = ap.parse_args(argv if argv is not None else [])
    try:
        import check_doc_sync as ds

        # --range reuses check_doc_sync's own _range helper (no duplicate git plumbing). Advisory, so
        # an empty range just falls back to staged (never a false-clean concern — this never blocks).
        rng = args.rng.strip() if args.rng else ""
        staged = ds._range(rng) if rng else ds._staged()
        if not staged:
            return 0
        root = Path.cwd()
        # Intersect the mechanically-detectable docs with the SSOT registry, so a doc renamed
        # or removed from _doc_registry automatically stops being checked (no drift). Fail-open:
        # if the registry can't be imported, check all detectors (an advisory must never vanish
        # for the wrong reason, but it also must never crash — see the outer except).
        try:
            import _doc_registry  # same-dir sibling

            registry_names = {r.name for r in _doc_registry.PROJECT_DOCS}
        except Exception:  # noqa: BLE001
            registry_names = None
        lines: list[str] = []
        audit: ModuleType | None = None
        skipped: str | None = None
        raised: list[str] = []  # docs the template rule could not judge — said, never dropped
        for doc, fired in _trigger_detectors().items():
            if registry_names is not None and doc not in registry_names:
                continue  # doc left the registry SSOT → no longer checked
            try:
                if not fired(staged):  # type: ignore[operator]
                    continue
                p = root / doc
                if not p.exists():
                    continue
                if _has_placeholder(p):
                    lines.append(
                        f"⚠️  {doc}: its Doc-Sync trigger fired but it still carries template "
                        f"placeholders — fill the stub (advisory)."
                    )
                    continue
                if audit is None and skipped is None:
                    audit, skipped = _template_audit()
                if audit is None:
                    continue
                left, err = _left_as_template(audit, doc, p)
                if err:
                    raised.append(f"{doc} ({err})")
                elif left is not None:
                    pct, share = left
                    lines.append(
                        f"⚠️  {doc}: its Doc-Sync trigger fired but {pct}% of its scaffold template "
                        f"is still verbatim in it ({share}% of the doc) — fill it or drop the "
                        f"template text (advisory)."
                    )
            except Exception:  # noqa: BLE001 — one detector failing must not sink the check
                continue
        for line in lines:
            print(line)
        if skipped:
            print(f"doc-stub: template rule skipped ({skipped}) — placeholders only")
        if raised:
            print(
                f"doc-stub: template rule raised on {', '.join(raised)} — judged by placeholders only"
            )
        if audit is not None and not _guarded(audit.template_history_complete)[0]:
            note = getattr(audit, "_HISTORY_NOTE", None)
            print(f"doc-stub: {note if isinstance(note, str) else 'template history incomplete'}")
    except Exception:  # noqa: BLE001 — fail-safe: never block a gate on a doc-stub check
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
