#!/usr/bin/env python3
# AFTER-EDIT: none
"""Capture + pin the live GlitchTip new-issue webhook envelope (watchdog Phase A).

Why this exists
---------------
The fabrik-lib watchdog error-tracker trigger parses GlitchTip's outgoing
new-issue webhook (Slack-style envelope first, Sentry-issue fallback). The exact
field set depends on which integration is configured at errors.vps1.ocoron.com,
and GlitchTip exposes **no API** to read alert rules / webhook recipients /
delivery logs (probed 2026-06-29: /rules/, /alert-rules/, /alerts/ all 404).
So the only way to learn the real shape is to RECEIVE one webhook at a listener.

Modes
-----
  inspect    Read-only: list projects, confirm the no-alert-API constraint,
             and print the one-time manual alert->webhook config runbook.
  lifecycle  Validate the disposable-project path: create -> fetch DSN -> delete.
  send-test  Create (or reuse) a disposable project + send a synthetic event via
             its DSN so a configured alert fires (so you don't need a real error).
  listen     Run an HTTP listener that writes the FIRST received POST verbatim to
             a fixture (body + headers). Run this where the VPS can reach it.
  verify     Drift-check: assert a captured fixture still carries the fields the
             watchdog parser reads. Warn-only by default; --check exits non-zero
             on drift (for CI). Never imports fabrik-lib (vendor, don't import).
  cleanup    Delete the disposable project.

Capture runbook (one-time, operator):
  1. `glitchtip_webhook_capture.py listen --out FIXTURE.json` on a VPS-reachable host.
  2. In GlitchTip UI (no API): project -> Alerts -> add a webhook recipient = the
     listener URL, rule "a new issue is created".
  3. `glitchtip_webhook_capture.py send-test` (or trigger a real error).
  4. The listener writes FIXTURE.json; hand it to the fabrik-lib parser-pin.
  5. `glitchtip_webhook_capture.py cleanup`.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from fabrik.drivers.glitchtip import (  # noqa: E402
    GLITCHTIP_URL,
    _fetch_dsn,
    _headers,
    _org_team,
    create_project,
    delete_project,
)

DISPOSABLE = "watchdog-webhook-probe"


def _api_get(path: str) -> tuple[int, str]:
    req = urllib.request.Request(GLITCHTIP_URL + path, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310 — our own infra
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(400).decode("utf-8", "replace")


def cmd_inspect(_args: argparse.Namespace) -> int:
    org, team = _org_team()
    print(f"[glitchtip-capture] base={GLITCHTIP_URL} org={org} team={team}")
    st, body = _api_get(f"/api/0/organizations/{org}/projects/")
    if st == 200:
        slugs = [p.get("slug") for p in json.loads(body)]
        print(f"[glitchtip-capture] projects: {slugs}")
    else:
        print(f"[glitchtip-capture] projects -> HTTP {st}", file=sys.stderr)
    # Confirm the no-alert-API constraint so the runbook is grounded, not assumed.
    probe = slugs[0] if st == 200 and slugs else "ocoron"
    rs, _ = _api_get(f"/api/0/projects/{org}/{probe}/rules/")
    print(f"[glitchtip-capture] alert-rule API present: {rs != 404} (HTTP {rs} on /rules/)")
    print(
        "\nNo alert/webhook API → configure once in the GlitchTip UI:\n"
        "  project → Alerts → New → recipient = <listener URL> → rule 'new issue'.\n"
        "Then: `listen` (VPS-reachable) → `send-test` → fixture written → `cleanup`."
    )
    return 0


def cmd_lifecycle(_args: argparse.Namespace) -> int:
    """Validate create → DSN → delete without sending anything (minimal live writes)."""
    org, _team = _org_team()
    headers = _headers()
    print(f"[glitchtip-capture] creating disposable project {DISPOSABLE!r} …")
    create_project(
        DISPOSABLE
    )  # platform defaults to "python"; 2nd arg is platform, not description
    try:
        dsn = _fetch_dsn(org, DISPOSABLE, headers)
        print(f"[glitchtip-capture] DSN fetched: {dsn.split('@')[-1]} (key redacted)")
    finally:
        delete_project(DISPOSABLE)
        print(f"[glitchtip-capture] deleted {DISPOSABLE!r} ✓")
    return 0


def cmd_send_test(args: argparse.Namespace) -> int:
    org, _team = _org_team()
    headers = _headers()
    project = args.project
    created = False
    if not _project_exists(org, project, headers):
        create_project(project)  # platform defaults to "python"
        created = True
    try:
        dsn = _fetch_dsn(org, project, headers)
        _send_sentry_event(dsn)
        print(f"[glitchtip-capture] sent synthetic event into {project!r} — webhook should fire")
    finally:
        if created and not args.keep:
            delete_project(project)
            print(f"[glitchtip-capture] deleted disposable {project!r}")
    return 0


def _project_exists(org: str, name: str, headers: dict[str, str]) -> bool:
    st, _ = _api_get(f"/api/0/projects/{org}/{name}/")
    return st == 200


def _send_sentry_event(dsn: str) -> None:
    """POST a minimal Sentry event to the DSN's store endpoint (Sentry protocol)."""
    # DSN: https://<public_key>@<host>/<project_id>
    rest = dsn.split("://", 1)[1]
    public_key, hostpath = rest.split("@", 1)
    host, project_id = hostpath.rsplit("/", 1)
    url = f"https://{host}/api/{project_id}/store/"
    event = {
        "message": "ZeroDivisionError: division by zero (watchdog capture probe)",
        "level": "error",
        "platform": "python",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(event).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Sentry-Auth": f"Sentry sentry_version=7, sentry_key={public_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310 — our own infra
        r.read()


def cmd_listen(args: argparse.Namespace) -> int:
    out = Path(args.out)
    captured: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 — http.server API
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8", "replace")
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                body = {"_raw": raw}
            captured["headers"] = dict(self.headers)
            captured["body"] = body
            captured["captured_at"] = datetime.now(UTC).isoformat()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, *_a: object) -> None:  # silence default logging
            pass

    srv = HTTPServer(("0.0.0.0", args.port), Handler)  # noqa: S104 — must be VPS-reachable
    print(f"[glitchtip-capture] listening on :{args.port} — waiting for ONE webhook POST …")
    while "body" not in captured:
        srv.handle_request()
    out.write_text(json.dumps(captured, indent=2), encoding="utf-8")
    print(f"[glitchtip-capture] captured → {out}")
    return cmd_verify(argparse.Namespace(fixture=str(out), check=False))


# --- drift-check: structural assertion of the parser's expected field-map ------
# Mirrors fabrik-lib error_tracker_webhook.from_payload WITHOUT importing it.
def _envelope_fields(body: dict) -> dict[str, object] | None:
    atts = body.get("attachments")
    if not isinstance(atts, list) or not atts or not isinstance(atts[0], dict):
        return None
    att = atts[0]
    title = att.get("title") or body.get("text")
    if not title:
        return None
    return {
        "name": title,
        "url": att.get("title_link"),
        "severity_via": "color",
        "color": att.get("color"),
    }


def _issue_fields(body: dict) -> dict[str, object] | None:
    issue = body.get("issue")
    if not isinstance(issue, dict):
        data = body.get("data")
        issue = data.get("issue") if isinstance(data, dict) else None
    if not isinstance(issue, dict):
        issue = body if (body.get("title") or body.get("message")) else None
    if not isinstance(issue, dict):
        return None
    name = issue.get("title") or issue.get("message")
    if not name:
        return None
    return {"name": name, "level_via": issue.get("level") or issue.get("severity")}


def cmd_verify(args: argparse.Namespace) -> int:
    fixture = Path(args.fixture)
    if not fixture.exists():
        print(f"[glitchtip-capture] no fixture at {fixture} — capture one first", file=sys.stderr)
        return 1 if args.check else 0
    data = json.loads(fixture.read_text(encoding="utf-8"))
    body = data.get("body", data)
    resolved = _envelope_fields(body) or _issue_fields(body)
    if resolved and resolved.get("name"):
        print(f"[glitchtip-capture] ✓ parser fields resolve: {resolved}")
        return 0
    print(
        "[glitchtip-capture] ⚠️  DRIFT: captured payload no longer yields a parser "
        f"`name` — envelope/issue shape changed. body keys={list(body)[:8]}",
        file=sys.stderr,
    )
    return 1 if args.check else 0


def cmd_cleanup(_args: argparse.Namespace) -> int:
    delete_project(DISPOSABLE)
    print(f"[glitchtip-capture] deleted {DISPOSABLE!r} (if it existed)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Capture + pin the GlitchTip webhook envelope.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inspect")
    sub.add_parser("lifecycle")
    sp = sub.add_parser("send-test")
    sp.add_argument("--project", default=DISPOSABLE)
    sp.add_argument("--keep", action="store_true")
    lp = sub.add_parser("listen")
    lp.add_argument("--port", type=int, default=9099)
    lp.add_argument("--out", default="docs/reference/fixtures/glitchtip-webhook.json")
    vp = sub.add_parser("verify")
    vp.add_argument("fixture", nargs="?", default="docs/reference/fixtures/glitchtip-webhook.json")
    vp.add_argument("--check", action="store_true", help="exit non-zero on drift (CI mode)")
    sub.add_parser("cleanup")
    args = ap.parse_args(argv)
    return {
        "inspect": cmd_inspect,
        "lifecycle": cmd_lifecycle,
        "send-test": cmd_send_test,
        "listen": cmd_listen,
        "verify": cmd_verify,
        "cleanup": cmd_cleanup,
    }[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
