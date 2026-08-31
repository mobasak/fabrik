"""Redis registry parsing + write shape (finding 01M1CKEK, tryton-crm 2026-08-31).

The live registry at /opt/monitoring/configs/redis/assignments.json is a versioned
ENVELOPE ({"version", "last_updated", "assignments", "free_indexes"} — same
convention as the postgres driver's allocations file), but `_read_registry` assumed
a flat {service: index} map and ran bare `int()` over every value — crashing on the
`last_updated` timestamp on EVERY read since 2026-05-15, swallowed as a non-fatal
warning under a green deploy. These tests pin: both shapes parse; the crash value
now raises a repairable RuntimeError instead of a bare ValueError; and writes emit
the envelope (never the flat map that would strip the metadata).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from fabrik.drivers import redis as redis_driver

# The live file's exact shape on vps1 at the time of the finding (secrets-free).
LIVE_ENVELOPE = {
    "version": 1,
    "last_updated": "2026-05-15T11:52:05+03:00",
    "assignments": {"authelia": 3, "glitchtip-web": 4},
    "free_indexes": [0, 1, 2, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
}


class TestExtractAssignments:
    def test_live_envelope_regression(self):
        """The exact production file that crashed `int()` must parse."""
        assert redis_driver.extract_assignments(LIVE_ENVELOPE) == {
            "authelia": 3,
            "glitchtip-web": 4,
        }

    def test_flat_legacy_map_still_parses(self):
        assert redis_driver.extract_assignments({"svc-a": 1, "svc-b": "7"}) == {
            "svc-a": 1,
            "svc-b": 7,
        }

    def test_timestamp_value_raises_repairable_error_not_valueerror(self):
        """The original crash string must produce RuntimeError naming the file."""
        with pytest.raises(RuntimeError, match="assignments.json"):
            redis_driver.extract_assignments({"svc": "2026-05-15T11:52:05+03:00"})

    def test_bool_value_rejected(self):
        # bool is an int subclass; True silently becoming index 1 would
        # double-book whoever legitimately holds index 1.
        with pytest.raises(RuntimeError, match="non-integer"):
            redis_driver.extract_assignments({"svc": True})

    def test_unicode_digit_raises_runtimeerror_not_valueerror(self):
        # "²".isdigit() is True but int("²") raises — the parse must stay
        # inside the RuntimeError contract (review finding, pass 1).
        with pytest.raises(RuntimeError, match="non-integer"):
            redis_driver.extract_assignments({"svc": "²"})

    def test_historically_accepted_string_forms_still_parse(self):
        # The old bare int() accepted " 7"/"+7"; the hardening must not
        # turn a long-working hand-edited registry into a hard failure.
        assert redis_driver.extract_assignments({"a": " 7", "b": "+3"}) == {"a": 7, "b": 3}

    def test_out_of_range_index_rejected(self):
        with pytest.raises(RuntimeError, match="out-of-range"):
            redis_driver.extract_assignments({"svc": -5})
        with pytest.raises(RuntimeError, match="out-of-range"):
            redis_driver.extract_assignments({"svc": 999999})

    def test_double_booked_index_rejected(self):
        # Two services on one logical DB defeats the isolation the registry
        # exists for — parse must refuse, not silently return the collision.
        with pytest.raises(RuntimeError, match="double-books"):
            redis_driver.extract_assignments({"svc-a": 3, "svc-b": 3})

    def test_newer_envelope_version_refused(self):
        # A v2 writer's file must not be read (and later clobbered back to v1).
        with pytest.raises(RuntimeError, match="version 1 only"):
            redis_driver.extract_assignments({"version": 2, "assignments": {"a": 1}})

    def test_empty_envelope_parses_empty(self):
        assert redis_driver.extract_assignments({"version": 1, "assignments": {}}) == {}


class TestReadRegistry:
    def test_reads_the_live_envelope_over_ssh(self):
        with patch.object(redis_driver, "ssh", return_value=json.dumps(LIVE_ENVELOPE)):
            assert redis_driver._read_registry() == {"authelia": 3, "glitchtip-web": 4}

    def test_absent_file_is_empty_registry(self):
        with patch.object(redis_driver, "ssh", return_value="{}"):
            assert redis_driver._read_registry() == {}


class TestAcquireHoldsTheLock:
    def test_acquire_serializes_via_file_lock(self):
        # postgres.py wraps its allocations mutation in file_lock; the redis
        # docstring claims the same convention — the lock IS half of it
        # (review finding, pass 1: concurrent applies double-book last-free).
        entered = []

        class _Lock:
            def __enter__(self):
                entered.append(True)
                return Path("/tmp/fake-lock")

            def __exit__(self, *a):
                return False

        with (
            patch.object(redis_driver, "file_lock", return_value=_Lock()) as fl,
            patch.object(redis_driver, "ssh", return_value=json.dumps(LIVE_ENVELOPE)),
        ):
            result = redis_driver.acquire_db_index("authelia", dry_run=True)
        fl.assert_called_once()
        assert entered == [True]
        assert result["db_index"] == 3  # existing assignment read under the lock


    def test_release_serializes_via_the_same_lock(self):
        # release is the other read-modify-write on the file; unlocked it
        # races acquire on last-writer-wins (round-2 re-sweep finding).
        with (
            patch.object(redis_driver, "file_lock") as fl,
            patch.object(redis_driver, "ssh", return_value=json.dumps(LIVE_ENVELOPE)),
            patch.object(redis_driver, "scp_to_vps"),
        ):
            redis_driver.release_db_index("authelia")
        fl.assert_called_once_with("redis-assignments", timeout_seconds=15.0)


class TestWriteRegistry:
    def test_writes_envelope_not_flat_map(self):
        """The write must preserve the envelope convention the box uses."""
        captured = {}

        def fake_scp(local, remote):
            with open(local) as fh:
                captured["body"] = fh.read()

        with (
            patch.object(redis_driver, "ssh", return_value=""),
            patch.object(redis_driver, "scp_to_vps", side_effect=fake_scp),
        ):
            redis_driver._write_registry({"authelia": 3, "tryton-crm": 5})

        data = json.loads(captured["body"])
        assert data["version"] == 1
        assert data["assignments"] == {"authelia": 3, "tryton-crm": 5}
        # free_indexes = complement over 0..15; 0 stays listed (unassigned in
        # the FILE; the allocator's CLI-reservation of 0 is policy, not state).
        assert data["free_indexes"] == [0, 1, 2, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
        assert data["last_updated"]
