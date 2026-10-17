"""The Work view: per-repo queues with the verdict controls and the filters (plan 2026-10-17-plan-1, T04).

Carries over today's Repos tab (`quota_dashboard._repos_page` / `_repo_pane`): the repo picker with fabrik
first (D-738), an owner chip per hub agent and the empty owner even at 0 (D-745), per-owner item tables
with Accept / Reject / Comment under the rule of D-917 (Accept and Reject on every open item except an
awaiting non-decision; Comment on every item), the tag filter and the skipped-store list. A pure
renderer: it receives `_view_data("work")` and writes only through `components`.

Behaviour lives in the attributes `app.js` reads: ``data-pick-group`` / ``data-pick`` / ``data-pick-to``
(the repo picker, ``/#work/<repo>``), ``data-filter-group`` with ``data-filter`` chips and a token tag box
over ``data-f-owner`` / ``data-f-tag``, and ``data-post`` / ``data-body`` / ``data-confirm`` /
``data-note`` / ``data-text-from`` on the verdict buttons. Every verdict body carries
`snapshot.token(item)`, so the server refuses a verdict on an item that changed under the operator's eyes.

Cobra check (D-253): the cheapest way to pass "every verdict is token-guarded" without the outcome is a
token computed from something other than the card's item; the tests compare each body's token to
`snapshot.token` of the item the row was built from.
"""

# AFTER-EDIT: docs/workstation/quota-dashboard.md

from __future__ import annotations

from urllib.parse import quote

from .. import components as ui
from .. import fmt, snapshot
from ..strings import t
from . import ViewContext, ViewResult

__all__ = ["render"]

_VERDICT_PATH = "/item-verdict"


def _owner_token(owner: str) -> str:
    """The owner as one whitespace-free, reversible filter token (the chip and its section agree on it).
    Percent-encoding keeps "a b" and "a_b" apart; the empty owner is a lone "%", which no encoded
    owner can be (an encoded "%" is always "%25")."""
    return quote(owner, safe="", errors="surrogatepass") if owner else "%"


def _tags(item: dict) -> list[str]:
    raw = item.get("tags") or []
    return [str(x) for x in (raw if isinstance(raw, list) else [raw]) if x]


def _owner_of(item: dict) -> str:
    # a decision waiting on the operator carries no owner: it is the operator's (W-7159f8e2)
    owner = str(item.get("owner") or "")
    return "operator" if not owner and item.get("status") == "awaiting-operator" else owner


def _owner_order(data: dict, name: str, groups: dict[str, list[dict]]) -> list[str]:
    given = data.get("owner_order")
    given = given.get(name) if isinstance(given, dict) else None
    if isinstance(given, list):
        order = [str(o) for o in given]
    else:
        hub = [str(a) for a in data.get("hub_agents") or []]
        order = hub + (["operator"] if "operator" not in hub else []) + [""]
    return order + sorted(o for o in groups if o not in order)


def _severity(status: str) -> str:
    return {"awaiting-operator": "warning", "blocked": "critical", "open": "info"}.get(
        status, "neutral"
    )


def _count(rows: list[dict], status: str) -> int:
    return sum(1 for i in rows if i.get("status") == status)


def _claimed(rows: list[dict]) -> int:
    return sum(1 for i in rows if i.get("_claim"))


def _last_comment(item: dict) -> ui.Safe | None:
    raw = item.get("comments")
    log = raw if isinstance(raw, list) else []
    last = log[-1] if log and isinstance(log[-1], dict) else None
    if last is None:
        return None
    fields = {
        "by": last.get("by") or t("work.by_default"),
        "action": last.get("action") or t("work.action_default"),
    }
    words = fmt.cap(str(last.get("text") or ""), 120)
    line = t("work.last", text=words, **fields) if words else t("work.last_bare", **fields)
    when = fmt.ago(last.get("at"))
    if when:
        line += f", {when}"
    if len(log) > 1:
        line += t("work.last_more", n=len(log))
    return ui.group(line, tag="span")


def _verdict_cell(repo: str, item: dict, slot: str) -> tuple[ui.Safe, list[ui.Safe]]:
    """The Operator cell and the dialogs its buttons name (the dialogs sit beside the table)."""
    raw_id = item.get("id")
    iid = raw_id if isinstance(raw_id, str) else ""
    if not iid:  # the server would 400 it and ids would collide: no controls, only what was said
        return ui.fragment(_last_comment(item), t("work.no_id")), []
    key = f"{repo}\0{slot}\0{iid}"  # slot: owner + occurrence of this id, so equal ids never share an element id
    body = {"repo": repo, "item": iid, "token": snapshot.token(item)}
    parts: list[object] = [_last_comment(item)]
    dialogs: list[ui.Safe] = []
    if not (item.get("status") == "awaiting-operator" and item.get("kind") != "decision"):
        question = str(item.get("question") or item.get("title") or iid)
        quoted = ui.fragment(t("work.dialog.lead"), " ", ui.group(question, tag="span"))
        for action, note in (("accept", "optional"), ("reject", "required")):
            dlg_id = ui.slug(key, f"work-{action}")
            dialogs.append(
                ui.dialog(
                    dlg_id,
                    t(f"work.{action}.title", item=iid),
                    quoted,
                    t(f"work.{action}.confirm"),
                    t("work.dialog.cancel"),
                    note=note,
                )
            )
            parts.append(
                ui.button(
                    t(f"work.{action}"),
                    kind="primary" if action == "accept" else "danger",
                    data={
                        "post": _VERDICT_PATH,
                        "body": {**body, "action": action},
                        "confirm": dlg_id,
                        "note": note,
                    },
                )
            )
    field_id = ui.slug(key, "work-cmt")
    parts.append(
        ui.field(
            t("work.comment_label", item=iid),
            name=field_id,
            id=field_id,
            placeholder=t("work.comment_placeholder"),
        )
    )
    parts.append(
        ui.button(
            t("work.comment"),
            data={
                "post": _VERDICT_PATH,
                "body": {**body, "action": "comment"},
                "text-from": field_id,
            },
        )
    )
    return ui.fragment(*parts), dialogs


def _next_cell(item: dict, cap: int, tip_cap: int) -> ui.Safe:
    """The Next text capped at ``cap``; a longer one opens to ``tip_cap`` (components write no title
    attribute, so the longer text rides a disclosure rather than a tooltip)."""
    nxt = str(item.get("next") or "")
    if len(nxt) <= cap:
        return ui.fragment(nxt)
    return ui.disclosure(fmt.cap(nxt, cap), fmt.cap(nxt, tip_cap))


def _owner_section(repo: str, owner: str, rows: list[dict], cap: int, tip_cap: int) -> ui.Safe:
    rows = sorted(
        rows,
        key=lambda i: (i.get("status") != "awaiting-operator", i.get("_prio", 9), str(i.get("id"))),
    )
    label = owner or t("work.unassigned")
    summary = ui.fragment(
        t("work.owner_summary", owner=label, n=len(rows)),
        " · ",
        t(
            "work.owner_meta",
            awaiting=_count(rows, "awaiting-operator"),
            blocked=_count(rows, "blocked"),
            claimed=_claimed(rows),
        ),
    )
    sid = ui.slug(f"{repo}\0{owner}", "work-og")
    data = {"f-owner": _owner_token(owner)}
    if not rows:
        return ui.disclosure(
            summary, ui.region_state("empty", t("work.no_owner_items")), data=data, id=sid
        )
    cells, row_data, dialogs = [], [], []
    seen: dict[str, int] = {}
    for i in rows:
        # The occurrence number counts only rows sharing this id, so a row's element ids stay
        # stable when other rows come and go (a typed comment survives the refresh).
        key = str(i.get("id", ""))
        n = seen[key] = seen.get(key, -1) + 1
        verdict, dlgs = _verdict_cell(repo, i, f"{owner}\0{n}")
        dialogs += dlgs
        status = str(i.get("status", ""))
        cells.append(
            [
                str(i.get("id", "")),
                str(i.get("kind", "")),
                ui.badge(_severity(status), status),
                t("work.prio", n=i.get("_prio", "")),
                str(i.get("title", "")),
                _next_cell(i, cap, tip_cap),
                ", ".join(_tags(i)),
                t("work.claimed_by", who=i["_claim"]) if i.get("_claim") else "",
                verdict,
            ]
        )
        row_data.append({"f-tag": " ".join(_tags(i))})
    tbl = ui.table(
        ui.slug(f"{repo}\0{owner}", "work-tbl"),
        t("work.table_label", owner=label, repo=repo),
        [
            t(k)
            for k in (
                "work.col.item",
                "work.col.kind",
                "work.col.status",
                "work.col.prio",
                "work.col.title",
                "work.col.next",
                "work.col.tags",
                "work.col.claim",
                "work.col.operator",
            )
        ],
        cells,
        row_data=row_data,
    )
    return ui.disclosure(ui.fragment(summary), ui.fragment(tbl, *dialogs), data=data, id=sid)


def _pane(data: dict, r: dict, cap: int, tip_cap: int) -> ui.Safe:
    name = str(r["name"])
    pid = ui.slug(name, "work-pane")
    if r.get("error"):
        body = ui.region_state("error", t("work.repo_failed", repo=name, error=r["error"]))
        return ui.group(body, data={"pick": name}, id=pid)
    items = [i for i in r.get("items") or [] if isinstance(i, dict)]
    parts: list[object] = []
    skipped = [str(w) for w in r.get("skipped") or []]
    if skipped:
        listing = ui.group(ui.fragment(*[ui.group(w, tag="li") for w in skipped]), tag="ul")
        parts.append(ui.disclosure(t("work.skipped", n=len(skipped)), listing, open=True))
    if not items:
        parts.append(ui.region_state("empty", t("work.no_items")))
        return ui.group(ui.fragment(*parts), data={"pick": name}, id=pid)
    groups: dict[str, list[dict]] = {}
    for it in items:
        groups.setdefault(_owner_of(it), []).append(it)
    owners = _owner_order(data, name, groups)
    parts.append(
        ui.group(
            t(
                "work.pane_intro",
                n=len(items),
                awaiting=_count(items, "awaiting-operator"),
                blocked=_count(items, "blocked"),
                claimed=_claimed(items),
                owners=len(groups),
            ),
            tag="span",
        )
    )
    chips = [
        ui.button(ui.fragment(t("work.chip_all"), " ", len(items)), data={"filter": "owner:"})
    ] + [
        ui.button(
            ui.fragment(o or t("work.unassigned"), " ", len(groups.get(o, []))),
            data={"filter": f"owner:{_owner_token(o)}"},
        )
        for o in owners
    ]
    parts.append(
        ui.group(
            ui.fragment(*chips), tag="nav", data={"chips": "owners"}, label=t("work.chips_label")
        )
    )
    parts += [_owner_section(name, o, groups.get(o, []), cap, tip_cap) for o in owners]
    return ui.group(ui.fragment(*parts), data={"pick": name}, id=pid)


def _safe_pane(data: dict, r: dict, cap: int, tip_cap: int) -> tuple[ui.Safe, bool]:
    """One repo's pane; a fault in it is that repo's error state, never the view's (as the old page)."""
    try:
        return _pane(data, r, cap, tip_cap), True
    except Exception as exc:  # noqa: BLE001 — isolate the repo, name the class
        name = str(r.get("name"))
        body = ui.region_state("error", t("work.pane_failed", repo=name, error=type(exc).__name__))
        return ui.group(body, data={"pick": name}, id=ui.slug(name, "work-pane")), False


def render(data: dict, ctx: ViewContext) -> ViewResult:
    ttl = data.get("repos_ttl_s")
    cadence = float(ttl) if isinstance(ttl, (int, float)) and not isinstance(ttl, bool) else 20.0
    cadence = max(cadence, 5.0)
    stamp = ui.freshness(fmt.read_ts(data.get("now")), cadence)
    root = {"refresh-s": int(cadence) if cadence.is_integer() else cadence}
    work = data.get("work")
    if not isinstance(work, list):
        err = work.get("error") if isinstance(work, dict) else None
        body = ui.region_state("error", t("work.all_failed", error=err or "unknown"), retry=True)
        return ViewResult(ui.group(ui.fragment(stamp, body), data=root), item_targets=[])
    repos = fmt.repo_order([r for r in work if isinstance(r, dict) and "name" in r])
    if not repos:
        body = ui.region_state("empty", t("work.no_repos"))
        return ViewResult(ui.group(ui.fragment(stamp, body), data=root), item_targets=[])
    cap = int(data.get("next_cap") or 160)
    tip_cap = int(data.get("next_tip_cap") or 600)
    tag_box = ui.field(
        t("work.tag_label"),
        name="tag",
        kind="search",
        id="work-tag",
        placeholder=t("work.tag_placeholder"),
        data={"filter": "tag", "filter-mode": "token"},
    )
    built = [_safe_pane(data, r, cap, tip_cap) for r in repos]
    ok = [good for _, good in built]
    shown = [r for r, good in zip(repos, ok, strict=True) if good]  # a faulted pane is no target
    total = sum(len(r.get("items") or []) for r in shown)
    picks = ui.group(
        ui.fragment(
            *[
                ui.button(
                    # a faulted repo is not counted: its pane shows the error instead of a queue
                    ui.fragment(r["name"], " ", len(r.get("items") or []))
                    if good
                    else ui.fragment(r["name"]),
                    data={"pick-to": str(r["name"])},
                )
                for r, good in zip(repos, ok, strict=True)
            ]
        ),
        tag="nav",
        data={"picker": "repo"},
        label=t("work.repo_picker"),
    )
    panes = ui.group(ui.fragment(picks, *[pane for pane, _ in built]), data={"pick-group": "repo"})
    intro = ui.group(t("work.intro", repos=len(shown), total=total), tag="span")
    body = ui.group(
        ui.fragment(stamp, intro, tag_box, panes), data={"filter-group": "work", **root}
    )
    # a verdict names an item by id: an item without a string id is shown but is no target
    targets = [
        {
            **r,
            "items": [
                i
                for i in r.get("items") or []
                if isinstance(i, dict) and isinstance(i.get("id"), str) and i["id"]
            ],
        }
        for r in shown
    ]
    return ViewResult(body, item_targets=targets)
