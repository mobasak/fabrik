"""A project name must not shadow a third-party library the scaffolded project imports (W-a352701a)."""

import re
from pathlib import Path

import pytest

from fabrik import scaffold
from fabrik.scaffold import SHADOWABLE_LIBRARY_NAMES, _validate_project_name

# A requirement's distribution name where its import name differs; every other name imports as
# itself with `-` read as `_`.
_IMPORT_NAME = {"argon2-cffi": "argon2", "pillow": "PIL", "pyjwt": "jwt", "python-dotenv": "dotenv"}
_TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
# A pinned requirement inside a string literal: `name>=1`, `name[extra]>=1`, `name==1`, `name~=1`.
_PINNED = re.compile(
    r"""(?:^|\\n|["'(,])\s*([A-Za-z][A-Za-z0-9_.-]*)(?:\[[^\]\n]*\])?(?:>=|==|~=)\d""", re.M
)


@pytest.mark.parametrize(
    "name",
    ["httpx", "fastapi", "redis", "sqlalchemy", "prometheus-client", "pydantic-settings", "boto3", "packaging"],
)
def test_library_shadowing_name_refused(name):
    with pytest.raises(ValueError, match="Reserved project name") as exc:
        _validate_project_name(name)
    assert "shadow" in str(exc.value)


def test_normal_name_accepted():
    _validate_project_name("acme-crm")


def test_every_pinned_scaffold_requirement_is_a_shadowable_name():
    # The list is static; this keeps it in step with the requirements the scaffolder writes inline
    # and the ones its templates carry.
    sources = [Path(scaffold.__file__)] + sorted(_TEMPLATES.glob("**/requirements*.txt"))
    pinned: set[str] = set()
    for path in sources:
        found = {m.group(1).lower() for m in _PINNED.finditer(path.read_text(encoding="utf-8"))}
        assert found, f"the reader found no pinned requirement in {path}"
        pinned |= found
    assert len(sources) >= 2 and "fastapi" in pinned, sources
    missing = sorted(
        n for n in pinned if _IMPORT_NAME.get(n, n.replace("-", "_")) not in SHADOWABLE_LIBRARY_NAMES
    )
    assert missing == [], f"add the import names of {missing} to SHADOWABLE_LIBRARY_NAMES"
