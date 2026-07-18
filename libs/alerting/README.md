# alerting

Fire-and-forget operational alerts with a two-hop delivery chain and title-based
dedup. **Never raises, never blocks the caller more than ~12s.** Stdlib-only (no
`apprise`/`requests` dependency — the name refers to the VPS Apprise service it
POSTs to, not the PyPI package).

## Delivery chain

1. **SSH → VPS Apprise** (primary) — `ssh <host> curl … --data-binary @- <apprise>/notify`, the JSON body piped over ssh **stdin**.
2. **Direct Telegram Bot API** (fallback, if SSH/Apprise fails) — stdlib `urllib`.
3. **Log a warning** (if both fail) — the alert is not lost silently.

A given `title` is suppressed for `ALERT_MIN_INTERVAL` seconds after a
**successful** send (a failed send is *not* recorded, so retries get through).

## Vendor it

```bash
cp -r /opt/fabrik-lib/alerting /opt/my-project/alerting
```

## Usage

```python
from alerting import send_alert

send_alert(
    title="PAUSED: iproyal_bw",                     # short; also the dedup key
    body="IPRoyal returned 402. Top up at dashboard.iproyal.com",
    severity="critical",                            # "critical" | "warning" | "info"
)
```

## Configuration (env)

| Var | Default | Purpose |
|---|---|---|
| `ALERT_ENABLED` | auto | `1` on / `0` off; auto-on if `TELEGRAM_BOT_TOKEN` or `ALERT_VPS_HOST` is set |
| `ALERT_MIN_INTERVAL` | `300` | Per-title dedup window (seconds) |
| `ALERT_VPS_HOST` | `vps` | SSH config alias for the hub VPS |
| `ALERT_APPRISE_URL` | `http://apprise:8000` | Apprise URL reachable **from** the VPS |
| `TELEGRAM_BOT_TOKEN` | — | Bot token (@BotFather) for the direct fallback |
| `TELEGRAM_CHAT_ID` | — | Target chat/user id |

## Security note

The Apprise hop runs a command over SSH, and **ssh re-joins everything after the
host into one string parsed by the remote shell**. The JSON payload (which
embeds `title`/`body`, often derived from error text) is therefore **never**
placed on the command line — `curl` reads it from stdin via `--data-binary @-`,
which ssh forwards from our process stdin. This avoids both word-splitting a
valid payload and shell-injection from hostile alert content.

## Verify it works (manual)

```bash
# with a reachable VPS + Apprise, or TELEGRAM_* set:
python -c "from alerting import send_alert; print(send_alert('test','hello','info'))"
```

Unit tests (`test_alerting.py`) cover the injection guard, dedup, enable/disable,
and the apprise→telegram→fail chain with subprocess/urllib mocked (no live deps).

## Dependencies

None beyond the Python standard library. See `requirements.txt`.

---

## Found a bug or a gap? Send it upstream — don't fork it

This module is **vendored (copied)** into your project, so a fix you make in your copy helps nobody else
and the next project re-hits it. A vendored copy cannot fix itself.

Append the symptom + your fix to **`UPSTREAM_FEEDBACK.md`** in this module's fabrik-lib directory (create
the file if it isn't there yet) and fabrik-lib folds it into the canonical module — every future vendor
inherits it. Include: what broke, the `path:line`, what you changed downstream, and whether you'd
recommend upstreaming it. This is the **only** write a consuming project should make into fabrik-lib.

⚠️ **Several AI agents author in this repo at once.** Stage **explicit paths only** (`git add <file>`) —
never `git add -A` — and never bundle a file you didn't write.
