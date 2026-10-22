import pytest

from tests.test_decision_panel import PANEL, _block, _full, _transcript, _user, hook, panel_mode  # noqa: F401

# expected True = passes unpaneled (operator-kept); False = refused unpaneled (panel-decided)
CASES = [
    # the label, five legitimate spellings
    ("deploy — Gate 2, operator-kept: public — a customer-facing production deploy", True),
    ("deploy — Gate 2, Operator-kept: public", True),
    ("deploy — Gate 2, **operator-kept:** public", True),
    ("deploy — Gate 2, operator kept: `public`", True),
    ("deploy — Gate 2, OPERATOR-KEPT:public", True),
    # each label token
    ("spend — operator-kept: above-ceiling", True),
    ("destructive — operator-kept: unbacked — the volume has no dump", True),
    ("credentials — operator-kept: operator-minted (a Stripe dashboard key)", True),
    ("publish — operator-kept: recurring — a monthly listing fee", True),
    # spend and irreversible are operator-kept while the ceiling is 0, label or not
    ("spend — $5 of API credits", True),
    ("spend — inside the ceiling", True),
    ("irreversible — drop and recreate the database", True),
    # prose without the label is panel-decided — negations and look-alikes included
    ("deploy — Gate 2, deploy to our own VPS, not customer-facing", False),
    ("deploy — Gate 2, a customer-facing production deploy", False),
    ("publish — publish to our own public docs site", False),
    ("destructive — no backup needed, the cache regenerates", False),
    ("credentials — the fleet mints itself, a database role", False),
    ("deploy — Gate 2 to the republic VPS", False),
    ("production data — a window that dumps first", False),
    # an unknown label token is not a label
    ("deploy — Gate 2, operator-kept: whatever", False),
    # design and plan approval never take the label
    ("design approval of docs/superpowers/specs/x-public-api-design.md, operator-kept: public", False),
    ("plan approval of docs/development/plans/x.md for a customer-facing app", False),
]


@pytest.mark.parametrize("why,kept", CASES)
def test_case(tmp_path, panel_mode, why, kept):
    tr = _transcript(tmp_path, _user("go"))
    r = hook.parse_decision_block(_block(None, ground="gate", why=why), run_live=False, transcript_path=tr)
    s = hook.parse_decision_block(_block(PANEL, ground="gate", why=why), run_live=False, transcript_path=_full(tmp_path))
    mark = "OK " if r[0] == kept else "BAD"
    print(f"\n{mark} kept={kept!s:5} unpaneled={r[0]!s:5} split={s[0]!s:5} {why[:70]!r} {'' if r[0] else r[1][:50]!r}")


def test_classless_block_names_no_class_first(tmp_path, panel_mode):
    tr = _transcript(tmp_path, _user("go"))
    r = hook.parse_decision_block(_block(None, ground="gate", why="gate — cross-repo: lands in fabrik-lib"), run_live=False, transcript_path=tr)
    print(f"\nCLASSLESS {r}")
