"""The view registry: the six views in navigation order and the protocol each view module follows
(plan 2026-10-17-plan-1, T02).

A view lives in ``dashboard_ui/views/<name>.py`` and defines ``render(data, ctx) -> ViewResult``; it
MAY define ``collect(ctx) -> dict``, whose keys the server merges over the data it hands in
(`quota_dashboard._view_data`). A view is a pure renderer: it never imports the dashboard module,
which runs as ``__main__`` — every value it needs from there arrives in ``data``. The server wraps
the returned markup in the fragment's root element, which carries ``data-stamp`` (`stamp`), so
`app.js` can skip a swap whose markup did not change.
"""

# AFTER-EDIT: docs/workstation/quota-dashboard.md

from __future__ import annotations

import hashlib
import importlib
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from ..components import Safe

__all__ = ["VIEWS", "ViewContext", "ViewResult", "load", "stamp"]

VIEWS = ("overview", "work", "accounts", "usage", "commands", "services")


@dataclass(frozen=True)
class ViewContext:
    """What every view may read besides its data: the /opt root, the hub root and the request's clock."""

    opt_root: Path
    fabrik_root: Path
    now: float


@dataclass(frozen=True)
class ViewResult:
    """A view's markup, and the action targets it rendered (the entries the dashboard's
    `_publish_pause_targets` / `_publish_item_targets` take) — ``None`` when it renders none."""

    html: Safe
    pause_targets: list[dict] | None = None
    item_targets: list[dict] | None = None


def load(name: str) -> ModuleType:
    """The view module ``dashboard_ui.views.<name>``; `LookupError` for a name outside `VIEWS`, a
    missing module, or one without a callable ``render``. An import error INSIDE a present module
    propagates as itself — that is a broken view, not a missing one."""
    if name not in VIEWS:
        raise LookupError(f"no view named {name!r}")
    qualified = f"{__name__}.{name}"
    try:
        mod = importlib.import_module(qualified)
    except ModuleNotFoundError as exc:
        if exc.name != qualified:
            raise
        raise LookupError(f"view {name!r} is not built") from exc
    if not callable(getattr(mod, "render", None)):
        raise LookupError(f"view {name!r} defines no render()")
    return mod


def stamp(markup: str) -> str:
    """The fragment's ``data-stamp``: 16 hex characters of sha256 over its markup."""
    return hashlib.sha256(markup.encode("utf-8", "surrogatepass")).hexdigest()[:16]
