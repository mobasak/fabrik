"""CI regression test — added by the platform team. Do not modify."""
from scripts.check_ports import compose_ports, registered_ports


def test_registered_port_not_flagged():
    reg = registered_ports("# registry\n8016 api\n")
    bad = [p for p in compose_ports('- "8016:8016"') if p not in reg]
    assert bad == []
