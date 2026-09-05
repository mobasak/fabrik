# T03 — The guard asserts the captured event through a swapped transport

## Scope
REPLACE ONLY the two flag-string tests (`tests/test_scaffold_glitchtip_security.py:31-41`) — T01's template tests in the same file stay, byte-identical — moving the Python half from "the emitted text contains two flag strings" to "the CAPTURED EVENT contains no secret" (rule 55: "Verify on the CAPTURED EVENT, never the init kwarg"): load the TEMPLATE module `templates/scaffold/python/glitchtip_init.py` directly (placeholders substituted in-test into `tmp_path`; the emitter is T02, merged LAST — the guard must not wait for it), import it with `SENTRY_DSN` set and `GLITCHTIP_TRACES_SAMPLE_RATE=1.0` (the module's env knob — the TEST sets both via `monkeypatch.setenv`, the gate line sets nothing — without it transactions sample at 0.05 and the transaction assertions are vacuous), assert `init_glitchtip() is True` (the module's ImportError path logs and returns False — a missing SDK must FAIL the guard, never pass it), then capture by the reference tests' own proven mechanism — `monkeypatch.setattr(sentry_sdk.get_client().transport, "capture_envelope", events.append)` (`/opt/site-provisioner/tests/test_glitchtip_init.py:61-63`; sentry-sdk 2.x ships everything through `capture_envelope`, synchronously, no `flush()` needed), mount the emitted app, and inside one request raise after: a local variable holding a `Settings`-like repr with a DSN and a JWT secret; a JSON body with a password; an `X-Signing-Secret` header; a token in the URL query; `logging.getLogger().error("otp=%s", secret)`; an outbound `httpx` call with `?apikey=` (a breadcrumb). Assert on the ERROR event and, with `traces_sample_rate=1.0`, on the TRANSACTION event: none of the secret strings appear anywhere in what would hit the wire — `capture_envelope` receives an `Envelope`, so serialize the reference tests' way (`/opt/site-provisioner/tests/test_glitchtip_init.py:68-74`: for each envelope, for each `item` in `envelope.items`, `json.dumps(item.payload.json, default=repr)`, joined) and substring-search that string, never a field list; `logentry` carries `message` only; `breadcrumbs` is absent or empty; `contexts`/`request`/`exception` hold only allowlisted keys. Keep the Node assertions (`:44-53`) as they are. Record the installed `sentry_sdk.VERSION` in the test's output line. Watched-fail-first: the same assertions are run once against the CURRENT inline literal (the f273064c init) — extracted by COMMAND, not by reading the 281 KB file — run this block verbatim (a heredoc: no shell escaping to get wrong; review pass 6 proved the previous one-liner was not shell-executable as printed):

```
python3 - <<'PY'
import re
s = open('src/fabrik/scaffold.py').read()
m = re.search(r"glitchtip_init\.py\"\)\.write_text\('''(.*?)'''\)", s, re.S)
open('/tmp/old_glitchtip_init.py', 'w').write(m.group(1))
print(len(m.group(1)), 'chars')
PY
```

(the literal opens MID-LINE at `src/fabrik/scaffold.py:1678` and closes at `:1737`, so a line-range `sed` drops the docstring opener and the last two lines — proven: the regex extract is 2,830 chars and parses; the range extract did not). HOW the assertions are pointed at it: the guard loads its module from the path in `GLITCHTIP_GUARD_MODULE` (default: the substituted template in `tmp_path`), so the watched fail is `GLITCHTIP_GUARD_MODULE=/tmp/old_glitchtip_init.py python -m pytest tests/test_scaffold_glitchtip_security.py -q -k captured_event` — expected RED on the locals/body/URL/logentry/breadcrumb assertions (the old init has no scrubber); the failing assertion names are pasted into this ticket's review artifact as the watched-fail record — and seen RED — recorded in the ticket's review artifact; that red is the proof this guard tests something.

Owner: infra
Depends: T01
Deps: none of its own — T01 (merged first) authorised `sentry-sdk[fastapi]` + `structlog` in the hub dev extras; this ticket's gate assumes `pip install -e .[dev]` has run.
Parallel: —
Complexity: native
Gate: python -m pytest tests/test_scaffold_glitchtip_security.py -q
Gate: python -m pytest tests/test_scaffold_glitchtip_security.py -q -k transaction
Docs: CHANGELOG.md — orchestrator-applied

## Touches
- tests/test_scaffold_glitchtip_security.py — PRIMARY PATH

## Behavior Contract
- **Given** the emitted module with a capturing transport, **When** a route raises with the six secrets in play, **Then** the serialized ERROR event contains none of them (substring search over the whole event).
- **Given** `traces_sample_rate=1.0`, **When** the request completes, **Then** the captured TRANSACTION event contains none of them either (`before_send_transaction` is registered; `client.py:917-922` skips `before_send` for transactions).
- **Given** a `logger.error("otp=%s", secret)`, **When** captured, **Then** `logentry == {"message": "otp=%s"}` — the template, never the interpolation; and no breadcrumb carries it.
- **Given** the current inline literal extracted to `/tmp/old_glitchtip_init.py`, **When** `GLITCHTIP_GUARD_MODULE=/tmp/old_glitchtip_init.py python -m pytest … -k captured_event` runs, **Then** it is RED — the failing assertion names recorded in the ticket's review artifact as the watched fail.
- **Given** the Node emitter, **When** the existing two Node assertions run, **Then** they still pass (unchanged surface).
- **Given** the hub `.venv` (T01 installed the dev extras), **When** the guard imports the template module, **Then** `init_glitchtip()` returns True and `sentry_sdk.VERSION` is printed — a False (the ImportError path) fails the test.
- **Given** T01's template tests in the same file, **When** T03 merges, **Then** they are byte-identical (the diff touches only the two replaced tests and the additions).

## Context Files
- templates/scaffold/python/glitchtip_init.py
- .windsurf/rules/core/45-testing-strategy.md
- .windsurf/rules/core/55-observability.md

(Out-of-repo read, measured and outside the budget: `/opt/site-provisioner/tests/test_glitchtip_init.py` 69,210 B — the 59 tests this guard's cases are drawn from.)
