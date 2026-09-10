# AFTER-EDIT: none
"""Price the fleet's REAL token usage from ~/.claude/.claude-manager/usage-history.json.

An AUDIT tool, deliberately separate from derive_cost.py: that module answers "what did THIS run
cost" for benchmark scoring (a 30-day rate + per-run valuation); this one answers "what has the
fleet actually consumed, per month and per model, and what would it have cost on the metered API".
They share a subject and nothing else.

PROVENANCE — measured by the fleet agent 2026-09-04 (mail 01M1PTQ5QXJR0AAGW3YYG3HHWE) at the
operator's direction, and reproduced byte-for-byte by intel before this file was committed:
111 days (2026-05-13 → 2026-09-04), 298,137.5M tokens, $230,838 - $262,014 API-equivalent,
Jun+Jul+Aug amortizing to $0.00764/MTok against $2,000 of subscriptions. It was living in an
ephemeral session scratchpad; committing it is the point of this file.

WHY THE RANGE IS THE ONLY ESTIMATE: cache writes bill 1.25x base input on a 5-minute TTL and 2x on
a 1-hour TTL, and usage-history does not record which. Everything else is exact.

⚠️ THREE MODELLING TRAPS this script exists to keep visible (fleet's analysis, all three verified):
  1. The amortized rate is BACKWARD-LOOKING and VOLUME-DEPENDENT — $0.01437/MTok in June,
     $0.00558 in July, $0.00712 in August, on a near-fixed cost. Never store it as a bare float;
     store the window, the accounts and the spend beside it.
  2. The MARGINAL cost of a subscription token is ZERO while an account has headroom, and when the
     headroom is gone the cost is a BLOCKED AGENT, not a dollar. A router comparing the amortized
     rate against a metered pool $/MTok as if they were the same unit will over-use the pool.
  3. Cache reads are 96-98% of all volume, so any model that does not keep the four counters
     separate is wrong by roughly 10x on the input side.

⚠️ The price table below is a DATED SNAPSHOT read 2026-09-04. Re-verify before trusting it: Opus
4.5 through 5 are $5/$25 while the RETIRED 4.1 and 4 are $15/$75, so a table that carries the old
opus price overstates the fleet's largest line by 3x.

Usage: python3 scripts/kilo-benchmarks/audit_usage_cost.py
"""

import json
import pathlib
from collections import defaultdict

M = 1e6

# Anthropic list prices per MTok, read 2026-09-04 from
# platform.claude.com/docs/en/about-claude/pricing — (base_input, 5m_cache_write, cache_read, output).
# Longest-prefix match, so `claude-opus-4-8` beats a bare `claude-opus-4`.
PRICES: list[tuple[str, tuple[float, float, float, float]]] = [
    ("claude-fable-5-1", (10, 12.5, 0.25, 50)),
    ("claude-mythos-5-1", (10, 12.5, 0.25, 50)),
    ("claude-fable-5", (10, 12.5, 1.0, 50)),
    ("claude-mythos-5", (10, 12.5, 1.0, 50)),
    ("claude-opus-5", (5, 6.25, 0.5, 25)),
    ("claude-opus-4-8", (5, 6.25, 0.5, 25)),
    ("claude-opus-4-7", (5, 6.25, 0.5, 25)),
    ("claude-opus-4-6", (5, 6.25, 0.5, 25)),
    ("claude-opus-4-5", (5, 6.25, 0.5, 25)),
    ("claude-opus-4-1", (15, 18.75, 1.5, 75)),  # RETIRED — 3x the 4.5+ price
    ("claude-opus-4", (15, 18.75, 1.5, 75)),  # RETIRED
    ("claude-sonnet-5", (2, 2.5, 0.2, 10)),
    ("claude-sonnet-4-6", (3, 3.75, 0.3, 15)),
    ("claude-sonnet-4-5", (3, 3.75, 0.3, 15)),
    ("claude-sonnet-4", (3, 3.75, 0.3, 15)),
    ("claude-haiku-4-5", (1, 1.25, 0.1, 5)),
    ("claude-haiku-3-5", (0.8, 1.0, 0.08, 4)),
]

USAGE_HISTORY = pathlib.Path.home() / ".claude" / ".claude-manager" / "usage-history.json"


def price_for(model: str) -> tuple[float, float, float, float] | None:
    """Longest-prefix price lookup; None means the model is unpriced and is reported as such."""
    best = None
    for prefix, row in PRICES:
        if model.startswith(prefix) and (best is None or len(prefix) > len(best[0])):
            best = (prefix, row)
    return best[1] if best else None


def main() -> int:
    data = json.loads(USAGE_HISTORY.read_text())
    by_month: dict[str, dict] = defaultdict(
        lambda: {"lo": 0.0, "hi": 0.0, "tok": 0, "cache_read": 0}
    )
    by_model: dict[str, dict] = defaultdict(lambda: {"lo": 0.0, "hi": 0.0, "tok": 0})
    unpriced: dict[str, int] = defaultdict(int)

    for day, record in sorted(data["days"].items()):
        month = day[:7]
        for model, use in (record.get("byModel") or {}).items():
            inp = use.get("input", 0)
            out = use.get("output", 0)
            cache_read = use.get("cacheRead", 0)
            cache_write = use.get("cacheCreation", 0)
            row = price_for(model)
            if row is None:
                unpriced[model] += inp + out + cache_read + cache_write
                continue
            p_in, p_write5m, p_read, p_out = row
            base = (inp * p_in + cache_read * p_read + out * p_out) / M
            lo = base + cache_write * p_write5m / M  # 5-minute TTL writes bill 1.25x input
            hi = base + cache_write * p_in * 2 / M  # 1-hour TTL writes bill 2x input
            total = inp + out + cache_read + cache_write
            for bucket in (by_month[month], by_model[model]):
                bucket["lo"] += lo
                bucket["hi"] += hi
                bucket["tok"] += total
            by_month[month]["cache_read"] += cache_read

    print(f"{'MONTH':10} {'tokens':>12} {'cache-read':>10}  {'API cost (5m - 1h writes)':>30}")
    tot_lo = tot_hi = tot_tok = 0.0
    for month in sorted(by_month):
        b = by_month[month]
        tot_lo += b["lo"]
        tot_hi += b["hi"]
        tot_tok += b["tok"]
        share = 100 * b["cache_read"] / b["tok"] if b["tok"] else 0.0
        print(
            f"{month:10} {b['tok'] / M:11,.1f}M {share:9.1f}%  ${b['lo']:12,.2f} - ${b['hi']:12,.2f}"
        )
    print(f"{'TOTAL':10} {tot_tok / M:11,.1f}M            ${tot_lo:12,.2f} - ${tot_hi:12,.2f}")

    print("\nBY MODEL")
    for model in sorted(by_model, key=lambda k: -by_model[k]["lo"]):
        b = by_model[model]
        if b["tok"]:
            print(f"  {model:28} {b['tok'] / M:11,.1f}M  ${b['lo']:11,.2f} - ${b['hi']:11,.2f}")
    if unpriced:
        print("UNPRICED (no price row — excluded from every total above):", dict(unpriced))

    window = ("2026-06", "2026-07", "2026-08")
    w_lo = sum(by_month[m]["lo"] for m in window if m in by_month)
    w_hi = sum(by_month[m]["hi"] for m in window if m in by_month)
    w_tok = sum(by_month[m]["tok"] for m in window if m in by_month)
    paid = 2000.0  # 3 + 3 + 4 accounts across Jun/Jul/Aug
    print(
        f"\nJUN+JUL+AUG: {w_tok / M:,.1f}M tok  ${w_lo:,.2f} - ${w_hi:,.2f}"
        f"  vs ${paid:,.0f} paid -> {w_lo / paid:.1f}x - {w_hi / paid:.1f}x"
    )
    print(f"amortized subscription rate, that window: ${paid / (w_tok / M):.5f} per MTok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
