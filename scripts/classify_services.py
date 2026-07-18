#!/usr/bin/env python3
# AFTER-EDIT: scripts/service_catalog.json
"""Web-ground the uncatalogued services (category=? in all-envs.env) via the OpenRouter pool.

For every NEEDS-TRIAGE provider in secrets/all-envs.env, dispatch ONE cheap pool research
unit (family-diverse models under the <=$1.5/Mtok cap, web-grounded via exa/brave) that
returns {category, cost, capability, url, status} — or category="?" when the web can't
identify a real vendor (no invented URLs). The pool sees only the env-var NAMES and any
non-secret URL values — never a secret value leaves the box. Flywheel-recorded.

    python scripts/classify_services.py            # dry-run: print proposals, write nothing
    python scripts/classify_services.py --apply    # merge identified providers into the catalog
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from libs.subagents import fanout, methodology, set_quality  # noqa: E402

ALL_ENVS = REPO / "secrets" / "all-envs.env"
CATALOG_PATH = REPO / "scripts" / "service_catalog.json"
CATEGORIES = (
    "ai-llm ai-image ai-audio ai-translate search scrape captcha proxy domains email "
    "storage backup research-data media-stock infra-platform dev-tools comms payments"
)
URL_KEY_RE = re.compile(r"(_URL|_BASE_URL|_ENDPOINT)$", re.I)
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def flagged_providers(path: Path) -> dict[str, dict]:
    """Parse the NEEDS-TRIAGE block: provider -> {names:[...], urls:[non-secret endpoints]}."""
    provs: dict[str, dict] = {}
    cur: str | None = None
    in_triage = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if "NEEDS-TRIAGE" in line:
            in_triage = True
            continue
        if not in_triage:
            continue
        if line.startswith("# ═"):  # next section header -> triage block ended
            break
        if line.startswith("#svc name="):
            cur = line.split("name=", 1)[1].split(" ", 1)[0]
            provs[cur] = {"names": [], "urls": []}
            continue
        m = KEY_RE.match(line)
        if cur and m:
            key, rest = m.group(1), m.group(2)
            provs[cur]["names"].append(key)
            if URL_KEY_RE.search(key):  # a URL value is a PUBLIC endpoint -> safe + identifying
                val = rest.split("   #", 1)[0].strip()
                if val.startswith("http"):
                    provs[cur]["urls"].append(val)
    return provs


def unit_prompt(prov: str, info: dict) -> str:
    hints = ("\nKnown endpoint(s): " + ", ".join(sorted(set(info["urls"])))) if info["urls"] else ""
    return (
        "Identify the external SaaS/API service behind these environment variable NAMES "
        "(you are given names + public endpoints only, never secret values).\n"
        f"Env vars: {', '.join(info['names'])}{hints}\n\n"
        "Search the web to confirm the vendor, what it does, and its pricing tier. "
        "Return ONLY a single-line JSON object and nothing else:\n"
        f'{{"name":"<lowercase-slug>","category":"<one of: {CATEGORIES}>",'
        '"cost":"free|freemium|paid|self-host","capability":"<one line, <=60 chars>",'
        '"url":"<official https url>","status":"active"}\n'
        "If web search does NOT clearly identify a real vendor, return exactly "
        f'{{"name":"{prov}","category":"?","cost":"?","capability":"unknown - needs human",'
        '"url":"?","status":"?"} — do NOT guess a url or category.'
    )


def extract_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--apply", action="store_true", help="write identified providers into the catalog"
    )
    args = ap.parse_args()

    if not ALL_ENVS.exists():
        print(f"{ALL_ENVS} missing — run scripts/gather_envs.py --apply first", file=sys.stderr)
        return 1

    provs = flagged_providers(ALL_ENVS)
    if not provs:
        print("No category=? providers to classify — nothing to do.")
        return 0

    names = list(provs)
    print(f"Classifying {len(names)} uncatalogued providers via the pool: {', '.join(names)}\n")
    results, table = fanout(
        "research",
        units=[unit_prompt(p, provs[p]) for p in names],
        repo=str(REPO),
        project="service-catalog",
        mode="read_only",
        k=1,
        web_tools=frozenset({"exa", "brave"}),
        max_turns=6,
        max_cost_usd=0.20,
        system=methodology("research"),
    )

    proposals: dict[str, dict] = {}
    for prov, r in zip(names, results, strict=True):
        obj = extract_json(getattr(r, "text", "")) if getattr(r, "error", None) is None else None
        proposals[prov] = obj or {
            "category": "?",
            "capability": "(no result)",
            "cost": "?",
            "url": "?",
            "status": "?",
        }
        score = 5 if proposals[prov].get("category") not in (None, "?") else 2
        try:
            set_quality(
                r.agent_id, score, project="service-catalog", task_type="research", model=r.model
            )
        except Exception as exc:  # noqa: BLE001 - flywheel is best-effort, never block classification
            print(f"  (flywheel set_quality skipped for {prov}: {exc})", file=sys.stderr)

    print("Proposed classifications:")
    for prov in names:
        p = proposals[prov]
        print(
            f"  {prov:22} -> {p.get('category', '?'):16} {p.get('cost', '?'):9} "
            f"{p.get('url', '?'):32} {p.get('capability', '')}"
        )

    identified = {p: v for p, v in proposals.items() if v.get("category") not in (None, "?")}
    print(
        f"\n{len(identified)}/{len(names)} identified; {len(names) - len(identified)} still need a human."
    )

    if not args.apply:
        print("\n[dry-run] Re-run with --apply to merge the identified ones into the catalog.")
        return 0

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    for prov, v in identified.items():
        root = prov.split("_")[0].upper()
        catalog[prov] = {
            "category": v.get("category", "?"),
            "cost": v.get("cost", "?"),
            "capability": str(v.get("capability", "?"))[:70],
            "url": v.get("url", "?"),
            "status": v.get("status", "active"),
            "match": [root],
        }
    CATALOG_PATH.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"\nWrote {len(identified)} providers into {CATALOG_PATH}. "
        "Re-run scripts/gather_envs.py --apply to refresh all-envs.env."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
