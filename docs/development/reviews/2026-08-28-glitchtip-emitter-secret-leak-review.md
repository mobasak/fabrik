# Review — scaffold GlitchTip emitter secret-leak fix

Surface: 6916ebb347600ba7f369435f5fb2e8c4d33634ed + diff-md5 d4a10e9e59abe48a10093a19f622834f

**Finding (transdoc 01M13279RB + correction 01M133NZWN, routed to @fleet via 01M13S4E):** the
scaffold-emitted `glitchtip_init` ships the JWT signing secret, DB DSN, and live request-body values to
GlitchTip on any handled ERROR log — `send_default_pii=False` closes neither channel.

**Fix under review (src/fabrik/scaffold.py, both emitters):**
- Python `sentry_sdk.init` (~1587): `+ include_local_variables=False` `+ max_request_body_size="never"`.
- Node `Sentry.init` (~3453): `+ includeLocalVariables: false` — and, GROUNDED (Sentry docs via context7),
  deliberately NOT the pack-mandated `maxRequestBodySize: 'never'` (no such @sentry/node option — Python-only;
  with `sendDefaultPii: false` Node reports body SIZE only, not content). Regression test both emitters.

The `review_rubric.py` invocation armed the finders (FLOOR: core/35-security-auth; MATCHED: core/10-python
GlitchTip discipline; + standing recurrence classes). HUB surface — the emitter distributes to every project.

Reviewers: pool `fanout("review", mode=read_only")` + native `fabrik-reviewer` Opus (authoritative, security
surface) + orchestrator Opus. Pass 2 is the native Opus authoritative pass.

## Coverage Checklist
| # | Class | Verdict |
|---|---|---|
| 1 | Python: third leak channel — HTTP `Authorization` header | REFUTED — the default `EventScrubber()` is ON regardless of `send_default_pii`, and the real installed `DEFAULT_DENYLIST` (32 entries) contains `authorization`, `x_api_key`, `token`, `secret`, `api_key`, `cookie` → the header value is scrubbed by key. (deepseek's "only Cookie filtered" was pre-EventScrubber.) Header keys retained, values redacted. |
| 2 | Node grounding: body size-only via sendDefaultPii + includeLocalVariables the only needed flag | CLEAN — independently confirmed by pool finder (gemini) + Sentry docs: `@sentry/node` has no `maxRequestBodySize` init option; with `sendDefaultPii:false` the body is size-only; locals default ON for Node → `includeLocalVariables:false` is the correct single flag. |
| 3 | dead-code avoidance: correctly did NOT emit the invalid @sentry/node body flag | CLEAN — the invalid Python-style flag is absent from the Node emitter (test asserts it never appears). |
| 4 | pack↔scaffold divergence on the Node body flag — correct + conformance risk | REFUTED (as a scaffold defect) — the scaffold is RIGHT: emitting the invalid flag would be a silent no-op, so omitting it is correct; the pack (`55-observability.md:200`) is the one that's wrong, escalated upstream to infra (`01M13YVJ`). No hub conformance gate greps the pack's exact flag string, so no gate trips. |
| 5 | test quality (behavior-without-a-test) | CLEAN — both emitters red-on-revert proven (strip flags → both tests fail); qwen confirmed no wrong-reason pass; the two reported behaviors (Python 2-flag, Node 1-flag+no-bogus) each have a test. |
| 6 | fail-open/closed: init no-ops safely when DSN unset / SDK missing | CLEAN — the DSN-guard + try/except ImportError paths are unchanged; qwen confirmed. |
| 7 | secret-in-code / 12-Factor III | CLEAN — no secret/constant introduced; only structural SDK flags added. |
| 8 | boundary/sentinel/prefix | CLEAN — the test's `"maxRequestBodySize" not in init` substring guard was made precise (comment reworded so the bogus token never appears); the flag-string asserts are exact. |
| 9 | cost/quota/limit accounting | CLEAN — N/A: no cost/quota/limit accounting in either emitter (sample-rate envs unchanged). |

## Native-Opus authoritative sweep (Pass 2) — grounded against installed sentry-sdk 2.55.0
| # | Channel | Verdict |
|---|---|---|
| O1 | `Authorization` request header | **REFUTED** — double-covered: `_asgi_common`/`_filter_headers` redacts `SENSITIVE_HEADERS` (incl. `AUTHORIZATION`) at extraction with `send_default_pii=False`, AND the default `EventScrubber` scrubs `authorization`/`proxy-authorization`. Confirms the Pass-1 refutation. No fix. |
| O2 | non-standard auth headers (`X-Auth-Token`, `X-Access-Token`, `Api-Key`…) | **RESIDUAL (out of scope)** — `SENSITIVE_HEADERS` is short; a JWT in a custom header ships. Config-closeable via `EventScrubber(denylist=DEFAULT_DENYLIST + [exact keys])` ONLY if a project uses such a header — fleet-specific, not a base-emitter concern, and not the reported finding. Noted for the pack. |
| O3 | exception message / repr (`raise ValueError(f"…{secret}")`) | **RESIDUAL (uncloseable by init)** — no `init` flag scrubs `exception.values[].value`; app-logging hygiene. The pack already mandates "short event name + correlation_id, never interpolate." Inline caveat added to the emitted comment. |
| O4 | `LoggingIntegration` `logentry.formatted`/`params` + non-denylisted `extra` | **RESIDUAL (uncloseable by init)** — free-text content channel; same app-hygiene class as O3. |
| O5 | breadcrumb message | **RESIDUAL (uncloseable by init)** — same class. |
| O6 | emitted comment overstated "closes NEITHER channel" | **FIXED** — reworded: `send_default_pii=False` + the default header filter/scrubber DO close the header channels; the two flags close locals/body; added the "flags do not sanitize free-text log content" caveat. |

**Net (native Opus):** the two Python flags + the Node flag *completely* close the two STRUCTURAL channels transdoc
reported (frame LOCALS + request BODY — `request_body_within_bounds` returns False for `"never"`). O1 refuted.
O2 is a fleet-specific config residual; O3/O4/O5 are free-text CONTENT channels no `init` option can close (app
hygiene, pack-covered). Only cosmetic O6 was changed in code.

## Residual (deliberate, documented)
- **Content channels (O3/O4/O5)** and **custom auth headers (O2)** are NOT closeable by the scaffold's `init`
  flags. O3/O4/O5 are app-logging-hygiene (never interpolate a secret into a log/exception string) — `55-observability.md`
  already mandates the discipline, and the emitted comment now carries the caveat. O2's denylist extension is
  fleet-specific. Both routed to infra as pack-note candidates (the pack thread opened by finding `01M13YVJ`).

## Pass Ledger
| Pass | finders | found | new | fixed |
|-----:|---|---:|---:|---:|
| 1 | pool `fanout("review")` ×3 (deepseek, gemini, qwen) + orchestrator grounding (context7 Sentry docs + live DEFAULT_DENYLIST) | 3 | 3 | 0 |
| 2 | native `fabrik-reviewer` Opus (authoritative, grounded vs installed sentry-sdk 2.55.0) + orchestrator | 6 | 5 | 1 (O6 comment) |
| 3 | orchestrator re-adjudication — O1 refuted (confirmed), O2–O5 residual/out-of-scope, in-scope structural channels CLOSED; gate green | 0 | 0 | 0 → EXIT (no in-scope defect stands; only a cosmetic comment changed) |
