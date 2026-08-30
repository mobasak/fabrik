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
