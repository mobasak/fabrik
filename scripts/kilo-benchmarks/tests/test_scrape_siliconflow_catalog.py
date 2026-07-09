"""Behavior Contract for scripts/kilo-benchmarks/scrape_siliconflow_catalog.py.

Minimal test file added 2026-07-09 during plan-2 `/fabrik-review` Pass 3/4 —
the SF `_ORG_MAP["meituan-longcat"]` self-mapping bug (adjacent-fix mirror of
the ModelScope Pass-1 fix) had zero regression coverage. This file locks in
the canonical mapping so a future refactor can't silently re-break it.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_org_map_meituan_maps_to_canonical_db_provider():
    """SF publishes as `meituan-longcat/LongCat-...`, DB is `meituan/longcat-*`.
    A self-mapping (`meituan-longcat: meituan-longcat`) yields zero flips
    forever — regression guard for the Pass-3 fix.
    """
    from scrape_siliconflow_catalog import _ORG_MAP, _sf_to_agent_id_candidates

    assert _ORG_MAP["meituan-longcat"] == "meituan", (
        "meituan-longcat must map to canonical DB provider 'meituan' — "
        "the DB has `meituan/longcat-flash-chat`, not `meituan-longcat/*`."
    )
    cands = _sf_to_agent_id_candidates("meituan-longcat/LongCat-Flash-Chat")
    assert all(c.startswith("meituan/") for c in cands), (
        f"meituan-longcat/ must resolve to meituan/, got {cands}"
    )
