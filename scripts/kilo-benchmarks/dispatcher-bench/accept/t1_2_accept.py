"""Alembic-artifact inspection for the domscan dismissal ticket (runs in the fabrik venv)."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "alembic" / "versions"
PRIOR_HEAD = "7f7d6e296bbf"  # head at ticket time
BASELINE = 13  # migration files at ticket time


def _migrations():
    out = {}
    for f in VERSIONS.glob("*.py"):
        text = f.read_text()
        rev = re.search(r"^revision(?::[^=]*)?\s*=\s*['\"]([0-9a-f]+)['\"]", text, re.M)
        down = re.search(r"^down_revision(?::[^=]*)?\s*=\s*(?:['\"]([0-9a-f]+)['\"]|None)", text, re.M)
        if rev:
            out[rev.group(1)] = {"down": down.group(1) if down and down.group(1) else None,
                                 "file": f, "text": text}
    return out


def test_exactly_one_new_migration_chained_from_head():
    migs = _migrations()
    assert len(migs) == BASELINE + 1, f"expected exactly one new migration, found {len(migs) - BASELINE}"
    downs = {m["down"] for m in migs.values()}
    heads = [r for r in migs if r not in downs]
    assert len(heads) == 1, f"multiple heads: {heads}"
    new_rev = heads[0]
    assert migs[new_rev]["down"] == PRIOR_HEAD, (
        f"new migration must chain from {PRIOR_HEAD}, chains from {migs[new_rev]['down']}"
    )


def test_migration_adds_both_columns_with_defaults():
    migs = _migrations()
    downs = {m["down"] for m in migs.values()}
    new = next(m for r, m in migs.items() if r not in downs)
    t = new["text"]
    assert "domscan_domains" in t
    assert re.search(r"add_column.*dismissed[\"']", t, re.S) or '"dismissed"' in t or "'dismissed'" in t
    assert "dismissed_at" in t
    assert re.search(r"dismissed.*server_default", t, re.S), "dismissed needs server_default false"
    assert "def downgrade" in t and "dismissed" in t.split("def downgrade")[-1]


def test_schema_sql_updated():
    sql = (ROOT / "db" / "schema.sql").read_text()
    block = sql[sql.index("domscan_domains"):]
    assert "dismissed" in block and "dismissed_at" in block
