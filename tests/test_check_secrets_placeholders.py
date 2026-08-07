"""Regression: doc placeholders (your-key-here, <token>, changeme…) are not real secrets and must
not trip check_secrets — while real credentials still are flagged."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "enforcement"))
import check_secrets as cs  # noqa: E402


def _scan(tmp_path, text):
    p = tmp_path / "doc.md"
    p.write_text(text)
    return [r.message for r in cs.check_file(p)]


def test_placeholders_are_skipped(tmp_path):
    for v in [
        'API_KEY="your-key-here"',
        'api_key="changeme"',
        'token="<your-token>"',
        'secret="{{VAULT_SECRET}}"',
        'password="xxxxxxxx"',
        'api_key="placeholder"',
    ]:
        assert _scan(tmp_path, v) == [], v


def test_real_credentials_still_flagged(tmp_path):
    for v in ['api_key="hunter2RealPassw0rd"', 'password="s3cr3tP@ssvalue"']:
        assert _scan(tmp_path, v), f"MISSED real secret: {v}"


def test_real_provider_keys_still_flagged(tmp_path):
    assert _scan(tmp_path, 'k = "sk-ant-' + "a" * 40 + '"')


def test_example_dsn_credentials_are_skipped(tmp_path):
    # Backtick-wrapped connection-string EXAMPLES in reference docs — placeholder creds.
    for v in [
        "Connection String: `postgresql://user:pass@host:port/db`",
        "URI: `postgresql://user:password@host:5432/db`",
        "`mongodb://user:pwd@host:27017/db`",
        "`mongodb+srv://user:password@cluster/db`",
    ]:
        assert _scan(tmp_path, v) == [], v


def test_real_dsn_password_still_flagged(tmp_path):
    for v in [
        "url = `postgresql://admin:Xk9d2RealPw@host:5432/db`",
        "`mongodb://root:s3cr3tValue@host:27017/db`",
    ]:
        assert _scan(tmp_path, v), f"MISSED real DSN secret: {v}"


def test_bare_shell_variable_reference_is_skipped(tmp_path):
    # Live false-positive 2026-08-07: RESTIC_PASSWORD="$RESTIC_PW" (a sibling's
    # sysadmin script) — a bare $VAR reference is an expansion, not a hardcoded
    # secret, exactly like the ${VAR} and $(cmd) forms already exempted.
    for v in [
        'RESTIC_PASSWORD="$RESTIC_PW"',
        'password="$PGPASS"',
        'secret="${VAULT_TOKEN}"',
        'token="$(cat /run/secret)"',
    ]:
        assert _scan(tmp_path, v) == [], v


def test_dollar_prefixed_but_literal_password_still_flagged(tmp_path):
    # A literal secret merely CONTAINING dollar signs later is still caught.
    assert _scan(tmp_path, 'password="hunter2$altyValue"')
