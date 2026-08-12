"""Shape-driven destroy: comprehensive teardown of a deployed service.

Why this module exists
----------------------
Pre-existing ``fabrik destroy`` (in ``cli.py``) only removed the Coolify
application and left a TODO on DNS deletion. Every shape-gated infrastructure
resource — Authelia rules, GlitchTip projects, Gatus endpoints, Backrest
plans, Grafana annotations, MeiliSearch indices, per-service Postgres
databases — was leaked on every teardown, and the canonical E2E workflow
in ``docs/DEPLOYMENT_ARCHITECTURE.md`` §9.6 had to paper over it with a by-hand
``python -c`` block that the operator was expected to remember.

This module is the symmetric counterpart to
:class:`fabrik.orchestrator.infrastructure.InfrastructureProvisioner`. It
reuses the exact same shape-resolution function
(:func:`resolve_applicability`) to decide which registrars *would have
been* touched for a given spec, then walks them in reverse contract
order and calls each driver's idempotent remove/delete entry point.

Design choices
--------------

* **Derived from the spec, not from live state.** We do not poll the VPS
  to discover resources; the spec's ``shape``/``infra`` blocks tell us
  everything, and every driver is already idempotent on 404. This keeps
  destroy fast and correct even when the apply-time orchestrator context
  is long gone.

* **Destructive actions gated behind ``drop_data``.** Postgres databases
  and MeiliSearch indices hold user data; auto-rollback policy
  (``rollback.py::_rollback_postgres``) leaves them in place. Destroy
  inherits that default — a naked ``fabrik destroy`` will warn about DB
  rows surviving the teardown and point the operator at the
  ``--drop-data`` flag. Only the throwaway-test-cleanup workflow should
  pass ``drop_data=True``.

* **Grafana annotations are not reversed.** They're informational-only
  and auto-expire; deleting them would require storing the per-deploy
  annotation id, which we don't persist. Ignored by design.

* **Every registrar call is best-effort.** A single failing driver
  doesn't abort the rest of the teardown. Failures are collected into
  :attr:`DestroyReport.errors` for the CLI to surface.

* **Order is strict reverse-of-provisioner:** meilisearch →
  authelia → glitchtip → backrest → gatus → postgres → app (compose) →
  DNS record → local project files. This mirrors
  ``InfrastructureProvisioner.provision`` so a partial destroy can be
  resumed safely (idempotency guarantees).
"""

from __future__ import annotations

import logging
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fabrik.orchestrator.infrastructure import resolve_applicability
from fabrik.spec_loader import Spec

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #


@dataclass
class ActionResult:
    """Single step outcome during destroy.

    Attributes:
        step: Short identifier (``authelia``, ``coolify``, ``dns``, …).
        status: One of ``removed`` (mutation applied), ``not_found``
            (nothing to do), ``skipped`` (gated off by flag or spec),
            ``dry_run`` (would-have-run), ``error`` (driver raised).
        detail: Human-readable one-liner for CLI output.
        error: Exception repr when ``status == "error"``.
    """

    step: str
    status: str
    detail: str = ""
    error: str | None = None


@dataclass
class DestroyReport:
    """Aggregate report returned by :func:`destroy_deployment`."""

    actions: list[ActionResult] = field(default_factory=list)

    @property
    def errors(self) -> list[ActionResult]:
        """All action results with ``status == "error"``."""
        return [a for a in self.actions if a.status == "error"]

    @property
    def had_errors(self) -> bool:
        return bool(self.errors)

    def add(self, step: str, status: str, detail: str = "", error: str | None = None) -> None:
        self.actions.append(ActionResult(step=step, status=status, detail=detail, error=error))


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _spec_to_dict(spec: Spec) -> dict[str, Any]:
    """Serialize a :class:`Spec` for ``resolve_applicability``.

    ``resolve_applicability`` accepts a plain dict to decouple it from
    the pydantic model; we use pydantic's ``model_dump`` with
    ``mode='json'`` so enum fields become their string values (``kind``
    is enum in the model but compared as a string inside
    ``resolve_applicability``).
    """
    return spec.model_dump(mode="json")


def _split_domain(fqdn: str) -> tuple[str, str] | None:
    """Split ``foo.vps1.ocoron.com`` → (``"foo.vps1"``, ``"ocoron.com"``).

    Duplicates ``cli._split_domain_for_dns`` to avoid importing from the
    CLI layer (which would create a circular dependency when the CLI
    imports this module). Returns ``None`` when the FQDN is too short
    to have both a subdomain and a base-zone.
    """
    parts = fqdn.split(".")
    if len(parts) < 3:
        return None
    base_parts = 2
    if (
        len(parts) >= 4
        and len(parts[-1]) == 2
        and parts[-2] in {"co", "com", "net", "org", "gov", "ac"}
    ):
        base_parts = 3
    subdomain = ".".join(parts[:-base_parts])
    base_domain = ".".join(parts[-base_parts:])
    return subdomain, base_domain


# --------------------------------------------------------------------------- #
# Individual teardown steps
# --------------------------------------------------------------------------- #
#
# Each ``_destroy_*`` helper returns an ``ActionResult`` and never raises.
# Drivers are imported lazily inside each function so a missing optional
# driver (e.g., the site-provisioner when running offline) doesn't block
# the rest of the teardown.


def _destroy_meilisearch(name: str, drop_data: bool, dry_run: bool) -> ActionResult:
    if not drop_data:
        return ActionResult(
            "meilisearch",
            "skipped",
            detail="index preserved (pass --drop-data to delete)",
        )
    try:
        from fabrik.drivers.meilisearch import delete_index

        uid = name.replace("-", "_")
        ok = delete_index(uid, dry_run=dry_run)
        return ActionResult(
            "meilisearch",
            "dry_run" if dry_run else ("removed" if ok else "not_found"),
            detail=f"index {uid}",
        )
    except Exception as e:  # noqa: BLE001 — best-effort
        return ActionResult("meilisearch", "error", error=repr(e))


def _destroy_authelia(domain: str, dry_run: bool) -> ActionResult:
    try:
        from fabrik.drivers.authelia import remove_access_rule

        ok = remove_access_rule(domain, dry_run=dry_run)
        # The driver returns True when rules were actually removed and
        # False when there were none to remove (idempotent-404). We map
        # both to a non-error outcome.
        return ActionResult(
            "authelia",
            "dry_run" if dry_run else ("removed" if ok else "not_found"),
            detail=f"domain {domain}",
        )
    except Exception as e:  # noqa: BLE001
        return ActionResult("authelia", "error", error=repr(e))


def _destroy_glitchtip(name: str, dry_run: bool) -> ActionResult:
    try:
        from fabrik.drivers.glitchtip import delete_project

        ok = delete_project(name, dry_run=dry_run)
        return ActionResult(
            "glitchtip",
            "dry_run" if dry_run else ("removed" if ok else "not_found"),
            detail=f"project {name}",
        )
    except Exception as e:  # noqa: BLE001
        return ActionResult("glitchtip", "error", error=repr(e))


def _destroy_backrest(name: str, dry_run: bool) -> ActionResult:
    try:
        from fabrik.drivers.backrest import remove_backup_plan

        plan_id = f"{name}-data"
        ok = remove_backup_plan(plan_id, dry_run=dry_run)
        return ActionResult(
            "backrest",
            "dry_run" if dry_run else ("removed" if ok else "not_found"),
            detail=f"plan {plan_id}",
        )
    except Exception as e:  # noqa: BLE001
        return ActionResult("backrest", "error", error=repr(e))


def _destroy_gatus(name: str, dry_run: bool) -> ActionResult:
    try:
        from fabrik.drivers.gatus import remove_endpoint

        ok = remove_endpoint(name, dry_run=dry_run)
        return ActionResult(
            "gatus",
            "dry_run" if dry_run else ("removed" if ok else "not_found"),
            detail=f"endpoint {name}",
        )
    except Exception as e:  # noqa: BLE001
        return ActionResult("gatus", "error", error=repr(e))


def _destroy_redis(name: str, drop_data: bool, dry_run: bool) -> ActionResult:
    """Release the Redis logical-DB index. ``drop_data`` flips FLUSHDB on.

    Symmetric counterpart to ``_provision_redis``: the registry slot is
    always released so ``acquire_db_index`` can hand it out to the next
    service. ``--drop-data`` additionally calls ``FLUSHDB`` on the freed
    DB so the next tenant starts clean — same fail-closed default as
    ``_destroy_postgres`` (skip data destruction unless asked).
    """
    try:
        from fabrik.drivers.redis import release_db_index

        ok = release_db_index(name, flushdb=drop_data, dry_run=dry_run)
        status = "dry_run" if dry_run else ("removed" if ok else "error")
        detail = f"db index for {name}" + (" (+FLUSHDB)" if drop_data else "")
        return ActionResult("redis", status, detail=detail)
    except Exception as e:  # noqa: BLE001
        return ActionResult("redis", "error", error=repr(e))


def _destroy_prometheus(name: str, dry_run: bool) -> ActionResult:
    """Remove the ``fabrik-<name>`` scrape job (best-effort)."""
    try:
        from fabrik.drivers.prometheus import remove_scrape_target

        ok = remove_scrape_target(name, dry_run=dry_run)
        status = "dry_run" if dry_run else ("removed" if ok else "error")
        return ActionResult("prometheus", status, detail=f"scrape job fabrik-{name}")
    except Exception as e:  # noqa: BLE001
        return ActionResult("prometheus", "error", error=repr(e))


def _destroy_postgres(name: str, drop_data: bool, dry_run: bool) -> ActionResult:
    """Drop the PostgreSQL database for a service.

    **CAVEAT:** PostgreSQL data is preserved by default. You must pass
    ``drop_data=True`` to drop the database. This is intentional to protect
    against accidental data loss on teardown.

    Args:
        name: Service name (used to derive the database name).
        drop_data: If True, drop the database. If False, skip deletion.
        dry_run: If True, plan only without mutating state.

    Returns:
        ActionResult with status (skipped/removed/not_found/error).
    """
    if not drop_data:
        return ActionResult(
            "postgres",
            "skipped",
            detail="database preserved (pass --drop-data to drop)",
        )
    try:
        from fabrik.drivers.postgres import drop_database

        # Name normalization must match create_database (hyphens -> underscores).
        db_name = name.replace("-", "_")
        result = drop_database(db_name, dry_run=dry_run)
        # On dry-run we report ``dry_run`` regardless of the driver's
        # response. The driver's own status is informational only when a
        # real mutation happened.
        status_map = {
            "dropped": "removed",
            "not_found": "not_found",
            "dry_run": "dry_run",
        }
        status = "dry_run" if dry_run else status_map.get(result.get("status", ""), "removed")
        return ActionResult("postgres", status, detail=f"database {db_name}")
    except Exception as e:  # noqa: BLE001
        return ActionResult("postgres", "error", error=repr(e))


def _destroy_compose(name: str, dry_run: bool, drop_data: bool = False) -> ActionResult:
    """Destroy a compose-deployed app via SSH."""
    import re

    from fabrik.drivers.ssh import ssh as _ssh

    try:
        if dry_run:
            return ActionResult("compose", "dry_run", detail=f"app {name}")

        if not re.match(r"^[a-z0-9][a-z0-9-]{0,62}$", name):
            return ActionResult("compose", "error", error=f"invalid app name: {name!r}")

        # Check directory exists
        try:
            _ssh(f"test -d /opt/{name}", timeout=10)
        except RuntimeError:
            return ActionResult("compose", "not_found", detail=f"app {name}")

        # Stop containers. Remove app-local named volumes only when
        # drop_data=True — mirrors the postgres/redis/meilisearch contract
        # so a plain destroy never silently deletes app state.
        down_flags = " -v" if drop_data else ""
        _ssh(f"cd /opt/{name} && sudo docker compose down{down_flags}", timeout=60)
        # Remove app directory
        _ssh(f"sudo rm -rf /opt/{name}", timeout=30)
        # Prune dangling images
        _ssh("sudo docker image prune -f", timeout=30)

        return ActionResult("compose", "removed", detail=f"app {name}")
    except Exception as e:  # noqa: BLE001
        return ActionResult("compose", "error", error=repr(e))


def _destroy_watchdog_governance(name: str, dry_run: bool) -> ActionResult:
    """Remove the per-project watchdog governance dir on the VPS.

    ``/var/lib/watchdog-governance/<name>`` (created by
    ``watchdog.WatchdogDriver._push_governance``) lives OUTSIDE ``/opt/<name>``
    by design — so ``_destroy_app`` / ``_destroy_files`` never reach it. Without
    this, a decommissioned project's world-readable CLAUDE.md/AGENTS.md/
    .windsurf/rules linger forever with no trace under /opt. Unconditional +
    idempotent (``rm -rf`` of a missing dir is a no-op): cleanup must not depend
    on the current spec still declaring a watchdog, since the project may have
    HAD one earlier.
    """
    # Guard before the destructive ssh — name flows into `rm -rf`.
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name or ""):
        return ActionResult("watchdog-governance", "error", error=f"unsafe project id: {name!r}")
    path = f"/var/lib/watchdog-governance/{name}"
    if dry_run:
        return ActionResult("watchdog-governance", "dry_run", detail=path)
    try:
        from fabrik.drivers.ssh import ssh as _ssh

        _ssh(f"sudo rm -rf {path}", timeout=15)
        return ActionResult("watchdog-governance", "removed", detail=path)
    except Exception as e:  # noqa: BLE001
        return ActionResult("watchdog-governance", "error", detail=path, error=repr(e))


def _destroy_app(name: str, dry_run: bool, drop_data: bool = False) -> ActionResult:
    """Destroy an app via its /opt/<name> compose project.

    Post-Coolify-migration apps all live at /opt/<name>; the former
    Coolify-API fallback has been removed (the stack no longer runs a
    Coolify API, so the fallback could only ever fail or hit a stale
    endpoint, masking the real _destroy_compose error). Errors now
    surface directly.
    """
    return _destroy_compose(name, dry_run, drop_data=drop_data)


def _destroy_dns(domain: str, dry_run: bool) -> ActionResult:
    split = _split_domain(domain)
    if split is None:
        return ActionResult(
            "dns",
            "skipped",
            detail=f"domain {domain!r} not splittable (need subdomain.base.tld)",
        )
    subdomain, base_domain = split
    try:
        from fabrik.drivers.dns import DNSClient

        if dry_run:
            return ActionResult("dns", "dry_run", detail=f"{subdomain}.{base_domain} A")
        client = DNSClient()
        # Driver is idempotent: a 404 from site-provisioner is normalized
        # to a successful no-op result payload.
        client.delete_record(base_domain, "A", subdomain)
        return ActionResult("dns", "removed", detail=f"{subdomain}.{base_domain} A")
    except Exception as e:  # noqa: BLE001
        # site-provisioner unavailable (offline dev, API key missing) is
        # common in smoke tests — surface as a warning, not a hard error,
        # since DNS records are cheap to clean up manually via Cloudflare.
        msg = str(e)
        if "404" in msg or "not found" in msg.lower():
            return ActionResult("dns", "not_found", detail=f"{subdomain}.{base_domain}")
        return ActionResult("dns", "error", error=repr(e))


def _destroy_files(name: str, base: Path, dry_run: bool) -> ActionResult:
    # Fabrik scaffolds projects directly under ``/opt/<name>``; the pre-existing
    # ``fabrik destroy`` instead removed ``apps/<name>`` (relative to cwd),
    # which never matched the real layout. ``base`` parameterizes this so
    # tests can redirect to tmp_path without touching /opt.
    target = (base / name).resolve()
    try:
        base_resolved = base.resolve()
    except FileNotFoundError:
        base_resolved = base
    # Refuse to remove anything outside the base dir (defence-in-depth
    # against a malicious ``spec.id`` containing ``../``).
    if not str(target).startswith(str(base_resolved)):
        return ActionResult(
            "files",
            "error",
            error=f"refusing to remove path outside base: {target}",
        )
    if not target.exists():
        return ActionResult("files", "not_found", detail=str(target))
    if dry_run:
        return ActionResult("files", "dry_run", detail=str(target))
    try:
        shutil.rmtree(target)
        return ActionResult("files", "removed", detail=str(target))
    except Exception as e:  # noqa: BLE001
        return ActionResult("files", "error", error=repr(e))


# --------------------------------------------------------------------------- #
# Partial-destroy dispatch (T2-02 G-F5) — module-level for T4-02 import        #
# --------------------------------------------------------------------------- #
#
# WARNING — keep this comment when editing:
#
# `_destroy_<reg>` functions in this module have HETEROGENEOUS signatures.
# Some take (name, drop_data, dry_run); others take (name, dry_run); authelia
# takes (domain, dry_run). A uniform `handler(spec.id, dry_run)` dispatch
# loop would crash at call time with a "missing positional argument"
# TypeError. `HANDLER_ARGS` is the indirection: each lambda receives
# ``(spec, drop_data, dry_run)`` and returns the exact arg tuple that the
# corresponding `_destroy_<reg>` function expects.
#
# `HANDLER_ARGS` and `HANDLER_FUNCS` MUST stay at module level: T4-02's
# `destroy_from_state` (state-aware destroy) imports them as
# ``from fabrik.orchestrator.destroyer import HANDLER_ARGS, HANDLER_FUNCS``.
# Moving them inside a function would break that import contract.
#
# `grafana` is intentionally excluded from both maps. Grafana annotations
# are point-in-time decorative markers, not destroyable lifecycle state —
# see destroyer.py's grafana skip-with-bookkeeping comment.
#
# Audit awareness covers all 9 registrars (audit_grafana returns n/a);
# destroy handlers cover 8.

HANDLER_FUNCS: dict[str, Callable[..., ActionResult]] = {
    "postgres": _destroy_postgres,
    "redis": _destroy_redis,
    "gatus": _destroy_gatus,
    "backrest": _destroy_backrest,
    "glitchtip": _destroy_glitchtip,
    "authelia": _destroy_authelia,
    "meilisearch": _destroy_meilisearch,
    "prometheus": _destroy_prometheus,
}

HANDLER_ARGS: dict[str, Callable[[Spec, bool, bool], tuple]] = {
    "postgres": lambda spec, drop_data, dry_run: (spec.id, drop_data, dry_run),
    "redis": lambda spec, drop_data, dry_run: (spec.id, drop_data, dry_run),
    "gatus": lambda spec, drop_data, dry_run: (spec.id, dry_run),
    "backrest": lambda spec, drop_data, dry_run: (spec.id, dry_run),
    "glitchtip": lambda spec, drop_data, dry_run: (spec.id, dry_run),
    "authelia": lambda spec, drop_data, dry_run: (spec.domain, dry_run),
    "meilisearch": lambda spec, drop_data, dry_run: (spec.id, drop_data, dry_run),
    "prometheus": lambda spec, drop_data, dry_run: (spec.id, dry_run),
}


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def destroy_deployment(
    spec: Spec,
    *,
    drop_data: bool = False,
    keep_dns: bool = False,
    keep_files: bool = False,
    project_base: Path = Path("/opt"),
    dry_run: bool = False,
) -> DestroyReport:
    """Tear down every resource created by ``fabrik apply`` for ``spec``.

    Args:
        spec: Loaded project spec. ``spec.id`` is the compose app name;
            ``spec.domain`` (if set) is used for DNS + Authelia +
            Gatus cleanup.
        drop_data: When ``True``, physically drop the Postgres database
            and delete the MeiliSearch index. Default ``False`` matches
            auto-rollback's fail-closed data-preservation policy.
        keep_dns: Skip the DNS record deletion.
        keep_files: Skip removal of ``/opt/<spec.id>`` project tree.
        project_base: Parent directory of scaffolded projects. Tests
            pass ``tmp_path`` here; production leaves the default
            ``/opt``.
        dry_run: Log everything but mutate nothing.

    Returns:
        :class:`DestroyReport` with a per-step breakdown. The caller
        decides how to render / exit-code this.
    """
    name = spec.id
    domain = spec.domain
    spec_dict = _spec_to_dict(spec)
    resolved = resolve_applicability(spec_dict)
    # ``resolved[k]`` is ``(should_run: bool, reason: str)`` — True means
    # the apply pass would have created the resource, so destroy must
    # try to reverse it.
    applicable = {k: v[0] for k, v in resolved.items()}

    report = DestroyReport()

    # ── Step A: Registrar teardown (reverse of infrastructure.py order) ──
    # Why this order: unwind UI/edge concerns before data concerns so a
    # failure deep in the chain (e.g., Postgres) still leaves the service
    # unreachable to users (Authelia + DNS already gone).

    # Prometheus scrape target — first (mirror of provisioner: prom is
    # last to come up, so first to come down). Best-effort; a lingering
    # job only produces ``up{}=0`` until the next manual cleanup.
    if applicable.get("prometheus"):
        report.actions.append(_destroy_prometheus(name, dry_run))
    else:
        report.add("prometheus", "skipped", detail="not applicable per shape")

    if applicable.get("meilisearch"):
        report.actions.append(_destroy_meilisearch(name, drop_data, dry_run))

    if applicable.get("authelia") and domain:
        report.actions.append(_destroy_authelia(domain, dry_run))
    else:
        report.add("authelia", "skipped", detail="not applicable per shape")

    if applicable.get("glitchtip"):
        report.actions.append(_destroy_glitchtip(name, dry_run))
    else:
        report.add("glitchtip", "skipped", detail="not applicable per shape")

    # Grafana annotations are informational and auto-expire; see module
    # docstring. We emit a bookkeeping ``skipped`` entry so the CLI
    # output still lists every registrar for completeness.
    report.add("grafana", "skipped", detail="annotations are informational")

    if applicable.get("backrest"):
        report.actions.append(_destroy_backrest(name, dry_run))
    else:
        report.add("backrest", "skipped", detail="not applicable per shape")

    if applicable.get("gatus") and domain:
        report.actions.append(_destroy_gatus(name, dry_run))
    else:
        report.add("gatus", "skipped", detail="not applicable per shape")

    if applicable.get("postgres"):
        report.actions.append(_destroy_postgres(name, drop_data, dry_run))
    else:
        report.add("postgres", "skipped", detail="not applicable per shape")

    # Redis logical-DB index — released after Postgres so the symmetric
    # data-handling rule is consistent: both data-bearing registrars
    # respect ``--drop-data``. The slot itself is always released.
    if applicable.get("redis"):
        report.actions.append(_destroy_redis(name, drop_data, dry_run))
    else:
        report.add("redis", "skipped", detail="not applicable per shape")

    # ── Step B: App (compose project at /opt/<name>) ──
    report.actions.append(_destroy_app(name, dry_run, drop_data=drop_data))

    # ── Step B2: Watchdog governance dir (lives OUTSIDE /opt/<name>) ──
    report.actions.append(_destroy_watchdog_governance(name, dry_run))

    # ── Step C: DNS record ──
    if keep_dns:
        report.add("dns", "skipped", detail="--keep-dns")
    elif domain:
        report.actions.append(_destroy_dns(domain, dry_run))
    else:
        report.add("dns", "skipped", detail="no domain in spec")

    # ── Step D: Local project files ──
    if keep_files:
        report.add("files", "skipped", detail="--keep-files")
    else:
        report.actions.append(_destroy_files(name, project_base, dry_run))

    # Summary log for operator eyes — single line per step matching the
    # provisioner's log format for grep-friendly diff against apply logs.
    for action in report.actions:
        if action.status == "error":
            logger.warning("destroy %s: ERROR %s", action.step, action.error)
        else:
            logger.info(
                "destroy %s: %s%s",
                action.step,
                action.status,
                f" ({action.detail})" if action.detail else "",
            )

    # Archive the state file. Best-effort; failure here is logged but
    # never aborts destroy. (T2-01 / G-F3.)
    if not dry_run:
        try:
            import fabrik.state as state_module

            archived = state_module.archive_destroyed(spec.id)
            if archived is not None:
                logger.info("destroy: state archived → %s", archived)
        except Exception as e:  # noqa: BLE001
            logger.warning("destroy: state archive failed (non-fatal): %s", e)

    return report


# --------------------------------------------------------------------------- #
# State-driven destroy (T4-02 G-F4)
# --------------------------------------------------------------------------- #


def destroy_from_state(
    state_data: dict[str, Any],
    spec: Spec,
    *,
    drop_data: bool = False,
    keep_dns: bool = False,
    keep_files: bool = False,
    project_base: Path = Path("/opt"),
    dry_run: bool = False,
) -> DestroyReport:
    """Reverse the registrars recorded in ``state_data["registrars_applied"]``.

    Why this exists (T4-02 G-F4 / Epic SC-3): the default destroy walks the
    spec's CURRENT shape, but a spec can drift between apply-time and
    destroy-time (e.g. ``has_search_feature`` flipped ``true → false`` after
    a meilisearch index was created). The state file captures what was
    actually applied; ``--use-state`` replays from that ground truth so the
    teardown reverses *what got deployed*, not *what the spec says now*.

    Three phases:

    **Phase 0 — Data-bearing guard.** Scan ``state_data["registrars_applied"]``
    for any entry whose ``data_bearing`` flag is ``True`` (postgres, redis,
    meilisearch per :data:`fabrik.state.DATA_BEARING_REGISTRARS`). If any
    are present AND ``drop_data`` is ``False``, return an empty-actions
    report with a single ``error`` action listing the protected entries.
    The CLI surfaces this as a clean refusal — operator must re-run with
    ``--drop-data`` to confirm.

    **Phase 1 — Registrar teardown in canonical reverse order.** Uses
    ``list(reversed(_REGISTRAR_ORDER))`` from
    :mod:`fabrik.orchestrator.infrastructure` — ``prometheus → meilisearch →
    authelia → grafana → glitchtip → backrest → gatus → redis → postgres``.
    Skips ``grafana`` (annotations are decorative; no destroyer exists).
    Dispatches per-registrar via :data:`HANDLER_FUNCS` and :data:`HANDLER_ARGS`
    (module-level since T2-02 amendment). Only registrars actually present
    in ``state_data["registrars_applied"]`` are invoked — drift from the
    current shape is irrelevant here.

    **Phase 2 — Non-registrar resources.** Coolify app (always),
    DNS (gated by ``keep_dns`` + domain present), local files (gated by
    ``keep_files``). The state file's ``registrars_applied`` does NOT
    contain deploy-tier resources by design (see ``state.save`` docstring) —
    they're invariant of the registrar set and always run last.

    Args:
        state_data: Parsed JSON payload from ``state.load(spec_id)``. Must
            contain ``registrars_applied: list[dict]``.
        spec: Loaded spec — needed for ``HANDLER_ARGS`` lambdas which
            reference ``spec.id`` and ``spec.domain``.
        drop_data: When ``True``, allow destruction of data-bearing
            registrars. Default ``False`` mirrors ``destroy_deployment``.
        keep_dns: Skip DNS record deletion.
        keep_files: Skip ``/opt/<spec.id>`` removal.
        project_base: Parent directory of scaffolded projects (test hook).
        dry_run: Log everything but mutate nothing.

    Returns:
        :class:`DestroyReport` populated step-by-step. ``had_errors`` is
        True iff Phase 0 refused OR any registrar/non-registrar step
        errored. Caller (CLI) chooses how to surface and exit.
    """
    from fabrik.orchestrator.infrastructure import _REGISTRAR_ORDER

    report = DestroyReport()
    registrars_applied = state_data.get("registrars_applied") or []
    applied_types = {entry.get("type") for entry in registrars_applied if entry.get("type")}

    # ── Phase 0: Data-bearing guard ───────────────────────────────────────
    data_bearing_entries = [
        entry for entry in registrars_applied if entry.get("data_bearing") is True
    ]
    if data_bearing_entries and not drop_data:
        names = ", ".join(sorted({entry.get("type", "?") for entry in data_bearing_entries}))
        report.add(
            "data-bearing-guard",
            "error",
            detail=(
                f"refused — state has data-bearing registrars ({names}); "
                f"re-run with --drop-data to confirm destruction"
            ),
            error=f"data_bearing entries present: {names}",
        )
        return report

    # ── Phase 1: Registrars in reversed canonical order ───────────────────
    # CRITICAL invariant — wrong order = FK violations / orphaned auth rows.
    # Skip grafana (no destroyer registered; annotations decorative).
    # Skip any registrar not actually in the state file (apply may have
    # skipped some per shape contract — don't try to destroy what wasn't
    # created).
    for reg in reversed(_REGISTRAR_ORDER):
        if reg == "grafana":
            if reg in applied_types:
                report.add(
                    "grafana",
                    "skipped",
                    detail="annotations are decorative; no destroyer",
                )
            continue
        if reg not in applied_types:
            continue
        try:
            args = HANDLER_ARGS[reg](spec, drop_data, dry_run)
            result = HANDLER_FUNCS[reg](*args)
            report.actions.append(result)
        except Exception as e:  # noqa: BLE001 — bounded; one bad handler doesn't abort teardown
            report.add(reg, "error", detail=f"handler raised: {e}", error=repr(e))

    # ── Phase 2: Non-registrar resources (app, DNS, files) ────────────
    # These are invariant of the registrar set; always run regardless of
    # state file contents. Symmetric with destroy_deployment Steps B/C/D.
    report.actions.append(_destroy_app(spec.id, dry_run, drop_data=drop_data))
    # D4: watchdog governance dir cleanup must NOT depend on the spec still declaring a watchdog —
    # symmetric with destroy_deployment:598. `--use-state` is the path you reach for when the spec is
    # already gone, so without this /var/lib/watchdog-governance/<id> leaks (accumulating stale dirs
    # on the VPS). Already idempotent (see _destroy_watchdog_governance docstring).
    report.actions.append(_destroy_watchdog_governance(spec.id, dry_run))

    if keep_dns:
        report.add("dns", "skipped", detail="--keep-dns")
    elif spec.domain:
        report.actions.append(_destroy_dns(spec.domain, dry_run))
    else:
        report.add("dns", "skipped", detail="no domain in spec")

    if keep_files:
        report.add("files", "skipped", detail="--keep-files")
    else:
        report.actions.append(_destroy_files(spec.id, project_base, dry_run))

    # Operator log line per step (grep-friendly diff against apply logs).
    for action in report.actions:
        if action.status == "error":
            logger.warning("destroy --use-state %s: ERROR %s", action.step, action.error)
        else:
            logger.info(
                "destroy --use-state %s: %s%s",
                action.step,
                action.status,
                f" ({action.detail})" if action.detail else "",
            )

    # Archive on success (any non-error completion). Best-effort; failure
    # logged non-fatal. Caller may also call archive_destroyed explicitly,
    # but we do it here for symmetry with destroy_deployment.
    if not dry_run and not report.had_errors:
        try:
            import fabrik.state as state_module

            archived = state_module.archive_destroyed(spec.id)
            if archived is not None:
                logger.info("destroy --use-state: state archived → %s", archived)
        except Exception as e:  # noqa: BLE001
            logger.warning("destroy --use-state: state archive failed (non-fatal): %s", e)

    return report


__all__ = (
    "ActionResult",
    "DestroyReport",
    "HANDLER_ARGS",
    "HANDLER_FUNCS",
    "destroy_deployment",
    "destroy_from_state",
)
