# AFTER-EDIT: scripts/mail.py | none
"""D-035 — the inter-agent message contract: 5W1H + factual WHY + SYSTEMIC mandatory
on substantive kinds (finding/request/upstream-feedback); advisory (warn, never refuse)."""
import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "fabrik_mail", Path(__file__).resolve().parent.parent / "scripts/mail.py")
mail = importlib.util.module_from_spec(_spec)
sys.modules["fabrik_mail"] = mail
_spec.loader.exec_module(mail)

FULL = """Subject: x
WHAT: the emitter drops overlays
WHERE: scripts/x.py:12
WHEN: 2026-08-30, run N
WHO: fleet owns the consumer
WHY: root cause reproduced — the regex anchors wrong (measured)
HOW: run X; fix direction: anchor it
SYSTEMIC: whole class of anchored regexes, blast radius 3 scripts
"""


def test_full_structure_has_no_gaps():
    assert mail._structure_gaps("finding", FULL) == []


def test_missing_sections_named():
    gaps = mail._structure_gaps("finding", "Subject: x\njust prose, no structure\n")
    for k in ("WHAT", "WHERE", "WHEN", "WHO", "WHY", "HOW", "SYSTEMIC"):
        assert k in gaps


def test_reply_kind_exempt():
    assert mail._structure_gaps("reply", "short ack prose") == []


def test_headers_matched_loosely():
    body = "**What:** a thing\n- where: f.py:1\nWHEN: today\nwho: me\nWhy: proven\nHow: so\nSystemic: class\n"
    assert mail._structure_gaps("request", body) == []


def test_empty_headers_and_quoted_blocks_do_not_satisfy():
    """MAJOR regression: empty 'WHY:' lines, quoted forwards ('> WHY: x') and code-fence
    templates satisfied the checker — structure without content, or someone else's."""
    empty = "WHAT:\nWHERE:\nWHEN:\nWHO:\nWHY:\nHOW:\nSYSTEMIC:\n"
    assert len(mail._structure_gaps("finding", empty)) == 7
    quoted = "\n".join(f"> {k}: real content here" for k in
                       ("WHAT", "WHERE", "WHEN", "WHO", "WHY", "HOW", "SYSTEMIC"))
    assert len(mail._structure_gaps("finding", quoted)) == 7
    fenced = "```\n" + "\n".join(f"{k}: template" for k in
                                 ("WHAT", "WHERE", "WHEN", "WHO", "WHY", "HOW", "SYSTEMIC")) + "\n```\n"
    assert len(mail._structure_gaps("finding", fenced)) == 7


# ── the two false-verdict classes, both measured live 2026-08-30 ──────────────────

QUALIFIED = """Subject: x
WHAT: the probe manufactures deaths
WHERE: scripts/sysadmin/mcp_health.py:130
WHEN: 2026-08-30
WHO: fleet
WHY (factual root cause, measured — not inferred): the budget is 8s, Claude's is 30s
HOW it bites: a compliant author is told they are non-compliant
SYSTEMIC (the class, never the instance): header-detection with a hard char budget
"""


def test_qualified_headers_are_not_false_flagged():
    """FALSE POSITIVE regression: a header may carry a qualifier.

    The contract itself invites one ("a FACTUAL root cause"), and mail.py's own
    docstring writes 'SYSTEMIC (the class, never just the instance)'. The old
    24-char budget rejected exactly those, so a fully compliant finding was told it
    was missing the sections it actually had.
    """
    assert mail._structure_gaps("finding", QUALIFIED) == []


def test_indented_example_headers_do_not_satisfy():
    """FALSE NEGATIVE regression — the worse direction, and the one that fooled me.

    A mail ABOUT the message contract quotes short example headers as evidence.
    Those are indented illustrations, not sections; counting them certified an
    unstructured mail as compliant (live: my own false-positive report passed the
    checker only because it quoted `WHY:` and `SYSTEMIC (the class):` as examples).
    """
    body = (
        "Subject: about the checker\n"
        "prose explaining the problem, with quoted examples below:\n"
        "    WHAT: example\n"
        "    WHERE: example\n"
        "    WHEN: example\n"
        "    WHO: example\n"
        "    WHY: example\n"
        "    HOW: example\n"
        "    SYSTEMIC: example\n"
    )
    assert len(mail._structure_gaps("finding", body)) == 7, (
        "indented illustrations are not section headers"
    )


def test_header_whose_body_is_a_block_on_following_lines():
    """FALSE POSITIVE #3 (live: my own duplicate-D-041 finding was flagged 'missing WHY').

    Content was required INLINE after the colon, so a section that opens with a
    command block, list or table underneath read as an empty section.
    """
    body = (
        "Subject: x\nWHAT: the thing\nWHERE: f.py:1\nWHEN: today\nWHO: fleet\n"
        "WHY (factual, reproduced):\n"
        "  $ grep -o '^| D-[0-9]*' docs/DECISIONS.md | sort | uniq -d\n"
        "  | D-041\n"
        "HOW: like so\nSYSTEMIC: the class\n"
    )
    assert mail._structure_gaps("finding", body) == []


def test_header_immediately_followed_by_another_header_is_still_empty():
    """The look-ahead must not paper over a genuinely empty section."""
    body = ("Subject: x\nWHAT: the thing\nWHERE: f.py:1\nWHEN: today\nWHO: fleet\n"
            "WHY:\nHOW: like so\nSYSTEMIC: the class\n")
    assert mail._structure_gaps("finding", body) == ["WHY"]


# ── two accidental-verdict classes, filed 2026-09-02/03 (01M1H52X, 01M1J0KY) — seen RED first ──


def test_slash_combined_header_credits_both_keys():
    """`WHEN/WHO: 2026-09-02, intel` is the form the corpus itself invites; the checker credited
    only the first key and warned 'missing: WHO' on a compliant finding (01M1H52X)."""
    body = ("WHAT: a thing\nWHERE: f.py:1\nWHEN/WHO: 2026-09-02, intel (three sessions)\n"
            "WHY: proven\nHOW: so\nSYSTEMIC: class\n")
    assert mail._structure_gaps("finding", body) == []
    # only the contract's own keys combine: an arbitrary prefix never credits the key (review, pass 1)
    garbage = body.replace("WHEN/WHO:", "abc/WHO:").replace("WHERE: f.py:1", "WHERE: f.py:1\nWHEN: today")
    assert mail._structure_gaps("finding", garbage) == ["WHO"]


def test_a_path_colon_inside_an_em_dash_header_does_not_pass_the_section():
    """`WHERE — \\`scripts/x.py:496\\`:` is NOT a `WHERE:` header; the old regex stopped at the
    `:496` colon and captured the tail as content, passing one mis-formatted section while
    flagging the six written identically (01M1J0KY)."""
    body = ("WHAT — a\nWHERE — `scripts/sync_enforcement_to_projects.py:496`:\nWHEN — today\n"
            "WHO — me\nWHY — proven\nHOW — so\nSYSTEMIC — class\n")
    assert len(mail._structure_gaps("finding", body)) == 7
