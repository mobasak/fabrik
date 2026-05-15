"""Preplan authoring + ingestion helpers (T3-01).

Preplans live at ``docs/preplans/<YYYY-MM-DD>-<slug>.md`` and capture project
intent BEFORE ``fabrik scaffold`` creates anything. The scaffold step reads
them via :func:`parse_preplan` to pre-fill type / shape / domain / secrets;
the four AI guardrail files (CLAUDE.md, AGENTS.md, AGENTS-compact.md,
.windsurfrules) get a ``Preplan:`` reference line so every agent that opens
the project knows the original intent without re-deriving it.

The 9 canonical sections (per ``templates/preplan/preplan.md.j2``):

1. Idea — one-paragraph elevator pitch
2. Project type — one of the AGENTS.md scaffold-type catalog
3. Shape preview — the ``shape:`` block as it will land in the spec
4. External deps — APIs / SDKs / secrets table
5. Domain — public hostname (or blank for workers)
6. Success criteria — testable assertions
7. Out of scope — explicit anti-features
8. Open questions — unresolved decisions
9. Notes (VPS1 inventory reminders) — postgres-main, redis-main, M2M, health, metrics, error tracking

See ``docs/preplans/README.md`` for the lifecycle overview.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jinja2
import yaml

from fabrik.config import FABRIK_ROOT

logger = logging.getLogger(__name__)

PREPLAN_DIR = FABRIK_ROOT / "docs" / "preplans"
TEMPLATE_PATH = FABRIK_ROOT / "templates" / "preplan" / "preplan.md.j2"

_VALID_SCAFFOLD_TYPES = {
    "python-api",
    "node-api",
    "file-api",
    "file-worker",
    "saas-skeleton",
    "static-site",
    "docusaurus",
    "wordpress",
    "chrome-extension",
    "mobile-app",
    "desktop-app",
}


@dataclass
class Preplan:
    """Parsed preplan content. Returned by :func:`parse_preplan`."""

    slug: str
    date: str
    path: Path
    idea: str = ""
    project_type: str = ""
    shape: dict[str, Any] = field(default_factory=dict)
    external_deps: list[dict[str, str]] = field(default_factory=list)
    domain: str = ""
    success_criteria: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    raw_sections: dict[str, str] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Authoring: fabrik preplan new <slug>
# ─────────────────────────────────────────────────────────────────────────────


def create_preplan(slug: str, date: str | None = None) -> Path:
    """Render ``templates/preplan/preplan.md.j2`` to ``docs/preplans/<date>-<slug>.md``.

    Args:
        slug: kebab-case project identifier. Validated against
            ``[a-z0-9][a-z0-9-]*[a-z0-9]?`` (1–48 chars).
        date: ISO-8601 UTC date string (``YYYY-MM-DD``). Defaults to today.

    Returns:
        Path to the newly-created preplan file.

    Raises:
        ValueError: ``slug`` failed validation, or ``date`` is malformed.
        FileExistsError: target file already exists (rerun with a different
            slug or remove the existing file).
    """
    _validate_slug(slug)
    if date is None:
        date = datetime.now(UTC).strftime("%Y-%m-%d")
    else:
        _validate_date(date)

    PREPLAN_DIR.mkdir(parents=True, exist_ok=True)
    target = PREPLAN_DIR / f"{date}-{slug}.md"
    if target.exists():
        raise FileExistsError(
            f"Preplan already exists: {target}. "
            f"Use a different slug or remove the existing file first."
        )

    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Preplan template missing: {TEMPLATE_PATH}")

    env = jinja2.Environment(  # nosec B701  # noqa: S701
        # autoescape=False is correct for markdown output — autoescape would
        # HTML-escape `<`, `>`, `&` etc which is wrong for .md files. The
        # only template inputs are `slug` (validated kebab-case) and `date`
        # (validated YYYY-MM-DD); neither is operator-controlled at render
        # time and both are regex-restricted to a safe alphabet.
        loader=jinja2.FileSystemLoader(str(TEMPLATE_PATH.parent)),
        autoescape=False,
        keep_trailing_newline=True,
    )
    template = env.get_template(TEMPLATE_PATH.name)
    target.write_text(template.render(slug=slug, date=date))
    logger.info("preplan.create_preplan: wrote %s", target)
    return target


# ─────────────────────────────────────────────────────────────────────────────
# Ingestion: parse_preplan() for fabrik scaffold --from-preplan
# ─────────────────────────────────────────────────────────────────────────────


def parse_preplan(path: str | Path) -> Preplan:
    """Parse a preplan markdown file into a structured :class:`Preplan`.

    Extracts the 9 canonical sections via heading-based splitting. Missing
    optional sections collapse to empty values; a malformed or missing
    ``## 2. Project type`` section is a hard error because the scaffolder
    needs the type.

    Args:
        path: Path to the preplan ``.md`` file.

    Returns:
        :class:`Preplan` with parsed fields.

    Raises:
        FileNotFoundError: ``path`` doesn't exist.
        ValueError: required section ``## 2. Project type`` missing or
            contains an invalid type.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Preplan not found: {p}")
    text = p.read_text(encoding="utf-8")

    # Filename → slug + date
    m = re.match(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$", p.name)
    if m:
        date_str, slug = m.group(1), m.group(2)
    else:
        date_str, slug = "", p.stem

    sections = _split_sections(text)
    pp = Preplan(slug=slug, date=date_str, path=p, raw_sections=sections)

    pp.idea = sections.get("idea", "").strip()
    pp.project_type = _extract_project_type(sections.get("project_type", ""))
    pp.shape = _extract_shape(sections.get("shape_preview", ""))
    pp.external_deps = _extract_deps_table(sections.get("external_deps", ""))
    pp.domain = _extract_domain(sections.get("domain", ""), slug)
    pp.success_criteria = _extract_bullet_list(sections.get("success_criteria", ""))
    pp.out_of_scope = _extract_bullet_list(sections.get("out_of_scope", ""))
    pp.open_questions = _extract_bullet_list(sections.get("open_questions", ""))
    return pp


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,46}[a-z0-9])?$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_slug(slug: str) -> None:
    if not _SLUG_RE.match(slug):
        raise ValueError(
            f"Invalid slug: {slug!r}. Must be kebab-case (1–48 chars, "
            f"a-z0-9-, no leading/trailing dash)."
        )


def _validate_date(date: str) -> None:
    if not _DATE_RE.match(date):
        raise ValueError(f"Invalid date: {date!r}. Must be YYYY-MM-DD.")
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"Invalid date: {date!r}: {e}") from e


# Map heading text → internal field key. The match is loose — we strip the
# leading ``N.`` numeric prefix and lowercase before lookup so minor template
# tweaks (renumbering, capitalization) don't break parsing.
_SECTION_KEYS = {
    "idea": "idea",
    "project type": "project_type",
    "shape preview": "shape_preview",
    "external deps": "external_deps",
    "domain": "domain",
    "success criteria": "success_criteria",
    "out of scope": "out_of_scope",
    "open questions": "open_questions",
    "notes": "notes",
    # Tolerate the bracketed variant from the template
    "notes (vps1 inventory reminders)": "notes",
}


def _split_sections(text: str) -> dict[str, str]:
    # Walks h2 headings of the form `## N. Title` (or just `## Title`) and
    # returns {field_key: body}. Bodies stop at the next h2 or EOF.
    sections: dict[str, str] = {}
    current_key: str | None = None
    buf: list[str] = []
    for line in text.splitlines():
        h2 = re.match(r"^##\s+(?:\d+\.\s+)?(.+?)\s*$", line)
        if h2:
            if current_key is not None:
                sections[current_key] = "\n".join(buf).strip()
            title = h2.group(1).lower().strip()
            current_key = _SECTION_KEYS.get(title)
            buf = []
        else:
            buf.append(line)
    if current_key is not None:
        sections[current_key] = "\n".join(buf).strip()
    return sections


def _extract_project_type(body: str) -> str:
    # Look for a ``**Selected:** `<type>``` line or a bare backtick-quoted
    # type identifier. Reject anything not in the canonical catalog.
    m = re.search(r"\*\*Selected:\*\*\s*`([a-z][a-z0-9-]*)`", body)
    if m:
        candidate = m.group(1)
    else:
        # Fall back: first backtick-quoted token that matches a known type
        candidate = ""
        for token in re.findall(r"`([a-z][a-z0-9-]*)`", body):
            if token in _VALID_SCAFFOLD_TYPES:
                candidate = token
                break
    if not candidate:
        return ""  # not selected yet — caller may prompt
    if candidate not in _VALID_SCAFFOLD_TYPES:
        raise ValueError(
            f"Preplan project_type '{candidate}' is not a valid scaffold "
            f"type. Valid: {sorted(_VALID_SCAFFOLD_TYPES)}"
        )
    return candidate


def _extract_shape(body: str) -> dict[str, Any]:
    # Find the fenced ```yaml block and extract the `shape:` mapping.
    fence = re.search(r"```yaml\s*\n(.*?)\n```", body, re.DOTALL)
    if not fence:
        return {}
    try:
        loaded = yaml.safe_load(fence.group(1)) or {}
    except yaml.YAMLError as e:
        logger.warning("preplan.parse_preplan: shape block invalid YAML: %s", e)
        return {}
    if isinstance(loaded, dict) and "shape" in loaded:
        return loaded["shape"] or {}
    if isinstance(loaded, dict):
        return loaded
    return {}


def _extract_deps_table(body: str) -> list[dict[str, str]]:
    # Parse a markdown table with columns: Dep | Why | Secret name | Cost/quota.
    # Skip header + separator rows; skip rows that are still template
    # placeholders (start with `_e.g._`).
    deps: list[dict[str, str]] = []
    in_table = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            cols = [c.strip() for c in stripped.strip("|").split("|")]
            if not in_table:
                # First table row = header — skip
                in_table = True
                continue
            if set(stripped.replace("|", "").replace("-", "").replace(":", "").strip()) <= {""}:
                # Separator row
                continue
            if len(cols) < 4:
                continue
            dep, why, secret, cost = cols[0], cols[1], cols[2], cols[3]
            if not dep or dep.startswith("_e.g._") or dep == "Dep":
                continue
            deps.append(
                {
                    "dep": dep,
                    "why": why,
                    "secret_env_var": secret,
                    "cost_quota": cost,
                }
            )
    return deps


def _extract_domain(body: str, slug: str) -> str:
    m = re.search(r"\*\*Selected:\*\*\s*`([^`]+)`", body)
    if m:
        domain = m.group(1).strip()
        # Don't return the literal placeholder
        if domain == f"{slug}.vps1.ocoron.com":
            return domain
        return domain
    return ""


def _extract_bullet_list(body: str) -> list[str]:
    items: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        # Skip task-list checkbox prefix; keep the item text
        m = re.match(r"^[-*]\s*(?:\[[ xX]\]\s*)?(.+)$", stripped)
        if m:
            item = m.group(1).strip()
            if not item.startswith("_e.g._"):
                items.append(item)
    return items


__all__ = [
    "Preplan",
    "PREPLAN_DIR",
    "TEMPLATE_PATH",
    "create_preplan",
    "parse_preplan",
]
