# T02 — `fabrik status` prints the last apply and the live containers
Appetite: 45

## Scope
Implements `spec § The delta` D2's verb half (`docs/superpowers/specs/2026-10-14-coolify-verb-retirement-design.md:142`) in `src/fabrik/cli.py:723-784`: after the `apps/<id>` block (`:741-750`) the Coolify block (`:752-782`, its lazy `from fabrik.drivers.coolify import CoolifyClient` at `:755`) is replaced by (a) a **Last apply** section from `fabrik.state.load(spec.id)` and (b) a **Live containers** section that walks `app_dir(spec)` with `SSHDeployer().probe_app(path)` under `_host_env(spec.target_vps)` and prints `_parse_compose_ps` rows — all three from T01 — with the messages and the exit-0 rule spec D2 states. A spec defect found by `app_dir` (a local path outside `/opt`) is printed as `Error: <message>` and exits 1, like a spec that fails to load (`cli.py:732-736`) — a plan decision, since the spec does not name this case for `status`. DO-NOT: touch `reconcile-all`, `projects` or `apply` (T03, T04, T05), or `deployer_ssh.py` (T01).

Depends: T01
Parallel: ⛓️
Complexity: simple
Gate: .venv/bin/python -m pytest tests/test_cli_status_live.py -q
Docs: none (`docs/reference/fabrik-cli-reference.md:268-274` is T10a's)

## Touches
- src/fabrik/cli.py — PRIMARY PATH
- tests/test_cli_status_live.py — NEW

## Behavior Contract
- **Given** a state record for the spec carrying `applied_at`, a 40-character `git_sha`, `target_vps: vps2`, two `registrars_applied` types and one `registrar_failures` row, **When** `fabrik status <spec>` runs with `probe_app` faked, **Then** the Last-apply section prints the timestamp, the sha truncated to 12 characters, `vps2`, both types and the failure row (spec § The delta D2a).
- **Given** no state record for the spec, **When** `fabrik status` runs, **Then** the Last-apply section prints `no state record — never applied from this checkout` and the exit code is 0 (spec § The delta D2a).
- **Given** `probe_app` returning `exists` True and the four-row JSON-Lines fixture of T01, **When** `fabrik status` runs, **Then** the REAL `_parse_compose_ps` yields four `Service · State · Health · ExitCode` lines, the running `""` row labelled `no healthcheck` and the exited `""` row labelled `—` (spec § The delta invariant 3; V1).
- **Given** `probe_app` returning `exists` False with `error` None for every candidate, **When** `fabrik status` runs, **Then** one `no <dir>/compose.yaml on vps1` line per candidate prints and the exit code is 0; given `exists` False with `error` set the line is `⚠️ could not reach vps1: <error>`; given `exists` True with `error` set it is `⚠️ could not read containers on vps1: <error>` — exit 0 in all three (spec § The delta D2, invariant 2).
- **Given** a record whose `target_vps` is `vps1` while the spec names `vps2`, **When** `fabrik status` runs, **Then** both hosts are printed, and `probe_app`'s calls ran with `FABRIK_VPS_SSH_HOST=vps2` (spec § The delta D2).
- **Given** a spec whose local `source.path` is `/srv/x`, **When** `fabrik status` runs, **Then** the output is `Error: ` + the `ProvisioningError` message and the exit code is 1, no ssh call made (plan decision; `cli.py:732-736` is the precedent).
- **Given** the rebased `status` function, **When** `inspect.getsource(fabrik.cli.status)` is searched, **Then** it contains neither `coolify` nor `Coolify` (spec § The delta D2; V8).

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-14-coolify-verb-retirement-design.md
- docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/T01-deployer-helpers.md
- src/fabrik/state.py
