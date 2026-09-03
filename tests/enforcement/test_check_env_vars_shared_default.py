# AFTER-EDIT: scripts/enforcement/check_env_vars.py
"""A shared DEFAULT constant is the sanctioned getenv idiom written across two lines.

wef finding 01M1MC5BBHEJJ3SYMS55NZBHAD: `DEFAULT_SEO_API_URL = "http://127.0.0.1:8016"` was
flagged although its ONLY consumer is `os.getenv("SEO_API_URL") or DEFAULT_SEO_API_URL`. The
per-line regex grades the FORM of the safe pattern, not the pattern — it cannot see a read two
hundred lines away. Sharing one default between the getenv read and the test that asserts it is
idiomatic, so the false positive recurs wherever it is done.

The exemption is narrow on purpose; these tests pin both halves — what it now allows, and every
shape it must still flag.
"""

import sys
from pathlib import Path

sys.path.insert(0, "/opt/fabrik/scripts/enforcement")
import check_env_vars as cev  # noqa: E402


def _results(tmp_path: Path, body: str, name: str = "probe.py"):
    f = tmp_path / name
    f.write_text(body)
    return cev.check_file(f)


def test_a_constant_consumed_only_as_a_getenv_default_is_exempt(tmp_path):
    """The reported shape, verbatim: the constant on its own line, the read far below."""
    body = (
        "import os\n"
        'DEFAULT_SEO_API_URL = "http://127.0.0.1:8016"\n'
        + "\n" * 20
        + 'base_url = os.getenv("SEO_API_URL") or DEFAULT_SEO_API_URL\n'
    )
    assert _results(tmp_path, body) == []


def test_the_positional_and_keyword_getenv_forms_are_exempt_too(tmp_path):
    for read in (
        'x = os.getenv("K", DEFAULT_URL)\n',
        'x = os.getenv("K", default=DEFAULT_URL)\n',
        'x = os.environ.get("K") or DEFAULT_URL\n',
        'x = os.environ.get("K", DEFAULT_URL)\n',
    ):
        body = 'DEFAULT_URL = "http://localhost:3000"\n' + read
        assert _results(tmp_path, body) == [], read


def test_the_js_env_form_is_exempt(tmp_path):
    body = 'const DEFAULT_URL = "http://localhost:3000";\nconst u = process.env.API_URL || DEFAULT_URL;\n'
    assert _results(tmp_path, body, "probe.ts") == []


# ── the teeth: every shape that must STILL flag ────────────────────────────────────────────


def test_a_constant_used_directly_still_flags(tmp_path):
    """`requests.get(DEFAULT_API_URL)` is exactly what the ban exists to catch — one direct use
    is enough, even when another use IS a getenv default."""
    body = (
        "import os, requests\n"
        'DEFAULT_API_URL = "http://localhost:9000"\n'
        'a = os.getenv("API") or DEFAULT_API_URL\n'
        "r = requests.get(DEFAULT_API_URL)\n"
    )
    assert _results(tmp_path, body), "a direct consumer must not be exempted"


def test_an_unread_constant_still_flags(tmp_path):
    """No consumer means nothing proves it is a default — an unused localhost literal is a smell."""
    body = 'DEFAULT_URL = "http://localhost:3000"\n'
    assert _results(tmp_path, body)


def test_a_lowercase_name_still_flags(tmp_path):
    """The exemption is for module CONSTANTS; a local variable is not one."""
    body = 'import os\ndefault_url = "http://localhost:3000"\nx = os.getenv("K") or default_url\n'
    assert _results(tmp_path, body)


def test_a_bare_hardcoded_url_still_flags(tmp_path):
    body = 'url = "http://localhost:3000"\n'
    assert _results(tmp_path, body)


def test_a_dsn_at_localhost_still_flags(tmp_path):
    """The HARD STOP class: DATABASE_URL pointing at localhost instead of postgres-main."""
    body = 'DSN = "postgresql://user@localhost:5432/db"\nengine = create_engine(DSN)\n'
    assert _results(tmp_path, body)
