"""Remote-side loopback constants pass the hub's localhost ban (W-3cb69ae8, mail 01M57PDDZG).

`scripts/enforcement/check_env_vars.py` scans every file a change lists, and a merge of master lists
every file master brought in. A loopback URL that is reached ON the VPS (over SSH) or inside a
container is correct there, yet reads to the check exactly like a dev-host default, so a branch that
merely merged master went red on a constant it never touched. Each such constant carries a reasoned
`# noqa`, as `orchestrator/verifier.py`'s identical Traefik constant already did.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "enforcement"))
import check_env_vars as cev  # noqa: E402

REMOTE_LOOPBACK = {
    # the VPS's own Traefik admin API, bound to 127.0.0.1:8080 and reached over SSH
    "src/fabrik/drivers/preflight.py": "TRAEFIK_API_LOCAL_URL",
    "src/fabrik/orchestrator/verifier.py": "TRAEFIK_ROUTERS_API",
    # prometheus's own loopback, called from inside the prometheus container
    "src/fabrik/drivers/prometheus.py": "PROMETHEUS_RELOAD_URL",
}


@pytest.mark.parametrize(("rel", "constant"), sorted(REMOTE_LOOPBACK.items()))
def test_a_remote_side_loopback_constant_passes_the_ban(rel, constant):
    path = ROOT / rel
    line = next(
        n for n, text in enumerate(path.read_text().splitlines(), 1) if text.startswith(constant)
    )
    flagged = [r.message for r in cev.check_file(path) if r.line_number == line]
    assert flagged == [], f"{rel}:{line} ({constant}) trips the localhost ban: {flagged}"
