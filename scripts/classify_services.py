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
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

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
            if URL_KEY_RE.search(key):  # a URL identifies the provider — send ONLY scheme://host,
                val = rest.split("   # ", 1)[0].strip()  # never the path/query (may embed a token)
                if val.lower().startswith("http"):
                    parts = urlsplit(val)
                    if parts.hostname:
                        provs[cur]["urls"].append(f"{parts.scheme}://{parts.hostname}")
    return provs


def build_proposals(names: list[str], results: list) -> tuple[dict[str, dict], set[str]]:
    """Split pool results into (proposals, errored).

    `errored` holds ONLY providers whose dispatch had a true transport/timeout/infra failure
    (`r.error` set — agent.py sets it, with empty text, for every such case). Those must NOT be
    tombstoned: the failure is transient, so the provider stays flagged and retries next run (C4).

    A COMPLETED response with no parseable JSON (`had_error` False, `obj` None) is deliberately NOT
    added to `errored`: the model answered but could not classify the vendor — a genuine
    unidentifiable outcome, same as an explicit category="?". It flows through to the tombstone loop
    and gets stubbed; otherwise it would re-bill a paid pool call on every daily run forever."""
    proposals: dict[str, dict] = {}
    errored: set[str] = set()
    for prov, r in zip(names, results, strict=True):
        had_error = getattr(r, "error", None) is not None
        obj = extract_json(getattr(r, "text", "")) if not had_error else None
        # KNOWN TRADEOFF: a COMPLETED response whose JSON is merely MALFORMED (trailing comma, bad
        # fence) also parses to None and is treated as unidentifiable → tombstoned under --apply
        # --tombstone-unresolved, not retried. Deliberate: bounded cost (no infinite re-bill) over
        # retrying a one-off formatting glitch; the stub is labelled "unidentified" and is
        # operator-reversible (delete it, or run classify_services.py without --tombstone to retry).
        if had_error:
            errored.add(prov)
        proposals[prov] = obj or {
            "category": "?",
            "capability": "(no result)",
            "cost": "?",
            "url": "?",
            "status": "?",
        }
    return proposals, errored


def tombstone_entry(prov: str) -> dict:
    """A catalog stub for a provider the WEB genuinely could not identify.

    The `category` is a NON-"?" value ("unidentified") on purpose: gather_envs buckets the
    NEEDS-TRIAGE block SOLELY on category=="?", so a "?" stub would stay in triage and get
    re-dispatched (re-billed) every daily run — the exact loop this closes (C2). The match
    prefix is the FULL provider name (not `prov.split("_")[0]`) so a compound name like
    `aws_bedrock` tombstones only AWS_BEDROCK_* keys, never every AWS_* key (C5)."""
    return {
        "category": "unidentified",
        "cost": "?",
        "capability": "web could not classify; add a real entry or remove the key",
        "url": "?",
        "status": "unidentified",
        "match": [prov.upper()],
    }


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
    ap.add_argument(
        "--only", help="comma-separated provider names to classify (default: all flagged)"
    )
    ap.add_argument(
        "--tombstone-unresolved",
        action="store_true",
        help="with --apply, also write a category='unidentified' stub (a non-'?' category, so it "
        "leaves the NEEDS-TRIAGE block) for providers the web could not identify, so they are NOT "
        "re-classified (re-billed) on every run. For the daily/automated path; a manual run omits "
        "it to retry unknowns. Providers that only ERRORED (transport/no-key) are never tombstoned.",
    )
    args = ap.parse_args()

    if not ALL_ENVS.exists():
        print(f"{ALL_ENVS} missing — run scripts/gather_envs.py --apply first", file=sys.stderr)
        return 1

    provs = flagged_providers(ALL_ENVS)
    if args.only:  # the re-bill guard: classify ONLY the named (new) providers, not all flagged
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        provs = {p: v for p, v in provs.items() if p in wanted}
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

    proposals, errored = build_proposals(names, results)
    for prov, r in zip(names, results, strict=True):
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
        root = prov.upper()  # FULL provider name — a compound like `aws_bedrock` must match only
        #                      AWS_BEDROCK_* keys, never every AWS_* key (same scoping as C5)
        catalog[prov] = {
            "category": v.get("category", "?"),
            "cost": v.get("cost", "?"),
            "capability": str(v.get("capability", "?"))[:70],
            "url": v.get("url", "?"),
            "status": v.get("status", "active"),
            "match": [root],
        }
    tombstoned = 0
    if args.tombstone_unresolved:
        # Persist a stub for a provider the WEB genuinely could not identify (not one that
        # merely errored — C4) so it drops out of NEEDS-TRIAGE and the daily path stops
        # re-dispatching a paid pool call for it forever. The category MUST be non-"?" —
        # gather_envs buckets NEEDS-TRIAGE purely on category=="?", so a "?" stub would
        # stay in triage and defeat the whole point (C2). The full provider name is the
        # match prefix (not split on "_") so `aws_bedrock` doesn't swallow every AWS_* key (C5).
        for prov in names:
            if prov in identified or prov in catalog or prov in errored:
                continue
            catalog[prov] = tombstone_entry(prov)
            tombstoned += 1
    tmp = CATALOG_PATH.with_name(CATALOG_PATH.name + ".tmp")  # atomic: no torn/corrupt JSON
    tmp.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, CATALOG_PATH)
    print(
        f"\nWrote {len(identified)} identified"
        + (f" + {tombstoned} unidentified-stub" if tombstoned else "")
        + f" providers into {CATALOG_PATH}. "
        "Re-run scripts/gather_envs.py --apply to refresh all-envs.env."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
