"""tests/test_state.py reloads fabrik.config, fabrik.locks_local and fabrik.state under a fake
FABRIK_ROOT. monkeypatch restores the env at teardown, but a reloaded module keeps the constants it
computed at import, so without a reload back every later test in the session saw FABRIK_ROOT,
STATE_DIR and LOCK_DIR pointing into a deleted pytest tmp dir (W-019e468b).

This file sorts after test_state.py ('.' < '_'), so in a full or directory run it executes after
that module's teardown. Run alone it passes trivially; its value is in the suite run, where it is the
only thing that can see the leak.
"""

from __future__ import annotations

from pathlib import Path


def _under_tmp(p: Path) -> bool:
    # pytest's basetemp is <TMPDIR>/pytest-of-<user>/…; TMPDIR is not always /tmp, so key on the
    # component pytest itself adds, never on a prefix built from tempfile.gettempdir()
    return any(part.startswith("pytest-of-") for part in Path(p).parts)


def test_state_modules_are_reloaded_back_after_test_state():
    import fabrik.config
    import fabrik.locks_local
    import fabrik.state

    for name, value in (
        ("fabrik.config.FABRIK_ROOT", fabrik.config.FABRIK_ROOT),
        ("fabrik.state.STATE_DIR", fabrik.state.STATE_DIR),
        ("fabrik.locks_local.LOCK_DIR", fabrik.locks_local.LOCK_DIR),
    ):
        assert not _under_tmp(Path(value)), f"{name} still points at a test's tmp dir: {value}"
