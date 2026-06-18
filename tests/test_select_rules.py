"""Tests for scripts/select_rules.py — the plan-time rule-pack selector.

Highest-risk paths: frontmatter parsing, and glob matching that EXCLUDES noise dirs
(bundled templates/, node_modules, .venv) so a pure-Python project doesn't false-flag
the TS/Node packs as ACTIVE.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_MOD = Path(__file__).resolve().parents[1] / "scripts" / "select_rules.py"
_spec = importlib.util.spec_from_file_location("select_rules", _MOD)
sr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sr)


def _pack(d: Path, rel: str, globs: str, desc: str) -> None:
    p = d / ".windsurf" / "rules" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\nactivation: glob\nglobs: [{globs}]\ndescription: {desc}\n---\n# rule\n")


def test_parse_frontmatter() -> None:
    globs, desc = sr._parse_frontmatter('---\nglobs: ["**/*.py", "**/*.sql"]\ndescription: Py\n---\nx')
    assert globs == ["**/*.py", "**/*.sql"] and desc == "Py"


def test_active_vs_available_by_project_files(tmp_path: Path) -> None:
    _pack(tmp_path, "core/10-python.md", '"**/*.py"', "Python")
    _pack(tmp_path, "core/12-node.md", '"**/*.js"', "Node")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x=1\n")  # python file → 10-python ACTIVE
    data = sr.collect(tmp_path)
    active = {e["pack"] for e in data["active"]}
    available = {e["pack"] for e in data["available"]}
    assert "core/10-python.md" in active
    assert "core/12-node.md" in available  # no .js in the project's own source


def test_bundled_templates_do_not_false_activate(tmp_path: Path) -> None:
    # A .tsx under templates/ (bundled reference) must NOT make the Node pack ACTIVE.
    _pack(tmp_path, "core/12-node.md", '"**/*.tsx"', "Node/TS")
    tpl = tmp_path / "templates" / "saas-skeleton" / "app"
    tpl.mkdir(parents=True)
    (tpl / "page.tsx").write_text("export default 1\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("x=1\n")
    data = sr.collect(tmp_path)
    assert "core/12-node.md" in {e["pack"] for e in data["available"]}  # excluded → not active


def test_reads_project_type(tmp_path: Path) -> None:
    (tmp_path / "project.yaml").write_text("name: x\ntype: python-api\n")
    assert sr._project_type(tmp_path) == "python-api"


def test_brace_glob_expansion(tmp_path: Path) -> None:
    # `**/main.{js,ts,mjs,cjs}` must match a real main.ts (pathlib has no brace expansion).
    _pack(tmp_path, "desktop-app/72-desktop.md", '"**/main.{js,ts,mjs,cjs}"', "Electron")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.ts").write_text("app\n")
    assert "desktop-app/72-desktop.md" in {e["pack"] for e in sr.collect(tmp_path)["active"]}


def test_tightened_chrome_glob_ignores_python_background(tmp_path: Path) -> None:
    # `**/background.{js,ts}` must NOT match a python `background_worker.py`.
    _pack(tmp_path, "chrome-ext/70.md", '"**/background.{js,ts}"', "Chrome")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "background_worker.py").write_text("x=1\n")
    assert "chrome-ext/70.md" in {e["pack"] for e in sr.collect(tmp_path)["available"]}
