"""The Overview view — "what needs me now?" (spec § Overview; plan 2026-10-17-plan-1, T03).

Sections, by urgency: the summary strip, the decisions waiting on the operator (grouped by repo, the
hub's first), the blocked merges, every agent, the quota strip and the health strip. When the band is
RED or WALL, or a probe has failed, the quota and health strips move above the decisions (receipt row
P5-r1, applied as the spec writes it: a faulted Health strip alone moves nothing).

Every word comes from `strings.t`, every value through a component, every behaviour from `app.js`'s
attributes: a verdict posts ``/item-verdict`` with the card's `snapshot.token`, Pause / Resume post
``/agent-pause`` — the server's existing endpoints, nothing new. The view publishes the targets it
shows (`ViewResult.item_targets`, `.pause_targets`) so a POST after a restart finds them.

Cobra check (D-253): the cheapest way to pass "the hub's group first, gate items first" without the
outcome is sorting on the fixture's own order; the tests feed the repos and items out of order, and
the summary counts are asserted against the fixture stores, never against the markup's own tally.
"""

# AFTER-EDIT: docs/workstation/quota-dashboard.md

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import datetime
from urllib.parse import quote

from .. import components as ui
from .. import fmt, merges
from ..snapshot import token
from ..strings import t
from . import ViewContext, ViewResult

__all__ = ["collect", "render"]

HUB = "fabrik"
GROWTH_LIMIT = (
    100  # more decisions than this at once: each group shows its FEW oldest (spec § Lifecycle)
)
FEW = 5
_GROUNDS = ("gate", "owned", "underivable")
_GROUND_SEVERITY = {"gate": "critical", "owned": "warning", "underivable": "info"}
_STATE_SEVERITY = {"working": "ok", "idle": "info", "stale": "warning", "away": "neutral"}
_BAND_SEVERITY = {"GREEN": "ok", "AMBER": "warning", "RED": "critical", "WALL": "critical"}
_WINDOWS = ("five_hour", "seven_day", "fable")
_NO_READING_YET = "no reading yet"  # `quota_dashboard._status_data`'s value before the first probe
_BAND_WINDOWS = ("five_hour", "seven_day")  # the windows the fleet band is computed from
_URGENT_BANDS = ("RED", "WALL")


def collect(ctx: ViewContext) -> dict:
    """The blocked merges, and the merge records the reader could not read (for the Health strip)."""
    bad: list[str] = []
    try:
        found: object = merges.blocked(ctx.opt_root, ctx.fabrik_root, unreadable=bad)
    except Exception as exc:  # noqa: BLE001 — the section's error state, never the view's
        found = {"error": f"{type(exc).__name__}: {exc}"}
    return {"blocked": found, "merge_unreadable": bad}


# ---------------------------------------------------------------- small readers
def _d(x: object) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x: object) -> list:
    return x if isinstance(x, list) else []


def _err(x: object) -> str | None:
    return str(x["error"]) if isinstance(x, dict) and "error" in x else None


def _epoch(x: object) -> float | None:
    """A number, or an ISO-8601 string, as epoch seconds; None for anything else."""
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x) if math.isfinite(x) else None
    if isinstance(x, str) and x:
        try:
            return datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp()
        except (ValueError, OverflowError, OSError):
            return None
    return None


def _dur(seconds: float | None) -> str:
    if seconds is None or not math.isfinite(seconds):
        return t("ov.dur.unknown")
    s = max(0, int(seconds))
    if s < 60:
        return t("ov.dur.s", n=s)
    if s < 3600:
        return t("ov.dur.min", n=s // 60)
    if s < 172800:
        return t("ov.dur.h", n=s // 3600)
    return t("ov.dur.d", n=s // 86400)


def _since(ts: object, now: float) -> str:
    when = _epoch(ts)
    return _dur(None if when is None else now - when)


def _line(*parts: object) -> ui.Safe:
    return ui.group(ui.fragment(*parts), tag="div")


def _items(*parts: object) -> ui.Safe:
    return ui.group(ui.fragment(*(ui.group(p, tag="li") for p in parts)), tag="ul")


def _guard(build: Callable[[], ui.Safe], title_key: str, ident: str) -> ui.Safe:
    """One section; a fault inside it is that section's error state, never the whole view's."""
    try:
        return build()
    except Exception as exc:  # noqa: BLE001
        return ui.section(
            t(title_key),
            ui.region_state("error", t("ov.section_failed", error=type(exc).__name__)),
            id=ident,
        )


# ---------------------------------------------------------------- decisions
def _awaiting(work: object) -> list[tuple[dict, list[dict]]]:
    """(repo entry, its awaiting items in card order) for every repo with any, in group order."""
    groups = []
    for repo in _l(work):
        if not isinstance(repo, dict) or repo.get("error"):
            continue
        items = [
            i
            for i in _l(repo.get("items"))
            if isinstance(i, dict) and i.get("status") == "awaiting-operator"
        ]
        if items:
            groups.append((repo, sorted(items, key=_item_key)))

    def oldest(entry: tuple[dict, list[dict]]) -> tuple:
        times = [e for e in (_epoch(i.get("created")) for i in entry[1]) if e is not None]
        return (
            str(entry[0].get("name")) != HUB,
            not times,
            min(times) if times else 0.0,
            str(entry[0].get("name")),
        )

    return sorted(groups, key=oldest)


def _item_key(item: dict) -> tuple:
    ground = item.get("ground")
    rank = 0 if ground == "gate" else 2 if not ground else 1
    created = _epoch(item.get("created"))
    return (rank, created is None, created or 0.0, str(item.get("id")))


def _ground(item: dict) -> ui.Safe:
    g = item.get("ground")
    if not g:
        return ui.badge("neutral", t("ov.ground.none"))
    if g in _GROUNDS:
        return ui.badge(_GROUND_SEVERITY[g], t(f"ov.ground.{g}"))
    return ui.badge("neutral", t("ov.ground.other", ground=g))


def _has_id(item: dict) -> bool:
    """Whether the board can act on ``item``: work.py's verdict takes a string id and nothing else
    (the Work view's same rule), so an item without one gets no controls and no target."""
    return isinstance(item.get("id"), str) and bool(item["id"])


def _card(repo: str, item: dict, now: float, seq: int = 0) -> ui.Safe:
    actionable = _has_id(item)
    ident = item["id"] if actionable else ""
    question = str(item.get("question") or "") or t("ov.dec.no_question")
    # an id-less card is keyed by its position, so two of them never share element ids
    key = f"{repo}/{ident}" if actionable else f"{repo}\x00no-id\x00{seq}"
    tok = token(item)

    def body(action: str) -> dict:
        return {"repo": repo, "item": ident, "action": action, "token": tok}

    comment_id = ui.slug(key, "cm")
    actions: list[object] = []
    if not actionable:
        pass  # no verdict, no comment: work.py would refuse every one of them
    elif item.get("kind") == "decision":
        acc_id, rej_id = ui.slug(key, "acc"), ui.slug(key, "rej")
        actions += [
            ui.button(
                t("ov.dec.accept"),
                kind="primary",
                data={
                    "post": "/item-verdict",
                    "body": body("accept"),
                    "confirm": acc_id,
                    "note": "optional",
                },
            ),
            ui.button(
                t("ov.dec.reject"),
                kind="danger",
                data={
                    "post": "/item-verdict",
                    "body": body("reject"),
                    "confirm": rej_id,
                    "note": "required",
                },
            ),
            ui.dialog(
                acc_id,
                t("ov.dec.accept_title", id=ident),
                ui.fragment(_line(question), _line(t("ov.dec.accept_consequence"))),
                t("ov.dec.accept_confirm", id=ident),
                t("ov.dec.keep"),
                note="optional",
            ),
            ui.dialog(
                rej_id,
                t("ov.dec.reject_title", id=ident),
                ui.fragment(_line(question), _line(t("ov.dec.reject_consequence"))),
                t("ov.dec.reject_confirm", id=ident),
                t("ov.dec.keep"),
                note="required",
            ),
        ]
    if actionable:
        actions += [
            ui.field(t("ov.dec.comment_label", id=ident), name=comment_id, id=comment_id),
            ui.button(
                t("ov.dec.comment"),
                data={"post": "/item-verdict", "body": body("comment"), "text-from": comment_id},
            ),
        ]
    creator = item.get("creator")
    title = str(item.get("title") or "") or t("ov.dec.no_title")
    return ui.card(
        t("ov.dec.card_title", id=ident, title=title) if actionable else title,
        ui.fragment(
            _line(t("ov.dec.asker", who=creator) if creator else t("ov.dec.asker_unknown")),
            ui.clamp(question, 3),
            None if actionable else _line(t("ov.dec.no_id")),
        ),
        badge=_ground(item),
        age=t("ov.dec.wait", age=_since(item.get("created"), now)),
        actions=ui.fragment(*actions),
        id=ui.slug(key, "dc"),
    )


def _decisions(data: dict, ctx: ViewContext, groups: list, shown: list) -> ui.Safe:
    now = ctx.now
    stamp = ui.freshness(fmt.read_ts(_epoch(data.get("now"))), data.get("refresh_s") or None)
    work = data.get("work")
    if _err(work) is not None:
        return ui.section(
            t("ov.dec.title"),
            ui.fragment(ui.region_state("error", t("ov.dec.error", error=_err(work))), stamp),
            id="ov-decisions",
        )
    notes = []
    for repo in _l(work):
        if isinstance(repo, dict) and repo.get("error"):
            notes.append(
                ui.badge(
                    "critical", t("ov.dec.repo_error", repo=repo.get("name"), error=repo["error"])
                )
            )
        elif isinstance(repo, dict) and repo.get("skipped"):
            notes.append(
                ui.badge(
                    "warning",
                    t("ov.dec.skipped", repo=repo.get("name"), n=len(_l(repo["skipped"]))),
                )
            )
    # the growth trigger counts DECISIONS (spec § Lifecycle), not every awaiting item
    total = sum(1 for _r, items in groups for it in items if it.get("kind") == "decision")
    parts: list[object] = [stamp, _items(*notes) if notes else None]
    if not groups:
        parts.append(ui.region_state("empty", t("ov.dec.none")))
    for i, (repo, items) in enumerate(groups):
        name = str(repo.get("name"))
        cut = total > GROWTH_LIMIT and len(items) > FEW  # only a group that actually hides items
        visible = items
        if cut:  # the FEW oldest by `created`, still shown in the group's card order
            oldest = sorted(
                items,
                key=lambda it: (
                    _epoch(it.get("created")) is None,
                    _epoch(it.get("created")) or 0.0,
                ),
            )
            keep = {id(it) for it in oldest[:FEW]}
            visible = [it for it in items if id(it) in keep]
        shown.append({**repo, "items": [it for it in visible if _has_id(it)]})  # no id, no target
        body = [_card(name, it, now, seq) for seq, it in enumerate(visible)]
        if cut:
            body.append(
                _line(
                    t("ov.dec.more", n=len(items)),
                    " ",
                    ui.link(t("ov.dec.more_link", repo=name), "/#work/" + quote(name, safe="")),
                )
            )
        parts.append(
            ui.disclosure(
                t("ov.dec.group", repo=name, n=len(items)),
                ui.fragment(*body),
                open=i == 0,
                data={"repo": name},
                id=ui.slug(name, "dg"),
            )
        )
    return ui.section(t("ov.dec.title"), ui.fragment(*parts), id="ov-decisions")


# ---------------------------------------------------------------- blocked merges
def _merges(data: dict, ctx: ViewContext) -> ui.Safe:
    stamp = ui.freshness(fmt.read_ts(ctx.now), data.get("refresh_s") or None)
    found = data.get("blocked")
    if _err(found) is not None:
        body: object = ui.region_state("error", t("ov.merge.error", error=_err(found)))
    elif not _l(found):
        body = ui.region_state("empty", t("ov.merge.none"))
    else:
        cards = []
        for b in _l(found):
            owner = (
                t("ov.merge.owner", owner=b["owner"])
                if b.get("owner")
                else t("ov.merge.owner_resolving")
                if b.get("owner_resolving") is True
                else t("ov.merge.owner_unresolved", error=b["owner_error"])
                if b.get("owner_error")
                else t("ov.merge.owner_unresolved_bare")
            )
            cards.append(
                ui.card(
                    t("ov.merge.card_title", repo=b.get("repo"), branch=b.get("branch")),
                    ui.fragment(
                        _line(
                            t("ov.merge.item", item=b["item"])
                            if b.get("item")
                            else t("ov.merge.no_item")
                        ),
                        _line(
                            t("ov.merge.requester", who=b["requester"])
                            if b.get("requester")
                            else t("ov.merge.no_requester")
                        ),
                        _line(
                            t("ov.merge.reason", reason=b["reason"])
                            if b.get("reason")
                            else t("ov.merge.no_reason")
                        ),
                        _line(owner),
                    ),
                    badge=ui.badge("warning", t("ov.merge.badge")),
                    age=t("ov.merge.age", age=_dur(b.get("age_s"))),
                    id=ui.slug(f"{b.get('repo')}/{b.get('branch')}", "bm"),
                )
            )
        body = ui.fragment(*cards)
    return ui.section(t("ov.merge.title"), ui.fragment(stamp, body), id="ov-merges")


# ---------------------------------------------------------------- agents
def _agent_repos(box: object) -> tuple[list[dict], int]:
    repos = [r for r in _l(_d(box).get("repos")) if isinstance(r, dict)]
    shown = [r for r in repos if r.get("agents") or r.get("error")]
    shown.sort(
        key=lambda r: (
            r.get("name") != HUB,
            not any(_d(a).get("state") == "working" for a in _l(r.get("agents"))),
            str(r.get("name")),
        )
    )
    return shown, len(repos) - len(shown)


def _item_line(it: object) -> str:
    it = _d(it)
    return t("ov.ag.item", id=it.get("id") or "", title=it.get("title") or t("ov.dec.no_title"))


def _agent_cells(a: dict, repo: str, now: float, dialogs: list) -> list[object]:
    name = str(a.get("name") or "")
    state = str(a.get("state") or "away")
    who = [name]
    if a.get("named_from") == "record":
        who.append(_line(t("ov.ag.named")))
    windows = a.get("windows")
    if isinstance(windows, int) and not isinstance(windows, bool) and windows > 1:
        who.append(_line(t("ov.ag.windows", n=windows)))
    label = t(f"ov.ag.state.{state}") if state in _STATE_SEVERITY else state
    st: list[object] = [ui.badge(_STATE_SEVERITY.get(state, "neutral"), label)]
    paused = a.get("paused") if isinstance(a.get("paused"), dict) else None
    if paused:
        st.append(
            _line(t("ov.ag.paused", by=paused.get("by") or "?", age=_since(paused.get("at"), now)))
        )
        if paused.get("partial"):
            st.append(_line(t("ov.ag.paused_partial")))
        if paused.get("why"):
            st.append(_line(t("ov.ag.paused_why", why=paused["why"])))
        if a.get("pause_honoured") is False:  # exactly False: a missing reading claims nothing
            st.append(_line(t("ov.ag.not_honoured")))
    if a.get("can_pause"):
        key = f"{repo}/{name}"
        if paused:
            dlg = ui.slug(key, "res")
            names = [str(n) for n in _l(paused.get("names"))] or [str(paused.get("name") or name)]
            st.append(
                ui.button(
                    t("ov.ag.resume"),
                    data={
                        "post": "/agent-pause",
                        "body": {"repo": repo, "agent": name, "action": "resume"},
                        "confirm": dlg,
                    },
                )
            )
            dialogs.append(
                ui.dialog(
                    dlg,
                    t("ov.ag.resume_title", agent=name, repo=repo),
                    _line(
                        t("ov.ag.resume_body", names=", ".join(names), by=paused.get("by") or "?")
                    ),
                    t("ov.ag.resume_confirm", agent=name),
                    t("ov.ag.resume_cancel"),
                )
            )
        else:
            dlg = ui.slug(key, "pau")
            st.append(
                ui.button(
                    t("ov.ag.pause"),
                    data={
                        "post": "/agent-pause",
                        "body": {"repo": repo, "agent": name, "action": "pause"},
                        "confirm": dlg,
                        "note": "optional",
                    },
                )
            )
            dialogs.append(
                ui.dialog(
                    dlg,
                    t("ov.ag.pause_title", agent=name, repo=repo),
                    _line(t("ov.ag.pause_body", agent=name)),
                    t("ov.ag.pause_confirm", agent=name),
                    t("ov.ag.pause_cancel"),
                    note="optional",
                )
            )
    cur = _d(a.get("now"))
    if cur:
        now_cell: list[object] = [_line(t("ov.ag.now", command=cur.get("command") or ""))]
        if cur.get("phases"):
            now_cell.append(
                _line(t("ov.ag.phase", phase=cur.get("phase"), phases=cur.get("phases")))
            )
        for k in ("title", "surface"):
            if cur.get(k):
                now_cell.append(_line(fmt.cap(str(cur[k]), 140)))
        now_cell.append(
            _line(t("ov.ag.stale_note"))
            if cur.get("stale")
            else _line(t("ov.ag.updated", age=_since(cur.get("updated_ts"), now)))
        )
    else:
        now_cell = [t("ov.ag.no_command")]
    holds = _item_line(a["claim"]) if a.get("claim") else t("ov.ag.dash")
    nxt = _d(a.get("next"))
    top = _l(nxt.get("top"))
    more = (nxt.get("queued") if isinstance(nxt.get("queued"), int) else 0) - len(top)
    next_cell: list[object] = [_items(*(_item_line(i) for i in top))] if top else []
    if more > 0:
        next_cell.append(_line(t("ov.ag.more_queued", n=more)))
    if not next_cell:
        next_cell = [t("ov.ag.nothing_queued")]
    merged = _l(a.get("merges"))
    if merged:
        m = _d(merged[0])
        merge_cell: list[object] = [
            t("ov.ag.merge", sha=m.get("sha") or "", age=_since(m.get("ts"), now))
        ]
        if m.get("item"):
            merge_cell.append(_line(m["item"]))
    elif a.get("merge_owner"):
        merge_cell = [t("ov.ag.merge_owner")]
    else:
        merge_cell = [t("ov.ag.dash")]
    return [
        ui.fragment(*who),
        ui.fragment(*st),
        ui.fragment(*now_cell),
        holds,
        ui.fragment(*next_cell),
        ui.fragment(*merge_cell),
    ]


def _agents(data: dict, ctx: ViewContext) -> ui.Safe:
    stamp = ui.freshness(fmt.read_ts(_epoch(data.get("now"))), data.get("refresh_s") or None)
    box = data.get("box")
    if _err(box) is not None:
        return ui.section(
            t("ov.agents.title"),
            ui.fragment(stamp, ui.region_state("error", t("ov.ag.error", error=_err(box)))),
            id="ov-agents",
        )
    repos, quiet = _agent_repos(box)
    counts = dict.fromkeys(_STATE_SEVERITY, 0)
    for r in repos:
        for a in _l(r.get("agents")):
            s = str(_d(a).get("state"))
            counts[s] = counts.get(s, 0) + 1
    parts: list[object] = [
        stamp,
        _line(t("ov.ag.counts", working=counts["working"], idle=counts["idle"], stale=counts["stale"],
                away=counts["away"], quiet=quiet)),
    ]  # fmt: skip
    if not repos:
        parts.append(ui.region_state("empty", t("ov.ag.none")))
    dialogs: list[object] = []
    headers = [t(f"ov.ag.h.{h}") for h in ("agent", "state", "now", "holds", "next", "merge")]
    for r in repos:
        name = str(r.get("name"))
        dormant = r.get("dormant")
        if isinstance(dormant, int) and not isinstance(dormant, bool) and dormant > 0:
            parts.append(_line(t("ov.ag.dormant", repo=name, n=dormant)))
        if r.get("error"):
            parts.append(ui.badge("critical", t("ov.ag.repo_error", repo=name, error=r["error"])))
            continue
        agents = [_d(a) for a in _l(r.get("agents"))]
        rows = [_agent_cells(a, name, ctx.now, dialogs) for a in agents]
        parts.append(
            ui.table(
                ui.slug(name, "agt"),
                t("ov.ag.table", repo=name),
                headers,
                rows,
                row_data=[{"agent": str(a.get("name") or "")} for a in agents],
            )
        )
    return ui.section(t("ov.agents.title"), ui.fragment(*parts, *dialogs), id="ov-agents")


# ---------------------------------------------------------------- quota
def _posture(status: object) -> tuple[dict, dict, dict]:
    payload = _d(_d(status).get("payload"))
    posture = _d(payload.get("posture"))
    return payload, _d(posture.get("active")), _d(posture.get("fleet"))


def _band(status: object) -> str | None:
    band = _posture(status)[1].get("band")
    return band if isinstance(band, str) and band else None


def _active_account(status: object) -> str | None:
    payload, active, _fleet = _posture(status)
    who = active.get("slug") or payload.get("active") or active.get("email")
    return str(who) if who else None


def _probe_failed(data: dict) -> bool:
    payload = _posture(data.get("status"))[0]
    failed = _l(_d(data.get("health")).get("failed"))
    return bool(payload.get("probe_failed")) or any(_d(f).get("key") == "probe" for f in failed)


def _num(x: object) -> float | None:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        return None
    return float(x)


def _quota(data: dict, ctx: ViewContext) -> ui.Safe:
    status = data.get("status")
    read_at = _num(_d(status).get("read_at"))
    stamp = ui.freshness(fmt.read_ts(read_at), data.get("probe_interval_s") or None)
    # the server's start-up "no reading yet" (`quota_dashboard._status_data`) is no failure: nothing
    # has been read so far, so it is the empty state; every other error is the error state
    if _err(status) is not None and _err(status) != _NO_READING_YET:
        return ui.section(
            t("ov.quota.title"),
            ui.fragment(stamp, ui.region_state("error", t("ov.q.none", error=_err(status)))),
            id="ov-quota",
        )
    if "payload" not in _d(status):
        return ui.section(
            t("ov.quota.title"),
            ui.fragment(stamp, ui.region_state("empty", t("ov.q.none_yet"))),
            id="ov-quota",
        )
    payload, active, fleet = _posture(status)
    windows = _d(fleet.get("windows"))
    band = _band(status)
    lines: list[object] = []
    if band:
        # the band is computed from the session and weekly windows only (`claude_rotate._fleet_band`,
        # fable=False), and a WALL or a hold is not one window's doing: name a window only otherwise
        hot = (
            []
            if band == "WALL" or _d(fleet.get("hold"))
            else [
                (u, w)
                for w in _BAND_WINDOWS
                if (u := _num(_d(windows.get(w)).get("utilization"))) is not None
            ]
        )
        text = (
            t("ov.q.band_on", band=band, window=t(f"ov.q.w.{max(hot)[1]}"))
            if hot
            else t("ov.q.band", band=band)
        )
        lines.append(ui.badge(_BAND_SEVERITY.get(band, "neutral"), text))
    fable = active.get("band_fable")
    if isinstance(fable, str) and fable:
        lines.append(
            ui.badge(_BAND_SEVERITY.get(fable, "neutral"), t("ov.q.band_fable", band=fable))
        )
    account = _active_account(status)
    if account:
        lines.append(_line(t("ov.q.active", account=account)))
    succ = _d(fleet.get("successor"))
    succ_name = succ.get("slug") or succ.get("email")
    lines.append(
        _line(t("ov.q.successor", account=succ_name) if succ_name else t("ov.q.no_successor"))
    )
    accounts = [a for a in _l(payload.get("accounts")) if isinstance(a, dict)]

    def reset_of(window: str, slug: object) -> object:
        """The reset of THIS window's reading, from the row of the account the fleet read it from
        (`posture.fleet.windows.<w>.slug`) — never the active account's, a different account's
        window; None (shown "—") when that account has no row."""
        row = next((a for a in accounts if slug and slug in _l(a.get("slugs"))), None)
        if row is None:
            return None
        if window == "fable":
            return _d(_d(row.get("model_windows")).get("Fable")).get("resets_at_epoch")
        return _d(row.get(window)).get("resets_at_epoch")

    for w in _WINDOWS:
        reading = _d(windows.get(w))
        u = _num(reading.get("utilization"))
        label = t(f"ov.q.w.{w}")
        reset = fmt.fmt_reset(_num(reset_of(w, reading.get("slug"))))
        lines.append(
            _line(
                t(
                    "ov.q.window",
                    window=label,
                    pct=f"{u:.0f}",
                    slug=reading.get("slug") or "?",
                    reset=reset,
                )
                if u is not None
                else t("ov.q.window_none", window=label, reset=reset)
            )
        )
    hold = _d(fleet.get("hold"))
    if hold:
        lines.append(ui.badge("critical", t("ov.q.hold", tier=hold.get("tier") or "?")))
    relief = _d(fleet.get("next_relief"))
    if relief:
        lines.append(
            _line(
                t(
                    "ov.q.relief",
                    account=relief.get("email") or "?",
                    when=fmt.fmt_reset(_num(relief.get("epoch"))),
                    window=relief.get("window") or "?",
                )
            )
        )
    if payload.get("probe_failed"):
        lines.append(ui.badge("critical", t("ov.q.probe_failed", error=payload["probe_failed"])))
    return ui.section(t("ov.quota.title"), ui.fragment(stamp, *lines), id="ov-quota")


# ---------------------------------------------------------------- health
def _health_faults(data: dict) -> list[str]:
    health = _d(data.get("health"))
    out = []
    for s in _l(health.get("stale")):
        s = _d(s)
        out.append(t("ov.h.stale", view=s.get("view") or "?", age=_dur(_num(s.get("age_s")))))
    keys = set()
    for f in _l(health.get("failed")):
        f = _d(f)
        if f.get("key") == "status" and f.get("error") == _NO_READING_YET:
            continue  # the start-up "no reading yet" is the quota strip's empty state, not a fault
        keys.add(f.get("key"))
        out.append(t("ov.h.failed", name=f.get("key") or "?", error=f.get("error") or "?"))
    payload = _posture(data.get("status"))[0]
    if payload.get("probe_failed") and "probe" not in keys:
        out.append(t("ov.h.failed", name="probe", error=payload["probe_failed"]))
    if _err(data.get("blocked")) is not None:
        out.append(t("ov.h.failed", name="blocked", error=_err(data.get("blocked"))))
    bad = _l(data.get("merge_unreadable"))
    if bad:
        out.append(t("ov.h.unreadable", n=len(bad)))
    return out


def _budget_lines(budget: object) -> list[object]:
    b = _d(budget)
    if not b or b.get("disabled") or "error" in b:  # an error is already a failed collector above
        return []
    if b.get("computing"):
        return [_line(t("ov.h.budget_computing"))]
    seats = []
    for s in _l(b.get("seats")):
        s = _d(s)
        key = s.get("key")
        label = t(f"ov.h.seat.{key}") if key in ("read_only", "heavy") else s.get("label") or "?"
        box = "?" if s.get("box") is None else s.get("box")
        taken = s.get("taken") or 0
        # today's wording, every fact kept (INV-2): the floor, the siblings' reservation, the quota cap
        if s.get("floored"):
            detail = t("ov.h.seat_box_floor", box=box, taken=taken)
        elif taken:
            detail = t("ov.h.seat_box_after", box=box, taken=taken)
        else:
            detail = t("ov.h.seat_box", box=box)
        if s.get("has_quota_cap"):
            detail = t("ov.h.seat_quota", detail=detail, cap=s.get("quota_cap"))
        seats.append(t("ov.h.budget_seat", label=label, allowed=s.get("allowed"), detail=detail))
    q = _d(b.get("quota"))
    if b.get("hold"):
        quota = t("ov.h.budget_hold")
    elif q.get("ok"):
        quota = t(
            "ov.h.budget_quota",
            active=q.get("active"),
            pct=q.get("hottest_pct"),
            eligible=q.get("eligible"),
            raw=q.get("eligible_raw", q.get("eligible")),
        )
    else:
        quota = t("ov.h.budget_quota_unknown")
    out: list[object] = [
        _line(t("ov.h.budget", seats=" · ".join(seats), cli_cap=b.get("cli_cap", "?"), quota=quota))
    ]
    caveats = [str(c) for c in _l(b.get("caveats"))]
    if caveats:
        out.append(_line(t("ov.h.budget_caveats", caveats=" · ".join(caveats))))
    return out


def _health(data: dict, ctx: ViewContext) -> ui.Safe:
    stamp = ui.freshness(fmt.read_ts(ctx.now), data.get("refresh_s") or None)
    faults = _health_faults(data)
    body: list[object] = [stamp]
    body.append(
        _items(*(ui.badge("warning", f) for f in faults))
        if faults
        else ui.badge("ok", t("ov.h.ok"))
    )
    body += _budget_lines(data.get("budget"))
    return ui.section(t("ov.health.title"), ui.fragment(*body), id="ov-health")


# ---------------------------------------------------------------- summary
def _summary(data: dict, ctx: ViewContext, groups: list) -> ui.Safe:
    stamp = ui.freshness(fmt.read_ts(_epoch(data.get("now"))), data.get("refresh_s") or None)
    links: list[object] = []
    if _err(data.get("work")) is not None:
        links.append(ui.link(t("ov.sum.work_error"), "#ov-decisions"))
    elif not groups:
        links.append(ui.link(t("ov.sum.no_decisions"), "#ov-decisions"))
    for repo, items in groups:
        times = [e for e in (_epoch(i.get("created")) for i in items) if e is not None]
        age = _dur(ctx.now - min(times)) if times else t("ov.dur.unknown")
        links.append(
            ui.link(
                t("ov.sum.decisions", repo=repo.get("name"), n=len(items), age=age), "#ov-decisions"
            )
        )
    # an unreadable collector is said as such, never as a count of 0
    blocked = data.get("blocked")
    links.append(
        ui.link(
            t("ov.sum.merges_error")
            if _err(blocked) is not None
            else t("ov.sum.merges", n=len(_l(blocked))),
            "#ov-merges",
        )
    )
    if _err(data.get("box")) is not None:
        links.append(ui.link(t("ov.sum.agents_error"), "#ov-agents"))
    else:
        repos, _quiet = _agent_repos(data.get("box"))
        idle = sum(1 for r in repos for a in _l(r.get("agents")) if _d(a).get("state") != "working")
        links.append(ui.link(t("ov.sum.agents", n=idle), "#ov-agents"))
    band, account = _band(data.get("status")), _active_account(data.get("status"))
    links.append(
        ui.link(
            t("ov.sum.band", band=band, account=account or "?")
            if band
            else t("ov.sum.band_unknown"),
            "#ov-quota",
        )
    )
    faults = len(_health_faults(data))
    links.append(
        ui.link(t("ov.sum.health", n=faults) if faults else t("ov.sum.healthy"), "#ov-health")
    )
    return ui.section(t("ov.summary.title"), ui.fragment(stamp, _items(*links)), id="ov-summary")


# ---------------------------------------------------------------- the view
def render(data: dict, ctx: ViewContext) -> ViewResult:
    groups = _awaiting(data.get("work"))
    shown: list[dict] = []
    summary = _guard(lambda: _summary(data, ctx, groups), "ov.summary.title", "ov-summary")
    decisions = _guard(lambda: _decisions(data, ctx, groups, shown), "ov.dec.title", "ov-decisions")
    blocked = _guard(lambda: _merges(data, ctx), "ov.merge.title", "ov-merges")
    agents = _guard(lambda: _agents(data, ctx), "ov.agents.title", "ov-agents")
    quota = _guard(lambda: _quota(data, ctx), "ov.quota.title", "ov-quota")
    health = _guard(lambda: _health(data, ctx), "ov.health.title", "ov-health")
    urgent = _band(data.get("status")) in _URGENT_BANDS or _probe_failed(data)
    order = (
        [summary, quota, health, decisions, blocked, agents]
        if urgent
        else [summary, decisions, blocked, agents, quota, health]
    )
    refresh = data.get("refresh_s")
    attrs = (
        {"refresh-s": refresh}
        if isinstance(refresh, (int, float)) and not isinstance(refresh, bool)
        else None
    )
    box = data.get("box")
    pause_targets = (
        [r for r in _l(_d(box).get("repos")) if isinstance(r, dict)] if _err(box) is None else []
    )
    return ViewResult(
        html=ui.group(ui.fragment(*order), tag="div", data=attrs),
        pause_targets=pause_targets,
        item_targets=shown,
    )
