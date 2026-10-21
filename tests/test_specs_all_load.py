"""Every YAML under specs/ is an appliable Spec, unless it sits in a directory of another schema.

D-1097 retired specs/infrastructure/: seven files that loaded nowhere and had drifted from the
compose mirrors under infra/vps1/. This guard keeps a non-appliable spec from reappearing.
Cheapest way to pass it without the outcome: put a broken Spec into an exempt directory, or
exempt a new one — the exemptions are three literal directories, and the second test refuses one
that covers specs/services/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fabrik.spec_loader import load_spec

SPECS = Path(__file__).resolve().parent.parent / "specs"

# Each directory holds another schema (or retired files), so a file there is not a Spec.
EXEMPT_DIRS = {
    ".archive": "retired specs, kept as history",
    "verification": "postconditions schema read by tests/contracts/test_deploy_postconditions.py",
    "sites": "WordPress site specs (docs/DEPLOYMENT_ARCHITECTURE.md § 3.3)",
}


def _spec_files() -> list[Path]:
    return sorted(
        p
        for p in SPECS.rglob("*")
        if p.suffix in (".yaml", ".yml")
        and p.is_file()
        and p.relative_to(SPECS).parts[0] not in EXEMPT_DIRS
    )


@pytest.mark.parametrize("path", _spec_files(), ids=lambda p: str(p.relative_to(SPECS)))
def test_every_spec_outside_the_exemptions_loads(path: Path) -> None:
    load_spec(path)


def test_exemptions_exist_and_never_cover_services() -> None:
    for name in EXEMPT_DIRS:
        assert (SPECS / name).is_dir(), f"stale exemption: specs/{name}/ does not exist"
        assert not "services".startswith(name), f"specs/{name}/ would exempt specs/services/"
    assert any(p.parent.name == "services" for p in _spec_files()), "no specs/services/*.yaml reached the guard"
