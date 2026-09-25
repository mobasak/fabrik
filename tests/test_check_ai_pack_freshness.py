"""Regression tests for scripts/check_ai_pack_freshness.py.

Adversarial-review guards (2026-06-29):
  F1 — a malformed/empty/negative AI_PACK_STALE_DAYS must not crash (exit 0 contract).
  F2 — an unreadable / non-UTF-8 pack must degrade, not abort the whole scan.
  F3 — a future-dated stamp must read as fresh without misleading "-Nd ago".
  Boundary — verified exactly STALE_DAYS ago is fresh; STALE_DAYS+1 is stale.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

FRESH = Path(__file__).resolve().parent.parent / "scripts" / "check_ai_pack_freshness.py"


def _load():
    spec = importlib.util.spec_from_file_location("freshchk_under_test", FRESH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod():
    return _load()


class TestStaleDaysParsing:
    @pytest.mark.parametrize("val", ["abc", "", "12.5", "  ", "ninety"])
    def test_invalid_env_falls_back_to_90(self, mod, monkeypatch, val):
        monkeypatch.setenv("AI_PACK_STALE_DAYS", val)
        assert mod._stale_days() == 90

    def test_negative_falls_back_to_90(self, mod, monkeypatch):
        monkeypatch.setenv("AI_PACK_STALE_DAYS", "-5")
        assert mod._stale_days() == 90

    def test_valid_value_respected(self, mod, monkeypatch):
        monkeypatch.setenv("AI_PACK_STALE_DAYS", "30")
        assert mod._stale_days() == 30

    def test_unset_defaults_90(self, mod, monkeypatch):
        monkeypatch.delenv("AI_PACK_STALE_DAYS", raising=False)
        assert mod._stale_days() == 90


def test_script_exits_zero_on_bad_env(tmp_path):
    """F1 end-to-end: a malformed threshold must not crash the daily-pipeline step."""
    r = subprocess.run(
        [sys.executable, str(FRESH)],
        env={"AI_PACK_STALE_DAYS": "abc", "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, f"stdout={r.stdout!r} stderr={r.stderr!r}"


class TestCheckPack:
    def test_bad_utf8_degrades_not_raises(self, mod, tmp_path):
        """F2: an unreadable pack degrades to unstamped instead of aborting."""
        p = tmp_path / "bad.md"
        p.write_bytes(b"Last content verification: 2026-06-01\n\xff\x80 invalid")
        status, _age, msg = mod.check_pack(p, date(2026, 6, 29))
        assert status == "unstamped"
        assert "unreadable" in msg

    def test_future_date_is_fresh_without_negative_phrasing(self, mod, tmp_path):
        """F3: future stamp → fresh, no misleading 'verified -Nd ago'."""
        p = tmp_path / "future.md"
        p.write_text("Last content verification: 2099-01-01\n", encoding="utf-8")
        status, _age, msg = mod.check_pack(p, date(2026, 6, 29))
        assert status == "fresh"
        assert "future" in msg
        assert "verified -" not in msg

    def test_boundary_90_fresh_91_stale(self, tmp_path, monkeypatch):
        monkeypatch.delenv("AI_PACK_STALE_DAYS", raising=False)
        mod = _load()  # STALE_DAYS == 90
        today = date(2026, 6, 29)
        for days, expected in ((90, "fresh"), (91, "stale")):
            p = tmp_path / f"p{days}.md"
            p.write_text(
                f"Last content verification: {(today - timedelta(days=days)).isoformat()}\n",
                encoding="utf-8",
            )
            assert mod.check_pack(p, today)[0] == expected

    def test_unstamped(self, mod, tmp_path):
        p = tmp_path / "u.md"
        p.write_text("# pack with no stamp\n", encoding="utf-8")
        assert mod.check_pack(p, date(2026, 6, 29))[0] == "unstamped"

    def test_malformed_date_degrades(self, mod, tmp_path):
        p = tmp_path / "m.md"
        p.write_text("Last content verification: 2026-13-99\n", encoding="utf-8")
        status, _age, msg = mod.check_pack(p, date(2026, 6, 29))
        assert status == "unstamped"
        assert "malformed" in msg

    def test_multiple_stamps_uses_newest(self, mod, tmp_path):
        """Residual-risk R2 closed: newest of multiple stamps wins, not first-in-file."""
        p = tmp_path / "multi.md"
        p.write_text(
            "Last content verification: 2020-01-01\nLast content verification: 2026-06-20\n",
            encoding="utf-8",
        )
        status, age, _msg = mod.check_pack(p, date(2026, 6, 29))
        assert status == "fresh"
        assert age == 9  # 2026-06-20, not the 2020 first-in-file stamp


class TestDeliveredBlocks:
    """D-415: the engine-delivered `last-refreshed:` blocks page when they stop moving."""

    def _pack(self, tmp_path: Path, stamp: str) -> Path:
        p = tmp_path / "10-x.md"
        p.write_text(
            f"<!-- GATEWAY_COUNTS:START — last-refreshed: {stamp} (auto-managed) -->\n",
            encoding="utf-8",
        )
        return p

    def test_a_block_older_than_the_limit_is_reported(self, mod, tmp_path):
        today = date(2026, 9, 25)
        pack = self._pack(tmp_path, "2026-09-07")
        assert mod.stale_delivered_blocks([pack], today, 3) == [
            "10-x.md: last-refreshed 2026-09-07 (18d old)"
        ]

    def test_a_block_at_the_limit_is_fresh(self, mod, tmp_path):
        today = date(2026, 9, 25)
        pack = self._pack(tmp_path, (today - timedelta(days=3)).isoformat())
        assert mod.stale_delivered_blocks([pack], today, 3) == []

    def test_the_cli_exits_one_on_a_stale_block_and_zero_when_fresh(
        self, mod, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(mod, "AI_PACKS_DIR", tmp_path)
        monkeypatch.setattr(mod, "_today", lambda: date(2026, 9, 25))
        self._pack(tmp_path, "2026-09-07")
        monkeypatch.setattr(sys, "argv", ["x", "--delivered-max-age", "3"])
        assert mod.main() == 1
        self._pack(tmp_path, "2026-09-24")
        assert mod.main() == 0

    def test_the_default_mode_still_never_fails(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "AI_PACKS_DIR", tmp_path)
        self._pack(tmp_path, "2020-01-01")
        monkeypatch.setattr(sys, "argv", ["x"])
        assert mod.main() == 0

    @pytest.mark.parametrize(
        "argv",
        [
            ["x", "--delivered-max-age"],
            ["x", "--delivered-max-age", "3", "extra"],
            ["x", "y", "--delivered-max-age"],
        ],
    )
    def test_a_malformed_paging_flag_is_exit_two_never_the_default_scan(
        self, mod, monkeypatch, argv
    ):
        monkeypatch.setattr(sys, "argv", argv)
        assert mod.main() == 2

    def test_a_missing_packs_dir_fails_closed(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "AI_PACKS_DIR", tmp_path / "absent")
        assert mod.delivered_main(3) == 1

    def test_packs_with_no_delivered_block_fail_closed(self, mod, tmp_path, monkeypatch):
        (tmp_path / "10-x.md").write_text("no marker here\n", encoding="utf-8")
        monkeypatch.setattr(mod, "AI_PACKS_DIR", tmp_path)
        assert mod.delivered_main(3) == 1

    def test_an_unreadable_pack_is_reported(self, mod, tmp_path):
        bad = tmp_path / "10-bad.md"
        bad.write_bytes(b"\xff\xfe last-refreshed: 2026-09-25")
        found = mod.stale_delivered_blocks([bad], date(2026, 9, 25), 3)
        assert any("unreadable" in m for m in found)
