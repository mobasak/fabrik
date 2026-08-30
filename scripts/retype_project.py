#!/usr/bin/env python3
# AFTER-EDIT: tests/test_retype_project.py | docs/workstation/mcp-roster.md
"""Retype a project + backfill its new type's missing scaffold files — WITHOUT data loss.

Built for the 2026-08-30 type-census sweep (operator: *"update the project types and rescafold
them without causing data loss in the repos"*). The type census went wrong because
`project.yaml::type` is set once at scaffold time and never re-verified against what the repo
actually became; correcting it means the repo now owes its NEW type's required files.

WHY A DEDICATED TOOL: there is no in-place rescaffold path by design —
``scaffold.create_project`` RAISES ``ValueError("Project already exists")`` on an existing
directory, so it can never overwrite a repo (verified at scaffold.py::create_project). The only
non-destructive route is: scaffold the correct type into a THROWAWAY temp dir, then copy in ONLY
the paths the repo does not already have.

THE SAFETY CONTRACT (each one is a test):
  1. NEVER overwrites, deletes, or merges an existing path — an existing file always wins.
  2. Every skipped path is REPORTED, so a genuinely-stale file becomes a visible operator
     decision instead of a silent clobber.
  3. Refuses a git-DIRTY repo (uncommitted work is a sibling's WIP by definition, and this box
     runs concurrent sessions).
  4. DRY-RUN BY DEFAULT — `--apply` is required to write anything.
  5. Refuses an invalid target type (the registry is the authority, never a free string).

Usage:
    python3 scripts/retype_project.py --repo /opt/<name> --to <scaffold-type>           # dry run
    python3 scripts/retype_project.py --repo /opt/<name> --to <scaffold-type> --apply
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fabrik import scaffold  # noqa: E402


@dataclass
class RetypePlan:
    """What a retype WOULD do (dry-run) or DID do (apply). Reported verbatim to the operator."""

    repo: Path
    current_type: str | None
    target_type: str
    missing: list[str] = field(default_factory=list)  # files the new type owes, absent today
    present: list[str] = field(default_factory=list)  # already satisfied
    copied: list[str] = field(default_factory=list)  # actually written (apply only)
    skipped_existing: list[str] = field(default_factory=list)  # temp had it, repo already did too
    blocked: str | None = None  # why nothing was done


def _git_dirty(repo: Path) -> bool:
    """True when the repo has uncommitted changes (or git cannot answer — fail SAFE)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return True  # cannot prove clean → treat as dirty, never write
    if out.returncode != 0:
        return True
    return bool(out.stdout.strip())


def _read_type(repo: Path) -> str | None:
    """`project.yaml::type`, or None. Line-scan (no yaml dep) — the file's shape is fixed."""
    p = repo / "project.yaml"
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("type:"):
                return line.split(":", 1)[1].strip()
    except OSError:
        return None
    return None


def _set_type(repo: Path, target: str) -> bool:
    """Rewrite ONLY the `type:` line, byte-for-byte otherwise. False when no line was found."""
    p = repo / "project.yaml"
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("type:"):
            nl = "\n" if line.endswith("\n") else ""
            lines[i] = f"type: {target}{nl}"
            p.write_text("".join(lines), encoding="utf-8")
            return True
    return False


def plan_retype(repo: Path, target_type: str, *, require_clean: bool = True) -> RetypePlan:
    """Compute the retype plan. READ-ONLY — writes nothing, ever."""
    plan = RetypePlan(repo=repo, current_type=_read_type(repo), target_type=target_type)
    if target_type not in scaffold.SCAFFOLD_TYPES:
        plan.blocked = (
            f"'{target_type}' is not a registered scaffold type "
            f"({', '.join(sorted(scaffold.SCAFFOLD_TYPES))})"
        )
        return plan
    if not (repo / "project.yaml").is_file():
        plan.blocked = f"no project.yaml at {repo} — not a scaffolded project"
        return plan
    if require_clean and _git_dirty(repo):
        plan.blocked = "repo is git-DIRTY — uncommitted work is a sibling's WIP; commit or stash first"
        return plan
    present, missing = scaffold.validate_project(repo, target_type)
    plan.present, plan.missing = present, missing
    return plan


def apply_retype(plan: RetypePlan, *, scaffold_fn=None) -> RetypePlan:
    """Execute a plan: set the type, then copy ONLY missing files from a throwaway scaffold.

    `scaffold_fn(tmp_dir, name, description, project_type)` is injected for tests so the suite
    never shells out a real scaffold. Existing paths are NEVER touched — that is the contract.
    """
    if plan.blocked:
        return plan
    _set_type(plan.repo, plan.target_type)
    if not plan.missing:
        return plan  # type corrected; the repo already satisfies the new type's file set

    fn = scaffold_fn or _default_scaffold
    tmp_root = Path(tempfile.mkdtemp(prefix="retype-"))
    try:
        staging = tmp_root / plan.repo.name
        fn(staging, plan.repo.name, f"{plan.repo.name} ({plan.target_type})", plan.target_type)
        for rel in plan.missing:
            src = staging / rel
            if not src.exists():
                continue  # the scaffolder did not emit it — report by omission, never invent
            dst = plan.repo / rel
            if dst.exists():
                # belt-and-braces: re-check at write time, not just at plan time
                plan.skipped_existing.append(rel)
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            plan.copied.append(rel)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    return plan


def _default_scaffold(dest: Path, name: str, description: str, project_type: str) -> None:
    """Real scaffold into a throwaway dir (never the repo)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    scaffold.create_project(
        name=name, description=description, base=dest.parent, project_type=project_type,
        generate_spec=False,
    )


def _render(plan: RetypePlan, applied: bool) -> str:
    head = f"{plan.repo.name}: {plan.current_type} -> {plan.target_type}"
    if plan.blocked:
        return f"BLOCKED  {head}\n         {plan.blocked}"
    lines = [f"{'APPLIED ' if applied else 'DRY-RUN '} {head}"]
    lines.append(f"         satisfied already: {len(plan.present)}")
    lines.append(f"         missing for new type: {len(plan.missing)}" + (f" — {', '.join(plan.missing)}" if plan.missing else ""))
    if applied:
        lines.append(f"         copied: {len(plan.copied)}" + (f" — {', '.join(plan.copied)}" if plan.copied else ""))
        if plan.skipped_existing:
            lines.append(f"         SKIPPED (already present, never overwritten): {', '.join(plan.skipped_existing)}")
    return "\n".join(lines)


def _main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Retype a project + backfill missing scaffold files")
    p.add_argument("--repo", required=True, type=Path)
    p.add_argument("--to", required=True, dest="target")
    p.add_argument("--apply", action="store_true", help="write (default is a dry run)")
    p.add_argument("--allow-dirty", action="store_true", help="override the git-clean guard")
    a = p.parse_args(argv)

    plan = plan_retype(a.repo, a.target, require_clean=not a.allow_dirty)
    if a.apply and not plan.blocked:
        plan = apply_retype(plan)
    print(_render(plan, applied=a.apply and not plan.blocked))
    return 1 if plan.blocked else 0


if __name__ == "__main__":  # pragma: no cover — CLI entry
    raise SystemExit(_main())
