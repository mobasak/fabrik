# AFTER-EDIT: .windsurf/rules/core/55-observability.md
"""The observability matrix in core/55-observability.md is pinned to what the scaffolder emits.

The matrix is a hand-kept restatement of the scaffolder, and it drifted twice: python-api once,
then file-api's `/metrics` read "Yes (scaffolded)" while `templates/file-api/` emitted no metrics
route at all (mail 01M3T5B3, W-a63d61a2). Each matrix row for a registered scaffold type is
scaffolded into tmp_path here, and its `/metrics` cell must agree with whether the emitted source
registers a `/metrics` route. The GlitchTip and structured-logging columns are pinned the same way
(review round 1 found four rows whose other cells still described a backend that is not emitted).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from fabrik.scaffold import SCAFFOLD_TYPES, create_project

REPO = Path(__file__).resolve().parents[1]
PACK = REPO / ".windsurf" / "rules" / "core" / "55-observability.md"
pytestmark = pytest.mark.skipif(
    os.getenv("CI") == "true", reason="scaffolds real projects; not run in CI"
)

# per column: what in the EMITTED source proves the capability. a route REGISTRATION, not a comment: `app.get('/metrics'`, FastAPI `app.mount("/metrics", …)`,
# Express `app.use('/metrics', router)`, Starlette `Mount("/metrics", …)`,
# prometheus-fastapi-instrumentator's `.expose(`, or a plain `http` handler's `path === '/metrics'`
_ROUTE_RE = re.compile(
    r"""(\.(get|route|mount|use)\(\s*["'`]/metrics["'`])|\bMount\(\s*["']/metrics["']"""
    r"""|\.expose\(|(===\s*["'`]/metrics["'`])"""
)


def _matrix() -> dict[str, dict[str, str]]:
    """{scaffold type: {column header: cell}} from the pack's matrix table."""
    lines = PACK.read_text(encoding="utf-8").splitlines()
    head = next(i for i, ln in enumerate(lines) if ln.startswith("| Scaffold |"))
    cols = [c.strip() for c in lines[head].strip("|").split("|")]
    rows = {}
    for ln in lines[head + 2 :]:
        if not ln.startswith("|"):
            break
        cells = [c.strip() for c in ln.strip("|").split("|")]
        rows[cells[0].strip("`")] = dict(
            zip(cols, cells, strict=True)
        )  # a row with a stray `|` fails loudly
    return rows


_SKIP = {".venv", "node_modules", "scripts", "libs"}
_DETECTORS = {
    "`/metrics`": _ROUTE_RE,
    "GlitchTip": re.compile(r"init_glitchtip\(|sentry_sdk\.init\(|Sentry\.init\("),
    "Structured logging": re.compile(
        r"^\s*(import structlog|from structlog|import pino|const pino)", re.M
    ),
}
ROWS = _matrix()


def _emits(project: Path, column: str) -> bool:
    for path in project.rglob("*"):
        # the project's own source only: never its .venv, node_modules, or the synced scripts/libs
        if path.suffix not in {".py", ".js", ".ts", ".mjs"} or _SKIP.intersection(path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        # a commented-out registration is not a registration
        code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith(("#", "//")))
        if _DETECTORS[column].search(code):
            return True
    return False


def _claims(scaffold: str, column: str) -> bool:
    """Whether the cell says the capability is emitted. "Yes …", "Backend …", "structlog …" and
    "pino …" do; "No", "N/A", "Per ticket" and "Client …" do not; "as `X`" reads X's cell."""
    cell = ROWS[scaffold][column].strip("* ").lower()
    alias = re.fullmatch(r"as `([a-z0-9-]+)`", cell)
    if alias:
        return _claims(alias.group(1), column)
    if cell.startswith(("yes", "backend", "structlog", "pino")):
        return True
    assert cell.startswith(("no", "n/a", "per ticket", "client", "wp ")), (
        f"unreadable {column} cell for {scaffold}: {cell!r}"
    )
    return False


@pytest.mark.parametrize("scaffold", sorted(t for t in ROWS if t in SCAFFOLD_TYPES))
def test_the_matrix_cells_match_what_the_scaffolder_emits(scaffold, tmp_path):
    try:
        create_project(name="obs-probe", project_type=scaffold, description="t", base=tmp_path)
    except NotImplementedError:  # a registered type the scaffolder refuses (wordpress)
        for column in _DETECTORS:
            assert not _claims(scaffold, column), f"{scaffold} cannot be scaffolded: {column} N/A"
        return
    wrong = [
        f"{column}: the pack says {ROWS[scaffold][column]!r}, the scaffold "
        f"{'emits' if emits else 'does not emit'} it"
        for column in _DETECTORS
        if _claims(scaffold, column) != (emits := _emits(tmp_path / "obs-probe", column))
    ]
    assert not wrong, f"55-observability.md matrix row {scaffold}: " + "; ".join(wrong)
