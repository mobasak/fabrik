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
