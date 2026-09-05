"""GlitchTip / Sentry SDK initialization (FastAPI service).

Reads SENTRY_DSN, falling back to GLITCHTIP_DSN. If neither is set → no-op (zero
overhead).

Import this module BEFORE FastAPI app creation in main.py:
    from {pkg}.glitchtip_init import init_glitchtip
    init_glitchtip()  # call once at module load
    app = FastAPI(...)

VENDORED — do not edit here expecting it to stick upstream.
  origin:   site-provisioner  api/glitchtip_init.py
  revision: 13d3243
Copied under the fabrik-lib law (vendor, never import across repos). It is a COPY: to
pull a later upstream fix, re-vendor and move the revision above, so a reader can always
diff this file against the sha it claims to be.

⚠️ THIS SURFACE MOVES. The first vendor pinned 4f5c158 and was six commits stale within
two hours — and the gap was not cosmetic: one commit fixed a redaction that missed 68.8%
of the shape it was built for, another closed a logging channel `_scrub_event` cannot
reach at all. Re-vendor by VERIFYING the upstream revision at that moment
(`git -C /opt/site-provisioner log -1 --format=%h -- api/glitchtip_init.py`), never by
trusting a sha written in a ticket.

Scaffold adaptations, all deliberate and each graded by
tests/test_scaffold_glitchtip_security.py:
  * ``server_name`` defaults to the service name, not the reference's hardcoded one;
  * ``LoggingIntegration(event_level=logging.ERROR)`` is the FLEET default (D-126) — the
    reference uses ``event_level=None``, which suits a service that never wants a log
    record to become an event. ``level`` and ``sentry_logs_level`` stay None, exactly as
    upstream: see the coupling note beside the call;
  * both integrations keep ``transaction_style="endpoint"``, the scaffold's existing
    transaction NAMING — dropping it would silently rename every transaction.

Apart from those, this file is byte-identical to the origin at the revision above, plus
COMMENTS added here. When re-vendoring, diff with comments in mind: the executable bytes
are the contract, not the prose.
"""
import logging
import os
import re

import structlog

# DENY BY DEFAULT. Everything below is an ALLOWLIST: a field is kept because it is named
# here, not dropped because someone remembered to remove it.
#
# This inversion is deliberate and was reached the hard way. Leak channels were found
# one at a time over five review rounds — frame locals, request body, log params, log
# breadcrumbs, scope extra, source context, outbound-URL breadcrumbs, request.url/query,
# transaction extra, db-span SQL, and span data.http.query — because each fix REMOVED A
# KNOWN-BAD FIELD. That is a denylist, and a denylist cannot see what it was not told
# about; it is the same failure the original report warned against ("do NOT fix this with
# a before_send name-denylist"), one level up: at the FIELD level instead of the KEY
# level. Real captured events also carry `_meta` (`serializer.py:420`, observed at
# `before_send`), which no round had considered. An earlier version of this comment named
# `aggregates` and `attrs` alongside it; both are SESSION-envelope fields
# (`sessions.py:140`), not event fields, in sentry-sdk 2.68.1 — the claim was 1 of 3 true
# and is corrected here rather than quietly dropped, because it also went to the hub.
# The allowlist drops unknown keys regardless, so nothing about the behaviour changes —
# which is exactly the point of deny-by-default: it was already correct about a field
# whose existence this comment described wrongly.
#
# So: name what triage genuinely needs, and drop the rest — including fields a future
# sentry-sdk adds, which is the case no enumeration can ever cover.
_ALLOWED_EVENT_KEYS = frozenset({
    "event_id", "timestamp", "start_timestamp", "platform", "level", "logger",
    "environment", "release", "server_name", "sdk", "type", "transaction",
    "transaction_info", "contexts", "exception", "threads", "logentry", "message",
    "modules", "measurements", "request", "spans",
})
# NOT "breadcrumbs": empty today only because of SDK CONFIG (max_breadcrumbs=0).
# Dropping the key costs nothing now and keeps it closed if that config regresses — one
# layer is not a proof, which is this module's whole premise.
# `logentry` IS kept, but drilled: `message` is the un-interpolated template, while
# `params`/`formatted` carry the interpolated VALUES.
# An earlier version of this comment justified the key by claiming that dropping it
# "would strip the message from every capture_message event". Measured against
# sentry-sdk 2.68.1: capture_message populates the TOP-LEVEL `message` key and leaves
# `logentry` absent, so the true number is ZERO. Its only producer is the logging
# integration, which this module disables outright — the key is unreachable in this
# configuration and is kept as a backstop against a future config change, not for the
# reason originally given.
_ALLOWED_LOGENTRY_KEYS = frozenset({"message"})
# NOT url / query_string / data / cookies: values, and ungated by the SDK.
_ALLOWED_REQUEST_KEYS = frozenset({"method", "headers", "env"})
# `env` holds only REMOTE_ADDR under ASGI today, and only when send_default_pii is on —
# but that is a guarantee living in the SDK, not here, and this module's premise is that
# one layer is not a proof. Drilled like every other kept sub-structure.
_ALLOWED_ENV_KEYS = frozenset({"REMOTE_ADDR", "SERVER_NAME", "SERVER_PORT"})
# Header NAMES are allowlisted too. Keeping `headers` wholesale would delegate safety to
# sentry_sdk's own SENSITIVE_HEADERS — a fixed tuple of 8 entries, 7 DISTINCT (the SDK
# lists X_FORWARDED_FOR twice; measured, not read off the source) — which is the very
# denylist shape this module abandoned: it covers Authorization/Cookie/X-Api-Key but not
# an X-Hub-Signature, an X-Signing-Secret, or any future custom auth header. Reproduced:
# a custom `X-Internal-Signing-Secret` shipped its value in full. These names are
# diagnostic and carry no credential.
_ALLOWED_SPAN_SCHEMES = frozenset({"http", "https"})
# "does this look like a URL rather than a route template / task name?" — used to decide
# whether `transaction` needs reducing. ONE definition; `_safe_origin` does its own,
# stricter parse (it also captures the authority) and remains the authority on SAFETY.
#
# The optional leading verb is not decoration. This comment used to claim the pre-check
# was merely "cheaper" than `_safe_origin` — i.e. that everything `_safe_origin` accepts,
# this matches. It did not hold: `_safe_origin` splits a leading verb off BEFORE parsing,
# so `"GET https://api.example.com/v1/reset?token=SEC"` was accepted there and rejected
# here, and the fallback transaction branch therefore returned that name WHOLE, token
# included. Unreachable in this service today (no ASGI path emits a verb-prefixed
# transaction name), but the containment the comment asserted is now actually true.
#
# A route template keeps its verb because it has no `scheme://`: "GET /widgets/{id}"
# does not match, and must not — reducing a matched route's template is the mirror
# failure this whole branch is conditional to avoid.
#
# The whitespace classes are not cosmetic either. The FIRST version of this widening
# asserted the containment in prose and was still false: `_safe_origin` tolerates leading
# and doubled whitespace, so "  https://h/p" and "GET  https://h/p" were accepted there
# and rejected here — the fuzz of that claim found violations. A containment
# asserted in a comment is worth what any unexecuted claim is worth, so the relation is
# now GRADED by a property test that fuzzes it rather than restated here.
_LOOKS_LIKE_URL_RE = re.compile(r"^\s*(?:\S+\s+)?[a-zA-Z][a-zA-Z0-9+.\-]*://")
# The span "verb" is allowlisted like everything else. It was previously re-emitted
# verbatim — "whatever precedes the first space" — so a description shaped
# "Authorization:Bearer-<secret> http://host" kept the secret while the URL half was
# correctly reduced. The URL half was deny-by-default and the verb half allow-by-default,
# in a function whose docstring claimed both were proven safe.
_ALLOWED_SPAN_VERBS = frozenset({
    "GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "CONNECT", "TRACE",
})
# `mechanism` is the ONE reduction that had no key allowlist — it nulled containers but
# passed any scalar through, so `mechanism["data"] = "<secret>"` shipped while
# `mechanism["data"] = {"k": "<secret>"}` was correctly dropped. Every test nested the
# secret one level deeper, so `data` was always a dict and the gap never showed.
# `data`/`meta` are a documented arbitrary bag with no triage value here, so they are
# simply not named — the same treatment span `data` already gets.
_ALLOWED_MECHANISM_KEYS = frozenset({
    "type", "handled", "synthetic", "description", "help_link", "exception_id",
    "parent_id", "is_exception_group", "source",
})
# Headers whose VALUE is a URL, so it is reduced to an origin rather than kept whole.
_URL_VALUED_HEADERS = frozenset({"referer", "origin"})
_ALLOWED_HEADER_NAMES = frozenset({
    "accept", "accept-encoding", "accept-language", "content-length", "content-type",
    "host", "origin", "referer", "user-agent",
})
# NOT "data": an arbitrary key-value bag. httpx/stdlib write the raw query string to
# data["http.query"] with no PII gate, which is how a later channel stayed open after
# the span DESCRIPTION was already being truncated.
_ALLOWED_SPAN_KEYS = frozenset({
    "op", "span_id", "parent_span_id", "trace_id", "start_timestamp", "timestamp",
    "status", "origin", "description",
})
# NOT arbitrary app-set contexts; "trace" is required for correlation.
_ALLOWED_CONTEXT_KEYS = frozenset({"trace", "runtime", "os"})
# `contexts.trace` carries its own data bag; allowlist inside it as well.
_ALLOWED_TRACE_KEYS = frozenset({"trace_id", "span_id", "parent_span_id", "op", "status", "origin"})
# runtime/os are SDK-populated and benign today, but they are dicts nobody drilled into —
# the same gap contexts["trace"] had before it was closed.
_ALLOWED_RUNTIME_KEYS = frozenset({"name", "version", "build"})
# Frame fields carrying VALUES rather than location. include_local_variables=False and
# include_source_context=False suppress these at the SDK layer; this is the structural
# backstop, because frame locals were leak channel #1 and rested on one config flag.
# Frames are REBUILT from these, not stripped of known-bad keys. Popping a fixed list is
# a denylist wearing a different coat: every other branch here rebuilds through _keep,
# and this one did not, so any shape deviation (values as a dict, stacktrace as a list,
# an extra key on the holder) shipped the ORIGINAL verbatim. Location survives; values do
# not — `vars`, `pre_context`, `context_line`, `post_context` are simply not named.
_ALLOWED_FRAME_KEYS = frozenset({
    "filename", "abs_path", "function", "lineno", "colno", "module", "in_app", "package",
})
_ALLOWED_EXC_VALUE_KEYS = frozenset({"type", "value", "module", "mechanism", "stacktrace", "id",
                                     "name", "crashed", "current"})


def _scalar_or_none(value):
    """Keep a scalar leaf; drop anything else, including a tuple/set/custom object."""
    return value if value is None or isinstance(value, _SCALARS) else None


# Keys whose value is legitimately a CONTAINER. Every other allowlisted key must hold a
# scalar, and `_keep` now enforces that — see its docstring.
# ⚠️ This set is GLOBAL, not per-allowlist: a key named here is exempt from the scalar-leaf
# rule wherever it appears. That is fine only because every member reachable through an
# allowlist is DRILLED by its caller. Two members (`frames`, `values`) are in no allowlist
# at all — they are drilled by `_rebuild_exception_holder` directly and are listed here as
# documentation, not as live rules.
#
# The latent bypass, named because it is one edit away: adding a container-valued key to
# `_ALLOWED_EVENT_KEYS` grants it the exemption at a level where nothing drills it, and it
# would ship whole. `stacktrace` is the live example — a real top-level `Event` key
# (`_types.py`) that is in this set for `_ALLOWED_EXC_VALUE_KEYS`'s sake. It is NOT in the
# event allowlist, and `test_container_exempt_top_level_keys_are_all_drilled` is what keeps
# it that way, rather than this comment.
_CONTAINER_VALUED_KEYS = frozenset({
    "request", "contexts", "logentry", "exception", "threads", "spans", "sdk", "modules",
    "measurements", "transaction_info", "headers", "env", "stacktrace", "frames",
    "values", "packages", "integrations", "mechanism", "trace", "runtime", "os",
})


def _keep(mapping: dict, allowed: frozenset) -> dict:
    """Keep allowlisted keys, and require a SCALAR value unless the key holds a container.

    Filtering by key NAME alone was the last instance of this module's recurring defect:
    a field that is always a string in real SDK output (`exception.values[].value`,
    `contexts.trace.trace_id`, `logentry.message`, `request.method`, `spans[].status`,
    thread `id`/`name`, …) would ship a nested dict verbatim if a third-party event
    processor or a future SDK ever put one there. Enforcing the leaf shape HERE closes that gap
    for every caller at the one helper they share, rather than adding a check per site —
    the class, not the instances. The number of such sites is deliberately not stated: it
    is a historical count a reader cannot check, and it would rot the moment a caller is
    added or removed.
    """
    return {
        k: (v if k in _CONTAINER_VALUED_KEYS else _scalar_or_none(v))
        for k, v in mapping.items()
        if k in allowed
    }


def _safe_origin(description: str) -> str | None:
    """Return "VERB scheme://host" if the description parses as one, else None.

    DENY BY DEFAULT, like everything else here. The previous version tried to SANITIZE
    an arbitrary string by cutting at "?" / "#", which silently did nothing whenever the
    description was not URL-shaped — so a redis `cache.get` key ("session:<token>") or a
    `subprocess` argv ("curl -H Authorization:Bearer <secret> ...") shipped whole, since
    only db-op descriptions are dropped outright. That is the same enumerate-the-bad
    shape this module abandoned at the field level, recurring one level further in.

    So: a description survives only if it can be REBUILT from parts we can prove safe —
    a verb and a scheme+host with any userinfo removed. Anything else returns None.
    The span reducer then DROPS the description (keeping `op`,
    so the trace shape survives); `_reduce_header_value` instead keeps the header key with
    a `None` value; the `transaction` reduction nulls the field. SIX call sites, THREE
    dispositions — the transaction reduction calls it from both of its branches, which is
    why the two numbers differ and why naming only one of them keeps going wrong. This
    sentence has now been wrong three times: "one caller" when a second appeared, "two"
    when a third did, and "three callers" once the call sites became four while the
    dispositions stayed three. Both counts are stated, and both are grep-checkable.
    """
    parts = description.strip().split(" ", 1)
    verb, target = (parts[0], parts[1]) if len(parts) == 2 else ("", parts[0])
    # `\s` in the authority class matters: excluding only /?# folded ANY trailing text
    # into the captured "host". Reproduced end-to-end through the stock StdlibIntegration —
    # `curl <url> -H "Authorization: Bearer <token>"` became a subprocess span whose
    # description shipped the token, because none of / ? # appear in it.
    match = re.match(r"^([a-zA-Z][a-zA-Z0-9+.\-]*)://([^\s/?#]*)", target.strip())
    if not match:
        return None
    scheme, authority = match.group(1), match.group(2)
    if scheme.lower() not in _ALLOWED_SPAN_SCHEMES:
        # The scheme is "whatever precedes ://" — the same allow-by-default position the
        # verb occupied. "AKIA<secret>://host" has no space, so it parses as a scheme.
        return None
    # Userinfo rides in the authority; the previous cut kept "user:pass@host".
    host = authority.rsplit("@", 1)[-1]
    if not host:
        return None
    # Drop an unrecognised verb rather than the whole description: the origin is still
    # useful for triage, and an unnamed verb is exactly where a secret would hide.
    safe_verb = verb.strip().upper() if verb.strip().upper() in _ALLOWED_SPAN_VERBS else ""
    return f"{safe_verb} {scheme}://{host}".strip()


def _rebuild_exception_holder(holder):
    """Rebuild an exception/threads holder through allowlists at every level.

    Every OTHER branch of the scrubber REBUILDS — most via `_keep`, while `mechanism`,
    `integrations`, `modules` and `headers` rebuild directly, all enforcing scalar leaves.
    This one used to walk the
    values -> stacktrace -> frames chain and pop four known-bad keys, which meant any
    shape it did not anticipate (values as a dict, stacktrace as a list, frames as a
    dict, a non-dict value item, an extra key on the holder) fell through untouched and
    shipped the ORIGINAL data. Frame `vars` is the DB DSN and JWT secret, so that gap
    mattered. Rebuilding fails closed on every one of those shapes.
    """
    if not isinstance(holder, dict):
        return None
    values = holder.get("values")
    if not isinstance(values, list):
        return {"values": []}

    rebuilt = []
    for value in values:
        if not isinstance(value, dict):
            continue
        value = _keep(value, _ALLOWED_EXC_VALUE_KEYS)
        if "value" in value:
            # The exception MESSAGE. Kept because triage needs it; credentials stripped
            # out of any URL inside it, because a DSN in a connection error is the most
            # likely remaining path for a real secret to leave this process.
            value["value"] = _redact_userinfo_in_text(value["value"])
        if "mechanism" in value:
            # `mechanism.data`/`.meta` are a documented protocol extension point — an
            # arbitrary bag, the same shape as span data and contexts.trace.data. The
            # generic pass in _scrub_event cannot reach it, because this branch is one of
            # the explicitly-drilled ones, so apply the same reduction here.
            mechanism = value["mechanism"]
            value["mechanism"] = (
                {
                    k: _scalar_or_none(v)
                    for k, v in mechanism.items()
                    if k in _ALLOWED_MECHANISM_KEYS
                }
                if isinstance(mechanism, dict)
                else None
            )
        if "stacktrace" in value:
            stacktrace = value["stacktrace"]
            frames = stacktrace.get("frames") if isinstance(stacktrace, dict) else None
            value["stacktrace"] = {
                "frames": [
                    _keep(frame, _ALLOWED_FRAME_KEYS)
                    for frame in frames
                    if isinstance(frame, dict)
                ]
                if isinstance(frames, list)
                else []
            }
        rebuilt.append(value)
    return {"values": rebuilt}


# The four SDK-populated metadata containers that survive `_ALLOWED_EVENT_KEYS`.
#
# An earlier attempt reduced these with a generic "scalars survive, nested bags do not"
# pass. That was the wrong abstraction, for three measured reasons: a `tuple`/`set`/custom
# object bypassed the dict/list type check entirely; the depth cutoff DESTROYED real data
# (`sdk.packages` -> [], `measurements.lcp` -> None) while its own comment claimed metadata
# survived; and a FLAT secret one level in (`{"leak": "..."}`) passed through untouched, so
# it never closed the class it was written for.
#
# The terminator was already present and did not need inventing: `_ALLOWED_EVENT_KEYS`
# drops any field a future SDK adds, because it is not named. What remained was the
# interior of these four — a finite, knowable set — so they are drilled by shape.
_ALLOWED_SDK_KEYS = frozenset({"name", "version", "packages", "integrations"})
_ALLOWED_PACKAGE_KEYS = frozenset({"name", "version"})
_ALLOWED_MEASUREMENT_KEYS = frozenset({"value", "unit"})
_ALLOWED_TRANSACTION_INFO_KEYS = frozenset({"source"})
_SCALARS = (str, int, float, bool)


def _reduce_origin(value):
    """Reduce an `origin` that carries a URL; leave an instrumentation identifier alone.

    `origin` is allowlisted on BOTH `contexts.trace` and `spans[]`, and `_keep` passed it
    through verbatim because it is a scalar. sentry-sdk sets it to a short identifier
    (`manual`, `auto.http.httpx`), so it looked harmless — but the allowlist does not
    enforce that, and an event processor or a future SDK putting a URL there shipped it
    whole. The mirror was visible in a single event: in one span, `description` was
    correctly reduced to `GET https://h` while `origin` beside it carried the credential.

    Unconditional reduction is the wrong fix and was measured before being rejected:
    `_safe_origin("manual")` is `None`, so it would null every legitimate value and destroy
    the attribution `origin` exists for. This is the same conditional shape the `transaction`
    field uses — reduce what looks like a URL, keep what does not — and for the same reason.
    """
    if not isinstance(value, str):
        return _scalar_or_none(value)
    if not _LOOKS_LIKE_URL_RE.match(value):
        return value            # an instrumentation identifier: carries no user data
    return _safe_origin(value)  # a URL: origin only, or dropped if it will not parse


# Credentials inside a free-text string.
#
# ONE rule, anchored on a scheme. Three earlier designs are recorded here because each was
# refuted by measurement and the reasons are the whole content of this comment:
#
#   1. `scheme://userinfo@`, separator-keyed. Missed 68.8% of the shape it existed for: the
#      message that quotes a DSN is a URL-PARSE failure, so the separator is damaged.
#   2. The same, plus a token-boundary lookbehind. The lookbehind refused any scheme preceded
#      by `:` — the JDBC and `KEY:` shapes — and measurement showed it prevented no
#      over-redaction the other rules did not already prevent.
#   3. A scheme-LESS `something:something@` rule. This was the worst of the three and it
#      looked like the best: it caught the scheme-stripped DSN, and it destroyed ordinary log
#      content that merely contains `word:word@word` — `mailto:`, `From:` headers,
#      `12:30:45@web01`, `nginx:1.25@sha256:…`, `ns:default@cluster-a`, and Windows
#      `C:\Users\me@domain`. Over-redaction went UP against the pattern it replaced (13 of
#      80 vs 6). It was also QUADRATIC — with no scheme to prune start positions the engine
#      retries at every character: 7.4s on a 60 KB value, reachable because
#      `max_value_length` is unset so field values reach `before_send` untruncated.
#
# So the scheme is required. It is what makes this linear, and it is what distinguishes a
# DSN from the `word:word@word` that ordinary log lines are full of. The separator may be
# damaged (`://`, `:/`, `//`) because that is the failure being redacted.
#
# The userinfo class permits `? # ' "` and excludes only whitespace, `/` and `@`. That
# matters: a password containing `#` or a quote leaked 100% under every previous design,
# because the class was copied from the well-formed-URL case where those are delimiters.
# `/` stays excluded so `https://host/path@ref` keeps its path — and a `/` inside a DSN
# password is not RFC 3986-valid unencoded, which is a stated residual below, not a claim
# that it cannot happen.
# TWO sub-rules, differing only in how much corroboration a damaged separator needs.
#
# An INTACT `://` is unambiguous enough on its own: `scheme://anything@` is a URL with
# userinfo, so no colon is required inside it (this is the rule that catches the bare-token
# `https://<token>@host` form).
#
# A DAMAGED separator (`//` or `:/`) is NOT unambiguous — `src//main@HEAD` and `C:/temp@1`
# have exactly that shape and are an ordinary path and a Windows path. So it additionally
# requires a COLON inside the userinfo, which every `user:pass` DSN has and neither of those
# does. That single distinction is what lets the damaged-separator case be covered at all
# without destroying paths; an earlier design that treated both separators alike damaged
# both of those strings.
# ⚠️ Two properties below are load-bearing and both were got wrong once.
#
# THE LOOKBEHIND is what makes this linear, and that is the single most-corrected sentence
# in this module. Requiring a scheme is NECESSARY AND NOT SUFFICIENT: without a boundary the
# engine starts a match at every character of one long `[A-Za-z0-9+.\-]` run and scans the
# rest of it each time — quadratic, 2.7s at 32 KB and 15.6s at 60 KB, synchronously inside
# `before_send`. The possessive `*+` stops backtracking WITHIN a run but not the retry at
# every start position, so it alone does not fix it either (measured: still quadratic).
#
# This lookbehind is deliberately NOT the one an earlier round removed. That one forbade a
# scheme preceded by `: = ,` and so blocked `jdbc:postgresql://…` and `KEY:<dsn>` — real
# shapes. This one forbids only another SCHEME character before the scheme, which prunes
# mid-run starts while leaving every one of those shapes matchable.
#
# THE `?#` SPLIT between the two alternatives is RFC 3986, not a heuristic. In a well-formed
# URL `?` and `#` START the query and fragment, so they cannot be inside userinfo — excluding
# them from the first alternative keeps `https://h?a=1@2` intact.
#
# The second alternative accepts `://` as well as the damaged separators, and permits `?#`,
# BECAUSE IT REQUIRES A COLON in the userinfo. That combination is what catches a password
# containing `#` behind an intact separator — a shape that falls between the two rules
# otherwise, and one that leaked 100% under an earlier design. The colon is what keeps the
# permissiveness safe: `https://h?a=1@2` has no colon in that position, so it stays intact.
#
# POSSESSIVE `*+` on the scheme run. Without it this is QUADRATIC, not linear: on one long
# unbroken `[A-Za-z0-9+.\-]` run the engine starts a match at every character and backtracks
# the whole run each time — 2.7s at 32 KB, 15.6s at 60 KB, synchronously inside
# `before_send`. An earlier comment here claimed "requiring the scheme is what makes this
# linear"; requiring it is necessary and NOT sufficient, and the measurement that "proved"
# linearity used `"a:"*n`, where the colons break the runs. `*+` refuses to give back the
# run, so a start position with no separator after it fails immediately.
#
# GREEDY userinfo INCLUDING `@`, which makes this match to the LAST `@` rather than the
# first. A password containing `@` otherwise ships its tail — and ships it BEHIND a
# `[redacted]@` marker, so the output reads as a successful redaction. That is worse than
# the documented `/` residual, where the string is left visibly untouched. `_safe_origin`
# has always used `rsplit("@", 1)[-1]` for exactly this reason, with a test named for it;
# the convention simply was not carried across to this function.
_SCHEME_START = r"(?<![A-Za-z0-9+.\-])"     # the scheme cannot begin mid-token
_URL_USERINFO_RE = re.compile(
    _SCHEME_START + r"([a-zA-Z][a-zA-Z0-9+.\-]*+://)([^\s/?#]+)@"
    r"|"
    + _SCHEME_START + r"([a-zA-Z][a-zA-Z0-9+.\-]*+(?::/{1,2}|//))([^\s/]*:[^\s/]*)@"
)


def _redact_userinfo_match(m: "re.Match") -> str:
    """Rebuild the matched prefix, dropping whichever alternative's userinfo matched."""
    if m.group(1) is not None:
        return f"{m.group(1)}[redacted]@"
    return f"{m.group(3)}[redacted]@"


def _redact_userinfo_in_text(value):
    """Strip credentials out of URLs embedded in a free-text field, keeping the text.

    This closes the residual the ORIGINATING report named and left open: "never interpolate
    a secret into a log message or exception string". Allowlisting cannot help here, because
    the field is allowlisted precisely BECAUSE triage needs it — `exception.values[].value`
    is the exception message and `logentry.message` is the log template.

    ⚠️ The DRIVER MECHANISM here was asserted wrongly once and is worth stating correctly,
    because the fix's shape depends on it. The first version claimed a connection failure
    quotes the DSN. Measured against this service's real stack (SQLAlchemy 2.0.25 +
    asyncpg), it does not: a refused connection raises `ConnectionRefusedError`, a DNS
    failure `gaierror`, an auth failure `InvalidPasswordError` — none carries the URL.

    The shape that DOES quote it is a URL-PARSE failure: `ArgumentError: Could not parse
    SQLAlchemy URL from string '<the entire DSN>'`. That reverses the design constraint,
    because a URL fails to parse precisely because its separator is damaged — so the first
    fix, which required `://`, missed the only case that actually reaches this field.
    This service has a `DATABASE_URL`, so the path is real rather than theoretical.

    Deliberately narrow, and the narrowness is the point. It removes ONLY the userinfo
    segment and leaves the message, the scheme, the host and the path — so the operator
    still sees which host refused the connection, which is the whole reason the field is
    kept. It is not a general secret scanner: a bare token in prose ("token=abc123") is
    still free text and still the developer's responsibility. Claiming otherwise would be
    the denylist mistake this module was rewritten to avoid.
    """
    if not isinstance(value, str):
        return value
    return _URL_USERINFO_RE.sub(_redact_userinfo_match, value)


def _reduce_logentry(logentry: dict) -> dict:
    """Strip credentials from the log TEMPLATE, which is kept for triage."""
    if "message" in logentry:
        logentry["message"] = _redact_userinfo_in_text(logentry["message"])
    return logentry


def _reduce_trace(trace: dict) -> dict:
    """Apply the origin reduction inside an already-allowlisted trace context."""
    if "origin" in trace:
        trace["origin"] = _reduce_origin(trace["origin"])
    return trace


def _reduce_metadata(event: dict) -> None:
    """Drill the SDK metadata containers by their REAL shapes, in place."""
    sdk = event.get("sdk")
    if "sdk" in event:
        if isinstance(sdk, dict):
            sdk = _keep(sdk, _ALLOWED_SDK_KEYS)
            packages = sdk.get("packages")
            if "packages" in sdk:
                sdk["packages"] = (
                    [
                        {k: _scalar_or_none(v) for k, v in _keep(p, _ALLOWED_PACKAGE_KEYS).items()}
                        for p in packages
                        if isinstance(p, dict)
                    ]
                    if isinstance(packages, list)
                    else []
                )
            integrations = sdk.get("integrations")
            if "integrations" in sdk:
                sdk["integrations"] = (
                    [i for i in integrations if isinstance(i, str)]
                    if isinstance(integrations, list)
                    else []
                )
            for key in ("name", "version"):
                if key in sdk:
                    sdk[key] = _scalar_or_none(sdk[key])
            event["sdk"] = sdk
        else:
            event["sdk"] = None

    if "modules" in event:
        modules = event["modules"]
        event["modules"] = (
            {k: _scalar_or_none(v) for k, v in modules.items()}
            if isinstance(modules, dict)
            else None
        )

    if "measurements" in event:
        measurements = event["measurements"]
        event["measurements"] = (
            {
                name: (
                    {k: _scalar_or_none(v) for k, v in _keep(m, _ALLOWED_MEASUREMENT_KEYS).items()}
                    if isinstance(m, dict)
                    else None
                )
                for name, m in measurements.items()
            }
            if isinstance(measurements, dict)
            else None
        )

    if "transaction_info" in event:
        info = event["transaction_info"]
        event["transaction_info"] = (
            {k: _scalar_or_none(v) for k, v in _keep(info, _ALLOWED_TRANSACTION_INFO_KEYS).items()}
            if isinstance(info, dict)
            else None
        )


def _reduce_header_value(name: str, value):
    """Scalar-enforce a header value, and reduce a URL-valued one to its origin.

    `referer` and `origin` are the allowlisted headers whose values are definitionally
    URLs. `request.url` and `request.query_string` are dropped for precisely that reason,
    and span descriptions go through `_safe_origin`; these two bypassed both because the
    header ALLOWLIST reasons about NAMES ("these carry no credential"), which is true of
    the name and not of the value. Reproduced: a same-origin request from
    `/reset?token=<jwt>` shipped the token intact via `referer`.

    An earlier version of this docstring claimed `referer` was "the one" such header and
    that "every URL this module emits" was reduced — both false while `origin` sat beside it
    on the same allowlist line. (Three places in this repo said `origin` was "two lines
    above"; it is the adjacent entry on ONE line. The claim was right, the location was not
    — a locational detail nobody re-derived because the sentence around it was true.)
    Stated cost of including `origin`: the literal
    `Origin: null` (sandboxed iframes) becomes `None`, a small CORS-triage loss.
    """
    value = _scalar_or_none(value)
    if name.lower() in _URL_VALUED_HEADERS and isinstance(value, str):
        return _safe_origin(value)
    return value


def _scrub_event(event: dict, hint: dict) -> dict:
    """Reduce an event to allowlisted fields before it leaves the process.

    Registered on BOTH `before_send` and `before_send_transaction`: the SDK skips
    `before_send` entirely for transaction events (`client.py:917-922`), so a hook
    registered only on the former leaves the whole transaction path unscrubbed.

    Note `extra` is absent from every allowlist — that alone closes scope extras and
    ArgvIntegration's `sys.argv`, without naming either.
    """
    # A raise ANYWHERE in here costs the WHOLE event: sentry-sdk wraps the hook in
    # `capture_internal_exceptions()`, so an exception is swallowed and the event dropped —
    # a scrubber that crashes is a scrubber that silently blinds you on the error path.
    #
    # Measured before adding this: 0 raises across the hostile FIELD shapes the test builds
    #  (23 top-level
    # keys × 22 hostile values, plus nested variants) — the reachable surface is already
    # total. This guard covers only a non-dict EVENT, which the SDK does not produce, so
    # its measured fire rate is ZERO. It is two lines and it makes the function total
    # rather than total-in-practice; that trade is worth it in a module now vendored into
    # other services, where "the SDK never does that" is an assumption about someone
    # else's caller.
    if not isinstance(event, dict):
        return {}

    event = _keep(event, _ALLOWED_EVENT_KEYS)

    # Every branch below DROPS a field whose shape is not what we expect, rather than
    # passing it through untouched. An `if isinstance(...)` that only ADDS scrubbing is
    # fail-OPEN: a `request` that arrives as a string, or `spans` as a dict, would sail
    # past the filter with its values intact. That is the same "cannot see what it was
    # not told about" failure as a denylist, one level down — at SHAPE instead of field.
    if "request" in event:
        request = event["request"]
        if isinstance(request, dict):
            request = _keep(request, _ALLOWED_REQUEST_KEYS)
            headers = request.get("headers")
            env = request.get("env")
            if "env" in request:
                request["env"] = (
                    _keep(env, _ALLOWED_ENV_KEYS) if isinstance(env, dict) else None
                )
            # Guarded like `env` three lines up. Unconditional assignment ADDED a
            # `"headers": null` to an event the SDK never sent one on, breaking the
            # "rebuild only what survived the allowlist" pattern this file states
            # elsewhere. No leak — but an asymmetry between two adjacent branches doing
            # the same job is how the next reader learns the wrong rule.
            if "headers" in request:
                request["headers"] = (
                    {
                        k: _reduce_header_value(k, v)
                        for k, v in headers.items()
                        # isinstance guard for the same reason `op` got one last round: a
                        # non-str key makes `.lower()` raise inside before_send, and
                        # sentry-sdk swallows that by DROPPING the whole event.
                        if isinstance(k, str) and k.lower() in _ALLOWED_HEADER_NAMES
                    }
                    if isinstance(headers, dict)
                    else None
                )
            event["request"] = request
        else:
            event["request"] = None

    if "contexts" in event:
        contexts = event["contexts"]
        if isinstance(contexts, dict):
            contexts = _keep(contexts, _ALLOWED_CONTEXT_KEYS)
            # Drill into each namespace too: `trace` carries its own `data` bag, the same
            # shape that made span data a leak channel.
            event["contexts"] = {
                name: (
                    # Fail CLOSED on a non-dict `trace`: the previous form fell through
                    # to `else ctx` and shipped it verbatim, which is the one fail-open
                    # guard left in a file whose whole invariant is that an isinstance
                    # check must DROP an unexpected shape, not skip past it.
                    (_reduce_trace(_keep(ctx, _ALLOWED_TRACE_KEYS))
                     if isinstance(ctx, dict) else None)
                    if name == "trace"
                    else (
                        _keep(ctx, _ALLOWED_RUNTIME_KEYS) if isinstance(ctx, dict) else None
                    )
                )
                for name, ctx in contexts.items()
            }
        else:
            event["contexts"] = None

    if "message" in event:
        # The TOP-LEVEL message — what `capture_message()` populates, and the field this
        # module's own comment identifies as the reachable one while calling `logentry`
        # unreachable. The first version of this fix redacted `logentry.message` and left
        # THIS untouched: it covered the field the comment says cannot be reached and missed
        # the field the comment says is reached. Both are redacted now; `logentry` stays as
        # the backstop its comment already describes.
        event["message"] = _redact_userinfo_in_text(event["message"])

    if "logentry" in event:
        logentry = event["logentry"]
        event["logentry"] = (
            _reduce_logentry(_keep(logentry, _ALLOWED_LOGENTRY_KEYS))
            if isinstance(logentry, dict)
            else None
        )

    for key in ("exception", "threads"):
        if key not in event:
            continue
        event[key] = _rebuild_exception_holder(event[key])

    # `transaction` is the route TEMPLATE when a route matched, but the raw request URL
    # when none did (`transaction_info.source == "url"`). The template is exactly what
    # triage needs and must survive; the raw URL is a value and is reduced. Conditional,
    # because reducing unconditionally would destroy the template for every matched
    # request — the mirror of this fix.
    transaction = event.get("transaction")
    if isinstance(transaction, str):
        # `transaction_info.source == "url"` is the SDK's OWN statement that it built this
        # name from a URL rather than a route template — strictly stronger than pattern-
        # matching the string, and it covers shapes the regex misses (a bare `/path`, when
        # `scope["server"]` is unset). The regex stays as the fallback for when the field
        # is absent, so neither signal is trusted alone.
        info = event.get("transaction_info")
        if isinstance(info, dict) and info.get("source") == "url":
            # Built from a URL: reduce it if it parses, drop it if it does not — a bare
            # path has no origin to keep, and shipping it whole is the leak.
            event["transaction"] = _safe_origin(transaction)
        elif _LOOKS_LIKE_URL_RE.match(transaction):
            event["transaction"] = _safe_origin(transaction)
        else:
            # `transaction` is the THIRD allowlist-kept field that can hold text a developer
            # wrote, and its URL gate is positional: `^\s*(?:\S+\s+)?scheme://` matches only
            # when the URL is the first or second whitespace token. A name like
            # "celery task for postgresql://user:pw@host/db" passed through whole.
            #
            # Reducing it to an origin here would destroy legitimate names, so the same
            # free-text redaction the message fields use is applied instead: the name
            # survives, the credential does not.
            event["transaction"] = _redact_userinfo_in_text(transaction)

    _reduce_metadata(event)

    if "spans" in event:
        spans = event["spans"]
        if not isinstance(spans, list):
            event["spans"] = []
            spans = []
        kept = []
        for span in spans:
            if not isinstance(span, dict):
                continue
            span = _keep(span, _ALLOWED_SPAN_KEYS)
            if "origin" in span:
                span["origin"] = _reduce_origin(span["origin"])
            # `op` reaches here as whatever _scalar_or_none allowed, which includes
            # int/float/bool — and `1.startswith(...)` raises, which the SDK swallows by
            # DROPPING the whole event. Silent loss of monitoring, so coerce.
            op = span.get("op")
            op = op if isinstance(op, str) else ""
            description = span.get("description")
            if op.startswith("db"):
                # The raw SQL, including any interpolated literal.
                span.pop("description", None)
            elif isinstance(description, str):
                safe = _safe_origin(description)
                if safe is None:
                    span.pop("description", None)
                else:
                    span["description"] = safe
            elif description is not None:
                span.pop("description", None)
            kept.append(span)
        event["spans"] = kept
    return event


def init_glitchtip() -> bool:
    """Initialize Sentry SDK for FastAPI. Returns True if init ran, False if no-op."""
    dsn = (os.environ.get("SENTRY_DSN") or os.environ.get("GLITCHTIP_DSN") or "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        # A DSN is configured, so someone EXPECTS monitoring. Failing silently here is
        # indistinguishable from a healthy service and hides a total loss of error
        # reporting (partial install, pin drift, a broken image layer), so say so loudly.
        # (An earlier version of this comment claimed "on stderr" while the call below
        # uses structlog, which writes to STDOUT when unconfigured — measured. It also
        # gave structlog's possible non-configuration as the reason for a structlog call.)
        structlog.get_logger(__name__).warning(
            "glitchtip_init_failed",
            reason="sentry_sdk not importable",
            impact="error reporting DISABLED for this process",
        )
        return False

    # Everything below is wrapped: a malformed GLITCHTIP_TRACES_SAMPLE_RATE ("0,05") or a
    # copy-pasted bad DSN otherwise raises out of api/main.py:2 — the FIRST statement of
    # the app — and takes the WHOLE SERVICE down. Losing monitoring is bad; losing the
    # service because monitoring was misconfigured is strictly worse, and it is the same
    # reasoning that made the ImportError path log-and-continue rather than fail silently.
    try:
        _init_sdk(sentry_sdk, FastApiIntegration, StarletteIntegration, LoggingIntegration, dsn)
    except Exception as e:
        structlog.get_logger(__name__).warning(
            "glitchtip_init_failed",
            reason=f"{type(e).__name__}: {e}",
            impact="error reporting DISABLED for this process; the service continues",
        )
        return False
    return True


def _init_sdk(sentry_sdk, FastApiIntegration, StarletteIntegration, LoggingIntegration, dsn):
    """Call sentry_sdk.init with this service's hardened configuration."""
    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("ENVIRONMENT", "production"),
        release=os.environ.get("GIT_SHA") or os.environ.get("COOLIFY_DEPLOYMENT_UUID"),
        traces_sample_rate=float(os.environ.get("GLITCHTIP_TRACES_SAMPLE_RATE", "0.05")),
        profiles_sample_rate=float(os.environ.get("GLITCHTIP_PROFILES_SAMPLE_RATE", "0")),
        send_default_pii=False,
        # Structural secret removal — send_default_pii=False closes NEITHER of these.
        # Frame locals ship Settings reprs (DB DSN, JWT secret); request bodies ship
        # passwords/OTPs. Both are attached regardless of send_default_pii.
        include_local_variables=False,
        max_request_body_size="never",
        # Source lines around every frame (pre_context/context_line/post_context) are a
        # SEPARATE knob from locals capture and default to on. A secret written as a
        # source literal ships through them untouched by every mitigation above —
        # reproduced. check_secrets should stop such a literal reaching the repo at all;
        # this is the structural backstop for when it does. Cost: GlitchTip shows the
        # frame (file, line, function) but not the surrounding source text.
        include_source_context=False,
        # Breadcrumbs are dropped ENTIRELY. Disabling the logging integration below stops
        # log records becoming breadcrumbs, but integrations auto-enable whenever their
        # package is installed, and several write VALUES into breadcrumbs with no
        # send_default_pii gate: StdlibIntegration/HttpxIntegration record the full
        # outbound URL incl. query string (reproduced: api/bing_webmaster_client.py puts
        # `apikey` in params, so the live Bing key rode into a LATER unrelated event),
        # Sqlalchemy/AsyncPG record raw SQL text (safe for bound params, not for an
        # interpolated literal — note this closes only the BREADCRUMB duplicate; the SPAN
        # copy is handled in _scrub_event), and stdlib records subprocess argv. A breadcrumb carries
        # no template to fall back to, so there is nothing to redact selectively.
        max_breadcrumbs=0,
        # Default is socket.gethostname(), which publishes the dev machine's or
        # container's hostname on every event. The service name is what we actually want.
        server_name=os.environ.get("SERVICE_NAME", "{name}"),
        before_send=_scrub_event,
        # The SDK SKIPS before_send for transaction events, so it must be registered
        # separately or every sampled transaction ships unscrubbed.
        before_send_transaction=_scrub_event,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            StarletteIntegration(transaction_style="endpoint"),
            # Close the stdlib-logging -> Sentry channel entirely. A log record reaches
            # GlitchTip through FOUR fields that neither flag above nor the EventScrubber
            # touches: logentry.params, logentry.formatted, extra-from-record, and the
            # breadcrumb trail (which keeps the INTERPOLATED message, with no safe
            # template to fall back to). event_level=None stops records becoming events;
            # level=None stops them becoming breadcrumbs.
            #
            # ⚠️ THOSE TWO ARE NOT THE WHOLE CHANNEL, and an earlier version of this comment
            # said "entirely" while enumerating only them. `LoggingIntegration` installs a
            # THIRD handler in sentry-sdk 2.68.1 — `_sentry_logs_handler`, defaulting to INFO
            # rather than None. It emits `log` envelope items carrying the interpolated body
            # and `sentry.message.parameter.0` (which IS `logentry.params`, one of the four
            # fields named above), and those items go out through `before_send_log` — a hook
            # this module does not register. So `_scrub_event` has ZERO reach into that
            # channel: the entire deny-by-default apparatus simply does not see it.
            #
            # It is gated behind the client option `enable_logs`, which defaults False and is
            # set nowhere in this repo. That is exactly the standard this module refuses for
            # itself elsewhere — "empty today only because of SDK CONFIG" — so the handler is
            # disabled outright rather than left resting on someone else's default.
            #
            # Unhandled errors are still reported via the Starlette/FastAPI integrations, and
            # explicit sentry_sdk.capture_exception() still works.
            # FLEET DEFAULT (D-126), and it DEPENDS ON THE ALLOWLIST ABOVE. Upstream uses
            # event_level=None, closing the log channel by never creating an event at all.
            # ERROR keeps the event — the fleet wants error records visible in GlitchTip —
            # so that channel is OPEN here and is closed instead by
            # `_ALLOWED_LOGENTRY_KEYS == {"message"}`, which keeps the message TEMPLATE and
            # drops `params`/`formatted`. Verified: `logger.error("otp=%s", secret)` yields
            # one event whose logentry is {'message': 'otp=%s'} with the secret absent.
            # ⚠️ Widening `_ALLOWED_LOGENTRY_KEYS` therefore turns THIS line into a leak,
            # while upstream's event_level=None would not. The two are coupled.
            # `sentry_logs_level=None` is kept EXACTLY as upstream: that third handler goes
            # out through `before_send_log`, which this module does not register, so
            # `_scrub_event` has zero reach into it. Raising it is not ours to do.
            LoggingIntegration(
                event_level=logging.ERROR, level=None, sentry_logs_level=None
            ),
        ],
    )
