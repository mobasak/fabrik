"""GlitchTip / Sentry SDK initialization (FastAPI service).

Reads SENTRY_DSN, falling back to GLITCHTIP_DSN. If neither is set → no-op (zero
overhead).

Import this module BEFORE FastAPI app creation in main.py:
    from {pkg}.glitchtip_init import init_glitchtip
    init_glitchtip()  # call once at module load
    app = FastAPI(...)

VENDORED — do not edit here expecting it to stick upstream.
  origin:   site-provisioner  api/glitchtip_init.py
  revision: a13c801
Copied under the fabrik-lib law (vendor, never import across repos). It is a COPY: to
pull a later upstream fix, re-vendor and move the revision above, so a reader can always
diff this file against the sha it claims to be.

⚠️ THIS SURFACE MOVES, AND THE MOVES ARE SECURITY-BEARING. Vendor #1 pinned 4f5c158 and
was six commits stale within two hours; by the fourth re-vendor the file had moved
fourteen times in two days. Not one of those moves was cosmetic — a redaction that missed
68.8% of its own shape, a channel `_scrub_event` cannot reach, a character before the
scheme that leaked 100% of the time, and a credential guard keyed on a literal "@" that
let 240 of 480 probes through when the DSN had no "@" in it. TWICE the upstream author's
NEXT commit corrected the fix they had just mailed us. So: re-vendor by VERIFYING the
revision at that moment (`git -C /opt/site-provisioner log -1 --format=%h --
api/glitchtip_init.py`), never by trusting a sha written in a ticket OR IN A MAIL — and
prefer the current committed revision over the one a message cites.

Scaffold adaptations, all deliberate and each graded by
tests/test_scaffold_glitchtip_security.py:
  * ``server_name`` keeps upstream's ``SERVICE_NAME`` env read; only the fallback differs
    (the scaffolded service name, not the origin repo's own);
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
import bisect
import ipaddress
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


# A zone id must look like an INTERFACE NAME. Without this the IPv6 parse is an unbounded
# escape hatch: `ipaddress.IPv6Address` accepts 93 of the 95 printable ASCII characters (all
# but "/" and "%") in a zone, of any length, so `::1%admin:hunter2` and `[::1%S3cretPassword]` are
# "valid addresses" and were returned VERBATIM by every caller that trusts the parse.
#
# The round-46 fix narrowed the bracket hatch from `[anything]` to `[<v6>%anything]` and
# stopped there — and the claim shipped with it, "a credential cannot parse as an IPv6
# address", was therefore false: the parse is a host validator only in the ABSENCE of a zone.
_IPV6_ZONE_RE = re.compile(r"[A-Za-z0-9._-]+")


def _is_ipv6_literal(candidate: str) -> bool:
    """True when `candidate` is an IPv6 address whose zone id, if any, is an interface name."""
    try:
        ipaddress.IPv6Address(candidate)
    except ValueError:
        return False
    zone = candidate.partition("%")[2]
    return not zone or bool(_IPV6_ZONE_RE.fullmatch(zone))


def _is_bare_authority(host: str) -> bool:
    """True only if `host` is a host with, at most, a NUMERIC port.

    ⚠️ THE POINT: an absent `@` does NOT mean an absent credential. A truncated or
    mistyped DSN leaves `https://admin:hunter2` — no `@` anywhere — and by SHAPE that is
    indistinguishable from a legitimate `host:port`. Every credential guard here keyed on
    `@`, so the `rsplit("@", 1)[-1]` below was a NO-OP on that shape and returned the whole
    credential as the "host", which then shipped verbatim.

    This is not a sixth heuristic. `api/google_search_console_client.py` hit the identical
    class and fixed it there, in prose naming it exactly — "An absent '@' does NOT mean an
    absent credential ... the previous version keyed on '@' alone". That fix was applied at
    the LOCATION and never carried across, so the two modules in this one repo disagreed on
    the identical string: GSC redacted `https://admin:hunter2`, this module shipped it.

    The test is deliberately NOT "does this look dangerous" — a denylist, and this module
    has been bitten by those repeatedly. It is "does this provably parse as an authority",
    and everything else fails closed.

    STATED LIMIT, identical to the sibling's and for the same reason: this is a PORT
    validator, not a credential detector. `user:1234` passes, because by the RFC grammar
    that IS host `user` port `1234`, indistinguishable from `example.com:8080`.
    """
    # An EMPTY authority is not a valid one. `_safe_origin` guards this explicitly and the
    # token path did not, so `https://user:PW@api.example.com/v1?x=@@@` split at the last `@`,
    # got an empty host, called it bare, and emitted `https://[redacted]@` — the whole URL
    # destroyed. Fail closed here so both callers agree.
    if not host:
        return False
    if host.startswith("["):
        # Bracketed IPv6 literal (`[::1]`, `[::1]:6379`) — the inner colons are address
        # separators, not a port, so the numeric rule must not be applied to them.
        #
        # ⚠️ The brackets must not become an ESCAPE HATCH, which is what the first version
        # of this branch was: it checked only that a `]` existed and the tail was empty or
        # `:digits`, so `[admin:hunter2]` and `[admin:hunter2]:5432` were "authorities" and
        # `_safe_origin` returned them VERBATIM. The commit that introduced it claimed to
        # have adopted the sibling module's convention; the sibling actually validates that
        # the literal parses as IPv6, and this did not — so the two modules still disagreed
        # on a credential-shaped string, which is the exact sentence that commit used to
        # describe the bug it was fixing. Parse it for real.
        closing = host.rfind("]")
        if closing == -1:
            return False
        tail = host[closing + 1 :]
        if tail and not (tail.startswith(":") and tail[1:].isdigit()):
            return False
        try:
            ipaddress.IPv6Address(host[1:closing])
        except ValueError:
            return False
        return _is_ipv6_literal(host[1:closing])
    if ":" not in host:
        return True
    # An UNBRACKETED IPv6 address is not RFC 3986-valid in a URL, but it is what appears in
    # real log lines (`http://fe80::1%eth0 unreachable`), and the multi-colon rule below read
    # it as credential material and redacted the host. Parsing settles it with no heuristic
    # and low risk: a credential does not parse as an IPv6 address UNLESS it hides in a
    # ZONE ID, which is why `_is_ipv6_literal` constrains the zone rather than trusting the
    # parse alone. An earlier version of this line asserted the unqualified universal and
    # was refuted by `::1%admin:hunter2`. Without a zone: `admin:hunter2`,
    # `nginx:1.25` and `a:b:c` all raise, while `fe80::1%eth0` (zone id included) does not.
    if _is_ipv6_literal(host):
        return True
    name, _, port = host.rpartition(":")
    return bool(name) and port.isdigit() and ":" not in name


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
    a `None` value; the `transaction` reduction nulls the field. THREE dispositions.

    ⚠️ The CALL-SITE COUNT is deliberately not stated any more. That number has been wrong
    four separate times in this one sentence — "one caller", then "two", then "three", then
    "six" — each time corrected by a reviewer rather than by the author, and each correction
    introduced the next wrong value. A count that cannot survive four attempts is not a fact
    worth carrying in prose; the dispositions are the part that means anything, and the
    sites are one `ast` query away for anyone who needs them.

    (The transaction reduction calls it from both of its branches, which is why a call-site
    count and a disposition count were ever different numbers — and why naming either one
    kept going wrong.)
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
    # ⚠️ Keying on "@" was the bug, not the fix. With no "@" the rsplit above is a no-op, so
    # `admin:hunter2` arrives here as the "host". Validate that what survived provably IS an
    # authority; anything else is credential material and the description is dropped.
    if not _is_bare_authority(host):
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
        # ⚠️ The gate is POSITIONAL — `^\s*(?:\S+\s+)?scheme://` matches only when the URL
        # is the first or second whitespace token. A value like
        # "auto.db.sqlalchemy connecting to <dsn>" therefore failed the gate and returned
        # VERBATIM. `transaction` had this same hole and closed it with the free-text
        # redaction; `origin` did not inherit the fix, so the identical string was redacted
        # in one field and shipped whole in the other.
        #
        # Reducing it to an origin would destroy a legitimate identifier, so the free-text
        # redaction is applied instead: the identifier survives, a credential inside it
        # does not — including its QUERY STRING, which the free-text rule alone does not
        # remove and which `_safe_origin` would have dropped had the gate matched.
        return _redact_query_in_identifier(value)
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
# ⚠️ THE ORDINALS BELOW ARE LOAD-BEARING AND WERE INVERTED FOR SEVERAL ROUNDS. When the
# alternation order was reversed to fix the `user@server` tail leak, the code moved and this
# prose did not, so every "first/second alternative" sentence pointed at the other rule and
# a sentence describing the userinfo class matched NEITHER class. Read the pattern, not this
# paragraph, if they ever disagree again.
#
# FIRST alternative — `(scheme(?::/{1,2}|//))([^\s/:]*+:[^\s]*)@`
#   Separator: `://`, `:/` or `//` — damaged OR intact.
#   Userinfo:  REQUIRES a colon. The head `[^\s/:]*+` EXCLUDES the colon, which is what gives
#              the required colon exactly one split point; without that exclusion the engine
#              retried every split inside a single match attempt and the pattern was
#              quadratic (15.6s at 60 KB) even though start positions were already pruned.
#              ⚠️ ATTRIBUTION, corrected twice and now stated with its measurement, because
#              THREE constructs here overlap and this comment has credited the wrong one in
#              two consecutive rounds. In order of what actually caps the work today:
#                * the `{0,256}` TAIL BOUND is the active guard. Without it the tail ran to
#                  end-of-string at every scheme start on a separator-dense, `@`-free value —
#                  14.7s at 128 KB, live, and past this file's own 5s test ceiling.
#                * the COLON EXCLUSION in `[^\s/:]` was the active guard BEFORE that bound
#                  existed. With the bound in place it is now belt-and-braces: removing it
#                  changes 0 of 200,003 outputs and costs 1.5-3.1x, all linear.
#                * the POSSESSIVE `*+` was never the guard at all, in either regime: 0 of
#                  200,003 outputs, 1.02x.
#              All three are kept — they are free — but only the first is load-bearing, and a
#              comment that promotes a redundant construct to "the fix" is how the real one
#              goes unmeasured for three rounds.
#              The tail `[^\s]*` excludes ONLY whitespace, so it permits `/`, `?`, `#` and
#              `@` — that is deliberate and it is what makes the match run to the LAST `@`.
#              A password containing `@` (the canonical Azure `user@server` login) otherwise
#              shipped its tail BEHIND a `[redacted]@` marker, which reads as a successful
#              redaction and is strictly worse than not matching at all.
#   Why it may require a colon and still be safe on a damaged separator: `src//main@HEAD`
#   and `C:/temp@1` have exactly the damaged shape and are an ordinary path and a Windows
#   path. Neither has a colon in the userinfo position; every `user:pass` DSN does. That one
#   distinction is what lets the damaged case be covered without destroying paths.
#
# SECOND alternative — `(scheme://)([^\s/?#]+)@`
#   Separator: INTACT `://` only.
#   Userinfo:  NO colon required — this is the only rule that catches a bare-token
#              `https://<token>@host`. It excludes `?` and `#` per RFC 3986, where they START
#              the query and fragment and so cannot appear inside userinfo; that exclusion is
#              what keeps `https://h?a=1@2` intact. It also excludes `/`.
#
# ORDER MATTERS because both can match at one position and Python's `|` takes the first.
# The colon-requiring, runs-to-the-last-`@` rule must lead.
#
# The scheme run is `[a-zA-Z][a-zA-Z0-9+.\-]{0,31}` — LENGTH-BOUNDED, not boundary-anchored
# and not possessive. An earlier revision used a `(?<![A-Za-z0-9+.\-])` lookbehind to prune
# mid-run starts; it also blocked `psql -dpostgresql://…` and 12 other real prefixes, so the
# length bound replaced it. No lookbehind survives in this module.
#
# ⚠️ STATED RESIDUAL, because an earlier version of this comment claimed the gap was closed
# and it is not: a BARE-TOKEN userinfo (no colon) containing `?` or `#` falls between both
# alternatives and is NOT redacted — `https://gh#p_<token>@host` ships whole. The claim was
# true for `user:pass` and false for a bare token, and the corpus could not show it because
# it varies the alphabet only in the `user:{secret}` form and covers the bare-token shape
# only with an alphanumeric secret; the two dimensions are never crossed.
#
# It is left open on measurement, not convenience. Permitting `?#` in the SECOND (bare-token)
# alternative — the first already permits them in its tail —
# closes all four leak shapes and over-redacts 5 of 8 real query strings — `https://h?a=1@2`,
# `https://h#f@g`, `http://h?x@y` — because `scheme://host?query@x` and
# `scheme://token#x@host` are STRUCTURALLY IDENTICAL. A regex cannot separate them, and a
# third heuristic invented to try is how the previous five iterations of this rule were each
# refuted. Tokens are overwhelmingly `[A-Za-z0-9_-]`, so the residual is narrow; it is
# asserted in the test rather than described only here.
#
# POSSESSIVE `*+` — and TWO things this comment said about it were wrong, one per round.
# First it claimed the `*+` sits on the scheme run (D-019 said so too); it does not, it sits
# on the FIRST alternative's userinfo head. Then it claimed that possessive quantifier is
# what closes the in-match blowup; it is not. Measured directly: making it greedy changes
# the output on 0 of 200,003 probed inputs and the timing by 1.02x at 128 KB. The construct
# that actually closes it is the COLON EXCLUSION in `[^\s/:]` — with the colon outside the
# class there is exactly one place the required `:` can sit, so there is nothing to retry.
# The `*+` is kept as belt-and-braces and is documented as such rather than as the fix.
#
# The two quadratic blowups here are DIFFERENT and each needed its own fix, which is why one
# fix kept looking like it had not worked. Across START POSITIONS: on one long unbroken
# `[A-Za-z0-9+.\-]` run the engine begins a match at every character — 2.7s at 32 KB, 15.6s
# at 60 KB, synchronously inside `before_send`; that one is closed by the 32-char LENGTH
# BOUND on the scheme run (below), not by a possessive quantifier, which was measured and
# did not help. Inside a SINGLE match attempt: the userinfo head splitting at each candidate
# colon; that one is closed TODAY by the `{0,256}` tail bound, and was closed before that
# bound existed by excluding the colon from the head class. Both are kept; only the bound is
# load-bearing (measured — see the FIRST-alternative note above). An earlier comment
# claimed "requiring the
# scheme is what makes this linear" — necessary, not sufficient — and the measurement that
# "proved" linearity used `"a:"*n`, where the colons break the runs and neither blowup can
# appear. Wrong shape, confident number.
#
# GREEDY userinfo INCLUDING `@`, which makes this match to the LAST `@` rather than the
# first. A password containing `@` otherwise ships its tail — and ships it BEHIND a
# `[redacted]@` marker, so the output reads as a successful redaction. That is worse than
# the documented `/` residual, where the string is left visibly untouched. `_safe_origin`
# has always used `rsplit("@", 1)[-1]` for exactly this reason, with a test named for it;
# the convention simply was not carried across to this function.
# The scheme run is LENGTH-BOUNDED rather than boundary-anchored, and that single change
# does two jobs a lookbehind could not.
#
# It removes a LEAK. A lookbehind that forbids a scheme-class character before the scheme
# also forbids the whole run it belongs to, so `psql -dpostgresql://user:pw@h/db` — valid
# psql syntax, and exactly what a `CalledProcessError` message quotes — matched NOTHING and
# shipped the DSN intact. So did any elided message beginning `...`. Measured: 13 of 95
# printable characters (`+-.` and the digits) blocked the match entirely, and the failure
# was fail-OPEN, emitting the credential whole rather than behind a `[redacted]@` marker.
# No round could see it because every corpus prefix ended in a space, quote, `=` or `:`.
#
# It also removes the QUADRATIC behaviour the lookbehind was there for. Bounding the run to
# 32 characters caps the work at each start position, so the scan is linear in input length
# without needing a boundary at all. A registered URI scheme is at most 30-odd characters;
# 32 is generous and the bound is what makes the cost predictable.
# The userinfo tail bound, named ONCE so the regex and the fail-closed net below cannot
# drift apart — they encode the same threshold and a silent disagreement between them
# would reopen the fail-open gap the net exists to close.
# ⚠️ PARSER-BASED, replacing seven successive regex designs. Operator decision, 2026-09-05.
#
# The regex approach was refuted SEVEN times, on both directions and on complexity, each time
# by a different reviewer: the failure mechanism, the separator form, the password alphabet,
# `@`-in-password, two distinct quadratics, a token-boundary lookbehind that fail-OPENed, the
# alternation order, a length bound that truncated behind its own marker, and the same bound
# failing OPEN. The last one destroyed 43.2% of a realistic structured-log corpus, because a
# rule that "runs to the last `@`" cannot know where a URL ENDS inside a JSON or logfmt
# record — it happily ran from a URL's port-colon into an unrelated email address.
#
# That is the whole defect class, and it is not fixable by a better pattern: a regex over free
# text has to GUESS the boundary. So the boundary is now READ instead.
#
# An authority ends at the first character that cannot appear in one. That single rule
# replaces the alternation order, the last-`@` heuristic, the trailing-punctuation trim, the
# length bound and its fail-closed net — all of which existed only to approximate it.
# Square brackets are the one subtlety: they delimit an IPv6 literal and are ordinary text
# anywhere else, so they extend the authority only when it opens with one.
_AUTHORITY_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~%:[]@"
)
# Characters that may appear INSIDE an authority but cannot END one, so they belong to the
# surrounding prose: `http://127.0.0.1:8000.` at the end of a sentence.
_AUTHORITY_TRAILING = "._~%:-"
# The scheme run stays length-bounded. Unlike the bound that was removed, this one cannot
# change the ANSWER for a real scheme — the longest registered URI scheme is under 32
# characters — and it is what keeps the scan linear across start positions.
_REDACTED = "[redacted]"


def _ends_url(char: str) -> bool:
    """True when `char` terminates a URL run.

    ⚠️ THIS ALSO TESTED `char.isspace()` for one round, and that clause was INERT — provably,
    not arguably. This function is called only on characters drawn from a `_NON_SPACE_RE`
    (`\\S+`) token, and an exhaustive scan of all 1,114,112 codepoints finds NONE that is both
    `isspace()` and matched by `\\S`. It could never fire.

    Worse, the comment justifying it named a leak it did not close: a password containing a
    non-breaking space ships its tail byte-identically before and after that change. That
    residual is real, it is the WHITESPACE residual this module has always had (`\\S+` splits
    the token there and no match crosses a token boundary), and it is pinned by a test rather
    than papered over. A fix written against a mechanism that cannot fire, with a confident
    comment attached, is the defect this review keeps finding in other people's code.
    """
    return char in _URL_END_CHARS
_NON_SPACE_RE = re.compile(r"\S+")
# A URL run may contain the path/query/fragment delimiters; an AUTHORITY may not, which is
# what `_first_delimiter` finds. Both stop at the characters that end a URL outright —
# quotes, braces, angle brackets, the comma joining two of them in one log line.
# ⚠️ The URL run is bounded by what ENDS a URL in prose, not by an ASCII allowlist. An
# allowlist stopped at the first non-ASCII byte, so a password containing `ä` was cut in half
# and its tail shipped. These are the characters that genuinely terminate a URL inside a log
# line — quote, brace, angle bracket, pipe, backslash, caret, backtick, comma, parenthesis —
# plus whitespace. Everything else, including non-ASCII, is URL content.
#
# ⚠️ CORRECTED: this sentence used to claim "a boundary rule, not a credential rule — deciding
# whether what was found IS a credential stays with `_is_bare_authority`". That is FALSE, and
# a reviewer was right to call it out. The boundary decides FIRST, by truncating the run
# before `_is_bare_authority` ever sees it, so these characters are part of the credential
# decision whether or not the comment says so.
#
# STATED RESIDUAL, and it is a deliberate trade rather than an oversight: a password
# containing one of these characters has its TAIL survive after the marker —
# `scheme://svc:Tr0ub4dor(3)@host` emits `[redacted](3)@host`. That is the "reads as a
# successful redaction" shape this module treats as its worst, so the alternative was
# measured rather than assumed: extending the run past an ender to a later `@` closes 4 of 4
# such passwords AND destroys 4 of 7 realistic log records — the 43.2% structured-log
# destruction that caused the engine to be replaced in the first place (D-030). Between a
# tail surviving on a punctuation-bearing password and half of all logfmt records being
# rewritten, this is the better trade, and this repo's own generated passwords are 32 chars
# of `[a-zA-Z0-9]` (`secrets.choice`) and contain none of these characters.
#
# Not a defence, a boundary: `_is_bare_authority` still decides everything the run does reach.
_URL_END_CHARS = frozenset(" \t\n\r\f\v\"'<>{}|\\^`,()")


def _scan_delimiter(token: str, start: int, end: int) -> int:
    """Index of the first `/?#` in the authority run, or -1. O(authority)."""
    for index in range(start, end):
        char = token[index]
        if char in "/?#":
            return index
        if char not in _AUTHORITY_CHARS:
            return -1
    return -1


def _scan_authority(token: str, start: int, end: int) -> int:
    """One past the longest leading run that could BE an authority. O(authority)."""
    index = start
    while index < end and token[index] in _AUTHORITY_CHARS and token[index] not in "/?#":
        index += 1
    return index


def _scan_for_any(token: str, start: int, end: int, chars: str) -> int:
    """Index of the first character of `chars` in [start, end), or -1."""
    for index in range(start, end):
        if token[index] in chars:
            return index
    return -1


def _first_delimiter(text: str) -> int:
    """Index of the first `/`, `?` or `#`, or -1. This is where an authority ends."""
    found = [i for i in (text.find("/"), text.find("?"), text.find("#")) if i != -1]
    return min(found) if found else -1


def _authority_prefix(text: str) -> str:
    """The longest leading run of `text` that could actually BE an authority.

    An ALLOWLIST, and it replaces a strip-set that kept needing new members: `;` after a
    port, `*` from markdown emphasis, `=` from `key=value`, `&`, `+`, `$` — every abutting
    character had to be enumerated, and the one not yet enumerated was collateral. Naming
    what an authority may CONTAIN ends that, which is the same inversion this module made at
    the field level and again at the character level.
    """
    end = 0
    while end < len(text) and text[end] in _AUTHORITY_CHARS:
        end += 1
    return text[:end].rstrip(_AUTHORITY_TRAILING)
_URL_START_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+.\-]{0,31}(://|:/|//)")


def _positions(token: str) -> "tuple[list[int], ...]":
    """`@`, run-ender and bracket offsets in one pass.

    ⚠️ PRECOMPUTED, and that is a complexity property rather than tidiness. Each of these was
    previously re-derived per scheme start — `rfind`, a forward scan to the run end, a
    `.find()` triple — so a token with many scheme starts cost O(n) per match. Measured at
    103s on a 128 KB value once nested URLs made the scan per-match. Precomputing once and
    bisecting makes every per-match lookup O(log n).
    """
    ats: list[int] = []
    enders: list[int] = []
    brackets: list[int] = []
    cuts: list[int] = []
    delims: list[int] = []
    for index, char in enumerate(token):
        if char == "@":
            ats.append(index)
        if _ends_url(char):
            enders.append(index)
        elif char in "[]":
            brackets.append(index)
        elif char in "?#":
            cuts.append(index)
        if char in "/?#":
            delims.append(index)
    return ats, enders, brackets, cuts, delims


def _first_at_or_after(positions: "list[int]", index: int) -> "int | None":
    """The first offset in `positions` at or after `index`."""
    found = bisect.bisect_left(positions, index)
    return positions[found] if found < len(positions) else None


def _last_at_before(positions: "list[int]", low: int, high: int) -> int:
    """The last offset in `positions` within [low, high), or -1."""
    found = bisect.bisect_left(positions, high) - 1
    return positions[found] if found >= 0 and positions[found] >= low else -1


def _redact_token(token: str, drop_query: bool) -> str:
    """Redact one whitespace-free token. Linear: every per-match lookup is O(log n)."""
    ats, enders, brackets, cuts, delims = _positions(token)
    out: list[str] = []
    pos = 0        # everything before this index is already in `out`
    scanned = 0    # everything before this index has already been EXAMINED
    length = len(token)
    for match in _URL_START_RE.finditer(token):
        if match.start() < scanned:
            continue
        separator = match.group(1)
        start = match.end()
        hard_end = _first_at_or_after(enders, start)
        hard_end = length if hard_end is None else hard_end
        # Square brackets belong to a URL only as an IPv6 literal's delimiters — anywhere else
        # they are ordinary text (markdown links, JSON arrays). But a bracketed host can also
        # FOLLOW a userinfo, so a bracket ends the run only if it precedes the first `@`.
        end = hard_end
        if not (start < length and token[start] == "["):
            first_at = _first_at_or_after(ats, start)
            first_bracket = _first_at_or_after(brackets, start)
            if (
                first_bracket is not None
                and first_bracket < hard_end
                and (first_at is None or first_bracket < first_at)
            ):
                end = first_bracket
        if end == start:
            continue
        # ⚠️ The FIRST `/?#` in the run, unconditionally. A version of this stopped at the
        # first non-authority character and returned -1, which sends `bare_at` to the last
        # `@` in the WHOLE run — precisely what the comment below says it must not do. The
        # result was a FABRICATED HOST: `git+ssh://git+bot@github.com/org/repo.git@v1.2` came
        # out as `git+ssh://[redacted]@v1.2`, the real host deleted and a tag shown in its
        # place. Any of `+ = & ! ; * $` in the authority triggered it.
        delimiter = _first_at_or_after(delims, start)
        delimiter = -1 if delimiter is None or delimiter >= end else delimiter
        last_at = _last_at_before(ats, start, end)
        bare_at = _last_at_before(ats, start, delimiter if delimiter != -1 else end)
        replacement = None
        keep_from = None
        if last_at != -1:
            userinfo_delimiter = _scan_for_any(token, start, last_at, "/?#")
            colon = token.find(":", start, last_at)
            # A COLON BEFORE THE FIRST `/?#` separates a userinfo from a path, and it is the
            # whole distinction: `scheme://a/b@c` is either host `a` with path `/b@c`, or
            # userinfo `a/b` with host `c`, and nothing else tells them apart. Getting it
            # wrong permissively destroyed 43.2% of a structured-log corpus.
            colon_first = colon != -1 and (
                userinfo_delimiter == -1 or colon < userinfo_delimiter
            )
            # An INTACT `://` also accepts a colon-less BARE TOKEN userinfo — the only rule
            # catching `https://<token>@host` — but its `@` is the last one BEFORE the first
            # delimiter, not the last overall.
            bare_token = separator == "://" and bare_at != -1
            if not colon_first and bare_token:
                last_at = bare_at
            if colon_first or bare_token:
                host_end = _scan_authority(token, last_at + 1, end)
                host = token[last_at + 1:host_end].rstrip(_AUTHORITY_TRAILING)
                # The HOST must itself parse, or the secret simply sits after the `@`.
                replacement = (
                    f"[redacted]@{host}" if _is_bare_authority(host) else "[redacted]"
                )
                keep_from = last_at + 1 + len(host) - start
        if replacement is None:
            authority_end = _scan_authority(token, start, end)
            authority = token[start:authority_end].rstrip(_AUTHORITY_TRAILING)
            if token.startswith(_REDACTED, start):
                # Our own marker is inert — but ONLY standing alone. A bare `startswith` here
                # is a fail-open: it would wave `scheme://[redacted]:<secret>` through.
                remainder = token[start + len(_REDACTED):authority_end]
                if ":" not in remainder and "@" not in remainder:
                    scanned = end
                    continue
            # An absent `@` is not an absent credential: a truncated DSN leaves
            # `scheme://user:secret`, shape-identical to `host:port` and separated from it
            # only by whether the port is numeric.
            if authority and "@" not in authority and not _is_bare_authority(authority):
                replacement = "[redacted]"
                keep_from = len(authority)
        tail_cut = -1
        if drop_query:
            base = start + (keep_from if keep_from is not None else 0)
            if keep_from is None:
                base = _scan_authority(token, start, end)
            tail_cut = _first_at_or_after(cuts, base)
            tail_cut = -1 if tail_cut is None or tail_cut >= end else tail_cut
            if tail_cut != -1 and token.startswith(_REDACTED, tail_cut + 1):
                tail_cut = -1
        if replacement is None and tail_cut == -1:
            # Resume past the AUTHORITY, not the whole run: a URL NESTED in this one's query
            # lives inside the same run, and skipping to the end hid it —
            # `https://proxy/?next=https://user:<secret>@host` shipped whole, 6 of 6 shapes.
            scanned = end if delimiter == -1 else delimiter
            continue
        out.append(token[pos:match.start()])
        if replacement is None:
            out.append(token[match.start():tail_cut])
        else:
            out.append(f"{token[match.start():start]}{replacement}")
        if tail_cut != -1:
            # Emit the PATH between the authority and the delimiter. The credential branch
            # jumped straight to `token[tail_cut]` and silently deleted it, so a value with
            # BOTH a userinfo and a query lost its path — contradicting this module's own
            # promise to leave "the message, scheme, host and path". No test saw it: every
            # query-cut case in the suite is credential-free, so the path-preserving branch
            # was always the one taken.
            if replacement is not None:
                out.append(token[start + keep_from:tail_cut])
            out.append(f"{token[tail_cut]}{_REDACTED}")
            pos = scanned = length
            break
        # Emit the scheme and replacement ONLY; the tail is left for the loop to re-examine,
        # which is where a nested URL lives, and is emitted by the next prefix append or the
        # final one. Emitting it here AND rewinding past it duplicated it.
        pos = scanned = start + keep_from
    if not out:
        return token
    out.append(token[pos:])
    return "".join(out)


def _redact_urls(value: str, drop_query: bool = False) -> str:
    """Strip credentials from URLs embedded in free text, keeping the text.

    Closes the residual the originating report named and left open: "never interpolate a
    secret into a log message or exception string". Allowlisting cannot help, because these
    fields are allowlisted precisely BECAUSE triage needs them.

    The DRIVER is a URL-PARSE failure, not a connection failure — a refused connection raises
    `ConnectionRefusedError`, DNS `gaierror`, auth `InvalidPasswordError`, and none carries
    the URL. What quotes it is `ArgumentError: Could not parse SQLAlchemy URL from string
    '<the whole DSN>'`. So the separator may be DAMAGED (`:/`, `//`) — that is the case being
    redacted, not an edge one.

    Deliberately narrow: it removes the credential and leaves the message, scheme, host and
    path, so an operator still sees which host refused. It is NOT a general secret scanner —
    a bare token in prose is still the developer's responsibility.

    Work is done PER WHITESPACE TOKEN, which is a complexity property rather than a
    convenience: every character class here excludes whitespace, so no match can cross a
    token.
    """
    if "://" not in value and ":/" not in value and "//" not in value:
        return value
    out: list[str] = []
    last = 0
    for token_match in _NON_SPACE_RE.finditer(value):
        token = token_match.group(0)
        redacted = _redact_token(token, drop_query)
        if redacted != token:
            out.append(value[last:token_match.start()])
            out.append(redacted)
            last = token_match.end()
    if not out:
        return value
    out.append(value[last:])
    return "".join(out)


def _redact_userinfo_in_text(value):
    """Free-text fields: strip the credential, keep the query string (D-026)."""
    if not isinstance(value, str):
        return value
    return _redact_urls(value)


def _redact_query_in_identifier(value: str) -> str:
    """SDK-populated URL-shaped fields: strip the credential AND the query/fragment.

    `request.url` and `query_string` are dropped from the allowlist and `referer` is reduced
    to a bare origin, all because a query string carries tokens; `_safe_origin` keeps only
    `scheme://host`. The leak was the FALLBACK `origin` and `transaction` share when their
    positional URL gate misses. The free-text fields are deliberately NOT included — that is
    D-026's scope decision, pinned by a test.
    """
    return _redact_urls(value, drop_query=True)



# The `@`-LESS half. `_URL_USERINFO_RE` requires a literal `@` in both alternatives, so a
# truncated or mistyped DSN — `postgresql://user:S3cretPw`, no `@` anywhere — walked past it
# untouched. That is the same class `_is_bare_authority` closes for the span/header/origin/
# transaction paths; this is the free-text path, and it needs its own pass because the
# credential is embedded in a sentence rather than being the whole value.
#
# ⚠️ THIS RULE SHIPPED BROKEN ONCE AND ALL THREE DEFECTS ARE WORTH KEEPING NAMED, because a
# reviewer found every one of them within a round and each was avoidable by a measurement the
# author simply did not take.
#
#   1. OVER-REDACTION, 7 of 48 realistic log lines. The authority class swallowed TRAILING
#      PUNCTUATION, so `Uvicorn running on http://127.0.0.1:8000.` — trailing full stop —
#      failed the authority test and took the delimiter with it, yielding
#      `http://[redacted]`. Same for a quote, brace, comma, semicolon or colon, which is
#      most structured log output: `{"url": "redis://redis-main:6379"}` came out with its
#      JSON truncated. ⚠️ The rate was 22.9% (11 of 48), not the 14.6% first reported —
#      re-measured by replaying the rule at its own commit. That INVERTS the comparison: it
#      is worse than the 16.3% for which this very module records rejecting an earlier
#      design as too destructive, not "in the same band" as first written.
#      The shipped grader could not see it: all 12 of its entries terminated the URL with a
#      space or a `/`. That is exactly the corpus blindness this file's own docstring
#      accuses the 26,880-case fuzz corpus of — committed in the same file, the same day.
#      Fixed by trimming trailing punctuation BEFORE the authority test and restoring it
#      after, so a delimiter is never part of the decision nor collateral in the result.
#
#   2. QUADRATIC — the third time in this file. The old `(?![^\s/?#]*@)` lookahead rescanned
#      forward for every backtracked length of the authority run — 118-140 SECONDS at
#      120-128 KB, synchronously inside `before_send`. (The first report of this said "197s
#      at 120 KB"; it does not reproduce, and the grader's payload is 128 KB, not 120.)
#      It was masked (anything that made it
#      backtrack also matched the rule above, which replaced the region first) and so latent
#      rather than live — but one reordering away from live, shipped with no complexity
#      measurement, in a file that documents two prior quadratics. The lookahead existed
#      ONLY to avoid re-redacting the `[redacted]@` this module itself emits, and a direct
#      sentinel test does that in constant time.
#
#   3. INCOMPLETE. It required an INTACT `://` while the rule above deliberately accepts the
#      damaged `:/` and `//` — for the SAME driver, a URL that fails to parse precisely
#      because its separator is damaged. So `postgresql:/app:S3cretPw` leaked: damaged
#      separator crossed with absent `@`, a cell no corpus covered. It now takes the same
#      separators as the rule it partners.
#   4. The authority CLASS also has to exclude the characters that separate one URL from
#      the next, or a comma-joined pair is read as a single authority:
#      `http://a.example:80,http://b.example:80` matched the run `a.example:80,http:` — not
#      an authority — and redacted across the boundary. Quotes and the comma end the run for
#      the same reason. SQUARE BRACKETS DO NOT and must not: they delimit an IPv6 literal and
#      are the one bracket pair that legitimately appears inside an authority. An earlier
#      version of this comment said brackets were excluded; they never were, and could not
#      be — the class is what is right and the sentence was what was wrong.

# ⚠️ ALLOWLIST, because the DENYLIST version destroyed anything it had not enumerated. It
# listed 13 punctuation characters as "characters that routinely ABUT a URL", and the comment
# beside it claimed "a delimiter is never part of the decision nor collateral in the result".
# Measured, 14 of 21 abutting shapes were altered: `**http://api:8000** is up` came out as
# `**http://[redacted] is up`, and `=`, `+`, `&`, `!`, `(`, `*` all took the tail with them.
# Enumerating the bad is the same failure this whole module was rewritten to stop doing, and
# it recurred here at the character level.
#
# So the authority CLASS above now names what an authority may CONTAIN — alphanumerics, the
# unreserved marks, `%` for percent-encoding, `:` for the port, `[`/`]` for IPv6, and `@`
# for the userinfo split. Anything else simply ends the run and is never seen by the
# decision. This set is only what may not END one: a trailing dot, colon or mark is legal
# inside a host and never terminates it.



# ⚠️ THE QUERY STRING IS CREDENTIAL-BEARING, and this module had already decided that
# everywhere except here. `request.url` and `query_string` are dropped from the allowlist,
# and a `referer` header is reduced to a bare origin — all three because a query string
# carries tokens. But the FREE-TEXT redaction stripped userinfo only, so the same secret
# survived in SIX other fields: `transaction`, `contexts.trace.origin`, `spans[].origin`,
# `exception.values[].value`, `logentry.message` and TOP-LEVEL `message`.
#
# ⚠️ This inventory said "five" and omitted top-level `message` — the same field a previous
# round singled out for being omitted from a DIFFERENT inventory in this same module, under
# a comment reading "it covered the field the comment says cannot be reached and missed the
# field the comment says is reached". Same omission, one round later, inside the fix written
# to close the previous one. Measured over the 10 allowlist-kept URL-capable fields: 3 closed
# here, 3 left as the stated residual, 6 total.
#
# ⚠️ "the 10 allowlist-kept URL-capable fields" was a number a reader could not
# re-derive, and the set is NINE when enumerated: the six above plus `spans[].description`,
# `headers.referer` and `headers.origin`, which are closed elsewhere. There is no tenth —
# `request.url` and `query_string` are not allowlist-kept, so they cannot be it. Stated as
# the enumeration rather than a count, because the count is what rotted.
#
# Measured end-to-end through `_scrub_event`: `?token=<secret>` reached the wire in all six
# while `referer` was correctly reduced — one module, two opposite answers about the same
# substring, decided by which field it happened to land in.
#
# This is NOT the "general secret scanner" the module's docstring declines to be. A bare
# `token=abc123` in prose is still free text and still the developer's problem. A QUERY
# STRING is a structured URL component this module already treats as dangerous; leaving it
# in five fields was the inconsistency, not closing it.
#
# COST, measured before shipping: 1 of the 48-entry benign corpus is altered — a legitimate
# `https://example.com?q=1` loses its parameters. That is the identical cost already accepted
# for `request.url` and `referer`, and the host and path survive so triage keeps the part
# that identifies the request.
# ⚠️ NOT A LENGTH-BOUNDED REGEX, and the bounded one it replaces is why. Spanning
# `scheme://<path>\?<query>` in a single pattern needs both runs bounded or it is quadratic
# (41s on a 128 KB repeated-scheme value). Bounding them traded that for TWO leaks and a
# false claim, all shipped together:
#   * a query longer than the bound left its remainder in the output, immediately AFTER the
#     `[redacted]` marker — the "reads as a successful redaction and is strictly worse than
#     not matching at all" failure this file already names three times;
#   * a PATH longer than the bound meant no length could satisfy the run before the literal
#     `?`, so the match failed and the query was emitted WHOLE — fail-open;
#   * and the comment claimed "no match lost", which was asserted rather than measured. Both
#     boundaries were one probe away.
# A bound that silently changes the ANSWER is not a safe way to buy linearity.
#
# exact one-repo-two-answers split this rule exists to close (`#access_token=` is the OAuth
# implicit-flow shape, i.e. the realistic case).






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
            # survives, the credential does not — including its QUERY STRING, which the
            # free-text rule alone does not remove. `transaction` and `origin` share this
            # positional gate and therefore share its fallback; the last time only one of
            # them was fixed, the identical string was redacted in one field and shipped
            # whole in the other.
            event["transaction"] = _redact_query_in_identifier(transaction)

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
    # copy-pasted bad DSN otherwise raises out of the module-level `init_glitchtip()` call in
    # api/main.py — effectively the first executable statement of
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


def _drop_log(log, hint):
    """Drop every structured-log envelope. `_scrub_event` has no reach into this channel.

    ⚠️ `enable_logs` does NOT close this channel, and the comment beside the
    `LoggingIntegration` kwarg said it did for a full round. That option is read at
    `integrations/logging.py:409-410`, i.e. at HANDLER-INSTALL time — it gates the stdlib
    logging BRIDGE. The channel itself is `Scope._capture_log` (`scope.py:1483-1497`), which
    has no `enable_logs` check at all; contrast its sibling `_capture_span` at :1515-1524,
    which explicitly gates on `has_span_streaming_enabled`. So a direct `sentry_sdk.logger.*`
    call emits a `log` envelope item carrying the interpolated parameter values —
    `sentry.message.parameter.*` — with `_scrub_event` never invoked.

    Reproduced with `enable_logs == False` and no `_experiments`: the full DSN, password
    included, on the wire. The stdlib path was already closed and stayed closed; this is the
    direct API, which no round had exercised.
    """
    return None


def _drop_metric(metric, hint):
    """Drop every metric envelope. `_scrub_event` has no reach into this channel.

    A hook, not a config flag, because the config flag is a documented NO-OP — see the
    comment at the `before_send_metric` kwarg below.
    """
    return None


def _first_set(*values: str | None) -> str | None:
    """The first value that is non-blank after stripping, or None."""
    for value in values:
        value = (value or "").strip()
        if value:
            return value
    return None


def _release() -> str | None:
    """The deployed SHA, or None — never a placeholder.

    ⚠️ Read the names the CONTAINER actually receives. `compose.yaml` passes `GIT_SHA` only as
    a BUILD ARG and puts `APP_GIT_SHA` in the runtime `environment:`; this read `GIT_SHA` and
    the retired Coolify deployment id, so every event since Coolify's retirement shipped with
    release=None. compose's own default is the literal "unknown", which is not a release:
    sending it would file every unbuilt deploy under one bogus release.

    ⚠️ Reading the right name does not by itself put a SHA in production. The hub spec sets
    `GIT_SHA: ""`, so compose's `${GIT_SHA:-unknown}` yields "unknown" and this returns None
    until the deploy passes the build arg (W-16322a6e). `GIT_SHA` is a fallback only for a run
    that EXPORTS it: `init_glitchtip()` runs at `api/main.py:3`, before anything loads `.env`.

    Each name is read with its own literal `os.environ.get("<NAME>")` so the env-example check,
    which matches literal reads, can see both.
    """
    candidates = (os.environ.get("APP_GIT_SHA"), os.environ.get("GIT_SHA"))
    # "unknown" is filtered PER NAME, so a placeholder APP_GIT_SHA falls through to a real
    # GIT_SHA rather than masking it.
    return _first_set(*(v for v in candidates if (v or "").strip() != "unknown"))


def _init_sdk(sentry_sdk, FastApiIntegration, StarletteIntegration, LoggingIntegration, dsn):
    """Call sentry_sdk.init with this service's hardened configuration."""
    sentry_sdk.init(
        dsn=dsn,
        # `APP_ENV` is what compose sets; `ENVIRONMENT` only for a run that exports it. A blank
        # or whitespace value falls through rather than shipping as the environment name.
        environment=_first_set(os.environ.get("APP_ENV"), os.environ.get("ENVIRONMENT"))
        or "production",
        release=_release(),
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
        # ⚠️ sentry-sdk 2.68.1 has FIVE `before_send*` hooks and `enable_metrics` is NOT one
        # of them — it is a documented NO-OP, and shipping it here was an inert fix that read
        # as a closed channel for a full round. `client.py:656-659` logs "The enable_metrics
        # option has no effect and will be removed in the next major" and then
        # `client.py:661-664` constructs the `MetricsBatcher` UNCONDITIONALLY, outside that
        # `if`. Contrast `span_batcher` at :666-671, which genuinely is gated. So the option
        # disabled nothing; a runtime probe still shipped a DSN inside a metric attribute
        # with `_scrub_event` never invoked, while the test asserted only that the kwarg had
        # been passed — a proxy where the real check was executable and cheap.
        #
        # The lever that works is the HOOK: `client.py:1259-1268` drops a metric when
        # `before_send_metric` returns None. Dropping rather than scrubbing, because nothing
        # in this repo emits metrics deliberately and the scrubber has no reach here anyway —
        # the same disposition as `max_breadcrumbs=0`.
        before_send_metric=_drop_metric,
        # The SEVENTH channel. `enable_logs` gates the stdlib BRIDGE, not the log
        # channel — `Scope._capture_log` has no such check — so a direct
        # `sentry_sdk.logger.*` call shipped the interpolated values with the scrubber
        # never invoked. Registering the hook is what closes it; see `_drop_log`.
        before_send_log=_drop_log,
        # Sessions are a SIXTH channel and they have no `before_send_*` hook at all, so a
        # hook-shaped inventory cannot see them. `auto_session_tracking` defaults True
        # (`consts.py:1333`). Today the ASGI integration pins `session_mode="request"`
        # (`integrations/asgi.py:229`), which aggregates and drops user info, so the payload
        # is release/environment/counts — LOW severity. It is closed anyway, on the same
        # standard this module applies everywhere else: not resting on someone else's
        # default for a channel the scrubber cannot reach.
        auto_session_tracking=False,
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
            # so that channel is OPEN here and is narrowed — NOT closed — by
            # `_ALLOWED_LOGENTRY_KEYS == {"message"}`, which keeps the message TEMPLATE and
            # drops `params`/`formatted`. Verified: `logger.error("otp=%s", secret)` yields
            # one event whose logentry is {'message': 'otp=%s'} with the secret absent.
            # ⚠️ Widening `_ALLOWED_LOGENTRY_KEYS` therefore turns THIS line into a leak,
            # while upstream's event_level=None would not. The two are coupled.
            #
            # ⚠️⚠️ THE RESIDUAL, stated because an earlier version of this comment said
            # "closed" and a reader would have believed it. The narrowing works only for
            # DEFERRED interpolation. A message built EAGERLY puts the secret in the
            # template itself, which is the field we keep:
            #     logger.error("token=%s", tok)   -> logentry.message "token=%s"   SAFE
            #     logger.error(f"token={tok}")    -> logentry.message "token=abc"  SHIPS
            # `.format()` and `+` concatenation behave like the f-string. The template is
            # still run through `_redact_userinfo_in_text`, so a URL-shaped credential is
            # caught (`postgres://u:pw@h` -> `postgres://[redacted]@h`) — but a BARE token
            # has no shape to key on and survives. Measured, not reasoned:
            # `_scrub_event` on `{"logentry": {"message": "auth failed for
            # token=BEARER_TOKEN_ABC123"}}` returns that string unchanged.
            # A SECOND residual, same root: `logger.error(..., exc_info=True)` on a CAUGHT
            # exception builds `exception.values[].value` from the exception's own message.
            # Since a13c801 that field IS run through the text redactor, so a URL-shaped
            # credential is caught there too — but, exactly as for the template, a BARE token
            # has no shape to key on: re-measured at a13c801,
            # `{"exception": {"values": [{"value": "bad key sk-live-DEADBEEF"}]}}` survives
            # scrubbing intact. For an UNCAUGHT exception this is a wash (the ASGI
            # integration reports it either way), but a caught-and-logged one becomes an
            # event ONLY under this line. So `raise ValueError(f"bad token {tok}")` caught
            # and logged is a leak here and is not one upstream.
            #
            # Upstream's event_level=None has neither residual, because the record never
            # becomes an event at all. So this is a REAL cost of the fleet default, not a
            # wash — it is accepted here because errors must be visible in GlitchTip, and it
            # is why scaffolded services log with %-style placeholders and keep secrets out
            # of exception messages.
            # `sentry_logs_level=None` is kept EXACTLY as upstream: that third handler goes
            # out through `before_send_log`, where `_scrub_event` has zero reach — the
            # registered `_drop_log` hook drops every log item instead of scrubbing it.
            # Raising it is not ours to do.
            LoggingIntegration(
                event_level=logging.ERROR, level=None, sentry_logs_level=None
            ),
        ],
    )
