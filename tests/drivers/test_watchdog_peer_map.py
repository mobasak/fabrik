"""Unit tests for fabrik.drivers.watchdog.host_prompt_substitutions (PR3).

The deterministic peer map MUST render the live trio (vps1/2/3) byte-identical
to the former hardcoded dict (no live-prompt regression), AND give a newly
provisioned vpsN real peers + mesh IP/role instead of "unknown".
"""

from fabrik.drivers.watchdog import host_prompt_substitutions as h


def test_trio_byte_identical_to_former_hardcoded_map():
    assert h("vps1") == {
        "name": "vps1", "ip": "10.99.0.1", "role": "hub",
        "peers": "vps2 (10.99.0.2), vps3 (10.99.0.3)",
    }
    assert h("vps2") == {
        "name": "vps2", "ip": "10.99.0.2", "role": "spoke",
        "peers": "vps1 (10.99.0.1), vps3 (10.99.0.3)",
    }
    assert h("vps3") == {
        "name": "vps3", "ip": "10.99.0.3", "role": "spoke",
        "peers": "vps1 (10.99.0.1), vps2 (10.99.0.2)",
    }


def test_new_spoke_gets_real_peers_and_mesh_ip_not_unknown():
    s = h("vps4")
    assert s["ip"] == "10.99.0.4"
    assert s["role"] == "spoke"
    # peers = the established fleet (vps4 is not in it, so all three)
    assert s["peers"] == "vps1 (10.99.0.1), vps2 (10.99.0.2), vps3 (10.99.0.3)"
    assert "unknown" not in s.values()


def test_non_vps_name_still_falls_back_to_unknown():
    assert h("watchdog-test") == {
        "name": "watchdog-test", "ip": "unknown", "role": "unknown", "peers": "unknown",
    }
