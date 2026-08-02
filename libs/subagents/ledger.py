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
)

# The diff is model-controlled and can be multi-MB; cap what goes into the log so
# one record can't bloat the JSONL (the FULL diff is still on the AgentResult).
_MAX_DIFF_CHARS = 100_000


def agent_record(spec: object, result: object) -> dict[str, object]:
    """Build the canonical provenance record for one agent run (secret-free).

    Reads only whitelisted attributes off ``spec``/``result`` via ``getattr`` —
    a secret attribute (e.g. ``api_key``) or an excluded one (``system``, ``text``)
    is never serialized. The ``diff`` is truncated (see ``_MAX_DIFF_CHARS``).
    """
    record: dict[str, object] = {"ts": datetime.now(UTC).isoformat()}
    for field in _SPEC_FIELDS:
        record[field] = getattr(spec, field, None)
    for field in _RESULT_FIELDS:
        record[field] = getattr(result, field, None)
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


def write_receipt(
    agent_id: object, project: str | None, *, receipt_dir: str | None = None
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
