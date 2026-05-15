"""Authelia access-control rule provisioning for the Coolify-managed container.

Context (verified live 2026-04-19):

* Authelia runs as a Coolify-managed service; the container name changes
  on every recreate — we resolve it via label ``coolify.serviceName=authelia``
  (same pattern as :mod:`fabrik.drivers.meilisearch` and
  :mod:`fabrik.drivers.gatus`).
* Config lives inside a Coolify-managed named volume, mounted at
  ``/config/configuration.yml`` inside the container. There is **no host
  path** at ``/opt/authelia/config/configuration.yml`` — earlier driver
  drafts that ``scp``'d to that path were wrong (LESSONS_LEARNT §8.12).
* Access-control rules do NOT hot-reload; changing
  ``access_control.rules`` requires a container restart (~15 s).

Design notes
------------

* **One bash script, one flock.** The entire read → parse-merge-validate
  → write → restart cycle runs as a single bash script via
  :func:`fabrik.drivers.locks.run_locked` on resource
  ``"authelia-config"``. Chaining multiple Python-side ``ssh()`` calls
  cannot hold a remote lock — see :mod:`fabrik.drivers.locks` module
  docstring for the proof.

* **Variables cross the wire via env + base64, never shell interpolation.**
  The new rule is serialized to YAML then base64-encoded; the encoded
  blob travels to the VPS as an environment variable
  (``RULE_B64={b64}``) that the Python heredoc reads via
  :func:`os.environ`. This immunizes the driver against every shell-
  escape hazard (single quotes, ``$``, backticks, newlines, unicode).
  Canonicalized in LESSONS_LEARNT §8.15 for all SSH→bash→python chains.

* **Quoted heredoc for Python.** The Python body uses ``<<'PY'`` (single-
  quoted delimiter). Bash does NOT expand ``$var`` before writing the
  script to python's stdin. The Python side reads config from env. Any
  variant using ``<<PY`` (unquoted) is a latent bug — bash would
  pre-expand ``$RULE_B64`` into the script body.

* **Idempotent per rule tuple.** Equality is
  ``(domain, policy, resources)``. A second identical call is a no-op
  that skips even the ``docker cp`` and ``docker restart`` — important
  because a restart interrupts every active Authelia session.

* **Rollback removes ALL rules for a domain.** When an orchestrator
  rolls back an admin-dashboard deploy that had both a ``two_factor``
  root rule AND an ``^/api/`` bypass, leaving either one behind would
  gate the wrong half of the traffic. :func:`remove_access_rule` filters
  ``rules`` by ``domain == target_domain``, removing every entry.

Environment
-----------

No Fabrik-side env vars. Authelia-side credentials and secrets already
live inside the container's Coolify-managed env. The driver only mutates
the YAML policy file.
"""

from __future__ import annotations

import base64
import logging
import re
import shlex
from typing import Any

import yaml as yaml_lib

from fabrik.drivers.locks import run_locked
from fabrik.drivers.ssh import ssh

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Constants / validators                                                       #
# --------------------------------------------------------------------------- #

VALID_POLICIES = frozenset({"deny", "bypass", "one_factor", "two_factor"})
"""The complete set of policy keywords Authelia accepts in
``access_control.rules[].policy``. Any other value is rejected before
the SSH call is even made — we will not let a typo silently re-lock
admin dashboards with an unrecognized policy."""

_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[a-zA-Z0-9-]{1,63}(?<!-)"
    r"(\.(?!-)[a-zA-Z0-9-]{1,63}(?<!-))*$"
)
"""FQDN validator — same shape as :mod:`fabrik.drivers.gatus._DOMAIN_RE`
for cross-driver consistency. Total length ≤ 253, each label 1–63 chars,
no leading or trailing hyphens, no underscores."""

_RESOURCE_RE = re.compile(r"^[\x20-\x7e]+$")
"""Resource regexes are printable-ASCII only. Authelia's Go regex engine
is permissive but we want to reject anything that could inject a newline
or NUL into the YAML at serialization time. Real-world resources
(``^/api/``, ``^/public/``, etc.) comfortably satisfy this."""

SHAPE_FLAG = "is_admin_dashboard"
"""Shape-gating key. Parallel to other opt-in drivers
(``has_search_feature``, ``has_error_tracking``)."""

_LOCK_RESOURCE = "authelia-config"
"""``/tmp/fabrik-authelia-config.lock`` on the VPS. Distinct from other
drivers' locks so e.g. a concurrent backrest mutation does not serialize
against an authelia one."""

_LOCK_TIMEOUT = 180
"""Seconds. Authelia restart observed ~15 s; config read + python merge
~1 s; allow ample headroom for VPS under load or the occasional slow
docker cp."""


# --------------------------------------------------------------------------- #
# Rule-precedence helper (T2-08 Part C / Lesson 56)                            #
# --------------------------------------------------------------------------- #


def _domain_shadows(rule_domain: Any, new_domain: str) -> bool:
    # True if ``rule_domain`` (string or list) matches ``new_domain`` either
    # exactly or via a ``*.X`` wildcard whose suffix new_domain ends with and
    # whose remainder has no extra dots. The wildcard form is what every
    # admin-UI gate in Fabrik uses (``*.vps1.ocoron.com``).
    if isinstance(rule_domain, str):
        candidates = [rule_domain]
    elif isinstance(rule_domain, list):
        candidates = [d for d in rule_domain if isinstance(d, str)]
    else:
        return False
    for rd in candidates:
        if rd == new_domain:
            return True
        if rd.startswith("*."):
            suffix = rd[1:]
            if new_domain.endswith(suffix):
                remainder = new_domain[: -len(suffix)]
                if remainder and "." not in remainder:
                    return True
    return False


def _compute_insert_index(
    rules: list[dict[str, Any]], new_rule: dict[str, Any], mode: str
) -> int | None:
    # Return the index BEFORE which new_rule must go for first-match-wins
    # correctness, or None to append. Mirrors the inline logic embedded in
    # ``_build_add_script``'s Python heredoc — keep them in sync.
    if mode != "before_twofactor":
        return None
    new_domain = new_rule.get("domain")
    if not isinstance(new_domain, str):
        return None
    for i, r in enumerate(rules):
        if r.get("policy") != "two_factor":
            continue
        if _domain_shadows(r.get("domain"), new_domain):
            return i
    return None


# --------------------------------------------------------------------------- #
# Validators                                                                   #
# --------------------------------------------------------------------------- #


def _validate_domain(domain: str) -> None:
    if not isinstance(domain, str) or not _DOMAIN_RE.match(domain):
        raise ValueError(
            f"Invalid Authelia domain {domain!r}: must be a bare FQDN "
            f"(e.g. 'coolify.vps1.ocoron.com')"
        )


def _validate_policy(policy: str) -> None:
    if policy not in VALID_POLICIES:
        raise ValueError(
            f"Invalid Authelia policy {policy!r}: must be one of {sorted(VALID_POLICIES)}"
        )


def _validate_resources(resources: list[str] | None) -> None:
    if resources is None:
        return
    if not isinstance(resources, list):
        raise ValueError("resources must be a list of regex strings or None")
    for r in resources:
        if not isinstance(r, str) or not r:
            raise ValueError(f"Invalid resource {r!r}: must be non-empty string")
        if not _RESOURCE_RE.match(r):
            raise ValueError(
                f"Invalid resource {r!r}: must be printable ASCII "
                f"(reject newlines, control chars, non-ASCII)"
            )


# --------------------------------------------------------------------------- #
# Shape gating                                                                 #
# --------------------------------------------------------------------------- #


def applies_to(shape: dict[str, Any] | None) -> bool:
    """Return True iff this project is an admin dashboard that needs forward-auth.

    Authelia is opt-in by shape — Fabrik will NOT gate a normal public
    service with forward-auth. The caller must additionally supply a
    ``domain`` (FQDN) when provisioning; we cannot gate a dashboard
    without knowing its hostname.

    Args:
        shape: Project shape dict. Must contain
            ``is_admin_dashboard=True`` for this driver to apply.

    Returns:
        True iff ``shape[SHAPE_FLAG]`` is truthy.
    """
    if not isinstance(shape, dict):
        return False
    return bool(shape.get(SHAPE_FLAG))


# --------------------------------------------------------------------------- #
# Container resolution                                                         #
# --------------------------------------------------------------------------- #


def _resolve_container() -> str:
    """Resolve the Authelia container name via its Coolify service label.

    Coolify suffixes the container with a UUID that changes on every
    recreate — looking up by label is UUID-agnostic.
    """
    name = ssh(
        "sudo docker ps --filter label=coolify.serviceName=authelia --format '{{.Names}}' | head -1"
    ).strip()
    if not name:
        raise RuntimeError(
            "Authelia container not found "
            "(label=coolify.serviceName=authelia). "
            "Is the Coolify-managed Authelia service running?"
        )
    return name


# --------------------------------------------------------------------------- #
# Remote script builder                                                        #
# --------------------------------------------------------------------------- #


def _build_add_script(container: str, rule_b64: str, domain: str, insert_mode: str) -> str:
    """Build the bash+python script that mutates Authelia's config.

    Isolated from :func:`add_access_rule` so unit tests can assert on
    the script's structure without having to invoke ``run_locked``.

    The script:

    1. ``docker exec cat`` the current config out to host ``/tmp``.
    2. Makes a timestamped backup; prunes to the last 10 backups.
    3. Runs a heredoc Python block that parses the YAML, checks for
       the exact (domain, policy, resources) tuple, and either:

       * prints ``IDEMPOTENT_NOOP`` (config already has the rule) —
         skip steps 5-6, skip restart.
       * writes a new YAML file with the rule inserted and validates
         it round-trips through ``yaml.safe_load``.

    4. If Python signaled idempotence by not creating the new file,
       exit ``ok-noop``.
    5. ``docker cp`` the new config into the container.
    6. ``docker restart`` (Authelia does not hot-reload access_control).
    7. Clean up staging files; backups stay for the 10-file rotation.

    The "did it produce a new file?" flag is the *presence* of
    ``/tmp/authelia.new.$TS.yml`` — an out-of-band signal that
    survives Python exiting 0 in both paths. We deliberately do NOT
    ``exit 1`` from Python on idempotence because that would trip
    ``set -euo pipefail``.
    """
    # shlex.quote covers every shell metacharacter we might see;
    # base64 payload is [A-Za-z0-9+/=] so it's inherently safe but
    # we still pass it via env var to avoid it ending up on the wire
    # in command-line form.
    return f"""set -euo pipefail
TS=$(date +%Y%m%d-%H%M%S)
CONT={shlex.quote(container)}
export RULE_B64={shlex.quote(rule_b64)}
export DOMAIN={shlex.quote(domain)}
export INSERT_MODE={shlex.quote(insert_mode)}
export TS

# 1. Read current config out of the container to /tmp (owned by root).
sudo docker exec "$CONT" cat /config/configuration.yml \\
    | sudo tee "/tmp/authelia.cur.$TS.yml" >/dev/null

# 2. Timestamped backup; prune to last 10.
sudo cp "/tmp/authelia.cur.$TS.yml" "/tmp/authelia.bak.$TS.yml"
sudo bash -c 'ls -1t /tmp/authelia.bak.*.yml 2>/dev/null | tail -n +11 | xargs -r rm -f'

# 3. Merge via Python (PyYAML available on VPS; variables arrive via env).
#    Quoted heredoc <<'PY' — bash does NOT expand $var into the Python body.
sudo -E python3 <<'PY'
import base64, os, sys, yaml

ts = os.environ['TS']
cur_path = f"/tmp/authelia.cur.{{ts}}.yml"
new_path = f"/tmp/authelia.new.{{ts}}.yml"

rule_b64 = os.environ['RULE_B64']
domain = os.environ['DOMAIN']
insert_mode = os.environ['INSERT_MODE']
new_rule = yaml.safe_load(base64.b64decode(rule_b64).decode())[0]

with open(cur_path) as f:
    cfg = yaml.safe_load(f) or {{}}

ac = cfg.setdefault('access_control', {{}})
rules = ac.setdefault('rules', [])
if not isinstance(rules, list):
    sys.stderr.write(
        f"ERROR: access_control.rules is not a list: {{type(rules).__name__}}\\n"
    )
    sys.exit(2)


def rule_matches(a, b):
    return (a.get('domain') == b.get('domain')
            and a.get('policy') == b.get('policy')
            and a.get('resources') == b.get('resources'))


if any(rule_matches(r, new_rule) for r in rules):
    sys.stdout.write("IDEMPOTENT_NOOP\\n")
    sys.exit(0)


# Precedence-aware insertion (mirrors _compute_insert_index in the driver
# module — keep them in sync). A wildcard rule like '*.vps1.ocoron.com'
# with policy: two_factor shadows any later specific-domain bypass for
# images.vps1.ocoron.com, because Authelia is first-match-wins. T2-08
# Part C closes Lesson 56.
def _domain_shadows(rule_domain, new_domain):
    if isinstance(rule_domain, str):
        candidates = [rule_domain]
    elif isinstance(rule_domain, list):
        candidates = [d for d in rule_domain if isinstance(d, str)]
    else:
        return False
    for rd in candidates:
        if rd == new_domain:
            return True
        if rd.startswith('*.'):
            suffix = rd[1:]
            if new_domain.endswith(suffix):
                remainder = new_domain[: -len(suffix)]
                if remainder and '.' not in remainder:
                    return True
    return False


if insert_mode == 'before_twofactor':
    idx = next(
        (
            i for i, r in enumerate(rules)
            if r.get('policy') == 'two_factor' and _domain_shadows(r.get('domain'), domain)
        ),
        None,
    )
    if idx is None:
        rules.append(new_rule)
    else:
        rules.insert(idx, new_rule)
else:
    rules.append(new_rule)

with open(new_path, 'w') as f:
    yaml.safe_dump(cfg, f, default_flow_style=False, sort_keys=False)

# Round-trip validate: if the emitted YAML can't be parsed back, we
# refuse to cp it into the container.
with open(new_path) as f:
    yaml.safe_load(f)

sys.stdout.write("WROTE_NEW\\n")
PY

# 4. If Python printed IDEMPOTENT_NOOP, /tmp/authelia.new.$TS.yml doesn't
#    exist — that's our out-of-band "no changes" signal.
#    The staging files are owned by root (created via sudo tee / sudo python3);
#    cleanup MUST use sudo rm or set -e will abort the script with
#    "Operation not permitted" (LESSONS_LEARNT §8.17).
if [ ! -f "/tmp/authelia.new.$TS.yml" ]; then
    echo "idempotent-noop"
    sudo rm -f "/tmp/authelia.cur.$TS.yml"
    exit 0
fi

# 5. Copy new config into the container volume.
sudo docker cp "/tmp/authelia.new.$TS.yml" "$CONT":/config/configuration.yml

# 6. Restart Authelia — access_control does NOT hot-reload.
sudo docker restart "$CONT" >/dev/null

# 7. Cleanup staging files (backups stay for the 10-file rotation).
sudo rm -f "/tmp/authelia.cur.$TS.yml" "/tmp/authelia.new.$TS.yml"
echo "ok"
"""


def _build_remove_script(container: str, domain: str) -> str:
    """Build the rollback script — remove ALL rules for ``domain``.

    Must remove both the root ``two_factor`` rule AND any
    ``resources=['^/api/']`` bypass (CSF §10); leaving either behind
    would mis-gate half the traffic for that host.
    """
    return f"""set -euo pipefail
TS=$(date +%Y%m%d-%H%M%S)
CONT={shlex.quote(container)}
export DOMAIN={shlex.quote(domain)}
export TS

sudo docker exec "$CONT" cat /config/configuration.yml \\
    | sudo tee "/tmp/authelia.cur.$TS.yml" >/dev/null

sudo -E python3 <<'PY'
import os, sys, yaml

ts = os.environ['TS']
cur_path = f"/tmp/authelia.cur.{{ts}}.yml"
new_path = f"/tmp/authelia.new.{{ts}}.yml"
domain = os.environ['DOMAIN']

with open(cur_path) as f:
    cfg = yaml.safe_load(f) or {{}}
ac = cfg.setdefault('access_control', {{}})
rules = ac.setdefault('rules', [])
if not isinstance(rules, list):
    sys.stderr.write("ERROR: access_control.rules is not a list\\n")
    sys.exit(2)

before = len(rules)
ac['rules'] = [r for r in rules if r.get('domain') != domain]
after = len(ac['rules'])

if before == after:
    sys.stdout.write("IDEMPOTENT_NOOP\\n")
    sys.exit(0)

with open(new_path, 'w') as f:
    yaml.safe_dump(cfg, f, default_flow_style=False, sort_keys=False)

# Round-trip validate before we copy it in.
with open(new_path) as f:
    yaml.safe_load(f)

sys.stdout.write(f"REMOVED {{before - after}} rule(s)\\n")
PY

# Staging files are root-owned (created by sudo tee / sudo python3);
# cleanup MUST use sudo rm — see LESSONS_LEARNT §8.17.
if [ ! -f "/tmp/authelia.new.$TS.yml" ]; then
    echo "idempotent-noop"
    sudo rm -f "/tmp/authelia.cur.$TS.yml"
    exit 0
fi

sudo docker cp "/tmp/authelia.new.$TS.yml" "$CONT":/config/configuration.yml
sudo docker restart "$CONT" >/dev/null
sudo rm -f "/tmp/authelia.cur.$TS.yml" "/tmp/authelia.new.$TS.yml"
echo "ok"
"""


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #


def add_access_rule(
    domain: str,
    policy: str = "two_factor",
    resources: list[str] | None = None,
    insert_before_twofactor: bool = False,
    dry_run: bool = False,
) -> dict[str, str]:
    """Add a forward-auth rule for ``domain`` to Authelia ``access_control.rules``.

    Args:
        domain: Bare FQDN to gate (e.g. ``"coolify.vps1.ocoron.com"``).
            Validated against :data:`_DOMAIN_RE`.
        policy: One of :data:`VALID_POLICIES`. Defaults to
            ``"two_factor"`` (the common case for admin dashboards).
        resources: Optional list of regex strings limiting the rule to
            specific paths (e.g. ``["^/api/"]`` for a Bearer-token
            API bypass — see Critical Success Factor §10).
        insert_before_twofactor: If ``True``, and an existing
            ``two_factor`` rule for the same domain is present, insert
            this new rule **before** it. Required for ``^/api/``
            bypass on admin dashboards with Bearer-token APIs so that
            Authelia matches the bypass FIRST and lets Bearer calls
            through to the backend.
        dry_run: Skip all VPS mutation.

    Returns:
        ``{"status": "added" | "exists" | "dry_run", "domain": domain}``

    Raises:
        ValueError: ``domain``, ``policy``, or ``resources`` failed
            validation.
        RuntimeError: container not found, or the locked mutation
            script failed. The ``ssh()`` wrapper includes stderr in
            the message.
    """
    _validate_domain(domain)
    _validate_policy(policy)
    _validate_resources(resources)

    if dry_run:
        logger.info(
            "[DRY RUN] Would add Authelia rule: domain=%s policy=%s resources=%s",
            domain,
            policy,
            resources,
        )
        return {"status": "dry_run", "domain": domain}

    container = _resolve_container()

    # Construct the rule in Python, serialize to YAML, base64 for transit.
    # yaml.safe_dump round-trips back through safe_load on the far side.
    new_rule: dict[str, Any] = {"domain": domain, "policy": policy}
    if resources:
        new_rule["resources"] = list(resources)

    rule_yaml = yaml_lib.safe_dump([new_rule])
    rule_b64 = base64.b64encode(rule_yaml.encode()).decode()

    insert_mode = "before_twofactor" if insert_before_twofactor else "append"
    script = _build_add_script(container, rule_b64, domain, insert_mode)

    result = run_locked(_LOCK_RESOURCE, script, timeout=_LOCK_TIMEOUT)
    if "idempotent-noop" in result:
        logger.info("Authelia rule already present (noop): domain=%s policy=%s", domain, policy)
        return {"status": "exists", "domain": domain}

    logger.info(
        "Authelia rule added: domain=%s policy=%s resources=%s",
        domain,
        policy,
        resources,
    )
    return {"status": "added", "domain": domain}


def remove_access_rule(domain: str, dry_run: bool = False) -> bool:
    """Rollback handler — remove ALL rules for ``domain`` and restart.

    Must remove both the root ``two_factor`` rule AND any associated
    ``^/api/`` bypass (CSF §10); leaving either behind would mis-gate
    the host.

    Args:
        domain: Bare FQDN (validated).
        dry_run: No-op, returns True.

    Returns:
        True on success (including the "no rules to remove" idempotent
        case) or on dry-run. False on any error — never raises.
    """
    _validate_domain(domain)

    if dry_run:
        logger.info("[DRY RUN] Would remove all Authelia rules for %s", domain)
        return True

    try:
        container = _resolve_container()
        script = _build_remove_script(container, domain)
        run_locked(_LOCK_RESOURCE, script, timeout=_LOCK_TIMEOUT)
        logger.info("Authelia rules removed for %s", domain)
        return True
    except Exception as e:  # noqa: BLE001 — rollback must not raise
        logger.warning("Authelia remove_access_rule(%s) failed (non-fatal): %s", domain, e)
        return False


__all__ = (
    "VALID_POLICIES",
    "SHAPE_FLAG",
    "applies_to",
    "add_access_rule",
    "remove_access_rule",
)
