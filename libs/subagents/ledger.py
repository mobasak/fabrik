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
from datetime import datetime, timezone
from pathlib import Path

# Defensive redaction for the one model/transport-controlled free-text field that
# reaches the on-disk log (`error`): a token accidentally embedded in an exception
# string must not be persisted. (OpenRouter sends the key in a header, not a URL,
# so this is belt-and-suspenders — cheap insurance for a durable audit log.)
_SECRET_RE = re.compile(
    r"sk-[A-Za-z0-9_\-]{6,}|Bearer\s+\S+|(?i:(?:api[_-]?key|token|secret)\s*[=:]\s*)\S+"
)


def _redact(text: str) -> str:
    return _SECRET_RE.sub("[redacted]", text)


class Ledger:
    """Append-only JSONL store. ``path`` is created (with parents) on first write."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def append(self, record: dict) -> None:
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
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line)
                fh.flush()

    def read_all(self) -> list[dict]:
        """Every well-formed record, in append order. Missing file → empty list.

        A corrupt/partial line (e.g. a crash-truncated tail) is **skipped**, not
        raised — one bad line must never sink the read of an otherwise-valid log.
        """
        if not self.path.exists():
            return []
        records: list[dict] = []
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


def agent_record(spec: object, result: object) -> dict:
    """Build the canonical provenance record for one agent run (secret-free).

    Reads only whitelisted attributes off ``spec``/``result`` via ``getattr`` —
    a secret attribute (e.g. ``api_key``) or an excluded one (``system``, ``text``)
    is never serialized. The ``diff`` is truncated (see ``_MAX_DIFF_CHARS``).
    """
    record: dict = {"ts": datetime.now(timezone.utc).isoformat()}
    for field in _SPEC_FIELDS:
        record[field] = getattr(spec, field, None)
    for field in _RESULT_FIELDS:
        record[field] = getattr(result, field, None)
    # normalize owned_paths to a plain list (it may be a tuple/other iterable)
    owned = record.get("owned_paths")
    record["owned_paths"] = list(owned) if owned else []
    # bound the model-controlled diff so it can't blow up a single JSONL line
    diff = record.get("diff")
    if isinstance(diff, str) and len(diff) > _MAX_DIFF_CHARS:
        record["diff"] = diff[:_MAX_DIFF_CHARS] + "\n…[diff truncated in ledger]"
    # redact any secret that slipped into the transport error string
    err = record.get("error")
    if isinstance(err, str):
        record["error"] = _redact(err)
    return record


__all__ = ["Ledger", "agent_record"]
