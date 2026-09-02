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
import fcntl
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from libs.subagents import fanout, methodology, set_quality  # noqa: E402

ALL_ENVS = REPO / "secrets" / "all-envs.env"
CATALOG_PATH = REPO / "scripts" / "service_catalog.json"


def _scheme(url: str) -> str:
    """`urlsplit(...).scheme`, or "" when the value is not a url at all (`http://a]b` raises
    ValueError — one malformed model answer must not discard the whole paid batch, BB5)."""
    try:
        return urlsplit(url).scheme
    except ValueError:
        return ""


def _host(url: str) -> str | None:
    try:
        return urlsplit(url).hostname
    except ValueError:
        return None


def _enum_category(raw) -> str:
    """The catalog category for a model answer: normalised, and `?` unless it IS an enum value —
    the ONE verdict every consumer (catalog, tombstone, report, flywheel score) reads (AS1/AU1/AU5)."""
    c = str(raw if raw is not None else "?").strip().lower()
    return c if c in CATEGORIES.split() else "?"


COSTS = ("free", "freemium", "paid", "self-host", "?")  # the catalog's live value set (AP1)
STATUSES = ("active", "retired", "retiring", "unidentified", "?")
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
        if (
            line.startswith("# ═") and "NEEDS-TRIAGE" in line
        ):  # the HEADER only — never a value (AU11)
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
                h = (
                    _host(val) if val.lower().startswith("http") else None
                )  # a malformed *_URL never kills classify (BB5)
                if h:
                    host = f"[{h}]" if ":" in h else h  # IPv6 keeps its brackets (BE8)
                    provs[cur]["urls"].append(f"{_scheme(val)}://{host}")
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


STATE_DIR = REPO / ".tmp" / "external-services"
CURSOR_PATH = STATE_DIR / "classify_cursor.json"  # {"after": "<last provider classified>"}
ERRORS_PATH = STATE_DIR / "classify_errors.json"  # {"<provider>": consecutive_error_runs}
LAST_RUN_PATH = (
    STATE_DIR / "classify_last.json"
)  # {"identified": [...], "tombstoned": [...], "errored": [...]}
ERROR_BUDGET = 3  # consecutive transport-error runs before a provider is tombstoned anyway


def bound_flagged(
    provs: dict[str, dict], max_per_run: int, after: str | None = None
) -> tuple[dict[str, dict], int, str | None]:
    """Keep `max_per_run` providers per run; return (kept, deferred_count, new_cursor).
    0 = unlimited (cursor None).

    The window walks the SORTED queue from the persisted cursor (`after` = the last name
    processed last run), wrapping at the end. A date-keyed offset was tried first and refuted in
    review: `(day × k) % N` with N changing daily lands on unrelated positions, so providers were
    skipped or double-billed. A cursor walks forward regardless of churn — every provider that
    stays flagged is reached within ceil(N / max_per_run) runs, and a permanently-erroring one is
    re-tried once per lap, never daily (its lap ends when ERROR_BUDGET tombstones it)."""
    if not max_per_run or len(provs) <= max_per_run:
        return provs, 0, None
    names = sorted(provs)
    start = 0
    if after is not None:
        start = sum(1 for n in names if n <= after) % len(names)
    keep = (names + names)[start : start + max_per_run]
    return {p: provs[p] for p in keep}, len(names) - len(keep), keep[-1]


def _read_json(path: Path, default):
    """State files are scratch (.tmp/): a missing, corrupt or wrong-SHAPED file is the default,
    never a crash that takes the chain down (review 2026-09-02, pass 2)."""
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
    return obj if isinstance(obj, type(default)) else default


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def apply_error_budget(
    errored: set[str],
    names: list[str],
    counts: dict[str, int],
    budget: int = ERROR_BUDGET,
    flagged: set[str] | None = None,
) -> tuple[dict[str, int], set[str]]:
    """Consecutive transport-error runs per provider. A provider that errors `budget` runs in a
    row is returned in `exhausted` (→ tombstoned like an unidentifiable one); a run that does NOT
    error resets its count. Closes the retired orchestrator's seen-set gap: without it a
    permanently-erroring provider was re-billed on every lap forever (review 2026-09-02)."""
    new = {
        k: v for k, v in counts.items() if isinstance(k, str) and isinstance(v, int)
    }  # a wrong-typed count is dropped (C2)
    for n in names:
        new[n] = new.get(n, 0) + 1 if n in errored else 0
    keep = set(names) if flagged is None else flagged | set(names)
    new = {k: v for k, v in new.items() if v > 0 and k in keep}  # a provider that left resets
    return new, {n for n in errored if new.get(n, 0) >= budget}


def code_only_provider(info: dict) -> bool:
    """True when the flagged provider's only 'key' is the synthetic CODE_HOST_URL line."""
    names = [n for n in info.get("names", []) if n != "CODE_HOST_URL"]
    return not names and bool(info.get("names"))


def _curated_tokens(meta: dict) -> set[str]:
    """An entry's prefixes — curated `match` AND model-merged `merged_match`, because
    `gather_envs.load_catalog`'s tie claims read both (CA4) — as tokens (`HF_` → `HF`)."""
    out: set[str] = set()
    for field in ("match", "merged_match"):
        raw = meta.get(field) or []
        out |= {
            str(x).upper().rstrip("_") for x in (raw if isinstance(raw, list) else [raw]) if str(x)
        }
    return out


def tombstone_of(catalog: dict, prov: str) -> bool:
    """True when the catalog's entry for `prov` is a tombstone — `unidentified`, or a bare `?`
    placeholder with no curated routing (`match`/`hosts`/`url`) — never a curated one: the only
    entry the merge path may remove (CA3/CC4)."""
    meta = catalog.get(prov) or {}
    category = str(meta.get("category") or "?")
    if category == "unidentified":
        return True
    return category == "?" and not any(
        meta.get(k) not in (None, "", "?", []) for k in ("match", "hosts", "url")
    )


def tombstone_entry(prov: str, code_only: bool = False) -> dict:
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
        "match": [] if code_only else [prov.upper()],
    }


def unit_prompt(prov: str, info: dict) -> str:
    hints = ("\nKnown endpoint(s): " + ", ".join(sorted(set(info["urls"])))) if info["urls"] else ""
    env_names = [n for n in info["names"] if n != "CODE_HOST_URL"]
    lead = (
        "Identify the external service reached at these endpoint(s), found as call sites in "
        "source code (no credential exists for it in the fleet)."
        if not env_names
        else "Identify the external SaaS/API service behind these environment variable NAMES "
        "(you are given names + public endpoints only, never secret values).\n"
        f"Env vars: {', '.join(env_names)}"
    )
    return (
        f"{lead}{hints}\n\n"
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
    ap.add_argument(
        "--max-per-run",
        type=int,
        default=10,
        help="classify at most N flagged providers per run (sorted, so the queue drains "
        "deterministically day by day); 0 = unlimited. Bounds the paid pool spend of the "
        "daily path — the code-host scan can enqueue hundreds of hosts at once.",
    )
    args = ap.parse_args()

    if not ALL_ENVS.exists():
        print(f"{ALL_ENVS} missing — run scripts/gather_envs.py --apply first", file=sys.stderr)
        return 1

    provs = flagged_providers(ALL_ENVS)
    all_flagged = set(provs)  # the WHOLE queue, before any --only narrowing (pass 5, Z2)
    if args.only:  # the re-bill guard: classify ONLY the named (new) providers, not all flagged
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        provs = {p: v for p, v in provs.items() if p in wanted}
        missing = wanted - set(provs)
        if missing:  # a name that is not flagged is a typo or already catalogued — say so (AF12)
            print(
                f"--only: {sorted(missing)} are not in NEEDS-TRIAGE ({len(all_flagged)} flagged)",
                file=sys.stderr,
            )
    if not provs:
        if args.only:  # every name was a typo or already catalogued: a requested run that did nothing is a failure (C6)
            print(
                "--only: none of the named providers is in NEEDS-TRIAGE — nothing dispatched",
                file=sys.stderr,
            )
            return 1
        print("No category=? providers to classify — nothing to do.")
        return 0
    # One classify at a time: the cursor is a read-modify-write, and a manual run racing the
    # daily one would process the same slice twice (double-billed) and lose one cursor update
    # (review 2026-09-02, pass 2). Non-blocking — the loser skips cleanly, exit 0.
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    lock_fh = open(STATE_DIR / "classify.lock", "w", encoding="utf-8")  # noqa: SIM115 - held for the run
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("another classify_services run holds the lock — skipping (no double-billing)")
        return 0
    cursor = _read_json(CURSOR_PATH, {}).get("after")
    if not isinstance(cursor, str):
        cursor = (
            None  # a wrong-typed cursor is the default, never a TypeError in bound_flagged (C2)
        )
    if (
        args.only
    ):  # an operator-named list is already bounded by what was typed — never cap it (AB1)
        provs, deferred, new_cursor = provs, 0, None
    else:
        provs, deferred, new_cursor = bound_flagged(provs, args.max_per_run, after=cursor)
    if deferred:
        print(
            f"bounded run: {len(provs) + deferred} flagged → classifying {len(provs)} now "
            f"(after {cursor!r}), {deferred} deferred to the next run"
        )

    names = list(provs)
    print(f"Classifying {len(names)} uncatalogued providers via the pool: {', '.join(names)}\n")
    # read + parse the catalog BEFORE spending: an unreadable file after the dispatch lost the
    # whole paid batch (the cursor had already moved — BH2)
    try:
        _catalog_probe = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        probe_at = datetime.now(UTC).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )  # every chain stamp is UTC (O6/BS10)
        if not isinstance(_catalog_probe, dict):
            raise ValueError("catalog is not a JSON object")
    except (OSError, ValueError) as exc:
        print(
            f"ERROR: {CATALOG_PATH} unreadable ({exc}) — nothing dispatched, nothing written, cursor unmoved (BK4)",
            file=sys.stderr,
        )
        return 1
    if new_cursor is not None and not args.only and args.apply:  # a dry run moves nothing (AF3)
        # persist the cursor BEFORE the paid dispatch: a `timeout` kill after dispatch would
        # otherwise re-bill the identical slice every day, forever (AC5)
        _write_json(CURSOR_PATH, {"after": new_cursor})
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
        # the flywheel sees the ENUM verdict, not the raw answer (AU5)
        score = 5 if _enum_category(proposals[prov].get("category")) != "?" else 2
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

    # identified = the ENUM accepts the (normalised) category — a model answer the enum flattens
    # is not an identification: it never merges into a curated entry (AU1), is never reported or
    # alerted as classified (AU2), and takes the tombstone path on the daily argv (AS1)
    identified = {p: v for p, v in proposals.items() if _enum_category(v.get("category")) != "?"}
    print(
        f"\n{len(identified)}/{len(names)} identified; {len(names) - len(identified)} still need a human."
    )

    if not args.apply:
        print("\n[dry-run] Re-run with --apply to merge the identified ones into the catalog.")
        return 0

    # the pre-dispatch parse was a readability PROBE; the merge reads the file FRESH so a hand edit
    # made during the minutes of the paid dispatch is never reverted by the write below (BK6)
    try:
        raw_catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw_catalog, dict):
            raise ValueError("catalog is not a JSON object")
    except (OSError, ValueError) as exc:
        # the paid batch is NOT lost: merge onto the pre-dispatch probe (the last good state) and
        # say so — the cursor has already moved and the money is spent (BM3)
        print(
            f"WARNING: {CATALOG_PATH} became unreadable during the dispatch ({exc}) — merging onto the pre-dispatch copy read at {probe_at}; any catalog edit landed since then is DISCARDED (repair the file, re-apply the edit) (BM3/BR7)",
            file=sys.stderr,
        )
        raw_catalog = _catalog_probe
    # `_`-prefixed keys are metadata (`_README`), never providers — the same convention
    # gather_envs.load_catalog applies; kept aside and written back first (AU9)
    catalog_meta = {k: v for k, v in raw_catalog.items() if k.startswith("_")}
    catalog = {
        k: v for k, v in raw_catalog.items() if not k.startswith("_") and isinstance(v, dict)
    }
    catalog_meta.update(
        {k: v for k, v in raw_catalog.items() if not k.startswith("_") and not isinstance(v, dict)}
    )  # a non-dict value is metadata too (AY8)
    merged_into: dict[str, str] = {}
    for prov, v in list(identified.items()):
        target = str(v.get("name") or "").strip().lower()
        if (
            target
            and target != prov
            and target in catalog
            and not (prov in catalog and not tombstone_of(catalog, prov))
        ):
            # a catalogued NON-tombstone source (a `?` placeholder with curated routing — the one
            # such shape that reaches here) is never folded into another vendor by a model's word:
            # the identified path keeps the operator's fields and fills its `?`, so it leaves
            # triage — merged, it stayed `?` and re-billed every lap forever (CE2)
            # the vendor is ALREADY catalogued under another key: a code-only provider records its
            # host on that entry (safebrowsing.googleapis → google-safe-browsing, AB3); an env-keyed
            # one lends its key prefix to that entry's `match` list (AD2) — never a duplicate
            # identity that the registry and dashboard would show as a second vendor
            entry = catalog[target]
            if code_only_provider(provs.get(prov, {})):
                hosts = entry.setdefault("hosts", [])
                if not isinstance(
                    hosts, list
                ):  # a hand-edited scalar (AF14); `null` is empty, not "None" (BH5)
                    hosts = entry["hosts"] = [] if hosts is None else [str(hosts)]
                for u in provs.get(prov, {}).get("urls", []):
                    h = _host(u)  # BB5
                    if h and h not in hosts:
                        hosts.append(h)
            else:
                # a MODEL-merged prefix lives in `merged_match`, never in the curated `match`:
                # gather_envs matches on both, registry_sync never feeds a fetcher from one (BH1)
                match = entry.setdefault("merged_match", [])
                if not isinstance(
                    match, list
                ):  # a hand-edited scalar (AF14's sibling, BE3); `null` is empty (BH5)
                    match = entry["merged_match"] = [] if match is None else [str(match)]
                token = prov.upper().rstrip("_")
                tombstone = prov in catalog and tombstone_of(catalog, prov)  # ONE rule (CD1)
                curated_anywhere = {
                    t
                    for other, meta in catalog.items()
                    if not (other == prov and tombstone)  # a surviving CURATED source counts (CA3)
                    for t in _curated_tokens(meta)
                }
                if token in _curated_tokens(entry):
                    pass  # the TARGET routes it already: merged, nothing minted (BW4)
                elif token in curated_anywhere:
                    # another entry routes the token: a merged copy would TIE with it and fail every
                    # scan (BX8). Merged WITHOUT a prefix (the curator keeps routing the key) and said
                    # by name. Unreachable from the scan — a key whose token any entry curates is
                    # routed, never flagged; CA5's own-entry orphan duplicated the target's url and
                    # de-attributed its host (CC3)
                    print(
                        f"  {prov}: merged into {target} without a prefix — {token} is curated elsewhere"
                    )
                elif prov.upper() not in match:
                    match.append(prov.upper())
            if prov in catalog and tombstone_of(catalog, prov):
                # a TOMBSTONE re-tried into another vendor: its own `match: [PROV]` left behind ties
                # with the merged copy and fails every scan from tomorrow, permanently (BX8). A
                # CURATED entry is never popped — that orphaned every key its `match` routed
                # (`CAPTCHA_API_KEY` → anticaptcha, executed at dd55ca81; CA3)
                catalog.pop(prov)
            merged_into[prov] = target
            identified.pop(prov)
    for prov, v in identified.items():
        root = prov.upper()  # FULL provider name — a compound like `aws_bedrock` must match only
        #                      AWS_BEDROCK_* keys, never every AWS_* key (same scoping as C5)
        url = str(v.get("url", "?"))
        if _scheme(url) not in ("http", "https"):
            url = "?"  # a model-authored url reaches the registry and the dashboard's page (AM4)
        # the enum fields are model-authored too and reach the dashboard's class attribute
        # (`cpill`) and the #svc line — anything outside the enum is `?` (AP1/AP2)
        # normalised first: a model's `AI-LLM` / `Freemium` / `ai-llm ` IS the enum value (AS1)
        cost = str(v.get("cost", "?")).strip().lower()
        status = (
            str(v.get("status", "?")).strip().lower()
        )  # an OMITTED status is unknown too (BB4/BE5)
        entry = {
            "category": _enum_category(
                v.get("category")
            ),  # CATEGORIES is a STRING — split, never substring
            "cost": cost if cost in COSTS else "?",
            "capability": " ".join(str(v.get("capability", "?")).split())[:70],
            "url": url,
            "status": status
            if status in STATUSES
            else "?",  # an out-of-enum status is UNKNOWN, never "active" (BB4)
            # a provider seen ONLY as a code call site has no env key behind it: a bare-word
            # match prefix would hijack unrelated vars (`allowed` → ALLOWED_ORIGINS; pass 2)
            "match": [] if code_only_provider(provs.get(prov, {})) else [root],
        }
        # `identified` is enum-gated above, so entry["category"] is never "?" here (AS1/AU1)
        if (
            prov in catalog
        ):  # a curated entry keeps its match/hosts when identified (AF8, mirror of AC11)
            for keep in (
                "match",
                "merged_match",
                "hosts",
            ):  # a merged prefix survives a rewrite/re-stub (BK2)
                if keep in catalog[prov]:
                    entry[keep] = catalog[prov][keep]
        if prov in catalog and not tombstone_of(catalog, prov):
            # the ONE reachable curated shape: a `?` placeholder the operator left with curated
            # routing (`match`/`hosts`/`url`) routes its own key, so its block sits in triage and is
            # dispatched (the daily path and `--only` alike); a real-category entry never gets here
            # (the scan files a key named for it under the entry, CC1). The operator's fields stand,
            # the model fills only what was `?` (CD2 — the class rounds 22–25 argued over, pinned)
            kept = {k: v for k, v in catalog[prov].items() if v not in ("?", None, "", [])}
            kept.pop("category", None)  # the enum verdict is the classifier's — a hand-edited
            # non-str category copied back re-flagged the block every lap, forever (CE3)
            entry = {**entry, **kept}
            if kept:  # never a claim of a keep that did not happen (CJ2)
                print(
                    f"  {prov}: kept the operator's {', '.join(sorted(kept))}"
                )  # not the proposal (CE5)
        catalog[prov] = entry
    if (
        args.only
    ):  # a hand-picked run is not a lap: it neither spends nor records the error budget (AC10)
        err_counts, exhausted = _read_json(ERRORS_PATH, {}), set()
    else:
        err_counts, exhausted = apply_error_budget(
            errored, names, _read_json(ERRORS_PATH, {}), flagged=all_flagged
        )
    if exhausted:
        verb = (
            "tombstoning"
            if args.tombstone_unresolved
            else "eligible for tombstone (--tombstone-unresolved not set)"
        )
        print(
            f"error budget exhausted ({ERROR_BUDGET} runs): {verb} {sorted(exhausted)}"
            " (an entry the catalog already carries is left as it is)"
        )
        errored = errored - exhausted
    tombstoned = 0
    tombstoned_names: list[str] = []
    if args.tombstone_unresolved:
        # Persist a stub for a provider the WEB genuinely could not identify (not one that
        # merely errored — C4) so it drops out of NEEDS-TRIAGE and the daily path stops
        # re-dispatching a paid pool call for it forever. The category MUST be non-"?" —
        # gather_envs buckets NEEDS-TRIAGE purely on category=="?", so a "?" stub would
        # stay in triage and defeat the whole point (C2). The full provider name is the
        # match prefix (not split on "_") so `aws_bedrock` doesn't swallow every AWS_* key (C5).
        for prov in names:
            if prov in identified or prov in errored or prov in merged_into:
                continue  # a merged host joined its vendor — never also a stub (AF2)
            _cat = catalog[prov].get("category") if prov in catalog else None
            if isinstance(_cat, str) and _cat and _cat != "?":  # == gather_envs.real_category (CM3)
                # a real entry — the SAME predicate the scan buckets on (Z10; CE3's mirror, CJ3): a
                # non-str category buckets to `?` there, so treating it as real here re-billed it daily
                continue
            stub = tombstone_entry(prov, code_only=code_only_provider(provs.get(prov, {})))
            if prov in catalog:  # a curated `?` entry keeps its match/hosts when re-stubbed (AC11)
                for keep in (
                    "match",
                    "merged_match",
                    "hosts",
                ):  # a merged prefix survives a rewrite/re-stub (BK2)
                    if keep in catalog[prov]:
                        stub[keep] = catalog[prov][keep]
                for keep in ("cost", "capability", "url", "status"):
                    if catalog[prov].get(keep) not in (None, "", "?"):
                        stub[keep] = catalog[prov][
                            keep
                        ]  # an unidentifiable answer never erases the operator's words (CE4)
            catalog[prov] = stub
            tombstoned += 1
            tombstoned_names.append(prov)
    tmp = CATALOG_PATH.with_name(CATALOG_PATH.name + ".tmp")  # atomic: no torn/corrupt JSON
    tmp.write_text(
        json.dumps({**catalog_meta, **catalog}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, CATALOG_PATH)
    if not args.only:  # a hand-picked run is not a lap: it moves neither the budget nor the cursor
        _write_json(ERRORS_PATH, err_counts)
    _write_json(
        LAST_RUN_PATH if not args.only else STATE_DIR / "classify_last_only.json",
        {
            "identified": sorted(identified),
            "tombstoned": sorted(tombstoned_names),
            "errored": sorted(errored),
        },
    )
    if identified:  # the retired orchestrator's "new providers" alert, kept (best-effort)
        try:
            sys.path.insert(0, str(REPO / "libs"))
            from alerting import send_alert  # noqa: PLC0415 - optional, box-local

            send_alert(
                "service-registry: new providers",
                f"classified {len(identified)}: {', '.join(sorted(identified))}",
                "info",
            )
        except Exception as exc:  # noqa: BLE001 - alerting is best-effort
            print(f"  (alert skipped: {exc})", file=sys.stderr)
    if merged_into:
        print(
            "merged into existing entries: "
            + ", ".join(f"{k} → {v}" for k, v in sorted(merged_into.items()))
        )
    print(
        f"\nWrote {len(identified)} identified"
        + (f" + {tombstoned} unidentified-stub" if tombstoned else "")
        + f" providers into {CATALOG_PATH}. "
        "Re-run scripts/gather_envs.py --apply to refresh all-envs.env."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
