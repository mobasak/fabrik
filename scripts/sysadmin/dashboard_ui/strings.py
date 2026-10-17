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
    # ---- the Overview view (T03)
    "ov.summary.title": "Summary",
    "ov.dec.title": "Decisions waiting",
    "ov.merge.title": "Blocked merges",
    "ov.agents.title": "Agents",
    "ov.quota.title": "Quota",
    "ov.health.title": "Health",
    "ov.section_failed": "This section could not be built ({error}).",
    "ov.dur.s": "{n} s",
    "ov.dur.min": "{n} min",
    "ov.dur.h": "{n} h",
    "ov.dur.d": "{n} d",
    "ov.dur.unknown": "an unknown time",
    "ov.sum.decisions": "{repo}: {n} waiting, oldest {age}",
    "ov.sum.no_decisions": "Nothing waiting on you",
    "ov.sum.work_error": "Decisions unreadable",
    "ov.sum.merges": "{n} blocked merges",
    "ov.sum.agents": "{n} agents not working",
    "ov.sum.band": "Band {band} · {account}",
    "ov.sum.band_unknown": "Band unknown",
    "ov.sum.health": "{n} health faults",
    "ov.sum.healthy": "No health faults",
    "ov.dec.none": "Nothing waiting on you",
    "ov.dec.error": "The work stores could not be read: {error}",
    "ov.dec.repo_error": "{repo}: the work store could not be read — {error}",
    "ov.dec.skipped": "{repo}: {n} unreadable work-store files skipped",
    "ov.dec.group": "{repo} — {n} waiting",
    "ov.dec.more": "Showing the five oldest of {n}.",
    "ov.dec.more_link": "See every item of {repo} in Work",
    "ov.dec.card_title": "{id} — {title}",
    "ov.dec.no_title": "(no title)",
    "ov.dec.no_question": "(no question recorded)",
    "ov.dec.asker": "Asked by {who}",
    "ov.dec.asker_unknown": "Asker unknown",
    "ov.dec.wait": "Waiting {age}",
    "ov.ground.gate": "Gate",
    "ov.ground.owned": "Owned",
    "ov.ground.underivable": "Underivable",
    "ov.ground.none": "No ground",
    "ov.ground.other": "Ground: {ground}",
    "ov.dec.accept": "Accept",
    "ov.dec.reject": "Reject",
    "ov.dec.comment": "Comment",
    "ov.dec.comment_label": "Comment on {id}",
    "ov.dec.accept_title": "Accept {id}?",
    "ov.dec.accept_consequence": "Accepting authorises the asking agent to act on this. A verdict cannot be undone.",
    "ov.dec.accept_confirm": "Accept {id}",
    "ov.dec.reject_title": "Reject {id}?",
    "ov.dec.reject_consequence": "Rejecting refuses the request; your reason is recorded with the verdict.",
    "ov.dec.reject_confirm": "Reject {id}",
    "ov.dec.keep": "Keep waiting",
    "ov.merge.none": "No blocked merges",
    "ov.merge.error": "The merge records could not be read: {error}",
    "ov.merge.badge": "Blocked",
    "ov.merge.card_title": "{repo} · {branch}",
    "ov.merge.item": "Item: {item}",
    "ov.merge.no_item": "Item: none",
    "ov.merge.requester": "Requested by {who}",
    "ov.merge.reason": "Reason: {reason}",
    "ov.merge.owner": "Next step: {owner}, the merge owner, resolves it",
    "ov.merge.owner_unresolved": "Merge owner unresolved: {error}",
    "ov.merge.age": "{age} ago",
    "ov.ag.counts": "{working} working · {idle} idle · {stale} stale · {away} with no window · {quiet} repos with no recent agent",
    "ov.ag.error": "The agents could not be read: {error}",
    "ov.ag.repo_error": "{repo}: its agents could not be read — {error}",
    "ov.ag.dormant": "{repo}: {n} dormant (seen over 7 days ago)",
    "ov.ag.none": "No agent seen in any repo",
    "ov.ag.table": "Agents in {repo}",
    "ov.ag.h.agent": "Agent",
    "ov.ag.h.state": "State",
    "ov.ag.h.now": "Now",
    "ov.ag.h.holds": "Holds",
    "ov.ag.h.next": "Next",
    "ov.ag.h.merge": "Last merge",
    "ov.ag.state.working": "working",
    "ov.ag.state.idle": "idle — window open, no running command",
    "ov.ag.state.stale": "stale — its running command is over 12 h old",
    "ov.ag.state.away": "no window open",
    "ov.ag.now": "/{command}",
    "ov.ag.phase": "phase {phase}/{phases}",
    "ov.ag.updated": "updated {age} ago",
    "ov.ag.stale_note": "its running command is over 12 h old",
    "ov.ag.no_command": "no running command",
    "ov.ag.dash": "—",
    "ov.ag.item": "{id} {title}",
    "ov.ag.more_queued": "+{n} more queued",
    "ov.ag.nothing_queued": "nothing queued",
    "ov.ag.merge": "{sha} {age} ago",
    "ov.ag.merge_owner": "merge owner (merges others)",
    "ov.ag.named": "named from its last run",
    "ov.ag.windows": "{n} windows",
    "ov.ag.paused": "paused by {by}, {age} ago",
    "ov.ag.paused_partial": "only some of its windows",
    "ov.ag.paused_why": "why: {why}",
    "ov.ag.not_honoured": "not honoured here until this repo's work.py syncs",
    "ov.ag.pause": "Pause",
    "ov.ag.resume": "Resume",
    "ov.ag.pause_title": "Pause {agent} in {repo}?",
    "ov.ag.pause_body": "{agent} stops starting new work at its next turn boundary. Resume undoes it.",
    "ov.ag.pause_confirm": "Pause {agent}",
    "ov.ag.pause_cancel": "Keep running",
    "ov.ag.resume_title": "Resume {agent} in {repo}?",
    "ov.ag.resume_body": "This lifts every pause marker listed: {names}. The first was set by {by}.",
    "ov.ag.resume_confirm": "Resume {agent}",
    "ov.ag.resume_cancel": "Keep paused",
    "ov.q.none": "No quota reading: {error}",
    "ov.q.band": "Band {band}",
    "ov.q.band_on": "Band {band} on {window}",
    "ov.q.band_fable": "Fable band {band}",
    "ov.q.active": "Active account: {account}",
    "ov.q.successor": "Successor: {account}",
    "ov.q.no_successor": "Successor: none",
    "ov.q.window": "{window}: {pct}% used ({slug}) · resets {reset}",
    "ov.q.window_none": "{window}: no reading · resets {reset}",
    "ov.q.w.five_hour": "5 h",
    "ov.q.w.seven_day": "Weekly",
    "ov.q.w.fable": "Fable",
    "ov.q.hold": "Hold: {tier}",
    "ov.q.relief": "Next relief: {account} at {when} ({window} window)",
    "ov.q.probe_failed": "Probe failed: {error}",
    "ov.h.ok": "No health faults",
    "ov.h.stale": "The {view} view's data is stale ({age} old)",
    "ov.h.failed": "{name} failed: {error}",
    "ov.h.unreadable": "{n} merge records could not be read",
    "ov.h.budget": "Box budget: {seats} · CLI cap {cli_cap} · {quota}",
    "ov.h.budget_seat": "{label} seats allowed now: {allowed} (box {box}, {taken} reserved by sibling sessions)",
    "ov.h.seat.read_only": "read-only",
    "ov.h.seat.heavy": "heavy",
    "ov.h.budget_hold": "fleet hold — dispatch nothing until relief",
    "ov.h.budget_quota": "quota: active {active} at {pct}%, {eligible} cool standbys of {raw} eligible",
    "ov.h.budget_quota_unknown": "quota: unknown",
    "ov.h.budget_caveats": "Caveats: {caveats}",
    "ov.h.budget_computing": "Box budget: computing…",
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
