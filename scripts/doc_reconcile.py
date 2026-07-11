#!/usr/bin/env python3
# AFTER-EDIT: none
"""Tier-1 doc reconcile — cheap-pool author → verify → converge, per fired Doc-Sync trigger.

For each registry doc whose mechanical Doc-Sync trigger fired in a change, dispatch ONE cheap
OpenRouter-pool author (``libs.subagents``) to emit a minimal structured edit that re-aligns the
doc with the code, VERIFY the emitted patch before applying it (default: a deterministic symbol
cross-check — every backtick identifier the patch adds must exist somewhere in the codebase, so an
invented endpoint/symbol is caught for free), apply on pass / re-author on drift, and loop until a
zero-edit md5 round (converged) or ``max_rounds``.

Design invariants (mirrors the plan + ``62-using-subagents``):
- **Registry-driven** — the doc set + triggers come from ``_doc_registry.PROJECT_DOCS`` via the
  proven ``check_doc_stubs._trigger_detectors`` mapping (no second doc list, no reinvented detector).
- **Verify-before-apply** — the pool patch is NEVER applied blind; ``verify_fn`` gates it. The DEFAULT
  is a mechanical symbol check (a standalone script cannot dispatch a native Claude Task); the
  higher-assurance native-Claude verify is injected by the orchestrating AI (``/fabrik-execute-plan``).
- **Flywheel** — every pool author is recorded via ``record_agent_run`` (NOT ``record_run``).
- **Never blocks** — any git / import / parse error degrades to a no-op; a doc-nuisance never breaks a
  gate. A project without the pool vendored (``ImportError``) no-ops gracefully.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent  # scripts/
_ROOT = _HERE.parent  # repo root
_ENF = _HERE / "enforcement"
for _p in (str(_ROOT), str(_ENF)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:  # the pool is vendored in fabrik + every scaffolded project; guard for the not-yet-vendored case
    from libs.subagents import AgentSpec, pick_models, record_agent_run, run_agents
except Exception:  # noqa: BLE001 — no pool → graceful no-op (the mechanical gates still run)
    AgentSpec = None  # type: ignore[assignment,misc]
    pick_models = None  # type: ignore[assignment]
    record_agent_run = None  # type: ignore[assignment]
    run_agents = None  # type: ignore[assignment]

# Text extensions the mechanical symbol-check scans when proving a patch's identifiers are real.
_TEXT_EXT = {
    ".py",
    ".md",
    ".yaml",
    ".yml",
    ".json",
    ".txt",
    ".toml",
    ".cfg",
    ".ini",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".sh",
    ".sql",
    ".html",
    ".css",
    ".example",
}
# Extensionless text files whose contents can legitimately define a referenced symbol.
_TEXT_NAMES = {"Makefile", "Dockerfile", "Procfile", "Justfile", "Caddyfile"}
_SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache"}
_GIT_TIMEOUT = (
    60  # seconds — bound every git call so a hung repo degrades instead of stalling a gate
)

VerifyFn = Callable[[str, object, "Path | str"], bool]


@dataclass
class ReconcileResult:
    """Outcome of reconciling ONE doc: status ∈ {applied, noop, drift, skipped, degraded}."""

    doc: str
    status: str
    applied: bool
    model: str | None = None


def fired_docs(diff_files: list[str]) -> list[object]:
    """Registry docs whose mechanical Doc-Sync trigger fired in ``diff_files``.

    Reuses ``check_doc_stubs._trigger_detectors`` (the 5 mechanically-detectable docs) intersected
    with the SSOT registry — a doc removed from ``_doc_registry`` automatically stops firing.
    """
    try:
        import _doc_registry  # same-dir sibling
        import check_doc_stubs as cds

        detectors = cds._trigger_detectors()
        out: list[object] = []
        files = list(diff_files)
        for row in _doc_registry.PROJECT_DOCS:
            det = detectors.get(row.name)
            if det is None:
                continue
            try:
                if det(files):  # type: ignore[operator]
                    out.append(row)
            except Exception:  # noqa: BLE001 — one detector failing must not sink the rest
                continue
        return out
    except Exception:  # noqa: BLE001 — registry/detector import failed → nothing fired (fail-safe)
        return []


def _added_lines(patch: str) -> str:
    return "\n".join(
        line[1:]
        for line in patch.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )


def _extract_tokens(added_text: str) -> set[str]:
    """Backtick-quoted code identifiers (≥3 chars) the patch introduces — the things to prove real."""
    toks: set[str] = set()
    for span in re.findall(r"`([^`]+)`", added_text):
        for ident in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", span):
            toks.add(ident)
    return toks


def _codebase_haystack(root: Path | str) -> str:
    parts: list[str] = []
    try:
        for p in Path(root).rglob("*"):
            if not p.is_file():
                continue
            if any(seg in _SKIP_DIRS for seg in p.parts):
                continue
            if p.suffix.lower() not in _TEXT_EXT and p.name not in _TEXT_NAMES:
                continue
            try:
                if p.stat().st_size > 1_000_000:
                    continue
                parts.append(p.read_text(errors="ignore"))
            except OSError:
                continue
    except OSError:
        pass
    return "\n".join(parts)


def _default_verify(patch: str, doc: object, root: Path | str) -> bool:
    """Mechanical symbol cross-check: every backtick identifier the patch ADDS must appear somewhere
    in the codebase — an identifier present nowhere is an invented endpoint/symbol → drift (reject).
    Fail-open: any error → True (a verify glitch must never block doc maintenance)."""
    try:
        toks = _extract_tokens(_added_lines(patch))
        if not toks:
            return True
        hay = _codebase_haystack(root)
        # word-boundary match (not raw substring) so an invented `Spec` is NOT satisfied by a real
        # `AgentSpec` — the token must appear as a whole identifier somewhere in the codebase.
        return all(re.search(r"\b" + re.escape(t) + r"\b", hay) for t in toks)
    except Exception:  # noqa: BLE001
        return True


def _patch_targets_only(patch: str, name: str, root: Path | str) -> bool:
    """True iff every file the patch modifies is exactly ``name``.

    Uses git's OWN patch parser (``git apply --numstat``) rather than regex header-scraping, so a
    ``b/``-less header, a rename/copy-only diff, or an extra file cannot slip a foreign-path change
    past the scope guard. Fail-CLOSED: an unparseable patch, a rename/copy, an empty file list, or
    any error → reject (a scope guard must never fail open).

    Assumes ``patch`` is git-format (``a/``/``b/`` prefixes) — which the pool guarantees, as
    ``result.diff`` comes from ``libs/subagents/workspace.worktree_diff`` = ``git diff --cached``.
    A prefix-less plain unified diff would numstat under ``-p1`` to a stripped path and be
    conservatively rejected (safe: drift → re-author, never a misapply)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "apply", "--numstat", "-"],
            input=patch,
            text=True,
            capture_output=True,
            timeout=_GIT_TIMEOUT,
        )
        if out.returncode != 0:
            return False  # git cannot even parse/stat the patch → do not apply
        paths: list[str] = []
        for line in out.stdout.splitlines():
            cols = line.split("\t")
            if len(cols) >= 3:
                p = cols[2].strip()
                if " => " in p or "{" in p:  # a rename/copy numstat form touches two paths → reject
                    return False
                paths.append(p)
        return bool(paths) and all(p == name for p in paths)
    except Exception:  # noqa: BLE001 — a scope guard fails CLOSED (reject), never open
        return False


def _apply_patch(patch: str, root: Path | str) -> None:
    subprocess.run(
        ["git", "-C", str(root), "apply", "--recount", "--"],
        input=patch,
        text=True,
        capture_output=True,
        check=True,
        timeout=_GIT_TIMEOUT,
    )


def _docset_md5(docs: list[object], root: Path | str) -> str:
    h = hashlib.md5()  # noqa: S324 — non-crypto change-detection only
    for d in sorted(docs, key=lambda r: getattr(r, "name", "")):
        p = Path(root) / getattr(d, "name", "")
        try:
            h.update(p.read_bytes())
        except OSError:
            h.update(b"")
    return h.hexdigest()


_PROMPT = """You maintain project documentation. A code change fired the Doc-Sync trigger for ONE doc.
Update that doc so it truthfully matches the code — nothing more.

Doc: {name}  (its role: {fills})

--- CODE CHANGE (unified diff) ---
{diff}

--- CURRENT DOC CONTENTS ---
{current}

--- INSTRUCTION ---
Edit {name} with the SMALLEST possible change (a targeted find/replace / section patch) so it matches
the code above. NEVER rewrite the whole doc. Only reference symbols, endpoints, flags, and names that
actually exist in the code change. If the doc is already correct, make no edit."""


def _build_prompt(doc: object, diff_text: str, current: str) -> str:
    return _PROMPT.format(
        name=getattr(doc, "name", "the doc"),
        fills=getattr(doc, "fills", ""),
        diff=diff_text[:8000],
        current=current[:8000],
    )


def _quality(status: str) -> float:
    """Automated flywheel signal: did the model produce an applicable, verified doc patch?"""
    return {"applied": 4.0, "noop": 3.0, "drift": 1.0}.get(status, 0.0)


def reconcile_doc(
    doc: object,
    diff_text: str,
    root: Path | str,
    verify_fn: VerifyFn | None = None,
) -> ReconcileResult:
    """Dispatch one pool author for ``doc``, verify its patch, apply on pass / mark drift on fail.

    ``verify_fn`` defaults to the mechanical symbol check; the orchestrator injects a native-Claude
    verify for the higher-assurance pass. Records one flywheel row per dispatch. Never raises.
    """
    if verify_fn is None:
        verify_fn = _default_verify
    name = getattr(doc, "name", "")
    if run_agents is None or AgentSpec is None or pick_models is None:
        return ReconcileResult(name, "skipped", False)
    try:
        models = pick_models("docs", n=1)
        if not models:
            return ReconcileResult(name, "degraded", False)
        model = models[0]
        docp = Path(root) / name
        current = docp.read_text(errors="ignore") if docp.exists() else ""
        spec = AgentSpec(
            task=_build_prompt(doc, diff_text, current),
            model=model,
            task_type="docs",
            tools_enabled=True,
            owned_paths=[name],
            max_turns=8,
            max_cost_usd=0.20,
            wall_clock_s=420.0,
        )
        results = run_agents([spec], repo=str(root))
        result = results[0] if results else None
        status, applied = "noop", False
        # The apply is its own try so that a failed git apply / verify does NOT skip the flywheel
        # record below — the pool did the (paid) work regardless of whether the patch landed.
        try:
            if result is None:
                status = (
                    "degraded"  # the pool returned nothing → a failed dispatch, not a real no-op
                )
            else:
                patch = getattr(result, "diff", "") or ""
                rstatus = getattr(result, "status", "")
                if patch.strip():
                    if rstatus not in ("done", "capped"):
                        # "error"/"out_of_scope" runs may carry a diff that is NOT scope-guarded
                        # (libs/subagents/agent.py:348 only scope-checks "done"/"capped") → never apply.
                        status = "drift"
                    elif not _patch_targets_only(patch, name, root):
                        status = "drift"  # touched a path it did not own → reject
                    elif verify_fn(patch, doc, root):
                        _apply_patch(patch, root)
                        status, applied = "applied", True
                    else:
                        status = "drift"
                else:
                    # An empty diff is a genuine no-op ONLY from a clean "done" run (doc already
                    # matches). An empty diff from any other status = a failed/incomplete dispatch →
                    # "degraded", so a persistently-failing pool never masquerades as converged.
                    status = "noop" if rstatus == "done" else "degraded"
        except Exception:  # noqa: BLE001 — apply/verify failure → degraded, but still record
            status, applied = "degraded", False
        if record_agent_run is not None and result is not None:
            try:
                record_agent_run(
                    spec, result, quality_score=_quality(status), project="doc-reconcile"
                )
            except Exception:  # noqa: BLE001 — recording must never break reconcile
                pass
        return ReconcileResult(name, status, applied, model=model)
    except Exception:  # noqa: BLE001 — never block on a single doc
        return ReconcileResult(name, "degraded", False)


def reconcile_loop(
    docs: list[object],
    diff_text: str,
    root: Path | str,
    verify_fn: VerifyFn | None = None,
    max_rounds: int = 3,
) -> dict:
    """Author→verify→re-author each fired doc until a zero-edit md5 round (converged) or max_rounds.

    Docs are parallel-safe (disjoint ``owned_paths``, one per doc). Never raises → degraded on error.
    """
    try:
        docs = list(docs)
        results: dict[str, ReconcileResult] = {}
        if not docs:
            return {"status": "converged", "rounds": 0, "docs": {}}
        rounds = 0
        for rnd in range(max_rounds):
            rounds = rnd + 1
            before = _docset_md5(docs, root)
            round_status: list[str] = []
            for doc in docs:
                name = getattr(doc, "name", "")
                try:
                    rr = reconcile_doc(doc, diff_text, root, verify_fn)
                except Exception:  # noqa: BLE001
                    rr = ReconcileResult(name, "degraded", False)
                round_status.append(rr.status)
                prev = results.get(name)
                # Keep the "applied" outcome sticky: once a doc was patched on disk, a LATER round's
                # noop (the doc now matches → empty diff) must not overwrite it to applied=False,
                # or main()'s "N doc(s) updated" tally would under-count every doc it actually fixed.
                if not (prev is not None and prev.applied and not rr.applied):
                    results[name] = rr
            after = _docset_md5(docs, root)
            # Converge ONLY when the round made no edits AND nothing is unresolved. Both "drift"
            # (patch failed verify → not applied) and "degraded" (apply error / timeout / failed
            # dispatch) leave md5 unchanged while the doc is still stale — keep re-authoring, don't
            # call it done. "noop"/"applied"/"skipped" are the resolved outcomes that may converge.
            unresolved = {"drift", "degraded"}
            if before == after and not any(s in unresolved for s in round_status):
                return {"status": "converged", "rounds": rounds, "docs": results}
        return {"status": "max_rounds", "rounds": rounds, "docs": results}
    except Exception:  # noqa: BLE001 — fail-safe: never raise into a caller/gate
        return {"status": "degraded", "rounds": 0, "docs": {}}


def _git_out(root: Path | str, args: list[str]) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, timeout=_GIT_TIMEOUT
    ).stdout


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Tier-1 doc reconcile (pool author → verify → converge)."
    )
    ap.add_argument(
        "--range", dest="rng", help="git range, e.g. <base>..HEAD (default: staged diff)"
    )
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    args = ap.parse_args(argv)
    try:
        root = Path(args.root).resolve()
        if args.rng:
            files = [
                f
                for f in _git_out(root, ["diff", args.rng, "--name-only"]).splitlines()
                if f.strip()
            ]
            diff = _git_out(root, ["diff", args.rng])
        else:
            files = [
                f
                for f in _git_out(root, ["diff", "--cached", "--name-only"]).splitlines()
                if f.strip()
            ]
            diff = _git_out(root, ["diff", "--cached"])
        docs = fired_docs(files)
        if not docs:
            print("doc-reconcile: no fired-trigger docs in range")
            return 0
        out = reconcile_loop(docs, diff, root)
        updated = sum(1 for r in out["docs"].values() if r.applied)
        print(
            f"doc-reconcile: {out['status']} in {out['rounds']} round(s); {updated} doc(s) updated"
        )
    except Exception as e:  # noqa: BLE001 — never block a gate/commit
        print(f"doc-reconcile: degraded ({e})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
