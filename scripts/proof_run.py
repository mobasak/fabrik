#!/usr/bin/env python3
# AFTER-EDIT: none
"""End-to-end deploy harness: prove every scaffold type deploys live on VPS.

Per-type loop for each T in SCAFFOLD_TYPES:
  1. CLEANUP   — fabrik destroy (idempotent), gh repo delete, rm -rf /opt/<name>
  2. NXDOMAIN  — confirm https://<name>.vps1.ocoron.com is dead before starting
  3. SCAFFOLD  — fabrik scaffold <name> --type <T> --no-spec
  4. PUSH      — gh repo create mobasak/<name> --private --source=. --push
  5. REGENSPEC — call generate_and_save_spec() now that git remote exists
                 (spec will have source.type=git pointing at the GH remote)
  6. APPLY     — fabrik apply <spec> --yes --use-orchestrator
  7. CURL      — curl -I https://<name>.vps1.ocoron.com<healthcheck.path>
                 must return 200 (or 301/302 for static docs landing pages)
  8. RECORD    — append to proof data; on failure, dump diagnostics and stop

On success of all 8 types → write /opt/fabrik/PROOF.md.
On any failure → stop the loop, dump diagnostics, exit non-zero.

Runs unattended. All output streamed to both stdout and
/opt/fabrik/proof-logs/<type>-<ts>.log.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# --- config -----------------------------------------------------------------

FABRIK_ROOT = Path("/opt/fabrik")
PROJECT_BASE = Path("/opt")
LOG_DIR = FABRIK_ROOT / "proof-logs"
PROOF_FILE = FABRIK_ROOT / "PROOF.md"
SPECS_DIR = FABRIK_ROOT / "specs" / "services"
VENV_PY = FABRIK_ROOT / ".venv" / "bin" / "python"
VENV_FABRIK = FABRIK_ROOT / ".venv" / "bin" / "fabrik"
GH_USER = "mobasak"

# Execution order from the mission brief.
#
# G9 (2026-05-05): ``chrome-extension`` was added back. The CRX itself
# ships via the Chrome Web Store, but the scaffolder ALSO emits a real
# FastAPI backend at ``server/`` plus canonical ``compose.yaml`` with
# Traefik labels and CORS middleware (see
# ``scaffold.py::_scaffold_chrome_extension`` B16/B18 fixes). The spec
# drives the backend, not the CRX. ``SPEC_ENABLED_TYPES`` includes it.
SCAFFOLD_TYPES = [
    "saas-skeleton",
    "node-api",
    "python-api",
    "file-api",
    "file-worker",
    "docusaurus",
    "static-site",
    "chrome-extension",
]

# `file-worker` has no Traefik / no HTTP surface. We can't curl it. Proof for
# workers is `Coolify app status == running:healthy` after apply, which is
# already validated inside `fabrik apply`'s verifier. Skip the curl phase.
NO_HTTP_TYPES = {"file-worker"}

# Pre-populated accept codes per type. 200 is the contract for healthy. We do
# NOT silently accept other codes — if a type returns 301/302/etc., that's a
# real signal worth investigating, not papering over.
#
# `docusaurus` healthcheck.path defaults to `/` per spec_generator._TYPE_DEFAULTS.
# `/` on a Docusaurus build serves the landing page with 200, so 200 is correct.
ACCEPT_CODES: dict[str, set[int]] = {
    "python-api": {200},
    "node-api": {200},
    "saas-skeleton": {200},
    "file-api": {200},
    "docusaurus": {200},
    "static-site": {200},
    # chrome-extension: backend FastAPI exposes /health → 200
    "chrome-extension": {200},
    # file-worker: handled by NO_HTTP_TYPES, never curled
}
DEFAULT_ACCEPT = {200}


# --- subprocess helpers -----------------------------------------------------


class CmdError(RuntimeError):
    def __init__(self, cmd: list[str], returncode: int, stdout: str, stderr: str):
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(f"cmd failed rc={returncode}: {' '.join(cmd)}")


def run(
    cmd: list[str],
    *,
    cwd: Path | str | None = None,
    check: bool = True,
    env_extra: dict[str, str] | None = None,
    timeout: int | None = None,
    logfile=None,
) -> subprocess.CompletedProcess:
    """Run a command, streaming output line-by-line to stdout AND logfile.

    H1: switched from ``subprocess.run(capture_output=True)`` to
    ``subprocess.Popen`` + line-by-line read because ``capture_output=True``
    buffers ALL of the subprocess's stdout/stderr in memory until the
    subprocess returns — for a long-running ``fabrik apply`` that means 5-15
    minutes of complete silence followed by one giant blob (or, worse, a
    truncated/lost blob if the harness's tee pipe closes before flush).

    The new implementation:
      - merges stderr into stdout (``stderr=STDOUT``) to preserve interleaving
      - reads one line at a time off the pipe
      - writes each line immediately to both ``sys.stdout`` AND ``logfile``,
        flushing both after every line
      - enforces ``timeout`` via wall-clock against the read loop
      - retains the ``CmdError`` raise contract for ``check=True`` callers

    The captured-output convenience attributes on the returned
    ``CompletedProcess`` (``.stdout``, ``.stderr``) are still populated so
    callers that grep them keep working; ``.stderr`` is empty by design
    because we merged it into ``.stdout``.
    """
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    header = f"\n$ {' '.join(cmd)}"
    if cwd:
        header = f"\n[cwd={cwd}]{header}"
    print(header, flush=True)
    if logfile:
        logfile.write(header + "\n")
        logfile.flush()

    captured: list[str] = []
    deadline = time.monotonic() + timeout if timeout else None
    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # line-buffered
        env=env,
    )
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            captured.append(line)
            sys.stdout.write(line)
            sys.stdout.flush()
            if logfile:
                logfile.write(line)
                logfile.flush()
            if deadline is not None and time.monotonic() > deadline:
                proc.kill()
                proc.wait(timeout=5)
                msg = f"\n⏱ timeout after {timeout}s: {' '.join(cmd)}\n"
                print(msg, flush=True)
                if logfile:
                    logfile.write(msg)
                    logfile.flush()
                raise CmdError(cmd, -1, "".join(captured), "timeout")
        rc = proc.wait()
    finally:
        if proc.stdout:
            proc.stdout.close()

    full = "".join(captured)
    if check and rc != 0:
        raise CmdError(cmd, rc, full, "")
    # Build a CompletedProcess for backward compatibility with run() callers
    # that read .stdout. .stderr stays empty since we merged streams above.
    return subprocess.CompletedProcess(args=cmd, returncode=rc, stdout=full, stderr="")


# --- env loading ------------------------------------------------------------


def load_env() -> dict[str, str]:
    """Load /opt/fabrik/.env keys we actually need. Skip malformed lines.

    H4: also loads Cloudflare creds so the harness can delete stale DNS
    records directly when ``fabrik destroy``'s DNS step fails with
    "SSH proxy request failed" (site-provisioner outage, ambient
    infrastructure breakage unrelated to this mission).
    """
    keys_needed = {
        "VPS_IP",
        "COOLIFY_API_URL",
        "COOLIFY_API_TOKEN",
        "COOLIFY_SERVER_UUID",
        "COOLIFY_PROJECT_UUID",
        "COOLIFY_ENVIRONMENT_UUID",
        "SITE_PROVISIONER_URL",
        "GITHUB_TOKEN",
        "GITHUB_USERNAME",
        # H4: Cloudflare bypass
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_ZONE_ID_OCORON",
    }
    loaded = {}
    env_file = FABRIK_ROOT / ".env"
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key in keys_needed:
            loaded[key] = value.strip().strip('"').strip("'")
    missing = keys_needed - loaded.keys()
    if missing:
        raise SystemExit(f"Missing env vars: {missing}")
    return loaded


# --- per-step implementations ----------------------------------------------


def cleanup(name: str, env: dict[str, str], log) -> None:
    """Destroy any prior deployment state for ``name``. Idempotent."""
    # SCOPE LOCK: belt-and-suspenders against typo / env-var injection.
    # Every destructive call below assumes name is bounded to fabrik-test-*.
    # If anything ever passes a different name, blow up loudly before touching
    # Coolify / DNS / GitHub / filesystem.
    assert name.startswith("fabrik-test-"), f"refusing to cleanup non-test resource: {name!r}"
    print(f"\n━━━━━ cleanup({name}) ━━━━━", flush=True)
    log.write(f"\n━━━━━ cleanup({name}) ━━━━━\n")

    # 1. fabrik destroy (handles Coolify app + DNS + registrars + local tree)
    # CAVEAT: Postgres and Meilisearch data are preserved by default.
    # We pass --drop-data here because this is a throwaway-test-cleanup workflow.
    # For production teardowns, omit --drop-data to protect against accidental data loss.
    spec_path = SPECS_DIR / f"{name}.yaml"
    if spec_path.exists():
        try:
            run(
                [str(VENV_FABRIK), "destroy", str(spec_path), "--yes", "--drop-data"],
                cwd=FABRIK_ROOT,
                check=False,
                logfile=log,
                timeout=300,
            )
        except CmdError:
            pass
    else:
        # No spec → destroy can't run. Manually delete Coolify app if it exists.
        _delete_coolify_app_by_name(name, env, log)

    # 2. Remove local project tree (idempotent)
    local = PROJECT_BASE / name
    if local.exists():
        run(["rm", "-rf", str(local)], check=False, logfile=log)

    # 3. Delete GitHub repo (idempotent — tolerate "not found")
    run(
        ["gh", "repo", "delete", f"{GH_USER}/{name}", "--yes"],
        check=False,
        logfile=log,
        env_extra={"GH_TOKEN": env["GITHUB_TOKEN"]},
        timeout=30,
    )

    # 4. Remove leftover spec file
    if spec_path.exists():
        spec_path.unlink()

    # 5. H4 — Cloudflare-direct DNS cleanup.
    # ``fabrik destroy``'s DNS step calls site-provisioner via SSH proxy,
    # which has been returning "SSH proxy request failed" reliably on every
    # invocation in this session. That leaves the ``<name>.vps1.ocoron.com``
    # A record pointing at the VPS, which then causes ``assert_nxdomain``
    # below to time out (120s wasted per iteration). Bypass the broken path
    # by talking to Cloudflare's API directly \u2014 the same API site-provisioner
    # would use if its SSH proxy worked. Scope-locked to ``fabrik-test-*``.
    _cf_delete_dns_record(name, env, log)


def _cf_delete_dns_record(name: str, env: dict[str, str], log) -> None:
    """Delete the A record for ``<name>.vps1.ocoron.com`` via Cloudflare API.

    Idempotent: missing record is not an error. Scope-locked to fabrik-test-*.
    """
    assert name.startswith("fabrik-test-"), f"refusing to delete DNS for non-test record: {name!r}"
    import urllib.error
    import urllib.request

    host = f"{name}.vps1.ocoron.com"
    zone_id = env["CLOUDFLARE_ZONE_ID_OCORON"]
    token = env["CLOUDFLARE_API_TOKEN"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    def _req(method: str, path: str, body: bytes | None = None) -> dict:
        url = f"https://api.cloudflare.com/client/v4{path}"
        req = urllib.request.Request(url, method=method, headers=headers, data=body)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        # Find record by name (returns 0..N records \u2014 we delete them all).
        search = _req("GET", f"/zones/{zone_id}/dns_records?name={host}&type=A")
        records = search.get("result", [])
        if not records:
            print(f"  cloudflare: no A record for {host} (already absent)")
            log.write(f"  cloudflare: no A record for {host}\n")
            return
        for r in records:
            rid = r["id"]
            _req("DELETE", f"/zones/{zone_id}/dns_records/{rid}")
            print(f"  cloudflare: deleted A record {host} (id={rid})")
            log.write(f"  cloudflare: deleted A record {host} (id={rid})\n")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        print(f"  cloudflare DELETE failed {e.code}: {body}")
        log.write(f"  cloudflare DELETE failed {e.code}: {body}\n")
    except Exception as e:
        print(f"  cloudflare DELETE crashed: {e}")
        log.write(f"  cloudflare DELETE crashed: {e}\n")


def _delete_coolify_app_by_name(name: str, env: dict[str, str], log) -> None:
    """Delete Coolify app matching ``name`` (if any) via Python driver."""
    sys.path.insert(0, str(FABRIK_ROOT / "src"))
    try:
        from fabrik.drivers.coolify import CoolifyClient

        c = CoolifyClient()
        apps = c.list_applications()
        for a in apps:
            if a.get("name") == name:
                uuid = a.get("uuid")
                print(f"Deleting Coolify app {name} uuid={uuid}")
                log.write(f"Deleting Coolify app {name} uuid={uuid}\n")
                try:
                    c.delete_application(uuid)
                except Exception as e:
                    msg = f"  (delete failed, non-fatal): {e}\n"
                    print(msg)
                    log.write(msg)
                return
    except Exception as e:
        log.write(f"(coolify lookup failed, non-fatal): {e}\n")


def assert_nxdomain(name: str, log, max_wait: int = 180) -> None:
    """Verify DNS has propagated NXDOMAIN before the next scaffold.

    After `fabrik destroy` the site-provisioner removes the A record, but
    Cloudflare negative-cache can retain the old answer briefly. Poll the
    authoritative NS until either NXDOMAIN or empty A answer.
    """
    host = f"{name}.vps1.ocoron.com"
    print(f"\n━━━━━ assert_nxdomain({host}) ━━━━━", flush=True)
    log.write(f"\n━━━━━ assert_nxdomain({host}) ━━━━━\n")
    deadline = time.time() + max_wait
    while time.time() < deadline:
        r = subprocess.run(
            ["dig", "+short", "+time=3", "+tries=1", "A", host, "@1.1.1.1"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        answer = r.stdout.strip()
        if not answer or "NXDOMAIN" in r.stderr:
            print(f"  NXDOMAIN confirmed for {host}")
            log.write(f"  NXDOMAIN confirmed for {host}\n")
            return
        print(f"  still resolves to {answer!r}, retrying in 10s…")
        log.write(f"  still resolves to {answer!r}\n")
        time.sleep(10)
    print(
        f"  ⚠ {host} still resolves after {max_wait}s — proceeding anyway "
        f"(fabrik apply will hit stale A)"
    )
    log.write(f"  WARN: {host} still resolves after {max_wait}s\n")


def scaffold(name: str, project_type: str, log) -> Path:
    """Run fabrik scaffold. Returns the project dir."""
    print(f"\n━━━━━ scaffold({name}, {project_type}) ━━━━━", flush=True)
    log.write(f"\n━━━━━ scaffold({name}, {project_type}) ━━━━━\n")
    run(
        [
            str(VENV_FABRIK),
            "scaffold",
            name,
            "--type",
            project_type,
            "-d",
            f"proof-run dummy for {project_type}",
            "--no-spec",
        ],
        cwd=PROJECT_BASE,
        logfile=log,
        timeout=120,
    )
    project_dir = PROJECT_BASE / name
    if not project_dir.exists():
        raise RuntimeError(f"scaffold did not create {project_dir}")
    return project_dir


def push_to_github(name: str, project_dir: Path, env: dict[str, str], log) -> str:
    """Create GH repo + push. Returns the remote URL.

    B25: must be ``--public``. The fabrik deployer at
    ``@/opt/fabrik/src/fabrik/drivers/coolify.py::create_git_application``
    always POSTs to ``/applications/public`` (see comment at line 496-505 —
    private-deploy-key and private-github-app endpoints exist but require
    extra setup out of scope for this driver path). A ``--private`` repo
    fails at Coolify's git clone with::

        fatal: could not read Username for 'https://github.com':
        No such device or address

    Throwaway ``fabrik-test-*`` repos are deleted on each loop iteration, so
    public visibility for the brief window of a proof run is acceptable.
    """
    print(f"\n━━━━━ push_to_github({name}) ━━━━━", flush=True)
    log.write(f"\n━━━━━ push_to_github({name}) ━━━━━\n")
    run(
        [
            "gh",
            "repo",
            "create",
            f"{GH_USER}/{name}",
            "--public",
            "--source=.",
            "--push",
            "--remote=origin",
        ],
        cwd=project_dir,
        logfile=log,
        env_extra={"GH_TOKEN": env["GITHUB_TOKEN"]},
        timeout=120,
    )
    remote = subprocess.run(
        ["git", "-C", str(project_dir), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    log.write(f"remote: {remote}\n")
    return remote


def regenerate_spec(name: str, project_type: str, project_dir: Path, log) -> Path:
    """Re-emit spec now that the git remote exists.

    Call generate_and_save_spec() directly — same entry point fabrik scaffold
    uses when --no-spec is NOT passed. Now that `git remote get-url origin`
    returns a real URL, `detect_git_source` will emit `source.type: git`.
    """
    print(f"\n━━━━━ regenerate_spec({name}) ━━━━━", flush=True)
    log.write(f"\n━━━━━ regenerate_spec({name}) ━━━━━\n")
    sys.path.insert(0, str(FABRIK_ROOT / "src"))
    from fabrik.scaffold import _detect_secrets  # type: ignore
    from fabrik.spec_generator import generate_and_save_spec  # type: ignore

    secrets_env, secrets_file = _detect_secrets(project_dir)
    spec_path = generate_and_save_spec(
        name,
        project_type,
        project_dir,
        SPECS_DIR,
        secrets_from_env=secrets_env,
        secrets_from_file=secrets_file,
        use_database=False,
    )
    print(f"  spec written: {spec_path}")
    log.write(f"  spec written: {spec_path}\n")

    # Sanity: assert source.type == git
    import yaml

    spec = yaml.safe_load(spec_path.read_text())
    src = spec.get("source", {})
    src_type = src.get("type") if isinstance(src, dict) else src
    if src_type != "git":
        raise RuntimeError(
            f"regenerate_spec: expected source.type=git, got {src_type!r}. "
            f"detect_git_source() didn't pick up the remote."
        )
    return spec_path


def apply(spec_path: Path, log) -> subprocess.CompletedProcess:
    """Run fabrik apply. Return the completed process (don't raise on failure —
    caller decides).

    H3: passes ``--keep-on-failure`` (B27) so that if the orchestrator's
    health-check or build phase fails, the Coolify app, GlitchTip project,
    DNS record, etc. are NOT auto-rolled-back. ``dump_diagnostics`` then has
    a live Coolify app uuid to query for deployment logs. The harness's
    ``cleanup`` step at the START of the next type-loop iteration is
    responsible for the deferred teardown.
    """
    print(f"\n━━━━━ apply({spec_path.name}) ━━━━━", flush=True)
    log.write(f"\n━━━━━ apply({spec_path.name}) ━━━━━\n")
    return run(
        [
            str(VENV_FABRIK),
            "apply",
            str(spec_path),
            "--yes",
            "--use-orchestrator",
            "--keep-on-failure",
        ],
        cwd=FABRIK_ROOT,
        logfile=log,
        check=False,
        timeout=1500,  # 25 min — covers first-build cold caches
    )


def read_spec(spec_path: Path) -> dict:
    import yaml

    return yaml.safe_load(spec_path.read_text())


def curl_healthcheck(name: str, hc_path: str, log) -> tuple[int, str]:
    """Curl the health URL with GET (NOT HEAD). Return (status_code, raw_output).

    HEAD (`-I`) is wrong here: FastAPI / uvicorn auto-route 405 with
    `allow: GET` on endpoints that only declared a GET handler. That false
    failure burned an hour during harness review (live python-api `/health`
    returns 200 on GET but 405 on HEAD).
    """
    url = f"https://{name}.vps1.ocoron.com{hc_path}"
    print(f"\n━━━━━ curl GET {url} ━━━━━", flush=True)
    log.write(f"\n━━━━━ curl GET {url} ━━━━━\n")
    # GET, follow redirects, capture status + first 500 bytes of body for
    # diagnostics. Body is logged but not used for pass/fail — only status.
    r = subprocess.run(
        [
            "curl",
            "-sL",
            "--max-time",
            "30",
            "-o",
            "/tmp/proof-hc-body",
            "-w",
            "HTTP/%{http_version} %{http_code}\\ncontent-type: %{content_type}\\nsize: %{size_download}\\nfinal-url: %{url_effective}\\n",
            url,
        ],
        capture_output=True,
        text=True,
    )
    body = ""
    try:
        body = Path("/tmp/proof-hc-body").read_text(errors="replace")[:500]
    except Exception:
        pass
    raw = r.stdout + ("\n--- body (first 500 bytes) ---\n" + body if body else "")
    if r.stderr:
        raw += "\n--- stderr ---\n" + r.stderr
    print(raw, flush=True)
    log.write(raw + "\n")
    # Parse the http_code line from -w output
    code = 0
    for ln in r.stdout.splitlines():
        if ln.startswith("HTTP/"):
            try:
                code = int(ln.split()[1])
            except (IndexError, ValueError):
                code = 0
            break
    return code, raw


def dump_diagnostics(name: str, env: dict[str, str], log) -> None:
    """Grab Coolify deployment logs + Traefik labels + container status.

    H3: writes a separate ``<type>-<ts>-build.log`` next to the run log
    containing the verbatim Coolify deployment-logs payload (parsed JSON
    log entries, one per line, prefixed by stream + command). This is the
    single most useful artifact for diagnosing build failures \u2014 it
    contains the actual ``docker build`` / ``docker exec`` stdout/stderr
    that Coolify captured. Requires ``--keep-on-failure`` to be in effect
    so the Coolify app still exists at this point; the
    ``/deployments/applications/{uuid}`` endpoint 404s once the app is gone.

    Also dumps the application JSON (full Coolify state) and the per-VPS
    docker ps + container labels for completeness.
    """
    print(f"\n━━━━━ diagnostics({name}) ━━━━━", flush=True)
    log.write(f"\n━━━━━ diagnostics({name}) ━━━━━\n")
    sys.path.insert(0, str(FABRIK_ROOT / "src"))
    try:
        from fabrik.drivers.coolify import CoolifyClient

        c = CoolifyClient()
        apps = c.list_applications()
        app = next((a for a in apps if a.get("name") == name), None)
        if app:
            uuid = app.get("uuid")
            log.write(f"Coolify app: {json.dumps(app, default=str, indent=2)}\n")
            print(f"Coolify app status: {app.get('status')}, uuid={uuid}")
            # Pull deployment logs via the documented Coolify v4 endpoint.
            # CoolifyClient has no public helper for this so we go through
            # the underlying ``_request`` to keep this scoped to the harness.
            try:
                resp = c._request("GET", f"/deployments/applications/{uuid}")
                deps = resp.get("deployments", []) if isinstance(resp, dict) else []
                build_log_path = log.name.replace(".log", "-build.log")
                with open(build_log_path, "w") as bf:
                    bf.write(f"# Coolify deployment logs for {name} (uuid={uuid})\n")
                    bf.write(f"# {len(deps)} deployment(s) recorded\n\n")
                    for i, d in enumerate(deps):
                        bf.write(
                            f"=== deployment {i + 1}/{len(deps)} "
                            f"uuid={d.get('deployment_uuid')} "
                            f"status={d.get('status')} "
                            f"created={d.get('created_at')} ===\n"
                        )
                        try:
                            entries = json.loads(d.get("logs") or "[]")
                        except json.JSONDecodeError:
                            bf.write("(unable to parse logs JSON)\n")
                            continue
                        for entry in entries:
                            t = entry.get("type", "?")
                            cmd = entry.get("command") or ""
                            out = entry.get("output", "")
                            if cmd:
                                bf.write(f"[{t}] $ {cmd}\n")
                            if out:
                                bf.write(f"[{t}] {out}")
                                if not out.endswith("\n"):
                                    bf.write("\n")
                        bf.write("\n")
                log.write(f"\nCoolify deployment logs written to: {build_log_path}\n")
                print(f"  build log: {build_log_path}")
            except Exception as e:
                log.write(f"(deployment-logs fetch failed: {e})\n")
                print(f"  build log fetch FAILED: {e}")
        else:
            log.write(f"No Coolify app found for {name}\n")
            print(f"  no Coolify app found for {name} (rollback fired despite --keep-on-failure?)")
    except Exception as e:
        log.write(f"diagnostics Coolify phase failed: {e}\n")

    # SSH to VPS for docker + traefik info (best-effort)
    try:
        from fabrik.drivers.ssh import ssh  # type: ignore

        try:
            ps = ssh(
                f"sudo docker ps -a --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep {name} || true"
            )
            log.write(f"\ndocker ps:\n{ps}\n")
        except Exception as e:
            log.write(f"(docker ps failed: {e})\n")
        try:
            labels = ssh(
                f"sudo docker inspect $(sudo docker ps -q --filter name={name} | head -1) "
                f"--format '{{{{json .Config.Labels}}}}' 2>/dev/null || true"
            )
            log.write(f"\ncontainer labels:\n{labels}\n")
        except Exception as e:
            log.write(f"(inspect failed: {e})\n")
    except Exception as e:
        log.write(f"diagnostics SSH phase failed: {e}\n")


# --- main loop --------------------------------------------------------------


def process_type(
    project_type: str,
    env: dict[str, str],
) -> dict:
    """Run the full per-type loop. Return a result dict."""
    name = f"fabrik-test-{project_type}"
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"{project_type}-{ts}.log"
    t_start = time.time()

    result: dict = {
        "type": project_type,
        "name": name,
        "log": str(log_path),
        "ok": False,
        "http_code": None,
        "curl_raw": "",
        "coolify_uuid": None,
        "git_commit": None,
        "elapsed_s": None,
        "error": None,
    }

    with log_path.open("w") as log:
        try:
            cleanup(name, env, log)
            assert_nxdomain(name, log, max_wait=120)
            project_dir = scaffold(name, project_type, log)
            remote = push_to_github(name, project_dir, env, log)
            result["git_remote"] = remote
            try:
                result["git_commit"] = subprocess.check_output(
                    ["git", "-C", str(project_dir), "rev-parse", "HEAD"],
                    text=True,
                ).strip()
            except Exception:
                pass
            spec_path = regenerate_spec(name, project_type, project_dir, log)
            spec = read_spec(spec_path)
            # B23: canonical spec key is `health:`, not `healthcheck:`. Match
            # the schema (`spec_loader.Spec.health`) and generator output.
            hc = spec.get("health") or {}
            hc_path = hc.get("path")
            if hc_path is None and project_type not in NO_HTTP_TYPES:
                # Spec scaffold bug: every HTTP-deployable type must declare
                # a health.path. Fail loud here rather than guess.
                raise RuntimeError(
                    f"spec for {name} has no health.path "
                    f"(and {project_type} is not in NO_HTTP_TYPES). Scaffold bug."
                )

            proc = apply(spec_path, log)
            if proc.returncode != 0:
                raise RuntimeError(f"fabrik apply exited rc={proc.returncode}")

            # Pull Coolify UUID from the just-applied app — BEST-EFFORT only.
            # The orchestrator deploys via SSH + Docker Compose (not Coolify), so the
            # Coolify API is often unreachable here; a failure must NOT abort the real
            # proof (the healthcheck curl below). It is used for a cosmetic UUID and
            # the NO_HTTP worker-status check.
            sys.path.insert(0, str(FABRIK_ROOT / "src"))
            app = None
            try:
                from fabrik.drivers.coolify import CoolifyClient

                c = CoolifyClient()
                app = next(
                    (a for a in c.list_applications() if a.get("name") == name),
                    None,
                )
                if app:
                    result["coolify_uuid"] = app.get("uuid")
            except Exception as cx:  # noqa: BLE001 — diagnostic-only lookup
                log.write(f"coolify uuid lookup skipped (non-fatal): {cx!r}\n")

            if project_type in NO_HTTP_TYPES:
                # Worker: no HTTP surface. Proof = Coolify reports running:healthy.
                status = (app or {}).get("status", "") or ""
                result["http_code"] = None
                result["curl_raw"] = f"(worker, no curl) coolify status={status!r}"
                if not status.startswith("running"):
                    raise RuntimeError(f"worker not in running:* state after apply: {status!r}")
                result["ok"] = True
            else:
                # Poll healthcheck with retries — cert + DNS may lag apply a bit
                accept = ACCEPT_CODES.get(project_type, DEFAULT_ACCEPT)
                code = 0
                raw = ""
                for _attempt in range(6):
                    code, raw = curl_healthcheck(name, hc_path, log)
                    if code in accept:
                        break
                    time.sleep(15)
                result["http_code"] = code
                result["curl_raw"] = raw

                if code not in accept:
                    raise RuntimeError(
                        f"healthcheck returned {code}; expected one of {sorted(accept)}"
                    )

                result["ok"] = True

        except Exception as e:
            result["error"] = repr(e)
            log.write(f"\n!!! FAILURE: {e}\n")
            import traceback

            tb = traceback.format_exc()
            log.write(tb)
            print(tb)
            try:
                dump_diagnostics(name, env, log)
            except Exception as dx:
                log.write(f"diagnostics dump crashed: {dx}\n")

        result["elapsed_s"] = round(time.time() - t_start, 1)
        log.write(f"\n=== result: {json.dumps(result, default=str, indent=2)} ===\n")
    return result


def write_proof(results: list[dict]) -> None:
    ts = datetime.now(UTC).isoformat(timespec="seconds")
    lines = [
        "# Fabrik Scaffold Proof — Live End-to-End Deploy",
        "",
        f"**Generated:** {ts}",
        "**Harness:** `@/opt/fabrik/scripts/proof_run.py`",
        "",
        "## Summary",
        "",
        "| Type | Result | HTTP | Coolify UUID | Elapsed |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        status = "PASS" if r["ok"] else "FAIL"
        lines.append(
            f"| `{r['type']}` | {status} | {r.get('http_code', '—')} | "
            f"`{r.get('coolify_uuid', '—')}` | {r.get('elapsed_s', '—')}s |"
        )
    lines.append("")
    lines.append("## Raw curl output (per type)")
    lines.append("")
    for r in results:
        lines.append(f"### `{r['type']}`")
        lines.append("")
        lines.append(f"- **Log:** `{r['log']}`")
        lines.append(f"- **Git commit:** `{r.get('git_commit', '—')}`")
        lines.append(f"- **Git remote:** `{r.get('git_remote', '—')}`")
        lines.append("")
        lines.append("```")
        lines.append((r.get("curl_raw") or "").strip() or "(no curl output)")
        lines.append("```")
        if not r["ok"]:
            lines.append("")
            lines.append(f"**Error:** `{r.get('error')}`")
        lines.append("")
    PROOF_FILE.write_text("\n".join(lines) + "\n")


def main() -> int:
    env = load_env()
    results: list[dict] = []
    all_ok = True
    only = os.environ.get("PROOF_ONLY")  # e.g. PROOF_ONLY=saas-skeleton
    types = [t for t in SCAFFOLD_TYPES if (not only or t == only)]
    print(f"Processing: {types}")
    for t in types:
        r = process_type(t, env)
        results.append(r)
        status = "✅ PASS" if r["ok"] else "❌ FAIL"
        print(
            f"\n\n{'#' * 60}\n# {status}  {t}  http={r.get('http_code')}"
            f"  elapsed={r.get('elapsed_s')}s\n{'#' * 60}\n"
        )
        if not r["ok"]:
            all_ok = False
            break  # stop on first failure per mission rules

    # Always write proof with whatever we have — partial proof is still useful
    write_proof(results)
    print(f"\nProof written to: {PROOF_FILE}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
