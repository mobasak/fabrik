#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_check_doc_links.py docs/workflows/FINAL_GATE_WORKFLOW.md
"""Link integrity for the live docs tree — every repo-path reference must resolve.

Born from the 2026-07-20 docs-truth convergence, which found 668 broken (source,
target) pairs because nothing enforced links. This gate keeps the LIVE tree at zero:

- SOURCES: tracked ``docs/**/*.md`` (excluding ``docs/archive/**`` — archived docs
  are frozen history, their internal links are exempt) plus the root navigation
  files (INDEX.md, README.md, CLAUDE.md, AGENTS.md, agents-fabrik.md,
  agents-fabrik-core.md).
- TARGETS: markdown links and bare repo-path mentions (docs/, scripts/, src/,
  specs/, configs/, templates/, .windsurf/ prefixes with doc/code extensions),
  resolved both repo-root-relative and source-file-relative.
- EXEMPT: http(s) URLs, anchors-only links, placeholder/example paths, the
  project-context allowlist (doc names that exist in scaffolded PROJECTS, cited
  from synced/orchestrator docs — they are not hub paths), and
  ``docs/reference/LOCAL_LLM_INFRASTRUCTURE.md`` as a SOURCE (operator-excluded
  from the 2026-07-20 run; waiver removed with its deferred link fixups).

Exit 0 = zero broken references; exit 1 otherwise (Tier-2 blocking).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

ROOT_SOURCES = [
    "INDEX.md",
    "README.md",
    "CLAUDE.md",
    "AGENTS.md",
    "agents-fabrik.md",
    "agents-fabrik-core.md",
]

# Doc names that live in scaffolded PROJECTS (cited from synced / orchestrator /
# workflow docs as project-side paths) — not hub files, never broken here.
PROJECT_CONTEXT_ALLOW = {
    "docs/DEPLOYMENT.md",
    "docs/OPERATIONS.md",
    "docs/RESILIENCE.md",
    "docs/data-contract.md",
    "docs/ui-design.md",
    "docs/flows.md",  # frozen journey contract (/fabrik-flows) — project-side artifact
    "docs/design-system.md",
    "docs/DATABASE_SCHEMA.md",
    "docs/FEATURES.md",  # exists hub-side too; harmless double-cover
    "docs/development/plans/00-research.md",
    "docs/preplan.md",
    "docs/multilingual-plan.md",
    "docs/reference/multilingual-plan.md",
    "docs/reference/scaffold-templates/FEATURES_TEMPLATE.md",
    "scripts/validate_i18n.py",
    "scripts/sync_rn_locales.py",  # i18n-kit adapter, scaffold-copied to projects
    "scripts/sync_docusaurus.py",  # i18n-kit adapter, scaffold-copied to projects
    "docs/lessons-learnt.md",  # legacy-tolerated project-side name (CLAUDE.md matrix)
    "docs/archive/README.md",  # scaffold-emitted per project; hub archive has none by design
    "docs/reference/opt-project-catalog.md",  # manifest DEST name in projects
    "scripts/ci_local.sh",
    "scripts/long_task.py",
    "db/schema.sql",
    "src/auth.py",
    "src/api.py",
    "src/main.py",
    "docs/FINANCIALS.md",
    "docs/API_REFERENCE.md",
    "docs/CHANGELOG.md",
    "docs/spec.md",
    "docs/user-guide/",
}

# Source files waived entirely (each with a reason + removal condition).
SOURCE_WAIVERS = {
    # Operator-excluded from the 2026-07-20 docs-truth run (live sibling WIP);
    # its :760/:762 links break transiently until the deferred fixups land.
    "docs/reference/LOCAL_LLM_INFRASTRUCTURE.md",
    # Live sibling-AI WIP spec (2026-07-20): forward-references files its own plan
    # will create. Waiver removed when that plan executes.
    "docs/superpowers/specs/2026-07-20-claude-p-first-class-scoring-design.md",
}

_PLACEHOLDER_RE = re.compile(
    r"[<>{}*]|YYYY|\bmy-api\b|\bmyservice\b|\bmy-service\b|\bmy-app\b|\bfoo\b"
    r"|example\.com|<your|\bNNN\b|\bxxx\b"
)

_LINK_RE = re.compile(r"\]\(([^)\s]+?)(?:#[^)]*)?\)")
_BARE_RE = re.compile(
    r"(?<![\w/-])((?:docs|scripts|src|specs|configs|templates|\.windsurf)/"
    r"[A-Za-z0-9_./-]+?\.(?:md|py|sh|yaml|yml|json|txt))(?![\w.-])"
)


def _is_template_source(rel: str) -> bool:
    """Scaffold templates carry INTENTIONAL placeholder refs — to a project's OWN
    future files (`src/app/...`, `docs/DATA_MODEL.md`) that don't exist until the
    template is filled in. They are not broken links; they are the whole point of a
    template. In the hub these live under ``templates/`` (not scanned) or
    ``docs/archive/`` (already skipped), but in a scaffolded PROJECT they land under
    ``docs/`` (e.g. ``docs/reference/scaffold-templates/FEATURES_TEMPLATE.md``) and
    would false-flag every project — and the check is synced, so it can't be fixed
    locally. Excluded as SOURCES by the ``*_TEMPLATE.md`` naming and the
    ``scaffold-templates/`` dir. (Reported by the /opt/seo AI: 21 of 28 "broken"
    refs were template artifacts.)"""
    name = rel.rsplit("/", 1)[-1]
    return name.endswith("_TEMPLATE.md") or "scaffold-templates/" in rel


def _tracked_md_sources() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "docs/**/*.md", "docs/*.md"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.splitlines()
    # Scope = the live KNOWLEDGE tree. Excluded as sources: all archives (frozen
    # history), the plan/epic/review/spec pipeline artifacts (they cite future
    # deliverables and pre-migration paths by design), LESSONS_LEARNT.md (a dated
    # ledger — entries cite files as they were on the entry date), and scaffold
    # TEMPLATES (intentional placeholder refs — see _is_template_source).
    skip_prefixes = (
        "docs/archive/",
        "docs/infrastructure/archive/",
        "docs/development/",
        "docs/superpowers/",
    )
    srcs = [
        p
        for p in out
        if not p.startswith(skip_prefixes)
        and p != "docs/LESSONS_LEARNT.md"
        and not _is_template_source(p)
    ]
    srcs += [p for p in ROOT_SOURCES if (REPO / p).exists()]
    # In a PROJECT, Fabrik-synced docs (gitignored, centrally distributed) are hub
    # CONTEXT, never a link-check target: their hub-relative refs cannot resolve
    # locally and cannot be fixed locally (synced-files gate forbids edits). The
    # lock records exactly what was distributed.
    lock = REPO / ".fabrik" / "synced.lock"
    if lock.exists():
        try:
            import json as _json

            synced = set(_json.loads(lock.read_text()))
            srcs = [p for p in srcs if p not in synced]
        except (ValueError, OSError):
            pass  # unreadable lock -> keep prior behavior
    return [REPO / p for p in sorted(set(srcs)) if str(Path(p)) not in SOURCE_WAIVERS]


def _iter_refs(text: str):
    """Yield (target, kind) pairs, skipping fenced code blocks for bare paths."""
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        # documented-stale convention: a line carrying the warning marker or an
        # explicit retirement note may cite a path that intentionally no longer
        # exists (Phase-D truth annotations) — skip its refs.
        if (
            "\u26a0" in line
            or "⚠" in line
            or "no longer exists" in line
            or ".deprecated" in line
            or "since removed" in line
            or "does not exist" in line
        ):
            continue
        for m in _LINK_RE.finditer(line):
            yield m.group(1), "link"
        if not in_fence:
            for m in _BARE_RE.finditer(line):
                yield m.group(1), "bare"


def _resolves(target: str, src: Path) -> bool:
    t = target.strip().strip("`")
    if not t or t.startswith(("http://", "https://", "mailto:", "#", "~")):
        return True
    if _PLACEHOLDER_RE.search(t):
        return True
    t = t.replace("%20", " ")
    norm = t.lstrip("/") if t.startswith("/") else t
    if not norm.startswith("../"):
        while norm.startswith("./"):
            norm = norm[2:]
    if norm.rstrip("/") in PROJECT_CONTEXT_ALLOW or norm in PROJECT_CONTEXT_ALLOW:
        return True
    # repo-root resolution
    if (REPO / norm).exists():
        return True
    # source-relative resolution
    cand = (src.parent / t).resolve()
    in_repo = str(cand).startswith(str(REPO) + "/")
    in_fabrik_lib = str(cand).startswith("/opt/fabrik-lib/")  # sanctioned sibling repo
    if not (in_repo or in_fabrik_lib):
        return False  # escaped to the host FS — never resolve there
    return cand.exists()


def main() -> int:
    as_json = "--json" in sys.argv
    broken: list[str] = []
    for src in _tracked_md_sources():
        try:
            text = src.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel_src = src.relative_to(REPO)
        seen: set[str] = set()
        for target, kind in _iter_refs(text):
            if target in seen:
                continue
            seen.add(target)
            # markdown links only need checking when they look like repo paths
            if kind == "link" and (
                target.startswith(("http", "#", "mailto:")) or "." not in target
            ):
                continue
            if kind == "link" and not re.search(
                r"\.(md|py|sh|yaml|yml|json|txt)$", target.split("#")[0]
            ):
                continue
            if not _resolves(target, src):
                broken.append(f"{rel_src}: broken ref -> {target}")
    if as_json:
        print(json.dumps({"status": "success" if not broken else "failure", "broken": broken}))
    else:
        for b in broken:
            print(f"ERROR: {b}")
        if not broken:
            print("check_doc_links: OK — zero broken references in the live tree")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
