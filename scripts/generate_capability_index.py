#!/usr/bin/env python3
"""Generate the Fabrik capability catalog — capabilities.json + docs/CAPABILITIES.md.

Self-verifying, GENERATED (never hand-curated): enumerates every invokable capability across the 9
surfaces (cli / driver / registrar / script / lib-module / scaffold / rules-pack / hook / command), verifies each by the
SAFEST probe available for that surface — CLI verbs run ``--help`` (exit 0); drivers/registrars/lib-modules
import; scaffolds/rules dir/file-check; **scripts are classified by header inspection, never executed**
(running an arbitrary script has side effects — one with no safe ``--help``/``--check`` probe is marked
``manual`` for an operator, not auto-run) — and emits a machine-readable manifest + an llms.txt-style
human/LLM catalog so a cold AI agent discovers + invokes every tool with zero onboarding.

A probe that errors is recorded ``status:"broken"`` and excluded from the usable set — never crashes the
run (fail-soft, core/58-resilience.md). If an ENTIRE surface probes broken, that's an env/generator error
and the run RAISES (the whole-surface guard) rather than emit a silently-all-broken catalog.

Usage: python scripts/generate_capability_index.py [--root <repo>]

# AFTER-EDIT: INDEX.md, docs/README.md, scripts/kilo-benchmarks/daily_refresh.sh, tests/test_generate_capability_index.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FABRIK_LIB = Path("/opt/fabrik-lib")

KINDS = (
    "cli",
    "driver",
    "registrar",
    "script",
    "lib-module",
    "scaffold",
    "rules-pack",
    "hook",
    "command",
)
_NON_MODULE_DIRS = {"docs", "docs-site", "node_modules", "scripts"}
_SCRIPT_SUBDIRS = (
    "enforcement",
    "sysadmin",
    "utils",
    "probes",
    "aro-wake",
    # ownership-coverage additions (2026-08-12): surfaces the agent-distinction
    # map must see. Still excluded on purpose: systemd (unit files, not
    # invokables), tests (internal), archive/.scratch/backups (dead).
    "kilo-benchmarks",
    "bootstrap",
    "audit",
    "credit_fetchers",
)
# Markers are DIRECTIVES at the START of a comment/docstring line (matched line-prefixed, NOT as a raw
# substring) — else this file's own marker tuples below would self-classify the generator as retired/manual.
_RETIRED_MARKERS = ("DEPRECATED", "RETIRED")
_MANUAL_MARKERS = ("CATALOG-MANUAL", "DESTRUCTIVE")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _ensure_src_path(root: Path) -> None:
    """Front-insert ``<root>/src`` on sys.path once — idempotent, so repeated build_catalog() calls
    (e.g. across the test suite) don't accumulate duplicate entries."""
    p = str(root / "src")
    if p not in sys.path:
        sys.path.insert(0, p)


def _read_head(path: Path, n: int = 4000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:n]
    except OSError:
        return ""


def _line_starts_with(head: str, markers: tuple[str, ...]) -> bool:
    """True iff some line, once its leading comment-hash/quotes are stripped, STARTS WITH a marker.

    Line-prefixed (not substring) so a script that merely *mentions* a marker in prose — or this
    generator's own `_RETIRED_MARKERS = ("DEPRECATED", …)` literal — is not misclassified.
    """
    for raw in head.splitlines():
        core = raw.strip().lstrip("#").strip().lstrip('"').strip()
        if core.startswith(markers):
            return True
    return False


def _classify_script(path: Path) -> tuple[str, str]:
    """(status, summary) for a script by header inspection — no execution (read-only)."""
    head = _read_head(path)
    summary = _first_docline(head)
    if _line_starts_with(head, _RETIRED_MARKERS):
        return "retired", summary
    if _line_starts_with(head, _MANUAL_MARKERS):
        return "manual", summary
    # A script exposes a safe probe iff it references argparse/--help/--check (parseable without side effects).
    if any(t in head for t in ("argparse", "--help", "--check", "if __name__")):
        return "ok", summary
    # No safe probe available → can't auto-verify → operator checks (not "broken": it may work fine).
    return "manual", summary


_BLOCK_SCALAR = ("|", ">", "|-", ">-", "|+", ">+")


def _first_docline(head: str) -> str:
    """First human-readable doc line — skipping shebangs, coding cookies, and a YAML front-matter block.

    Every `.windsurf/rules/**/*.md` opens with a `---` front-matter block; its ``description:`` is the
    real summary. A *proper* block (leading `---` WITH a closing `---`) is mined for ``description:`` and
    otherwise skipped so its keys never leak; a usable description falls through to the body's first
    heading. A lone leading `---` with no closing fence is treated as an ordinary horizontal rule (its
    body is still parsed) — so a markdown file that merely opens with an HR is not silently swallowed.
    """
    lines = head.splitlines()
    body_start = 0
    first = next((i for i, ln in enumerate(lines) if ln.strip()), None)
    if first is not None and lines[first].strip() == "---":
        close = next((j for j in range(first + 1, len(lines)) if lines[j].strip() == "---"), None)
        if close is not None:  # a real front-matter block (opening + closing fence)
            for ln in lines[first + 1 : close]:
                b = ln.strip()
                if b.lower().startswith("description:"):
                    val = b.split(":", 1)[1].strip().strip('"').strip("'")
                    if (
                        val and val not in _BLOCK_SCALAR
                    ):  # empty / block-scalar → fall through to heading
                        return val[:160]
            body_start = close + 1  # no usable description → parse the body after the block
        # else: no closing fence → leading `---` is just an HR; parse from the top (body_start stays 0)
    for raw in lines[body_start:]:
        bare = raw.strip()
        if not bare or bare == "---":  # blank or an HR/stray fence — never a summary
            continue
        # Skip shebang + coding cookies on the RAW line (before stripping the leading #, which would
        # otherwise hide the `#!`/`# coding:` and make it look like real doc text).
        if bare.startswith(("#!", "# -*-", "-*-")) or bare.lower().startswith(
            ("# coding:", "# vim:")
        ):
            continue
        s = bare.lstrip("#").strip().strip('"').strip("'").strip()
        if not s:
            continue
        # Skip a bare Python `import`/`from` STATEMENT (real code, not a `# import …` prose comment —
        # so a bash comment that happens to start with "import" is not dropped).
        if not bare.startswith("#") and s.startswith(("import ", "from ")):
            continue
        return s[:160]
    return ""


def _probe_help(argv: list[str], python: str = sys.executable) -> bool:
    """True iff ``<python> -m <module> <verb> --help`` exits 0. Never raises (fail-soft)."""
    try:
        r = subprocess.run(
            [python, *argv, "--help"],
            capture_output=True,
            timeout=30,
            cwd=str(REPO),
        )
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# Agent-ownership mapping (hub-agent-roles spec r2 Wiring 5; mirrors the charter beat
# tables in docs/reference/agents/ — edit together). kind-level defaults first, then
# script path-prefix overrides; anything unmatched is "unassigned" (a kaizen WARN
# signal for intel, never a crash).
_OWNER_KIND_DEFAULTS = {
    "hook": "infra",
    "command": "infra",
    "rules-pack": "infra",
    "cli": "fleet",
    "driver": "fleet",
    "registrar": "fleet",
    "scaffold": "fleet",
    "lib-module": "external:fabrik-lib",
}
_OWNER_SCRIPT_PREFIXES = (
    ("scripts/kilo-benchmarks/", "intel"),
    ("scripts/enforcement/", "infra"),
    ("scripts/sysadmin/", "infra"),
    ("scripts/utils/", "infra"),
    ("scripts/probes/", "infra"),
    ("scripts/aro-wake/", "infra"),
    ("scripts/bootstrap/", "infra"),
    ("scripts/audit/", "infra"),
    (
        "scripts/credit_fetchers/",
        "infra",
    ),  # provider-account plumbing — coupled to registry_sync + the daily_refresh chain (infra)
    ("scripts/vps_", "fleet"),  # deploy-facing exceptions, named per the plan
)


def _owner(kind: str, invoke: str) -> str:
    if kind == "script":
        # bind at the PATH TOKEN, not anywhere in the invoke: "python scripts/x.py" → the
        # scripts/… token must START WITH the prefix (a filename merely containing the
        # prefix text, or an argument echoing it, must not match — pool finder, Phase B)
        path = next((tok for tok in invoke.split() if tok.startswith("scripts/")), "")
        for prefix, who in _OWNER_SCRIPT_PREFIXES:
            if path.startswith(prefix):
                return who
        return "infra"  # remainder scripts default to the machinery beat
    return _OWNER_KIND_DEFAULTS.get(kind, "unassigned")


def _rec(
    name: str, kind: str, summary: str, invoke: str, status: str, doc_link: str | None = None
) -> dict:
    defects: list[str] = []
    if status == "broken":
        defects.append("broken")
    elif status == "retired":
        defects.append("retired")
    if doc_link is None:
        defects.append("undocumented")
    return {
        "name": name,
        "kind": kind,
        "summary": summary,
        "invoke": invoke,
        "status": status,
        "owner": _owner(kind, invoke),
        "defects": defects,
        "doc_link": doc_link,
        "verified_at": _now(),
    }


# --- per-surface enumerators (each returns list[record]; each is guarded whole-surface) ----------------


def _enum_cli(root: Path) -> list[dict]:
    try:
        _ensure_src_path(root)
        from fabrik.cli import cli  # type: ignore
    except Exception:
        # Fail-CLOSED (symmetric with _enum_drivers): a failed CLI import is an env/generator error, not
        # "0 CLI verbs". Emit a broken sentinel so the whole-surface guard RAISES rather than silently
        # dropping all 55 verbs from the catalog (Behavior 7).
        return [
            _rec(
                "fabrik (cli import failed)",
                "cli",
                "fabrik.cli failed to import",
                "python -m fabrik.cli --help",
                "broken",
                doc_link="AGENTS.md",
            )
        ]
    recs: list[dict] = []

    def walk(group, prefix: tuple[str, ...] = ()) -> None:
        for n, cmd in sorted(getattr(group, "commands", {}).items()):
            path = (*prefix, n)
            if getattr(cmd, "commands", None):
                walk(cmd, path)
            else:
                verb = " ".join(path)
                ok = _probe_help(["-m", "fabrik.cli", *path])
                recs.append(
                    _rec(
                        f"fabrik {verb}",
                        "cli",
                        (cmd.help or "").strip().split("\n")[0][:160],
                        f"python -m fabrik.cli {verb} --help",
                        "ok" if ok else "broken",
                        doc_link="AGENTS.md",
                    )
                )

    walk(cli)
    return recs


def _enum_drivers(root: Path) -> list[dict]:
    d = root / "src" / "fabrik" / "drivers"
    _ensure_src_path(root)
    recs = []
    for f in sorted(d.glob("*.py")):
        if f.stem == "__init__":
            continue
        head = _read_head(f)
        # Org retirement beats the mechanical probe (2026-08-12 — the stale-ok class: the
        # supabase driver imported fine and read "ok" a month after the platform retired it).
        if _line_starts_with(head, _RETIRED_MARKERS):
            status = "retired"
        elif _line_starts_with(head, _MANUAL_MARKERS):
            status = "manual"
        else:
            try:
                __import__(f"fabrik.drivers.{f.stem}")
                status = "ok"
            except Exception:
                status = "broken"
        recs.append(
            _rec(
                f.stem,
                "driver",
                _first_docline(_read_head(f)),
                f"from fabrik.drivers.{f.stem} import ...",
                status,
                doc_link="docs/SERVICES.md",
            )
        )
    return recs


def _enum_registrars(root: Path) -> list[dict]:
    try:
        _ensure_src_path(root)
        from fabrik.orchestrator.infrastructure import _REGISTRAR_ORDER  # type: ignore
    except Exception:
        # Fail-CLOSED (symmetric with _enum_drivers/_enum_cli): a failed import is an env error, not
        # "0 registrars" → broken sentinel so the whole-surface guard RAISES (Behavior 7).
        return [
            _rec(
                "(registrars import failed)",
                "registrar",
                "infrastructure module failed to import",
                "specs/services/<id>.yaml shape → <registrar>",
                "broken",
                doc_link="AGENTS.md",
            )
        ]
    return [
        _rec(
            r,
            "registrar",
            f"{r} registrar (auto-provisioned per spec shape)",
            f"specs/services/<id>.yaml shape → {r}",
            "ok",
            doc_link="AGENTS.md",
        )
        for r in _REGISTRAR_ORDER
    ]


def _enum_scripts(root: Path) -> list[dict]:
    s = root / "scripts"
    recs: list[dict] = []
    files: list[Path] = []
    for pat in ("*.py", "*.sh"):
        files.extend(s.glob(pat))
    for sub in _SCRIPT_SUBDIRS:
        for pat in ("*.py", "*.sh"):
            files.extend((s / sub).glob(pat))
    for f in sorted(set(files)):
        if ".archive" in f.parts:
            continue
        status, summary = _classify_script(f)
        rel = f.relative_to(root)
        recs.append(
            _rec(
                str(rel),
                "script",
                summary,
                f"python {rel}" if f.suffix == ".py" else f"bash {rel}",
                status,
                doc_link="INDEX.md",
            )
        )
    return recs


def _enum_lib_modules(root: Path) -> list[dict]:
    if not FABRIK_LIB.is_dir():
        return []
    recs = []
    for d in sorted(FABRIK_LIB.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name in _NON_MODULE_DIRS:
            continue
        readme = d / "README.md"
        has_readme = readme.exists()
        summary = _first_docline(_read_head(readme)) if has_readme else ""
        # The module exists → status:ok; a missing README is a `defects[]` item, not a status value.
        rec = _rec(
            d.name,
            "lib-module",
            summary,
            f"vendor /opt/fabrik-lib/{d.name}/",
            "ok",
            doc_link=f"/opt/fabrik-lib/{d.name}/README.md" if has_readme else None,
        )
        if not has_readme:
            rec["defects"].append("incomplete")
        recs.append(rec)
    return recs


def _enum_scaffolds(root: Path) -> list[dict]:
    try:
        _ensure_src_path(root)
        from fabrik.scaffold import SCAFFOLD_TYPES  # type: ignore

        scaffold_types = frozenset(SCAFFOLD_TYPES)
    except Exception:
        scaffold_types = frozenset()
    recs = []
    # Only registry types with a template dir are emitted — a bare templates/<helper>/ dir is
    # not an invokable capability (the old kind='script' rows with a folder-path "invoke",
    # incl. templates/.archive/, were catalog noise — 2026-08-12 fix). A registry type with
    # NO template dir (e.g. wordpress, kept in SCAFFOLD_TYPES for deploy/shape only) is
    # deliberately absent: the catalog reports disk-truth invokability.
    for d in sorted((root / "templates").glob("*/")):
        name = d.name
        if name not in scaffold_types:
            continue
        recs.append(
            _rec(
                name,
                "scaffold",
                "project scaffold",
                f"fabrik scaffold --type {name}",
                "ok",
                doc_link="docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md",
            )
        )
    return recs


def _enum_hooks(root: Path) -> list[dict]:
    """Repo-level Claude Code hooks (.claude/hooks/*.py) — the enforcement-mesh surface the
    agent-ownership map must cover (2026-08-12). Classified like scripts (markers + safe-probe
    tokens), never executed. The BOX-side mesh (~/.claude/bin) is deliberately NOT catalogued:
    it is machine-local state — regenerating on another checkout would drift the artifact —
    and `docs/workstation/hooks-index.md` is its canonical inventory."""
    recs = []
    for f in sorted((root / ".claude" / "hooks").glob("*.py")):
        status, summary = _classify_script(f)
        recs.append(
            _rec(
                f.name,
                "hook",
                summary,
                f"python3 .claude/hooks/{f.name}",
                status,
                doc_link="docs/workstation/hooks-index.md",
            )
        )
    return recs


def _enum_commands(root: Path) -> list[dict]:
    """The command corpus (commands/_sources/*.md → box-wide /<name> skills). Summary is the
    front-matter description; status is repo-deterministic — "ok" iff the source carries a
    non-empty description (no $HOME probing: the rendered-install check is the renderer's
    `--check`, not the catalog's)."""
    recs = []
    for f in sorted((root / "commands" / "_sources").glob("*.md")):
        summary = _first_docline(_read_head(f))
        recs.append(
            _rec(
                f.stem,
                "command",
                summary,
                f"/{f.stem}",
                "ok" if summary else "incomplete",
                doc_link="CLAUDE.md",
            )
        )
    return recs


def _enum_rules(root: Path) -> list[dict]:
    recs = []
    for f in sorted((root / ".windsurf" / "rules").rglob("*.md")):
        rel = f.relative_to(root)
        recs.append(
            _rec(
                str(rel.relative_to(".windsurf/rules")),
                "rules-pack",
                _first_docline(_read_head(f)),
                str(rel),
                "ok",
                doc_link=str(rel),
            )
        )
    return recs


_ENUMERATORS = {
    "cli": _enum_cli,
    "driver": _enum_drivers,
    "registrar": _enum_registrars,
    "script": _enum_scripts,
    "lib-module": _enum_lib_modules,
    "scaffold": _enum_scaffolds,
    "rules-pack": _enum_rules,
    "hook": _enum_hooks,
    "command": _enum_commands,
}


def build_catalog(root: Path = REPO) -> list[dict]:
    """Enumerate + probe all surfaces. Fail-soft per probe; RAISE if any surface is 100% broken."""
    catalog: list[dict] = []
    for kind, fn in _ENUMERATORS.items():
        recs = fn(root)
        # Whole-surface-broken guard: a whole kind coming back broken is an env/generator error.
        if recs and all(r["status"] == "broken" for r in recs):
            raise RuntimeError(
                f"whole-surface-broken: every '{kind}' entry probed broken "
                f"({len(recs)}) — likely an environment/generator error, not {len(recs)} broken tools"
            )
        catalog.extend(recs)
    return catalog


# --- emit ---------------------------------------------------------------------------------------------


def render_llms_txt(catalog: list[dict]) -> str:
    lines = [
        "# Fabrik Capability Catalog",
        "",
        "> Every invokable capability in the Fabrik repo, generated + liveness-verified. "
        "A cold AI planner/orchestrator agent reads this first to discover and invoke tools. "
        "Machine-readable form: capabilities.json.",
        "",
    ]
    by_kind: dict[str, list[dict]] = {k: [] for k in KINDS}
    for c in catalog:
        by_kind.setdefault(c["kind"], []).append(c)
    for kind in KINDS:
        items = [c for c in by_kind.get(kind, []) if c["status"] == "ok"]
        if not items:
            continue
        lines.append(f"## {kind}")
        for c in sorted(items, key=lambda x: x["name"]):
            link = _doc_link_from_docs(c["doc_link"])
            lines.append(
                f"- [{c['name']}]({link}) (owner: {c['owner']}): {c['summary'] or c['invoke']}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _doc_link_from_docs(doc_link: str | None) -> str:
    """Rewrite a REPO-ROOT-relative doc_link so it resolves from ``docs/CAPABILITIES.md``.

    The generator records targets as repo-root paths (``AGENTS.md``, ``INDEX.md``,
    ``docs/SERVICES.md``) because that is how the rest of the codebase cites them — but the
    OUTPUT lands in ``docs/``, where ``AGENTS.md`` resolves to the non-existent
    ``docs/AGENTS.md``. Measured 2026-08-25: 273 of the repo's 386 broken links were this one
    bug, 71% of the total, all in this generated file. Absolute paths and URLs pass through
    untouched.
    """
    if not doc_link:
        return "#"
    if doc_link.startswith(("/", "http://", "https://", "#", "../")):
        return doc_link
    if doc_link.startswith("docs/"):
        return doc_link[len("docs/") :]  # already inside docs/ — drop the prefix
    return f"../{doc_link}"  # repo-root file, one level up from docs/


def main(root: Path = REPO, out_dir: Path | None = None) -> int:
    out = out_dir or root
    (out / "docs").mkdir(parents=True, exist_ok=True)
    catalog = build_catalog(root)
    # seeded so the kaizen signal key EXISTS at zero — a consumer must never KeyError on a
    # healthy catalog; the stdout line below derives from THIS dict (one census, one truth)
    owners_census: dict[str, int] = {"unassigned": 0}
    for c in catalog:
        owners_census[c["owner"]] = owners_census.get(c["owner"], 0) + 1
    payload = {"generated_at": _now(), "owners": owners_census, "capabilities": catalog}
    (out / "capabilities.json").write_text(json.dumps(payload, indent=2) + "\n")
    (out / "docs" / "CAPABILITIES.md").write_text(render_llms_txt(catalog))
    (out / "llms.txt").write_text(
        "# Fabrik\n\n> Fabrik is a one-operator project-deploy hub. The full invokable-capability "
        "catalog for AI agents lives in docs/CAPABILITIES.md (+ machine-readable capabilities.json).\n\n"
        "## Capabilities\n- [Capability catalog](docs/CAPABILITIES.md): every tool, verified\n"
    )
    ok = sum(1 for c in catalog if c["status"] == "ok")
    # the unassigned count is intel's kaizen WARN signal — always reported, never a failure
    print(
        "owners: "
        + " ".join(f"{k}:{v}" for k, v in sorted(owners_census.items()) if k != "unassigned")
        + f" | unassigned: {owners_census['unassigned']}"
    )
    print(
        f"capability catalog: {len(catalog)} entries ({ok} ok, "
        f"{len(catalog) - ok} broken/retired/manual/incomplete)"
    )
    return 0


if __name__ == "__main__":
    root = REPO
    if "--root" in sys.argv:
        root = Path(sys.argv[sys.argv.index("--root") + 1])
    raise SystemExit(main(root))
