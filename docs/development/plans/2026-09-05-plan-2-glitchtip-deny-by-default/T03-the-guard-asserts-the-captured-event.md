# T03 — The guard asserts the captured event through a swapped transport

## Scope
Rewrite `tests/test_scaffold_glitchtip_security.py`'s Python half from "the emitted text contains two flag strings" (`:31-41`) to "the CAPTURED EVENT contains no secret" (rule 55: "Verify on the CAPTURED EVENT, never the init kwarg"): load the TEMPLATE module `templates/scaffold/python/glitchtip_init.py` directly (placeholders substituted in-test into `tmp_path`; the emitter is T02, merged LAST — the guard must not wait for it), import it with `SENTRY_DSN` set and `sentry_sdk`'s transport swapped for a capturing one (`sentry_sdk.transport.Transport` subclass collecting envelopes), mount the emitted app, and inside one request raise after: a local variable holding a `Settings`-like repr with a DSN and a JWT secret; a JSON body with a password; an `X-Signing-Secret` header; a token in the URL query; `logging.getLogger().error("otp=%s", secret)`; an outbound `httpx` call with `?apikey=` (a breadcrumb). Assert on the ERROR event and, with `traces_sample_rate=1.0`, on the TRANSACTION event: none of the secret strings appear anywhere in the serialized envelope (`json.dumps(event)` — a substring search over the WHOLE event, not a field list); `logentry` carries `message` only; `breadcrumbs` is absent or empty; `contexts`/`request`/`exception` hold only allowlisted keys. Keep the Node assertions (`:44-53`) as they are. Record the installed `sentry_sdk.VERSION` in the test's output line. Watched-fail-first: the same assertions are run once against the CURRENT inline literal extracted from `src/fabrik/scaffold.py:1678-1735` (the f273064c init) and seen RED — recorded in the ticket's review artifact; that red is the proof this guard tests something.

Owner: infra
Depends: T01
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
- **Given** the current inline literal (the two-flag init at `src/fabrik/scaffold.py:1678-1735`), **When** the same assertions run against it, **Then** they are RED — recorded in the ticket's review artifact as the watched fail.
- **Given** the Node emitter, **When** the existing two Node assertions run, **Then** they still pass (unchanged surface).

## Context Files
- templates/scaffold/python/glitchtip_init.py
- .windsurf/rules/core/45-testing-strategy.md
- .windsurf/rules/core/55-observability.md

(Out-of-repo read, measured and outside the budget: `/opt/site-provisioner/tests/test_glitchtip_init.py` 69,210 B — the 59 tests this guard's cases are drawn from.)
