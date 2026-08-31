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


class TestReadRegistry:
    def test_reads_the_live_envelope_over_ssh(self):
        with patch.object(redis_driver, "ssh", return_value=json.dumps(LIVE_ENVELOPE)):
            assert redis_driver._read_registry() == {"authelia": 3, "glitchtip-web": 4}

    def test_absent_file_is_empty_registry(self):
        with patch.object(redis_driver, "ssh", return_value="{}"):
            assert redis_driver._read_registry() == {}


class TestWriteRegistry:
    def test_writes_envelope_not_flat_map(self):
        """The write must preserve the envelope convention the box uses."""
        captured = {}

        def fake_scp(local, remote):
            captured["body"] = open(local).read()

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
