"""The Accounts view (plan 2026-10-17-plan-1, T05): rotation order, session / weekly / Fable meters, the
quota governor's verdict, fleet warnings, the rotation rule, and each account's Edit disclosure.

A pure renderer: every value arrives in ``data`` (`quota_dashboard._view_data("accounts")`), nothing
here probes, reads an account file or imports the dashboard module. The four account controls post
today's bodies to today's endpoints (INV-1): ``/switch {account: <slug>}``, ``/park {account: <email>,
park: bool}``, ``/cap {account: <email>, cap: null|0-100}``, ``/threshold {account: <email>,
threshold: null|50-100}``. Each sits behind the row's closed Edit disclosure and confirms in a dialog
stating its consequence; the typed cap / rotate-at value is read by ``data-input`` (no script here).

Cobra check (D-253): the cheapest way to satisfy "controls only where today shows them" without the
outcome is rendering every control on every row and relying on the endpoint to refuse; the tests pin
the per-row absences (active / parked / bad slug / bad email / return / pending rows).
"""

# AFTER-EDIT: docs/workstation/quota-dashboard.md

from __future__ import annotations

import math
import re

from .. import components as ui
from ..fmt import fmt_age, fmt_reset, posture_sub, read_ts, tone
from ..strings import t
from . import ViewContext, ViewResult

_SEVERITY = {"crit": "critical", "warn": "warning", "ok": "ok"}


def _num(x: object) -> float | None:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        return None
    return float(x)


def _match(pattern: object, text: str) -> bool:
    """``pattern`` fully matches ``text``; a missing or invalid pattern matches nothing (no control)."""
    try:
        return isinstance(pattern, str) and re.fullmatch(pattern, text) is not None
    except re.error:
        return False


def _thr(data: dict) -> float | None:
    return _num(data.get("trigger_threshold"))


def _refresh(data: dict) -> int:
    s = _num(data.get("refresh_s"))
    return 20 if s is None else max(5, int(s))


def _wrap(data: dict, body: object) -> ui.Safe:
    return ui.group(body, data={"refresh-s": _refresh(data)})


def _meter(acct: dict, key: str, window_s: float | None, now: float, extra: str, is_active: bool):
    win = acct.get(key) if key != "fable" else (acct.get("model_windows") or {}).get("Fable")
    win = win if isinstance(win, dict) else {}
    used = _num(win.get("utilization"))
    if used is None:
        return ui.fragment(t("accounts.cell.none"))
    left = 100.0 - used
    reset = _num(win.get("resets_at_epoch"))
    age = _num(acct.get("age_s"))
    reset_passed = reset is not None and reset <= now
    if acct.get("source") == "cache" and (
        reset_passed or (window_s and age is not None and age >= window_s)
    ):
        # a cached reading older than its window measures a window that has since rolled over
        if not is_active:
            blind = t("accounts.cell.blind") if acct.get("weekly_cap") is not None else ""
            return ui.fragment(
                ui.badge("ok", t("accounts.cell.idle")),
                " ",
                t("accounts.cell.idle_note", blind=blind),
            )
        win_txt = (
            t("accounts.cell.window_h", h=f"{window_s / 3600:.0f}")
            if window_s
            else t("accounts.cell.window")
        )
        return ui.fragment(
            ui.badge("warning", t("accounts.cell.unknown")),
            " ",
            t(
                "accounts.cell.old_note",
                age=fmt_age(age) or t("accounts.cell.age_unknown"),
                window=win_txt,
            ),
        )
    return ui.fragment(
        ui.badge(_SEVERITY[tone(left)], t("accounts.cell.left", left=f"{left:.0f}")),
        " ",
        t("accounts.cell.used", used=f"{used:.0f}", reset=fmt_reset(reset), extra=extra),
    )


def _badges(acct: dict, rank: str | None, is_active: bool) -> list[ui.Safe]:
    out: list[ui.Safe] = []
    if rank:
        out.append(ui.badge("ok" if is_active else "neutral", rank))
    parked = acct.get("parked") is True
    cap = _num(acct.get("weekly_cap"))
    seven = _num((acct.get("seven_day") or {}).get("utilization"))
    walled = seven is not None and seven >= 100.0
    if parked:
        out.append(ui.badge("critical", t("accounts.badge.parked")))
    elif cap is not None:
        out.append(ui.badge("info", t("accounts.badge.cap", cap=f"{cap:g}")))
    if acct.get("cap_walled") is True and not parked:
        out.append(ui.badge("critical", t("accounts.badge.reserved")))
    elif walled:
        out.append(ui.badge("critical", t("accounts.badge.walled")))
    if acct.get("source") == "cache":
        age = fmt_age(_num(acct.get("age_s")))
        if age:
            out.append(ui.badge("neutral", age))
    return out


def _controls(acct: dict, slug: str, email: str, is_active: bool, data: dict):
    """(controls cell, dialogs) for one account row."""
    slug_ok = _match(data.get("slug_re"), slug)
    email_ok = _match(data.get("email_re"), email)
    parked = acct.get("parked") is True
    word = None
    if parked:
        word = t("accounts.word.parked")
    elif is_active or not slug_ok:
        word = t("accounts.word.active")
    parts: list[object] = []
    dialogs: list[object] = []
    cancel = t("accounts.dlg.cancel")
    if not parked and not is_active and slug_ok:
        dlg = ui.slug(slug, "dlg-switch")
        parts.append(
            ui.button(
                t("accounts.btn.switch"),
                data={"post": "/switch", "body": {"account": slug}, "confirm": dlg},
            )
        )
        dialogs.append(
            ui.dialog(
                dlg,
                t("accounts.dlg.switch.title", slug=slug),
                t("accounts.dlg.switch.body", slug=slug),
                t("accounts.dlg.switch.confirm"),
                cancel,
            )
        )
    if email_ok:
        verb = "unpark" if parked else "park"
        dlg = ui.slug(email, "dlg-park")
        parts.append(
            ui.button(
                t("accounts.btn.enable" if parked else "accounts.btn.disable"),
                data={
                    "post": "/park",
                    "body": {"account": email, "park": not parked},
                    "confirm": dlg,
                },
            )
        )
        dialogs.append(
            ui.dialog(
                dlg,
                t(f"accounts.dlg.{verb}.title", email=email),
                t(f"accounts.dlg.{verb}.body", email=email),
                t(f"accounts.dlg.{verb}.confirm"),
                cancel,
            )
        )
        cap = _num(acct.get("weekly_cap"))
        cap_id, cap_dlg = ui.slug(email, "cap"), ui.slug(email, "dlg-cap")
        parts.append(
            ui.field(
                t("accounts.field.cap", email=email),
                name="cap",
                kind="number",
                id=cap_id,
                # /cap takes whole numbers only (set_account_cap): a stored 80.5 is pre-filled as "80.5",
                # never as 80 (a resubmit would lower it) and never blank (an untouched Set would clear
                # it) — the field's whole-number grammar refuses it until the operator types a value
                value=(f"{cap:g}" if cap is not None and not parked else ""),
                min=0,
                max=100,
            )
        )
        parts.append(
            ui.button(
                t("accounts.btn.cap"),
                data={
                    "post": "/cap",
                    "body": {"account": email},
                    "input": f"cap:int:0:100:nullable:{cap_id}",
                    "confirm": cap_dlg,
                },
            )
        )
        dialogs.append(
            ui.dialog(
                cap_dlg,
                t("accounts.dlg.cap.title", email=email),
                ui.fragment(
                    t("accounts.dlg.cap.pre", email=email),
                    ui.value_of(cap_id),
                    t("accounts.dlg.cap.post"),
                ),
                t("accounts.dlg.cap.confirm"),
                cancel,
            )
        )
        thr = _num(acct.get("session_threshold"))
        trig = _thr(data)
        thr_label = (
            t("accounts.field.thr", email=email, default=f"{trig:g}")
            if trig is not None
            else t("accounts.field.thr_nodefault", email=email)
        )
        placeholder = f"{trig:g}" if trig is not None else ""
        thr_id, thr_dlg = ui.slug(email, "thr"), ui.slug(email, "dlg-thr")
        parts.append(
            ui.field(
                thr_label,
                name="threshold",
                kind="number",
                id=thr_id,
                value="" if thr is None else f"{thr:g}",
                min=50,
                max=100,
                placeholder=placeholder,
            )
        )
        parts.append(
            ui.button(
                t("accounts.btn.thr"),
                data={
                    "post": "/threshold",
                    "body": {"account": email},
                    "input": f"threshold:float:50:100:nullable:{thr_id}",
                    "confirm": thr_dlg,
                },
            )
        )
        dialogs.append(
            ui.dialog(
                thr_dlg,
                t("accounts.dlg.thr.title", email=email),
                ui.fragment(
                    t("accounts.dlg.thr.pre", email=email),
                    ui.value_of(thr_id),
                    t("accounts.dlg.thr.post"),
                ),
                t("accounts.dlg.thr.confirm"),
                cancel,
            )
        )
    disc = (
        ui.disclosure(
            t("accounts.edit"), ui.fragment(*parts), id=ui.slug(f"{slug}\n{email}", "edit")
        )
        if parts
        else None
    )
    return ui.fragment(word, " " if word and disc else None, disc), dialogs


def _account_row(e: dict, rank: str, data: dict, now: float, posture: object):
    acct = e["acct"]
    email = str(acct.get("email", "?"))
    slug = (acct.get("slugs") or ["?"])[0]
    is_active = e["kind"] == "active"
    five_extra = posture_sub(posture, "five_hour") if is_active else ""
    weekly_extra = posture_sub(posture, "seven_day") if is_active else ""
    fable_extra = posture_sub(posture, "fable") if is_active else ""
    who = ui.fragment(email, " ", ui.group(slug, tag="span"), " ", *_badges(acct, rank, is_active))
    ctl, dialogs = _controls(acct, slug, email, is_active, data)
    cells = [
        who,
        _meter(acct, "five_hour", data.get("five_hour_s"), now, five_extra, is_active),
        _meter(acct, "seven_day", data.get("seven_day_s"), now, weekly_extra, is_active),
        _meter(acct, "fable", data.get("seven_day_s"), now, fable_extra, is_active),
        ctl,
    ]
    return cells, {"acct": slug, "row": e["kind"]}, dialogs


def _return_row(e: dict, rank_n: int):
    acct = e["acct"]
    email = str(acct.get("email", "?"))
    slug = (acct.get("slugs") or ["?"])[0]
    when = fmt_reset(e["returns_at"]) if e.get("returns_at") else t("accounts.return.unknown")
    who = ui.fragment(
        t("accounts.return.name", email=email),
        " ",
        ui.group(t("accounts.return.sub", slug=slug), tag="span"),
        " ",
        ui.badge("neutral", t("accounts.return.badge", n=rank_n, when=when)),
        ui.badge("neutral", t("accounts.return.badge2")),
    )
    dash = "—"
    return [who, dash, dash, dash, t("accounts.return.no_switch")], {"acct": slug, "row": "return"}


def _pending_row(slug: str, data: dict):
    if not _match(data.get("slug_re"), slug):
        return None
    who = ui.fragment(
        slug,
        " ",
        ui.group(t("accounts.pending.sub"), tag="span"),
        " ",
        ui.badge("neutral", t("accounts.pending.badge")),
    )
    dash = t("accounts.cell.none")
    return [who, dash, dash, dash, t("accounts.pending.note")], {"acct": slug, "row": "pending"}


def _governor(payload: dict, data: dict):
    active = payload.get("active")
    row = next((a for a in payload.get("accounts") or [] if active in (a.get("slugs") or [])), None)
    if row is None:
        return None
    utils: list[float] = []
    for k in ("five_hour", "seven_day"):
        u = _num((row.get(k) or {}).get("utilization"))
        if u is not None:
            utils.append(u)
    for w in (row.get("model_windows") or {}).values():
        u = _num((w or {}).get("utilization"))
        if u is not None:
            utils.append(u)
    mx = max(utils) if utils else None
    reserve = _num(data.get("reserve_pct"))  # None: unknown, never a 0% fact
    walled = row.get("cap_walled") is True
    undecided = reserve is None and not walled and mx is not None
    to_pool = walled or mx is None or (reserve is not None and mx >= reserve)
    pool_on = data.get("pool_policy_on") is True  # anything but exactly True is OFF (D-181/D-182)
    if undecided:
        routine = t("accounts.gov.unknown")
    elif to_pool and not pool_on:
        routine = t("accounts.gov.routine_off")
    else:
        routine = t("accounts.gov.route.pool" if to_pool else "accounts.gov.route.ob")
    if walled and not pool_on:
        incident = t("accounts.gov.incident_off")
    else:
        incident = t("accounts.gov.route.diagnose" if walled else "accounts.gov.route.ob")
    # severity follows the same off-rule as the text: with the pool OFF, shedding is disabled and
    # a routine route to it is not a warning
    sev = (
        "critical"
        if walled
        else ("info" if undecided else ("warning" if to_pool and pool_on else "ok"))
    )
    detail = t(
        "accounts.gov.detail",
        mx=f"{mx:.0f}%" if mx is not None else t("accounts.gov.unknown"),
        reserve=f"{reserve:.0f}%" if reserve is not None else t("accounts.gov.unknown"),
        walled=t("accounts.gov.yes" if walled else "accounts.gov.no"),
        routine=routine,
        incident=incident,
    )
    return ui.card(
        t("accounts.gov.title", active=str(active or "—")),
        detail,
        badge=ui.badge(sev, t("sev." + sev)),
    )


def render(data: dict, ctx: ViewContext) -> ViewResult:
    status = data.get("status")
    queue = data.get("queue")
    payload = status.get("payload") if isinstance(status, dict) else None
    if not isinstance(payload, dict) or not isinstance(queue, list):
        err = (status or {}).get("error") if isinstance(status, dict) else None
        if err is None and isinstance(queue, dict):
            err = queue.get("error")
        return ViewResult(
            _wrap(
                data,
                ui.region_state(
                    "error", t("accounts.error", error=err or t("accounts.error_none"))
                ),
            )
        )

    now = _num(data.get("now")) or ctx.now
    banners: list[ui.Safe] = []
    failure = status.get("probe_failure")
    if failure:
        reason = failure.get("error", "") if isinstance(failure, dict) else str(failure)
        banners.append(ui.badge("critical", t("accounts.banner.probe", error=reason)))
    if payload.get("pause") == "marker":
        banners.append(ui.badge("warning", t("accounts.banner.paused")))
    elif payload.get("pause") == "error":
        banners.append(ui.badge("critical", t("accounts.banner.pause_error")))
    if not [e for e in queue if e.get("kind") != "return"]:
        banners.append(ui.badge("warning", t("accounts.banner.none")))

    back = next((e for e in queue if e.get("kind") == "return"), None)
    rows: list[list[object]] = []
    row_data: list[dict] = []
    dialogs: list[object] = []
    posture = payload.get("posture")
    for e in queue:
        kind, n = e["kind"], e["n"]
        if kind == "return":
            cells, rd = _return_row(e, n)
            rows.append(cells)
            row_data.append(rd)
            continue
        if kind == "active":
            rank = (
                t(
                    "accounts.rank.active_also",
                    n=n,
                    m=back["n"],
                    when=fmt_reset(back.get("returns_at")),
                )
                if back
                else t("accounts.rank.active", n=n)
            )
        elif kind == "eligible":
            rank = t("accounts.rank.next" if n == 2 else "accounts.rank.line", n=n)
        elif e.get("returns_at"):
            rank = t("accounts.rank.returns", n=n, when=fmt_reset(e["returns_at"]))
        else:
            rank = t("accounts.rank.returns_unknown", n=n)
        cells, rd, dlgs = _account_row(e, rank, data, now, posture)
        rows.append(cells)
        row_data.append(rd)
        dialogs.extend(dlgs)
    for p in payload.get("pending") or []:
        pr = _pending_row(str(p), data)
        if pr is not None:
            rows.append(pr[0])
            row_data.append(pr[1])

    table = ui.table(
        "accounts-table",
        t("accounts.table"),
        [t("accounts.col." + c) for c in ("account", "session", "weekly", "fable", "controls")],
        rows,
        row_data=row_data,
    )
    warns = [str(w) for w in payload.get("fleet_warnings") or []]
    warn_block = (
        ui.card(
            t("accounts.warnings"),
            ui.group(ui.fragment(*[ui.group(w, tag="li") for w in warns]), tag="ul"),
            badge=ui.badge("warning", t("sev.warning")),
        )
        if warns
        else None
    )
    trig = _thr(data)
    interval = int(_num(data.get("probe_interval_s")) or 0)
    rule = (
        t("accounts.rule", threshold=f"{trig:.0f}", interval=interval)
        if trig is not None
        else t("accounts.rule_nothreshold", interval=interval)
    )
    body = ui.fragment(
        ui.freshness(read_ts(_num(status.get("read_at"))), _refresh(data)),
        *banners,
        warn_block,
        _governor(payload, data),
        table,
        ui.group(rule, tag="span"),
        *dialogs,
    )
    return ViewResult(_wrap(data, body))
