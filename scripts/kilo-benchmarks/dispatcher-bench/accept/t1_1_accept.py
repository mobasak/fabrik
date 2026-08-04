from scripts.check_ports import compose_ports, registered_ports


def _bad(compose, registry):
    reg = registered_ports(registry)
    return [p for p in compose_ports(compose) if p not in reg]


def test_registered_quoted():
    assert _bad('- "8016:8016"', "8016 api\n") == []


def test_registered_unquoted():
    assert _bad("- 9101:9101", "# x\n9101 metrics\n") == []


def test_unregistered_still_flagged():
    assert _bad('- "9999:9999"', "8016 api\n") == [9999]
