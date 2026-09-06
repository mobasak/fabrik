"""Durable append-only JSONL provenance store for subagent runs.

The final containment layer: every subagent run is recorded — what it was asked
to do, which model ran it, how it ended, what it cost, and the diff it produced —
so a pool run is auditable after the fact.

* :class:`Ledger` is a thin append-only JSONL writer (one JSON object per line).
  Appends are line-atomic (a process-wide lock serializes writers) so parallel
  agents can record concurrently without corrupting a line.
* :func:`agent_record` builds the canonical record from a spec + result. It is a
  **whitelist** — only known-safe fields are copied, so a secret carried on the
  spec (an API key, a system prompt) can never leak into the on-disk log.

Vendors the append-a-dict shape of ai-consult's ``ConsultStore`` (``store.py``),
enhanced with the agent-run record instead of the consult record.
"""

from __future__ import annotations

import json
import os
import re
import threading
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

try:
    import fcntl  # POSIX advisory file locking (Linux/WSL — the fleet target)
except ImportError:  # pragma: no cover - non-POSIX; falls back to in-process lock only
    fcntl = None  # type: ignore[assignment]

# Defensive redaction for every free-text field that reaches the on-disk log — `error`
# (transport-controlled) AND `task`/`diff` (caller- and model-controlled: a caller can inline a
# secret into the task, or the model can emit one into the diff — the tojlo-mail leak was a
# `DATABASE_URL` password pasted into a review task landing in `.tmp/subagents/ledger.jsonl`, which
# tripped a project secrets gate). It masks the COMMON credential SHAPES (keys/tokens, the password in
# a URL/DSN incl. the no-user `redis://:pw@` form, `password=…`, AWS/GitHub tokens) and only those, so
# it never mangles ordinary prose/code. NOT a full secret scanner — pair it with gitignoring `.tmp/`
# (defense-in-depth for an exotic shape these patterns don't model).
_SECRET_RE = re.compile(
    r"sk-[A-Za-z0-9_\-]{6,}"
    r"|Bearer\s+\S+"
    r"|AKIA[0-9A-Z]{16}"  # AWS access-key id
    r"|gh[pousr]_[A-Za-z0-9]{20,}"  # GitHub token (ghp_/gho_/ghu_/ghs_/ghr_)
    r"|(?i:(?:api[_-]?key|token|secret|password)\s*[=:]\s*)\S+"
)
# The password in a `scheme://[user]:password@host` URL/DSN — user is OPTIONAL (`*`) so the canonical
# no-user Redis/PG form `redis://:pw@host` is caught too. Masks ONLY the password group, keeping the
# scheme/user/host so the record stays legible.
_URL_CRED_RE = re.compile(r"(://[^:@/\s]*:)([^@/\s]+)(@)")


def _redact(text: str) -> str:
    return _URL_CRED_RE.sub(r"\1[redacted]\3", _SECRET_RE.sub("[redacted]", text))


class Ledger:
    """Append-only JSONL store. ``path`` is created (with parents) on first write."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def append(self, record: dict[str, object]) -> None:
        """Append one record as a single JSON line (line-atomic under the lock).

        ``default=str`` keeps a non-JSON-native value (e.g. a datetime) from
        raising — the store must never drop a provenance record on a type quirk.
        The write is ``flush``ed (not ``fsync``ed): a process crash can still lose
        an OS-buffered tail line, which :meth:`read_all` tolerates.

        This is the LOCAL, always-on audit copy. The centralized ``subagent_runs``
        flywheel is written SEPARATELY and DELIBERATELY by the orchestrator via
        :func:`pg_ledger.record_run` AFTER it judges the run — so the row carries a
        ``quality_score``. The ledger does NOT auto-write to Postgres: a runtime
        auto-write could only supply a NULL quality, and would then DUPLICATE the
        orchestrator's quality-bearing row (the table is INSERT-only, so the two can't
        be merged). One run → one authoritative flywheel row, via ``record_run``.
        """
        line = json.dumps(record, default=str) + "\n"
        with self._lock:  # in-process: serialize threads sharing this Ledger instance
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                # cross-process: the per-repo DEFAULT ledger_path can be appended by SEVERAL
                # orchestrator processes at once (multiple Claude sessions in one repo). A large,
                # diff-bearing record exceeds the OS atomic-append size, so without an advisory
                # lock two processes' lines can interleave and corrupt the JSONL. flock(LOCK_EX)
                # serializes the write cross-process (releases on close); threading.Lock alone is
                # per-process and can't. A distinct ledger_path per orchestrator also avoids it,
                # but this makes the shared default safe too.
                if fcntl is not None:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                fh.write(line)
                fh.flush()

    def read_all(self) -> list[dict[str, object]]:
        """Every well-formed record, in append order. Missing file → empty list.

        A corrupt/partial line (e.g. a crash-truncated tail) is **skipped**, not
        raised — one bad line must never sink the read of an otherwise-valid log.
        """
        if not self.path.exists():
            return []
        records: list[dict[str, object]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # tolerate a partial/corrupt line rather than fail the whole read
        return records


# The provenance whitelist: ONLY these fields are copied into a record. Anything
# else on the spec/result (api keys, system prompts, raw transcripts, model text)
# is deliberately excluded so it cannot land in the on-disk log.
_SPEC_FIELDS = ("task", "model", "owned_paths", "task_type")
_RESULT_FIELDS = (
    "agent_id",
    "status",
    "provider",
    "cost_usd",
    "turns",
    "latency_s",  # wall-clock seconds for the run (None if not captured)
    "diff",
    "error",
    "tool_calls",  # name→count map (provenance) — no secret
    # Added 2026-09-02 (Phase F). Both already existed on AgentResult and were discarded at the DB
    # boundary — the flywheel could not normalise cost by task size, and `latency_s` silently
    # contained our own queue wait.
    "out_tokens",  # F3 — completion tokens, summed per run
    "queue_s",     # F2 — seconds spent waiting on the provider sub-cap + global semaphore
)

# The diff is model-controlled and can be multi-MB; cap what goes into the log so
# one record can't bloat the JSONL (the FULL diff is still on the AgentResult).
_MAX_DIFF_CHARS = 100_000

# T04 — `lanes.classify`'s structured `FailureCause.cause` vocabulary, mapped onto this ledger's
# PRE-EXISTING `failure_reason` tokens (a live column with historical rows — see the branch below).
# `classify` emits `auth / rate-limited / unavailable / request-too-large / model-gone /
# priced-out / bad-request / error`; `loop.py` additionally tags a content-stall cap directly with
# `content-stall` (never produced by `classify` itself — verified at both source sites). This is
# NOT a rename table: three causes get a NEW token rather than a lossy fold, a decision made here
# and not silently —
#
#   * `model-gone` — NOT the same thing as this ledger's existing `invalid-model-id`.
#     `invalid-model-id` is commented "OURS" (a typo'd model id caught before dispatch);
#     `model-gone` is a model that answered and was RETIRED. Folding them would destroy a
#     distinction an operator needs when reading this column.
#   * `request-too-large` / `bad-request` — both OUR-fault classes (a malformed/oversized request
#     WE sent), with no existing counterpart. Folding either into `provider-error` would attribute
#     our own mistake to the vendor in every ranking query that groups by this column.
#
# So the value SET widens by three tokens — a Doc Sync Matrix "table/column/enum changed" event.
# `failure_reason` is plain TEXT with no CHECK constraint (`pg_ledger.py:62`), so this is not a
# migration, but any downstream reader that enumerates known tokens (a dashboard, `select`'s
# ranking) needs to learn the three new ones; that note is owed to `pg_ledger.py`'s callers, not
# resolved here (out of this ticket's owned paths).
_CAUSE_TO_REASON: dict[str, str] = {
    "rate-limited": "rate-limited",  # 1:1, already the same word on both sides
    "priced-out": "priced-out",  # 1:1, already discriminated at the substring site below
    # 1:1 in MEANING, not spelling: loop.py's content-stall cap and this token are the same event
    # (the provider accepted and streamed nothing) seen from two different callers.
    "content-stall": "provider-stalled",
    "auth": "auth-failed",
    # `unavailable` (a 429/503-adjacent transient provider failure) and `error` (classify's own
    # catch-all: "5xx, a transport/timeout error, or anything unclassified") both land on THIS
    # ledger's own catch-all rather than the narrower `transport` token — `error` explicitly
    # covers real 5xx provider failures, not only transport/timeout ones, and mapping it to
    # `transport` would misdescribe a genuine provider fault as a network issue.
    "unavailable": "provider-error",
    "error": "provider-error",
    # WIDENED (see the module comment above): no existing token was honest for these three.
    "model-gone": "model-gone",
    "request-too-large": "request-too-large",
    "bad-request": "bad-request",
}


def agent_record(spec: object, result: object) -> dict[str, object]:
    """Build the canonical provenance record for one agent run (secret-free).

    Reads only whitelisted attributes off ``spec``/``result`` via ``getattr`` —
    a secret attribute (e.g. ``api_key``) or an excluded one (``system``, ``text``)
    is never serialized. The ``diff`` is truncated (see ``_MAX_DIFF_CHARS``).
    """
    record: dict[str, object] = {"ts": datetime.now(UTC).isoformat()}
    # WHICH SESSION produced this run. Three agents share one ledger file, so without it a
    # per-session gate can only accuse the whole file — it cannot tell whose run went unrecorded.
    # Omitted (not null) when unknown, so a row predating this field is distinguishable from one
    # written by a harness that provides no session. Never derived from the process: a pid-based
    # identity changes between an agent's own commands (the repo_lock trap).
    if (_sid := session_id()) is not None:
        record["session_id"] = _sid
    for field in _SPEC_FIELDS:
        record[field] = getattr(spec, field, None)
    for field in _RESULT_FIELDS:
        record[field] = getattr(result, field, None)
    # ── F1/F3: derive the columns the flywheel needs from what the result already carries ────────
    # F3 — the DB column is `tokens_out`; the AgentResult attribute is `out_tokens`. Map, don't
    # rename the attribute: 48 vendored copies read it.
    record["tokens_out"] = record.get("out_tokens")

    # F1 — WHY the run failed, as a short machine-readable token. The DB had NO error column at all,
    # so `status='error'` could not be told from OUR price cap and a provider stall could not be told
    # from OUR turn ceiling. Three model verdicts were nearly drawn from that gap in a single day.
    #
    # ⚠️ This is ALSO how G1 is delivered. G1 asked for `capped` to split into `stalled` /
    # `turn_exhausted`. Doing that literally would widen the public `AgentStatus` Literal that all 48
    # vendored copies narrow on — a far larger contract change than the distinction is worth, and one
    # that breaks every consumer type-checking against the old set. The DISTINCTION is what G1 needs,
    # and it lives here losslessly: `capped` + `reason='provider-stalled'` vs `capped` +
    # `reason='turn-budget-exhausted'`. Historical rows stay derivable (`status='capped' AND
    # turns=0`), so nothing already recorded is stranded.
    _status = str(record.get("status") or "")
    _turns = record.get("turns")
    _err = str(record.get("error") or "")
    # T04 — PREFER the structured cause (`result.failure`, a `lanes.FailureCause`) over every
    # branch below, when the result carries one. `failure` is deliberately NOT in
    # `_RESULT_FIELDS`: `Ledger.append` serializes with `json.dumps(record, default=str)`, so
    # whitelisting the raw dataclass would land its `repr()` in the record as a new free-text
    # field to substring-match — the exact defect this ticket removes, re-created one field over.
    # Read the cause off the result (duck-typed via `getattr`, like every other field here) and
    # write only the MAPPED TOKEN via `_CAUSE_TO_REASON`.
    #
    # This DELIBERATELY outranks the `capped` turns-based split just below: a `capped` run that
    # lost to a mid-flight rate-limit, a retired model, or a content stall is a PRECISE verdict
    # `loop.classify` already reached (`loop.py:508,595,787`) — the turns-based
    # provider-stalled/turn-budget-exhausted split is a coarser fallback for exactly the case
    # nothing more specific fired (a plain wall-clock/turn-budget cap with nothing to classify,
    # `loop.py:502,549,723`, carries no `failure` at all and is unaffected by this branch).
    #
    # An unmapped cause (none exist in the enumerated vocabulary today, but a future `classify`
    # addition could land here before this table is updated) falls through to the branches below
    # rather than writing an unvetted token — the same "map, never widen silently" rule this
    # table itself exists to honor.
    _failure = getattr(result, "failure", None)
    _cause = getattr(_failure, "cause", None) if _failure is not None else None
    if isinstance(_cause, str) and _cause in _CAUSE_TO_REASON:
        record["failure_reason"] = _CAUSE_TO_REASON[_cause]
    elif _status == "capped":
        # The module already draws this line for the human-readable message (`_cap_message`):
        # 0 turns means the provider accepted and streamed nothing; >=1 means it worked and ran out.
        # This NARROWS the fork above; it does not remove it — a `capped` result with no
        # structured cause still falls here, same as before T04.
        record["failure_reason"] = (
            "provider-stalled" if not _turns else "turn-budget-exhausted"
        )
    elif _status == "error" and _err:
        # Keep the FULL text in the JSONL; the column carries a short, groupable token so the
        # ranking can partition failures without a LIKE over free text.
        low = _err.lower()
        if "max price" in low:
            record["failure_reason"] = "priced-out"        # OURS, not the model's
        elif "not a valid model id" in low:
            record["failure_reason"] = "invalid-model-id"  # OURS
        elif "429" in low:
            record["failure_reason"] = "rate-limited"
        elif "403" in low or "auth" in low:
            record["failure_reason"] = "auth-failed"
        elif "connection" in low or "disconnect" in low or "stalled" in low:
            record["failure_reason"] = "transport"
        else:
            record["failure_reason"] = "provider-error"
    else:
        record["failure_reason"] = None

    # normalize owned_paths to a plain list (it may be a tuple/other iterable)
    owned = record.get("owned_paths")
    record["owned_paths"] = list(cast("Iterable[Any]", owned)) if owned else []
    # bound the model-controlled diff so it can't blow up a single JSONL line
    diff = record.get("diff")
    if isinstance(diff, str) and len(diff) > _MAX_DIFF_CHARS:
        record["diff"] = diff[:_MAX_DIFF_CHARS] + "\n…[diff truncated in ledger]"
    # FAIL-CLOSED secret redaction on EVERY free-text field that reaches the on-disk log — the caller
    # can inline a credential in the task, the model can emit one in the diff, and a token can slip
    # into a transport error. Scrub all three so `.tmp/subagents/ledger.jsonl` never persists a
    # plaintext secret regardless of whether the project gitignored `.tmp/` (enforcement, not a doc).
    for f in ("task", "diff", "error"):
        v = record.get(f)
        if isinstance(v, str):
            record[f] = _redact(v)
    return record


# ── Local receipts — the flywheel-enforcement rail ─────────────────────────────
# The enforcement gate CANNOT `SELECT subagent_runs` (the writer role is INSERT-only), so it needs a
# LOCAL signal that a run was recorded+scored. `record_agent_run` writes a receipt here on a confirmed
# DB write; `audit_unrecorded` reconciles ledger↔receipts to surface pool runs that ran but were never
# recorded (= ledger − receipts). Native subagents never write the ledger, so they are never flagged.
RECEIPTS_FILENAME = "receipts.jsonl"


def _receipts_path(receipt_dir: str | None) -> Path:
    """The receipts file. ``receipt_dir`` (the run's ``<repo>/.tmp/subagents``) if given, else
    ``.tmp/subagents/`` relative to CWD — which co-locates with the DEFAULT ledger when the
    orchestrator runs from the repo root (the convention). A caller not at repo-root passes
    ``receipt_dir`` explicitly."""
    base = Path(receipt_dir) if receipt_dir else Path(".tmp") / "subagents"
    return base / RECEIPTS_FILENAME


# The harness-provided per-session identity. NOT a name we own — it is a convention of the
# environment we happen to run in, so it is read defensively and its absence is normal.
_SESSION_ENV = "CLAUDE_CODE_SESSION_ID"


def session_id(override: str | None = None) -> str | None:
    """This session's identity, or ``None``.

    Why an env var and never a derived value: three sessions share one ledger, so a per-session
    "unscored runs" gate needs to tell them apart — but anything derived from the PROCESS is
    unstable. ``repo_lock.py`` proved that here on 2026-08-13: it identified holders by
    ``getppid()``, an agent runs each shell command in a NEW process, and the lock became
    permanently unreleasable because the ppid at release never matched the one at acquire.

    ``None`` is a normal, expected answer — a vendored copy in CI or another harness has no such
    variable, and callers must degrade rather than fail.

    (The name is infra's `CLAUDE_SESSION_ID` corrected: that variable is unset; the live one is
    `CLAUDE_CODE_SESSION_ID`.)
    """
    if override:
        return override
    val = os.getenv(_SESSION_ENV)
    return val or None


def write_receipt(
    agent_id: object,
    project: str | None,
    *,
    receipt_dir: str | None = None,
    session: str | None = None,
) -> bool:
    """Append one receipt marking a run as recorded+scored. BEST-EFFORT: returns ``False`` and never
    raises on any error (a missing receipt after a real DB write only costs a false advisory WARN,
    never a broken run). Reuses :class:`Ledger` so the append is cross-process flock-protected."""
    try:
        Ledger(str(_receipts_path(receipt_dir))).append(
            {
                "agent_id": str(agent_id),
                "ts": datetime.now(UTC).isoformat(),
                "recorded": True,
                "project": project,
                # Omitted entirely when unknown, rather than written as null: a receipt that
                # SAYS session=null is indistinguishable from one written before this field
                # existed, and a reconciler cannot tell "no session" from "old receipt".
                **({"session_id": sid} if (sid := session_id(session)) else {}),
            }
        )
        return True
    except Exception:  # noqa: BLE001 — best-effort: a receipt-write failure never breaks a run
        return False


def audit_unrecorded(
    ledger_path: str, receipts_path: str | None = None
) -> list[dict[str, object]]:
    """Ledger entries whose ``agent_id`` has NO matching receipt — pool runs that ran but were never
    scored+recorded. ``receipts_path`` defaults co-located with the ledger. Never raises; a missing
    ledger (no pool use) → ``[]``."""
    if receipts_path is None:
        receipts_path = str(Path(ledger_path).parent / RECEIPTS_FILENAME)
    ledger_entries = Ledger(ledger_path).read_all()  # [] if the ledger file is absent
    recorded = {
        r.get("agent_id")
        for r in Ledger(receipts_path).read_all()
        if r.get("recorded") and r.get("agent_id")
    }
    return [
        e
        for e in ledger_entries
        if e.get("agent_id")
        and e.get("agent_id") not in recorded
        # an errored run (a config-refusal — sandbox/grounding — or a transport failure) produced no
        # gradeable output to score, so it must NOT be flagged as "ran-but-unrecorded".
        and e.get("status") != "error"
    ]


__all__ = [
    "Ledger",
    "agent_record",
    "write_receipt",
    "audit_unrecorded",
    "RECEIPTS_FILENAME",
]
