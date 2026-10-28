"""W-7c497bab: constructing a TemplateRenderer must not write into the tree.

`__init__` used to mkdir both `templates_dir` and `output_dir`, so a test or probe that only parses a
template wrote into the tree it reads. Now `output_dir` is created only by a real (non-dry-run) render,
and `templates_dir` is never created.
"""

from __future__ import annotations

from pathlib import Path

from fabrik.spec_loader import Spec
from fabrik.template_renderer import TemplateRenderer

REPO = Path(__file__).resolve().parent.parent


def _spec() -> Spec:
    return Spec.model_validate(
        {
            "id": "demo-svc",
            "template": "node-api",
            "domain": "demo.vps1.ocoron.com",
            "resources": {"memory": "512M", "cpu": "0.5"},
        }
    )


def test_construction_creates_no_directories(tmp_path):
    # Both paths come from the constructor's own parameters.
    templates = tmp_path / "missing" / "templates"
    output = tmp_path / "missing" / "apps"
    TemplateRenderer(templates_dir=templates, output_dir=output)
    assert not templates.exists()
    assert not output.exists()


def test_real_render_still_writes_files(tmp_path):
    output = tmp_path / "fresh" / "apps"
    renderer = TemplateRenderer(templates_dir=REPO / "templates", output_dir=output)
    paths = renderer.render(_spec())
    assert (output / "demo-svc" / "compose.yaml").is_file()
    assert Path(paths["compose.yaml"]) == output / "demo-svc" / "compose.yaml"


def test_dry_run_creates_no_output_dir(tmp_path):
    output = tmp_path / "apps"
    TemplateRenderer(templates_dir=REPO / "templates", output_dir=output).render(
        _spec(), dry_run=True
    )
    assert not output.exists()
