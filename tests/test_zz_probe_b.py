import pytest
from tests.test_decision_panel import hook, _block, _transcript, _user, _full, PANEL, panel_mode  # noqa: F401

KEPT = [
    "gate — publishing to the public",
    "gate — Gate 2, a customer-facing production deploy",
    "gate — spend above the ceiling",
    "gate — a recurring contract",
    "gate — deleting data with no backup",
    "gate — credentials only the operator can mint",
    "gate — Gate 2, a customer facing deploy",
]
PANELLED = [
    "gate — Gate 2, deploy to our own VPS",
    "gate — destructive, with a verified backup",
    "gate — credentials the fleet mints itself",
    "gate — publish to our own surfaces",
    "gate — production data window, dump first",
    "gate — unpublished draft, publish later",
    "gate — design approval of docs/superpowers/specs/x-design.md",
]


@pytest.mark.parametrize("why", KEPT)
def test_kept(tmp_path, panel_mode, why):
    tr = _transcript(tmp_path, _user("go"))
    r = hook.parse_decision_block(_block(None, ground="gate", why=why), run_live=False, transcript_path=tr)
    print(f"\nKEPT     {why!r:62} unpaneled -> {r[0]} {r[1][:60]!r}")


@pytest.mark.parametrize("why", PANELLED)
def test_panelled(tmp_path, panel_mode, why):
    tr = _transcript(tmp_path, _user("go"))
    r = hook.parse_decision_block(_block(None, ground="gate", why=why), run_live=False, transcript_path=tr)
    s = hook.parse_decision_block(_block(PANEL, ground="gate", why=why), run_live=False, transcript_path=_full(tmp_path))
    print(f"\nPANELLED {why!r:62} unpaneled -> {r[0]} {r[1][:60]!r} | split -> {s}")
