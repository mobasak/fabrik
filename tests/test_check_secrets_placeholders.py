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
    # Discriminates the exemption BOUNDARY: $ followed by a non-name char
    # (digit) is NOT a shell reference — must still be flagged. Also a
    # mid-string $ never engages the lookahead.
    assert _scan(tmp_path, 'password="$19.99longvalue"')
    assert _scan(tmp_path, 'password="hunter2$altyValue"')


def test_dsn_command_substitution_is_skipped(tmp_path):
    # Reciprocal half of the $-reference stance: the DSN patterns must exempt
    # $(cmd) exactly like the credential pattern does.
    assert _scan(tmp_path, "postgresql://user:$(vault_read_pw)@host:5432/db") == []
    assert _scan(tmp_path, "mongodb://user:$(op read pw)@host/db") == []


def test_dsn_real_password_still_flagged(tmp_path):
    assert _scan(tmp_path, "postgresql://user:Xk9realpw2@host:5432/db")


# ── vendor tokens this box issues (added after a LIVE MISS, 2026-08-30) ───────────
# A literal Grafana token reached a commit in scripts/sysadmin/mcp_defs.json and only
# GitHub push protection stopped it: check_secrets had no Grafana pattern. These pin
# the gap closed, and pin that the ${VAR} form the catalog uses stays clean.

def test_grafana_service_account_token_is_caught(tmp_path):
    """The exact miss: a glsa_ literal in the MCP catalog must not reach a commit."""
    f = tmp_path / "mcp_defs.json"
    f.write_text('{"env": {"GRAFANA_SERVICE_ACCOUNT_TOKEN": '
                 '"glsa_FAKEfake0123456789abcdefFAKEfake_12ab34cd"}}')
    assert cs.check_file(f), "a literal glsa_ token must be caught"


def test_openrouter_and_firecrawl_keys_are_caught(tmp_path):
    f = tmp_path / "conf.json"
    f.write_text('{"OPENROUTER_API_KEY": "sk-or-v1-' + "0123456789abcdef" * 4 + '",\n'
                 ' "FIRECRAWL_API_KEY": "fc-' + "0123456789abcdef" * 2 + '"}')
    assert len(cs.check_file(f)) >= 2, "both vendor keys must be caught"


def test_placeholder_form_of_those_keys_is_clean(tmp_path):
    """The catalog's real shape — ${VAR} references — must stay green, or the check
    is wallpaper the next author learns to ignore."""
    f = tmp_path / "mcp_defs.json"
    f.write_text('{"env": {"GRAFANA_SERVICE_ACCOUNT_TOKEN": "${GRAFANA_SERVICE_ACCOUNT_TOKEN}",'
                 ' "OPENROUTER_API_KEY": "${OPENROUTER_API_KEY}",'
                 ' "FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}"}}')
    assert cs.check_file(f) == [], "placeholders are the CORRECT form"


def test_credential_pattern_requires_matching_quotes():
    """01M1GNV1 (youtube, 2026-08-31): `PW=$(grep -E '^X_PASSWORD=' .env | cut -d= -f2-)"` on ONE
    line — a single-quoted grep pattern followed later by a double quote — matched the credential
    regex, which accepted any quote type at either end. Only a matching pair is a literal."""
    import re as _re

    mixed = "PW=$(grep -E '^PAYMENTS_SERVICE_DB_PASSWORD=' .env | cut -d= -f2-)\"\n"
    real = "password = 'hunter2hunter2'\n"
    hits_mixed = [name for pat, name in cs.SECRET_PATTERNS if _re.search(pat, mixed)]
    hits_real = [name for pat, name in cs.SECRET_PATTERNS if _re.search(pat, real)]
    assert not hits_mixed, hits_mixed
    assert hits_real, "a real quoted password must still match"
