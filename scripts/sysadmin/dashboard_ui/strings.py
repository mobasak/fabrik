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
