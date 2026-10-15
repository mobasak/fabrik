# T05 — `fabrik apply` loses `--legacy`, `--use-orchestrator`, `--skip-dns`, `--skip-deploy`; `deploy.py` is deleted; cli wording
Appetite: 45

## Scope
Implements `spec § The delta` D1 and D10's `cli.py` lines (`docs/superpowers/specs/2026-10-14-coolify-verb-retirement-design.md:141`, `:151`). In `src/fabrik/cli.py`: the options `:398-417` (`--skip-dns`, `--skip-deploy`, `--use-orchestrator`, `--legacy`) and their parameters `:445-449`, the docstring lines `:458-466` that name them, the `if use_orchestrator:` notice `:510-514` and the legacy fall-through `:560-705` (everything after the `if not legacy:` block, which always exits, `:517-559`) are removed and the block dedented; `--yes` STAYS with the help text `accepted for compatibility; the orchestrator path never prompts`; `src/fabrik/deploy.py` (63 lines, its only importer `cli.py:679`) is deleted. The D10 wording: `:891` (`--partial` help → `no DNS removal, no file cleanup`), the `destroy` docstring `:932` and `:935` (the Coolify app sentence and the pre-fix history line), the partial-destroy comment `:1077-1078`, `:1124` and `:1129` leave the destroy preview, `:2402` → `pre-deploy sequence`, `:2473` → `ready for deployment`; `audit-registrars`' hint `:1477` keeps naming `reconcile-all`. DO-NOT: touch `status`, `reconcile-all`, `projects`, or the `export`/`import` lines `:2883-2889` and `:2963-2983` (T06); never touch `scripts/proof_run.py` (T08 drops its `--use-orchestrator` at `:518`).

Depends: T04
Parallel: ⛓️
Complexity: simple
Gate: .venv/bin/python -m pytest tests/test_cli_apply_flags.py -q
Docs: none (`docs/reference/fabrik-cli-reference.md:116-129` and `docs/DEPLOYMENT_ARCHITECTURE.md:75` are T10a's and T10b's)

## Touches
- src/fabrik/cli.py — PRIMARY PATH
- src/fabrik/deploy.py
- tests/test_cli_apply_flags.py — NEW

## Behavior Contract
- **Given** `fabrik apply <spec> --legacy`, `--use-orchestrator`, `--skip-dns` and `--skip-deploy`, **When** each is invoked through `CliRunner`, **Then** each exits 2 with click's `No such option` naming the flag (spec § The delta D1).
- **Given** `fabrik apply <spec> --yes --dry-run` with the orchestrator faked, **When** it runs, **Then** `--yes` is accepted, the fake is called once, and `fabrik apply --help` carries `accepted for compatibility; the orchestrator path never prompts` (spec § The delta D1, review O2-8).
- **Given** the tree after this ticket, **When** inspected, **Then** `src/fabrik/deploy.py` is absent, `git grep -n deploy_to_coolify -- src` returns 0 lines, and `inspect.getsource(fabrik.cli.apply)` contains neither `legacy` nor `use_orchestrator` (spec § The delta D1; V8).
- **Given** the `destroy` preview and the `--partial` help, **When** `fabrik destroy --help` and the preview text are read, **Then** the help says `no DNS removal, no file cleanup` and no `Coolify` word remains in `cli.py:925-940`, `:1075-1080` or `:1120-1130` (spec § The delta D10).
- **Given** `git grep -n -i coolify -- src/fabrik/cli.py` after this ticket, **When** it runs, **Then** every remaining hit lies inside the `export`/`import` docstring T06 owns (`:2886`) and none elsewhere — T02, T03 and T04 removed theirs upstream (`:752-782`, `:1228`, `:1549-1584`, `:1618-1646`) (spec § The delta D1, D10; V8).

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-14-coolify-verb-retirement-design.md
