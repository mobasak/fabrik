"""Behavior-Contract tests for scripts/sysadmin/incident_context.py (TDD — written FIRST).

The marshaller is the HOST side of the pool-diagnosis path: when ob@ is capped, an incident can't
run the autonomous fix on ob@, so a read-only pool worker diagnoses it instead. But a single-shot
`fanout(mode="read_only")` worker has NO file tools — so the marshaller assembles a bundle (the
GlitchTip webhook + bounded docker log tails + host state), writes it durably to
~/.claude/state/incidents/<id>.json, and INLINES its content into the worker's prompt. The proposal
is mesh-notify'd to the operator and NEVER auto-applied.

All I/O (docker logs, host state, the pool, the notifier) is injected — nothing shells out.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "incident_context", _ROOT / "scripts" / "sysadmin" / "incident_context.py"
)
incident_context = importlib.util.module_from_spec(_spec)
sys.modules["incident_context"] = incident_context
_spec.loader.exec_module(incident_context)  # type: ignore[union-attr]


def _marshaller(tmp_path, *, pool=None, notify=None, logs=None, state=None, applied=None):
    dispatched: dict = {}

    def _pool(prompt, **kw):
        dispatched["prompt"] = prompt
        dispatched["kwargs"] = kw
        return "DIAGNOSIS: restart container X; root cause is OOM."

    def _notify(subject, detail):
        dispatched.setdefault("notifications", []).append((subject, detail))

    return incident_context.IncidentMarshaller(
        incidents_dir=tmp_path / "incidents",
        log_tail_lines=200,
        docker_logs_fn=logs or (lambda container, lines: f"[{container}] line1\nline2 (of {lines})"),
        state_fn=state or (lambda: "docker ps: X Up\nsystemctl: ok"),
        pool_fn=pool or _pool,
        notify_fn=notify or _notify,
        apply_fn=applied,  # if the code ever tries to auto-apply, this records it (it must NOT)
    ), dispatched


def test_build_bundle_assembles_webhook_logs_state(tmp_path):
    m, _ = _marshaller(tmp_path)
    bundle = m.build_bundle({"error": "boom", "project": "svc"}, containers=["svc", "worker"])
    assert bundle["webhook"] == {"error": "boom", "project": "svc"}
    assert set(bundle["log_tails"]) == {"svc", "worker"}
    assert "line1" in bundle["log_tails"]["svc"]
    assert "docker ps" in bundle["state"]


def test_write_bundle_to_host_path(tmp_path):
    m, _ = _marshaller(tmp_path)
    bundle = m.build_bundle({"error": "boom"}, containers=["svc"])
    path = m.write_bundle("incident-42", bundle)
    assert path == tmp_path / "incidents" / "incident-42.json"
    assert path.exists()
    assert json.loads(path.read_text())["webhook"] == {"error": "boom"}


def test_diagnose_inlines_bundle_content_into_single_shot_worker(tmp_path):
    m, d = _marshaller(tmp_path)
    result = m.diagnose("incident-7", {"error": "OOM in svc", "project": "svc"}, containers=["svc"])
    # the bundle CONTENT is inlined into the prompt — NOT a bare path
    assert "OOM in svc" in d["prompt"]          # webhook content inlined
    assert "line1" in d["prompt"]               # log-tail content inlined
    assert "docker ps" in d["prompt"]           # host state inlined
    assert str(tmp_path / "incidents") not in d["prompt"]  # never hands the worker a path to read
    # dispatched single-shot read_only
    assert d["kwargs"].get("mode") == "read_only"
    assert result["diagnosis"].startswith("DIAGNOSIS")


def test_diagnose_notifies_operator_and_never_auto_applies(tmp_path):
    applied = {"count": 0}
    m, d = _marshaller(tmp_path, applied=lambda proposal: applied.__setitem__("count", applied["count"] + 1))
    m.diagnose("incident-9", {"error": "boom"}, containers=["svc"])
    # the operator is notified with the proposal
    assert d.get("notifications"), "operator must be mesh-notified with the proposal"
    # and the fix is NEVER auto-applied
    assert applied["count"] == 0


def test_diagnose_persists_bundle_before_dispatch(tmp_path):
    order: list[str] = []
    m, _ = _marshaller(
        tmp_path,
        state=lambda: (order.append("state") or "state"),
        pool=lambda prompt, **kw: (order.append("dispatch") or "DIAGNOSIS: x"),
    )
    m.diagnose("incident-1", {"error": "boom"}, containers=["svc"])
    path = tmp_path / "incidents" / "incident-1.json"
    assert path.exists()                        # bundle written durably
    assert order.index("state") < order.index("dispatch")  # assembled BEFORE the worker runs


def test_log_tails_bounded_to_configured_lines(tmp_path):
    seen = {}
    m, _ = _marshaller(tmp_path, logs=lambda container, lines: seen.__setitem__("lines", lines) or "tail")
    m.build_bundle({"error": "x"}, containers=["svc"])
    assert seen["lines"] == 200  # the INCIDENT_LOG_TAIL_LINES default bounds the inlined size


class _Gov:
    def __init__(self, dest):
        self.dest = dest

    def route(self, kind, *, caller=None):
        return self.dest


# TERMINAL entry: an incident with ob@ headroom returns "run the fix on ob@" (the caller runs it +
# releases the lock); the marshaller is NOT invoked.
def test_run_incident_routes_to_obat_when_headroom(tmp_path):
    m, d = _marshaller(tmp_path)
    out = m.run_incident({"id": "i1", "error": "x"}, containers=["svc"], governor=_Gov("ob@"))
    assert out["action"] == "run_on_obat"
    assert out["incident_id"] == "i1"
    assert "governor" in out          # handed back so the caller can release_incident() after the fix
    assert not (tmp_path / "incidents" / "i1.json").exists()  # no diagnosis marshalled on the ob@ path


# TERMINAL entry: a capped incident marshals a read-only pool diagnosis + notifies (never dropped).
def test_run_incident_marshals_when_capped(tmp_path):
    m, d = _marshaller(tmp_path)
    out = m.run_incident({"id": "i2", "error": "OOM"}, containers=["svc"], governor=_Gov("pool-diagnose"))
    assert out["action"] == "pool_diagnosed"
    assert out["diagnosis"].startswith("DIAGNOSIS")
    assert d.get("notifications")                        # operator handed the proposal
    assert (tmp_path / "incidents" / "i2.json").exists()  # bundle persisted for the read-only worker
