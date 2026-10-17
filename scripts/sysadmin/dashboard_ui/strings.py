"""The dashboard's string catalogue — every user-visible word the page layer writes (D-926, DT6).

`t(key, **fields)` looks the key up in the ACTIVE catalogue and fills its `{field}` slots with
`str.format`; an unknown key raises `KeyError`, so a typo is loud, never a blank. `use(mapping)` swaps
the active catalogue for the duration of a `with` block — the stand-in-locale test, and the seam a
second language would use: adding one is a mapping with the same keys, never an edit to a component.
The shell hands this whole catalogue to `app.js` as inert JSON, so the script's words come from here too.

Cobra check (D-253): the cheapest way to satisfy "every word comes from the catalogue" without the
outcome is a key whose value is a whole sentence glued from caller text — a component that writes
`t("x", text=<English>)`. The tests render every component under a stand-in catalogue and assert no
catalogue-owned English survives; caller-supplied text is the caller's catalogue lookup to make.
"""

# AFTER-EDIT: docs/workstation/quota-dashboard.md

from __future__ import annotations

import contextlib
import contextvars
from collections.abc import Iterator, Mapping

CATALOGUE: dict[str, str] = {
    "app.lang": "en",
    "app.title": "Command centre",
    "shell.skip": "Skip to content",
    "shell.menu": "Menu",
    "shell.nav_label": "Views",
    "shell.theme.system": "Theme: system",
    "shell.theme.light": "Theme: light",
    "shell.theme.dark": "Theme: dark",
    "sev.critical": "Critical",
    "sev.warning": "Warning",
    "sev.ok": "OK",
    "sev.info": "Info",
    "sev.neutral": "Neutral",
    "dialog.note.optional": "Note (optional)",
    "dialog.note.required": "Reason (required)",
    "clamp.more": "Show all",
    "clamp.less": "Show less",
    "state.loading": "Loading…",
    "state.still_loading": "Still loading…",
    "state.too_long": "This is taking too long. Please try again.",
    "state.failed": "This view could not be loaded.",
    "state.broken": "This view loaded but could not be shown. Reload the page; if it happens again, the view has a fault.",
    "state.retry": "Retry",
    "fresh.read_at": "Read at {time}",
    "fresh.never": "Not read yet",
    "fresh.ago_s": "Read {n} s ago",
    "fresh.ago_min": "Read {n} min ago",
    "fresh.ago_h": "Read {n} h ago",
    "fresh.stale": "Stale — {age}",
    "fresh.went_stale": "Some figures on this view are stale.",
    "stale.banner": "Stale page: what you see was rendered {age} ago, and {cause}.",
    "stale.age_s": "{n} s",
    "stale.age_min": "{n} min",
    "stale.age_unknown": "an unknown time",
    "stale.cause.failed": "the last probe failed at {time} with {error}; the details are in the dashboard log",
    "stale.cause.old": "no probe has finished since — a probe may be hung or still running",
    "view.failed": "This view could not be built ({error}). Try again; if it keeps failing, the dashboard log has the details.",
    "act.done": "Done.",
    "act.changed": "This item changed since the view was loaded. The view was reloaded; check it and try again.",
    "act.diverged": "The board's copy of this repo is out of step with its main checkout, so nothing was sent. Sync the checkout, then try again.",
    "act.failed": "That did not work: {error}",
    "act.unreachable": "The board did not answer. Reload the view to see whether the change landed.",
    "act.clear": "clear",
    "act.refuse.text": "Type a comment first.",
    "act.refuse.note": "Give a reason before confirming.",
    "act.refuse.required": "Enter a value first.",
    "act.refuse.range": "Enter a number from {min} to {max}.",
    "act.refuse.range_or_empty": "Enter a number from {min} to {max}, or leave it empty.",
    "act.refuse.whole": "Enter a whole number from {min} to {max}.",
    "act.refuse.whole_or_empty": "Enter a whole number from {min} to {max}, or leave it empty.",
    "act.refuse.confirm": "This action needs a confirmation step the page does not have. Nothing was sent.",
    "act.refuse.no_reason": "This action needs a reason, but the page has no place to give one. Nothing was sent.",
    "act.refuse.no_field": "The field this action reads is missing from the page. Nothing was sent.",
    "act.refuse.path": "This button has no valid action. Nothing was sent.",
    "link.new_tab": "(opens in a new tab)",
    "usage.title": "Claude subscription spend by tier",
    "usage.intro": "All Claude Code and claude -p usage over {window} ({tokens} tokens), {priced} Weights: haiku 1x, sonnet 2x, opus 5x, fable 10x. Base ${base}/MTok at weight 1. Sum of tiers: {recon} This is an allocation, not an invoice: the subscription is a flat fee with no per-model billing, and the weights are an operator assumption matching the list-price ratio 1:2:5:10. Rebuilt by the 06:00 cron; last built {built}.",
    "usage.priced_fee": "priced against ${spend} - what the ${fee}/month subscription costs over these {days} days ({note}), since a rolling window is not a calendar month.",
    "usage.priced_plain": "priced against ${spend} for that window.",
    "usage.recon_ok": "reconciles to ${spend}.",
    "usage.recon_bad": "DOES NOT reconcile: ${total} vs ${spend}.",
    "usage.fee_part": "{n} {month} day(s) at ${fee}/{dim}",
    "usage.unclassified": "{tokens} tokens are NOT in any total on this page - no tier matched {names}. Add the tier to _TIER_WEIGHT in scripts/claude_p_cost.py; until then that spend is unallocated and those days are missing from the calendar.",
    "usage.unclassified_title": "Unclassified tokens",
    "usage.empty": "No tier-weighted spend is recorded yet, so no table is shown (an empty table would read as $0 spent).",
    "usage.error": "The spend sidecar could not be read: {error}",
    "usage.col.tier": "Tier",
    "usage.col.weight": "Weight",
    "usage.col.tokens": "Tokens",
    "usage.col.share": "Share",
    "usage.col.rate": "$/MTok",
    "usage.col.cost": "Cost",
    "usage.table": "Spend by tier",
    "usage.cal.title": "Daily token consumption",
    "usage.cal.intro": "Every recorded day, newest month first, with its share of the busiest day ({peak} tokens). Every day is priced on a rolling 30-day window ending that day - the fee pro-rated across the months it crosses, over the tokens actually run in it - so a month block totals what its days consumed at the rate prevailing around them, not that month's invoice.",
    "usage.cal.month": "{label}: {tokens}B tokens, ${cost}{fee}",
    "usage.cal.fee": ", fee ${fee}/mo",
    "usage.cal.caption": "Days of {label}",
    "usage.cal.col.date": "Date",
    "usage.cal.col.tokens": "Tokens",
    "usage.cal.col.cost": "Cost",
    "usage.cal.col.peak": "Of peak day",
    "usage.cal.col.tiers": "Per tier",
    "usage.cal.no_usage": "no usage",
    "commands.title": "Commands",
    "commands.intro": "Every /fabrik-* command in pipeline order ({n} sources under commands/_sources/, read live - purpose, when-to-use and skip-when come from each command's own description, the successor from the assembler's NEXT map). Stages run top to bottom; gates are invoked at boundaries; utilities at any point.",
    "commands.unreadable": "Command corpus unreadable - no commands/_sources/fabrik-*.md under {root}.",
    "commands.error": "The command catalogue could not be read: {error}",
    "commands.tab.list": "Commands",
    "commands.tab.matrix": "Service matrix",
    "commands.tabs": "Command views",
    "commands.find": "Find a command",
    "commands.table": "Commands in pipeline order",
    "commands.col.n": "#",
    "commands.col.command": "Command",
    "commands.col.stage": "Stage",
    "commands.col.purpose": "Purpose",
    "commands.col.when": "When to use",
    "commands.col.skip": "Skip when",
    "commands.col.next": "Next",
    "commands.col.natives": "Native subagents",
    "commands.col.tiers": "Model tiers",
    "commands.natives.help": "Native subagents: the Claude Task subagent types the command's live text names (the pool is OFF by ruling, D-181/D-182 - every fan-out is native), with the model tier beside each. Seats per round first - the command's own dispatch rule: an Opus authoritative floor where it has one, plus one seat per independent unit of the surface (D-186), so the seat count is the unit count, never a fixed number.",
    "commands.tiers.help": "Model tiers: every tier the command's own steps name - including one no seat mention is near, like a tiering paragraph's Haiku only for trivial-mechanical checks.",
    "commands.detail": "Detail of /{name}",
    "commands.none": "-",
    "commands.floor_opus": "at least 1 opus",
    "commands.per_unit": "1 per {units}",
    "commands.no_rule": "no per-unit rule",
    "commands.matrix.intro": "Which outside-the-box service each command actually reaches - read from the corpus itself ({rendered} of {n} rows from the rendered commands under {root}), so the dots are never typed here. A dot means the command names that service's own invocation token (fanout(, WebSearch, mcp__firecrawl, fabrik apply) - not that it merely mentions the service in prose. Read it as a good index, not a proof: it is a literal text match over the command, so it reads no negations (a token named only to say it does not apply is still credited), and it re-reads a command when that file's mtime or size changes. The columns are the one hand-held half: adding a new external service to the fleet means adding a row to _EXT_SERVICES in scripts/sysadmin/quota_dashboard.py.",
    "commands.matrix.caveat": "{k} of {n} rows did NOT come from the rendered corpus ({names}{more}) - they fell back to _sources/, or could not be read at all. The assembler appends the shared pool and mail fragments, so they UNDER-report; re-render with commands/assemble_commands.py from master.",
    "commands.matrix.table": "Command by outside service",
    "commands.matrix.col.command": "Command",
    "commands.matrix.dot": "uses",
    "commands.matrix.nodot": "does not use",
    "commands.matrix.total": "of {n}",
    "services.title": "Services",
    "services.pool.title": "OpenRouter pool",
    "services.pool.line": "${remaining} remaining of ${granted}{age}{note}",
    "services.pool.exhausted": " - EXHAUSTED: every fanout() returns HTTP 402 with no output and no spend. Top up at openrouter.ai/settings/credits.",
    "services.pool.low": " - under ${warn}; a long fan-out will hit HTTP 402 mid-run. Top up at openrouter.ai/settings/credits.",
    "services.pool.stale": " - cached {age} s ago, endpoint unreachable",
    "services.pool.unreadable": "Pool balance UNREADABLE - {why} while reading the cached balance. The OpenRouter figure is simply missing, not zero.",
    "services.pool.unconfigured": "The OpenRouter pool is not configured on this box, or no balance is cached yet, so no balance is shown.",
    "services.pool.error": "The pool balance could not be read: {error}",
    "services.apis.title": "Search-API quota and renewal",
    "services.apis.intro": "What is left of the three metered search services the matrix tracks, and when each renews - {stamp}, refreshed every {min} min off the render path (a probe costs Brave one query). A blank is never shown: a value we cannot obtain says why.",
    "services.apis.stamp_none": "not read yet",
    "services.apis.stamp_future": "stamped in the future - clock skew",
    "services.apis.stamp_age": "read {min} min ago",
    "services.apis.error": "The search-API quotas could not be read: {error}",
    "services.apis.empty": "No search-API quota has been read yet.",
    "services.apis.table": "Search-API quotas",
    "services.apis.col.service": "Service",
    "services.apis.col.plan": "Plan",
    "services.apis.col.remaining": "Remaining",
    "services.apis.col.renews": "Renews",
    "services.apis.stale": "reading out of date",
    "services.apis.unlimited": "unlimited",
    "services.apis.nocap": "n/a - no monthly cap",
    "services.apis.overdue": "overdue",
    "services.apis.why.unconfigured": "no API key configured on this box",
    "services.apis.why.unavailable": "not exposed by the provider's API",
    "services.apis.why.no-headers": "the provider stopped sending its rate-limit headers",
    "services.apis.why.no-data": "the provider's response carried no credit fields",
    "services.apis.why.error": "probe failed ({error})",
    "services.apis.why.unread": "not read yet",
    "services.ext.title": "External services",
    "services.ext.missing": "External-services page not generated yet - expected at {path}, written daily by the external-services chain.",
    "services.ext.age": "The fleet's external services and credentials inventory, regenerated {hours} h ago by the daily chain (scripts/gen_dashboard.py, 06:00).",
    "services.ext.open": "Open the external-services page",
}

# per thread / per task: a `use` block in one request never leaks into another's render
_active: contextvars.ContextVar[Mapping[str, str]] = contextvars.ContextVar(
    "catalogue", default=CATALOGUE
)


def t(key: str, **fields: object) -> str:
    """The active catalogue's text for ``key``, its ``{field}`` slots filled; ``KeyError`` if the key
    is unknown or a slot is left unfilled (a raw ``{error}`` never reaches the page)."""
    return _active.get()[key].format(**fields)


def active() -> Mapping[str, str]:
    """The catalogue in force — what the shell hands to the script."""
    return _active.get()


@contextlib.contextmanager
def use(mapping: Mapping[str, str]) -> Iterator[None]:
    """Make ``mapping`` the active catalogue inside the block, restoring the previous one after."""
    token = _active.set(mapping)
    try:
        yield
    finally:
        _active.reset(token)
