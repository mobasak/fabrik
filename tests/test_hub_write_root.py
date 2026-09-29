"""T01 — hub write root: tracked outputs land in the invoker's tree.

Spec: docs/superpowers/specs/2026-09-29-hub-worktree-cutover-design.md § The delta D3, § V9.

Every fixture below builds its OWN throwaway git repo under `tmp_path` to stand in for the hub —
never a worktree of the real /opt/fabrik (CLAUDE.md § Shared repo). `_HUB_PATH` (the module-level
constant each of the four converted files carries) is monkeypatched to that fake repo so the
git-common-dir-parent comparison in `_resolve_fabrik_root` matches it instead of the real hub.
"""

from __future__ import annotations

import importlib.util
import itertools
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# The four converted files, keyed for parametrized cross-target tests below — every target must
# answer the SAME `_resolve_fabrik_root` call the same way, config.py included, so a defect in any
# one replica (not just config.py) turns its own parametrize case red.
_TARGETS: dict[str, Path] = {
    "config": Path("src/fabrik/config.py"),
    "sync_projects": Path("scripts/sync_projects.py"),
    "vps_sync": Path("scripts/vps_sync.py"),
    "command_feedback_report": Path("scripts/command_feedback_report.py"),
}

_MODULE_TAG = itertools.count()


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True, timeout=10
    )


def _init_fake_hub(tmp_path: Path, name: str = "hub-main") -> Path:
    """A throwaway repo standing in for the hub main checkout."""
    hub = tmp_path / name
    hub.mkdir()
    _git("init", "-q", cwd=hub)
    _git("config", "user.email", "test@example.com", cwd=hub)
    _git("config", "user.name", "Test", cwd=hub)
    (hub / "README.md").write_text("fake hub\n")
    _git("add", "README.md", cwd=hub)
    _git("commit", "-q", "-m", "seed", cwd=hub)
    return hub


def _add_worktree(hub: Path, tmp_path: Path, name: str = "probe") -> Path:
    wt = tmp_path / name
    _git("worktree", "add", "-q", "-b", f"worktree-{name}", str(wt), "HEAD", cwd=hub)
    return wt


def _load_module(path: Path, name: str) -> ModuleType:
    """Load a script by its FILE PATH, bypassing any installed `fabrik` package — a script under
    `scripts/` is never installed, so this always executes the copy on disk at `path`, worktree
    included."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_target(key: str) -> ModuleType:
    """Load one of the four converted files by its `_TARGETS` key, with a fresh, collision-free
    module name every call (parametrized tests reload the same file repeatedly)."""
    rel = _TARGETS[key]
    return _load_module(REPO_ROOT / rel, f"_t01_{key}_{next(_MODULE_TAG)}")


# ── Behavior Contract row 1 (cross-target): every one of the four converted files answers the
# SAME `_resolve_fabrik_root` call the same way — config.py's own function AND each replica's
# independently-typed copy. A mutation to any single target's algorithm (not only config.py's)
# must turn its own parametrize case red.


@pytest.mark.parametrize("target", sorted(_TARGETS))
def test_resolve_fabrik_root_from_linked_worktree_all_targets(tmp_path, monkeypatch, target):
    hub = _init_fake_hub(tmp_path)
    wt = _add_worktree(hub, tmp_path)
    monkeypatch.delenv("FABRIK_ROOT", raising=False)
    module = _load_target(target)
    monkeypatch.setattr(module, "_HUB_PATH", hub)
    monkeypatch.chdir(wt)
    assert module._resolve_fabrik_root() == wt.resolve()


@pytest.mark.parametrize("target", sorted(_TARGETS))
def test_resolve_fabrik_root_from_main_checkout_all_targets(tmp_path, monkeypatch, target):
    hub = _init_fake_hub(tmp_path)
    monkeypatch.delenv("FABRIK_ROOT", raising=False)
    module = _load_target(target)
    monkeypatch.setattr(module, "_HUB_PATH", hub)
    monkeypatch.chdir(hub)
    assert module._resolve_fabrik_root() == hub.resolve()


@pytest.mark.parametrize("target", sorted(_TARGETS))
def test_resolve_fabrik_root_outside_any_hub_tree(tmp_path, monkeypatch, target):
    """A git tree that exists but is NOT a worktree of the hub falls back to the hub path."""
    hub = _init_fake_hub(tmp_path)
    other = _init_fake_hub(tmp_path, name="unrelated-repo")
    monkeypatch.delenv("FABRIK_ROOT", raising=False)
    module = _load_target(target)
    monkeypatch.setattr(module, "_HUB_PATH", hub)
    monkeypatch.chdir(other)
    assert module._resolve_fabrik_root() == hub.resolve()


@pytest.mark.parametrize("target", sorted(_TARGETS))
def test_resolve_fabrik_root_outside_any_git_tree(tmp_path, monkeypatch, target):
    hub = _init_fake_hub(tmp_path)
    outside = tmp_path / "not-a-repo"
    outside.mkdir()
    monkeypatch.delenv("FABRIK_ROOT", raising=False)
    module = _load_target(target)
    monkeypatch.setattr(module, "_HUB_PATH", hub)
    monkeypatch.chdir(outside)
    assert module._resolve_fabrik_root() == hub.resolve()


@pytest.mark.parametrize("target", sorted(_TARGETS))
def test_resolve_fabrik_root_env_var_always_wins(tmp_path, monkeypatch, target):
    hub = _init_fake_hub(tmp_path)
    wt = _add_worktree(hub, tmp_path)
    override = tmp_path / "explicit-override"
    override.mkdir()
    monkeypatch.setenv("FABRIK_ROOT", str(override))
    module = _load_target(target)
    monkeypatch.setattr(module, "_HUB_PATH", hub)
    monkeypatch.chdir(wt)
    assert module._resolve_fabrik_root() == override


# ── Behavior Contract row 2 / spec § V9: writes land in the worktree, not the main checkout ──


def _seed_sync_projects_outputs(repo: Path) -> None:
    (repo / "docs").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "PROJECT_CATALOG.md").write_text(
        "# Catalog\n\n<!-- AUTO-GENERATED:PROJECTS:START -->\nold\n<!-- AUTO-GENERATED:PROJECTS:END -->\n"
    )
    (repo / "PORTS.md").write_text("# Ports\n\nnothing here yet\n")


def test_sync_projects_writes_land_in_the_worktree_not_the_main_checkout(tmp_path, monkeypatch):
    hub = _init_fake_hub(tmp_path)
    _seed_sync_projects_outputs(hub)
    _git("add", "docs/PROJECT_CATALOG.md", "PORTS.md", cwd=hub)
    _git("commit", "-q", "-m", "seed sync outputs", cwd=hub)
    wt = _add_worktree(hub, tmp_path)

    monkeypatch.delenv("FABRIK_ROOT", raising=False)
    monkeypatch.chdir(wt)
    module = _load_module(REPO_ROOT / "scripts" / "sync_projects.py", "_t01_sync_projects_write")
    monkeypatch.setattr(module, "_HUB_PATH", hub)
    monkeypatch.setattr(module, "FABRIK_ROOT", module._resolve_fabrik_root())
    assert wt.resolve() == module.FABRIK_ROOT

    # SSH/VPS-equivalent layer for this script is its /opt scan — stub it so the test is
    # deterministic and never depends on the box's real /opt contents.
    monkeypatch.setattr(module, "scan_projects", lambda root=Path("/opt"): [])

    rc = module.main()
    assert rc == 0

    # Tracked output changed in the WORKTREE...
    catalog_in_worktree = (wt / "docs" / "PROJECT_CATALOG.md").read_text()
    assert "Total projects: 0" in catalog_in_worktree

    # ...and the main checkout's tracked file is untouched.
    hub_status = _git("status", "--porcelain", cwd=hub).stdout
    assert hub_status == ""
    assert "Total projects: 0" not in (hub / "docs" / "PROJECT_CATALOG.md").read_text()


def _seed_vps_sync_outputs(repo: Path) -> None:
    infra = repo / "docs" / "infrastructure"
    infra.mkdir(parents=True, exist_ok=True)
    body = (
        "# VPS Status\n\n"
        "**Last Updated:** 2026-01-01\n\n"
        "| Running containers | 0 (placeholder) |\n\n"
        "### Running Containers (2026-01-01)\n\n(none)\n\n---\n"
    )
    (infra / "vps-status.md").write_text(body)
    (infra / "vps-urls.md").write_text("**Last Updated:** 2026-01-01\n")
    (infra / "vps-complete-inventory.md").write_text(
        "**Date:** 2026-01-01\n\n**Total Containers:** 0\n"
    )


def test_vps_sync_writes_land_in_the_worktree_not_the_main_checkout(tmp_path, monkeypatch):
    hub = _init_fake_hub(tmp_path)
    _seed_vps_sync_outputs(hub)
    _git(
        "add",
        "docs/infrastructure/vps-status.md",
        "docs/infrastructure/vps-urls.md",
        "docs/infrastructure/vps-complete-inventory.md",
        cwd=hub,
    )
    _git("commit", "-q", "-m", "seed vps outputs", cwd=hub)
    wt = _add_worktree(hub, tmp_path)

    monkeypatch.delenv("FABRIK_ROOT", raising=False)
    monkeypatch.chdir(wt)
    module = _load_module(REPO_ROOT / "scripts" / "vps_sync.py", "_t01_vps_sync_write")
    monkeypatch.setattr(module, "_HUB_PATH", hub)
    resolved = module._resolve_fabrik_root()
    assert resolved == wt.resolve()
    monkeypatch.setattr(module, "FABRIK_ROOT", resolved)
    monkeypatch.setattr(
        module, "VPS_STATUS", resolved / "docs" / "infrastructure" / "vps-status.md"
    )
    monkeypatch.setattr(module, "VPS_URLS", resolved / "docs" / "infrastructure" / "vps-urls.md")
    monkeypatch.setattr(
        module, "VPS_INVENTORY", resolved / "docs" / "infrastructure" / "vps-complete-inventory.md"
    )

    # SSH/VPS layer stubbed — no real docker/ssh call, a fixed container list instead.
    stub_containers = [{"name": "hub_authelia_1", "image": "authelia/authelia", "status": "Up"}]

    assert module.update_vps_status(stub_containers) is True
    assert module.update_timestamp(module.VPS_URLS) is True
    assert module.update_inventory_count(len(stub_containers)) is True

    # Tracked outputs changed in the WORKTREE...
    assert "1 (Coolify stack" in (wt / "docs" / "infrastructure" / "vps-status.md").read_text()
    assert (
        "**Total Containers:** 1"
        in (wt / "docs" / "infrastructure" / "vps-complete-inventory.md").read_text()
    )

    # ...and the main checkout is untouched.
    hub_status = _git("status", "--porcelain", cwd=hub).stdout
    assert hub_status == ""


def test_command_feedback_report_repo_default_follows_the_worktree(tmp_path, monkeypatch):
    """Exercises the SCRIPT's real `main()` parser (never a parser rebuilt in the test) — a
    mutation of the `--repo` default back to a hard-coded `Path("/opt/fabrik")` must turn this
    red. `--take` is the cheapest real code path that both (a) builds the actual argparse parser
    inside `main()` with no `--repo` flag, so the DEFAULT is what gets parsed, and (b) hands the
    parsed `a.repo` to a function this test can intercept (`take()`) without touching the ledger
    or any other file."""
    hub = _init_fake_hub(tmp_path)
    wt = _add_worktree(hub, tmp_path)
    monkeypatch.delenv("FABRIK_ROOT", raising=False)
    monkeypatch.chdir(wt)
    module = _load_module(
        REPO_ROOT / "scripts" / "command_feedback_report.py", "_t01_cfr_default_probe"
    )
    monkeypatch.setattr(module, "_HUB_PATH", hub)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "t01-probe-session")

    captured: dict[str, Path] = {}

    def _fake_take(command: str, repo: Path, session: str, ledger) -> str:
        captured["repo"] = repo
        return "stubbed"

    monkeypatch.setattr(module, "take", _fake_take)

    rc = module.main(["--take", "some-command"])
    assert rc == 0
    assert captured["repo"] == wt.resolve()


# ── Behavior Contract row 3: every hub-root write hit is converted or dispositioned ─────────

CONVERTED_FILES = {
    "src/fabrik/config.py",
    "scripts/sync_projects.py",
    "scripts/vps_sync.py",
    "scripts/command_feedback_report.py",
}

# path -> one-line reason. Every reason is one of:
#   config     — imports FABRIK_ROOT from fabrik.config; follows the D3 fix without its own edit
#   untracked  — its only writes near the literal are to a gitignored path (verified against
#                .gitignore: data/, .tmp/, .cache/, logs/, .droid/, proof-logs/, PROOF.md,
#                .env*, *.db, *.log, .mcp.json) or to ~/.claude, outside the repo entirely
#   other-repo — writes a DIFFERENT repo/store (/opt/fabrik-mail, /opt/fabrik-dr-store, a
#                downstream /opt/<project>, or the remote VPS over SSH) — D3 governs the HUB's
#                own tree, not another repo's
#   main-only  — a cron/daemon/boot job invoked only against the fixed hub checkout, never from
#                an agent's worktree (D5's own examples: the kilo pipeline, the boot hook)
#   no-write   — the matched literal sits in a comment, a read-only reference, a test fixture, or
#                a path already derived from `__file__` (so already worktree-relative) — not a
#                write-root site at all
#   deferred   — writes a TRACKED file via a hard-coded root, same class as the four converted
#                files, but outside T01's Touches — a real follow-up, not silently dropped
ALLOWLIST: dict[str, str] = {
    # ── config: already follow fabrik.config.FABRIK_ROOT ──
    "scripts/audit_all_registrars.py": "config: `from fabrik.config import FABRIK_ROOT`",
    "src/fabrik/cli.py": "config: imports FABRIK_ROOT (ticket DO-NOT — scaffold.py/cli.py follow without edits)",
    "src/fabrik/scaffold.py": "config: imports FABRIK_ROOT (ticket DO-NOT — scaffold.py/cli.py follow without edits)",
    "src/fabrik/dev_tools.py": "config: `from .config import FABRIK_ROOT`",
    "src/fabrik/drivers/prometheus.py": "config: local `from fabrik.config import FABRIK_ROOT` inside its writer",
    "src/fabrik/orchestrator/gpu_metrics.py": "config: `from fabrik.config import FABRIK_ROOT`",
    "src/fabrik/orchestrator/gpu_rent.py": "config: `from fabrik.config import FABRIK_ROOT`",
    "src/fabrik/orchestrator/gpu_state.py": "config: `from fabrik.config import FABRIK_ROOT`",
    "src/fabrik/orchestrator/validator.py": "config: `from fabrik.config import FABRIK_ROOT`",
    "src/fabrik/orchestrator/vultr_drill.py": "config: `from fabrik.config import FABRIK_ROOT`",
    "src/fabrik/orchestrator/vultr_provision.py": "config: `from fabrik.config import FABRIK_ROOT`",
    "src/fabrik/orchestrator/vultr_state.py": "config: `from fabrik.config import FABRIK_ROOT`",
    "src/fabrik/portability.py": "config: `from fabrik.config import FABRIK_ROOT`",
    "src/fabrik/preplan.py": "config: `from fabrik.config import FABRIK_ROOT`",
    "src/fabrik/registry.py": "config: `from fabrik.config import FABRIK_ROOT`",
    "src/fabrik/spec_loader.py": "config: `from fabrik.config import FABRIK_ROOT`",
    "src/fabrik/state.py": "config: `from fabrik.config import FABRIK_ROOT`",
    # ── untracked: writes only land in gitignored paths, or outside the repo (~/.claude) ──
    ".claude/hooks/final_gate_stop.py": "untracked: run-record state under ~/.claude/state, outside the repo",
    ".claude/hooks/mcp_watch.py": "untracked: MCP health state under ~/.claude, outside the repo",
    ".claude/hooks/quota_stop.py": "untracked: quota/hold state under ~/.claude, outside the repo",
    ".claude/hooks/session_orient.py": "untracked: session-binding state under ~/.claude, outside the repo",
    "scripts/aro-wake/claude_rotate.py": "untracked: byte-identical vendored copy of scripts/sysadmin/claude_rotate.py — rotate-ledger.jsonl under ~/.claude/state",
    "scripts/audit_envs.py": "untracked: writes data/env_audit.yaml (gitignored `data/`)",
    "scripts/check_commit_trailers.py": "untracked: install() writes only the git hooks dir (commit-msg + a backup), never a tracked path; _HUB_PATH is a read-only hub-identity comparison",
    "scripts/command_run.py": "untracked: run records under ~/.claude/state/command-runs, outside the repo",
    "scripts/dev_tracker.py": "untracked: writes .droid/dev_tracker.db (gitignored `.droid/`)",
    "scripts/proof_run.py": "untracked: writes proof-logs/ and PROOF.md (both gitignored)",
    "scripts/provision_glitchtip_project.sh": "untracked: reads gitignored .env only; provisions a REMOTE GlitchTip project, no local tracked-file write",
    "scripts/provision_watchdog_ro.py": "untracked: reads gitignored .env.sysadmin only; provisions a remote target, no local tracked-file write",
    "scripts/snapshot_vps_state.py": "untracked: writes .tmp/vps-snapshot-<label>.json (gitignored `.tmp/`)",
    "scripts/sysadmin/claude_rotate.py": "untracked: rotate-ledger.jsonl under ~/.claude/state, outside the repo",
    "scripts/sysadmin/detect_reversals.py": "untracked: writes logs/lessons-pending.jsonl + logs/sysadmin-actions.jsonl (gitignored `logs/`)",
    "scripts/sysadmin/emit_mcp_project_config.py": "untracked: writes /opt/fabrik/.mcp.json (not tracked — `git ls-files .mcp.json` is empty)",
    "scripts/sysadmin/install_user_hooks.py": "untracked: installs into the user's own ~/.claude hooks, outside the repo",
    "scripts/sysadmin/quota_dashboard.py": "untracked: quota dashboard state under ~/.claude, outside the repo",
    "scripts/sysadmin/quota_posture_hook.py": "untracked: quota posture state under ~/.claude, outside the repo",
    "scripts/sysadmin/selfwatch_check.py": "untracked: self-watch arm marker under ~/.claude, outside the repo (invokes selfwatch_arm.sh by path)",
    "scripts/sysadmin/send-telegram.sh": "untracked: reads gitignored .env.sysadmin only; sends to the Telegram API, no local tracked-file write",
    "src/fabrik/drivers/modal_provider.py": "untracked: reads gitignored .env.sysadmin + a fixed template dir; its Modal deployment output is written into the TARGET project, not a hub-hardcoded tracked path",
    # ── other-repo: the write target is a DIFFERENT store/repo than the hub's own tree ──
    ".claude/hooks/mail_notify.py": "other-repo: writes /opt/fabrik-mail (sanctioned exception, CLAUDE.md HARD STOPS)",
    "scripts/bootstrap/bootstrap-hub.sh": "other-repo: reads/restores from /opt/fabrik-dr-store, the disaster-recovery env store",
    "scripts/bootstrap/bootstrap-spoke-restore.sh": "other-repo: reads/restores from /opt/fabrik-dr-store",
    "scripts/deploy_doc_policy.py": "other-repo: writes .doc-policy.md into every /opt/<project> repo, not the hub's own tree",
    "scripts/distribute_subagents.sh": "main-only: D-196 (2026-09-08) — hub-only re-vendor target for libs/subagents, never a worktree write",
    "scripts/mail.py": "other-repo: writes /opt/fabrik-mail (sanctioned exception, CLAUDE.md HARD STOPS)",
    "scripts/sync_enforcement_to_projects.py": "other-repo: distributes governance files into every downstream /opt/<project> repo",
    "scripts/sync_gatus_to_vps.sh": "other-repo: writes to the remote VPS over SSH; already honours $FABRIK_ROOT when set for its LOCAL read side",
    "scripts/sync_prometheus_to_vps.sh": "other-repo: writes to the remote VPS over SSH; already honours $FABRIK_ROOT when set for its LOCAL read side",
    "scripts/sync_schema_to_projects.py": "other-repo: distributes schema files into every downstream /opt/<project> repo",
    "scripts/sysadmin/feedback_relay.py": "other-repo: routes through mail.py to /opt/fabrik-mail; the daily relay itself is main-checkout cron",
    "src/fabrik/drivers/postgres.py": "other-repo: reads fixed /opt/fabrik-lib paths (vendored schema + subagents module) — not a hub write-root site",
    "src/fabrik/drivers/watchdog.py": "other-repo: reads fabrik-lib sidecar + hub sysadmin scripts to PROVISION a remote watchdog target — not a hub write-root site",
    "src/fabrik/orchestrator/sysadmin_tokens.py": "other-repo: writes /opt/fabrik-dr-store (already env-overridable via FABRIK_DR_STORE)",
    # ── main-only: cron/daemon/boot scripts invoked only against the fixed hub checkout ──
    "scripts/aro-wake/main.py": "main-only: standalone host daemon bound to /opt/fabrik (writes are to gitignored logs/ state)",
    "scripts/external_services_chain.sh": "main-only: already honours ${FABRIK_ROOT:-/opt/fabrik}; the default path is the external-services cron chain",
    "scripts/kilo-benchmarks/autocommit_pipeline_outputs.sh": "main-only: spec § What exists today — the kilo pipeline commits only in the main checkout",
    "scripts/kilo-benchmarks/daily_refresh.sh": "main-only: kilo-benchmarks daily cron refresh, fixed to /opt/fabrik (no env override)",
    "scripts/kilo_model_sync_startup.sh": "main-only: WSL-boot-triggered model sync, fixed to the hub checkout",
    "scripts/sysadmin/bot.py": "main-only: the veteran-sysadmin AI dispatcher — production cron pattern, fixed to /opt/fabrik",
    "scripts/sysadmin/canary_grounding.py": "main-only: sysadmin monitoring cron, fixed to /opt/fabrik",
    "scripts/sysadmin/ci_health_probe.py": "main-only: sysadmin monitoring cron; the matched write is a mesh-notify subprocess argument, not a file write",
    "scripts/sysadmin/daily-digest.sh": "main-only: daily cron digest, fixed to /opt/fabrik",
    "scripts/sysadmin/monthly-backup-verify.sh": "main-only: monthly cron, fixed to /opt/fabrik",
    "scripts/sysadmin/morning-report.sh": "main-only: daily cron, fixed to /opt/fabrik",
    "scripts/sysadmin/proactive-check.sh": "main-only: cron probe, fixed to /opt/fabrik",
    "scripts/sysadmin/rules_currency_watch.py": "main-only: infra's rules-pack currency beat, fixed to /opt/fabrik/.windsurf/rules",
    "scripts/sysadmin/rules_render_versions.py": "main-only: infra's rules-pack render beat, fixed to /opt/fabrik/.windsurf/rules",
    "scripts/sysadmin/weekly-maintenance.sh": "main-only: weekly cron, fixed to /opt/fabrik",
    "scripts/sysadmin/weekly-security.sh": "main-only: weekly cron, fixed to /opt/fabrik",
    "scripts/sysadmin/weekly_catchup.sh": "main-only: weekly cron; already honours ${FABRIK_ROOT:-/opt/fabrik}",
    "scripts/wsl_startup_hook.sh": "main-only: the WSL boot hook itself, fixed to /opt/fabrik at machine startup",
    # ── no-write: comment, read-only reference, test fixture, or already __file__-derived ──
    "docs/reference/research/2026-09-23-stop-compaction/mine.py": "no-write: dated one-off research artifact, loads final_gate_stop.py by absolute path to inspect it, does not write a tracked hub file",
    "scripts/.scratch/test_env_consolidation.py": "no-write: dead scratch test (last touched 2026-05-25), force-tracked despite scripts/.scratch/ being gitignored",
    "scripts/enforcement/check_doc_links.py": "no-write: `/opt/fabrik/` is a READ-side prefix check classifying a doc link, not a write target",
    "scripts/enforcement/check_structure.py": "no-write: the matched lines are a COMMENT describing the pattern, no FABRIK_ROOT usage of its own",
    "scripts/enforcement/check_sync_trigger_coverage.py": "no-write: already resolves via its own `hub_root()` helper (falls back to DEFAULT_HUB); reads to verify sync-trigger regex coverage, writes no tracked hub file",
    "scripts/enforcement/check_vendored_drift.py": "no-write: the H4 hub-identity check (`_is_hub`) — its only write-call hit is a read-only `git rev-parse --git-common-dir` subprocess; no `.write_text`/`.mkdir`/etc. in the file",
    "scripts/final_gate.py": "no-write: the gate's own hub-identity check (H4, a separate ticket) — computes the diff/staging root for the current run, not a tracked-output destination",
    "scripts/fleet_doc_audit.py": "no-write: `FABRIK_ROOT = Path(__file__).resolve().parents[1]` — already worktree-relative; the flagged literal is incidental",
    "scripts/generate_capability_index.py": "no-write: `REPO = Path(__file__).resolve().parent.parent` — already worktree-relative; the flagged literal is a doc_link reference to /opt/fabrik-lib",
    "scripts/kilo-benchmarks/guard_selection_freshness.py": "no-write: receives FABRIK_ROOT from its caller explicitly (comment: never hardcode /opt/fabrik here); CWD is its own fallback",
    "scripts/kilo-benchmarks/stage_ai_rule_renders.py": "no-write: `REPO = Path(os.environ.get('FABRIK_ROOT') or '/opt/fabrik')` — already env-aware; caller passes it explicitly",
    "scripts/kilo-benchmarks/tests/capture_golden.py": "no-write: `FABRIK_ROOT = SCRIPT_DIR.parent.parent` — already worktree-relative",
    "scripts/kilo-benchmarks/tests/test_autocommit_freshness_wiring.py": "no-write: test fixture — exercises autocommit_pipeline_outputs.sh's FABRIK_ROOT handling, not its own",
    "scripts/kilo-benchmarks/tests/test_flywheel_safety.py": "no-write: test fixture — exercises another script's FABRIK_ROOT handling, not its own",
    "scripts/kilo-benchmarks/tests/test_golden_parity.py": "no-write: test fixture — exercises capture_golden.py's FABRIK_ROOT handling via `cg.FABRIK_ROOT`, not its own",
    "scripts/kilo-benchmarks/tests/test_pool_eval_pause.py": "no-write: test fixture — synthesises a FABRIK_ROOT= line for a subprocess probe, not its own literal",
    "scripts/kilo-benchmarks/update_gateway_counts.py": "no-write: `FABRIK_ROOT = SCRIPT_DIR.parent.parent` — already worktree-relative",
    "scripts/rivals_run.py": "no-write: `HUB_LIBS = Path('/opt/fabrik/libs')` is a READ-side import path for the vendored subagents beat; its own report output is written relative to the target repo",
    "scripts/scratch_sweep.py": "no-write: sweeps/removes only untracked scratch paths (CLAUDE.md § EXIT) — the literal is a comparison base for classifying paths, not a write root",
    "scripts/sysadmin/liveness_audit.py": "no-write: the matched text is a quoted STRING describing a symptom found in ANOTHER script (this audit tool's own finding text), not its own literal",
    "scripts/sysadmin/test_claude_rotate.py": "no-write: test fixture for scripts/sysadmin/claude_rotate.py's cwd/HUB_REPO handling",
    "scripts/tests/test_gather_envs.py": "no-write: test fixture — /opt/fabrik appears only as example credential-path test data",
    "scripts/tests/test_registry_sync.py": "no-write: test fixture — /opt/fabrik appears only as example credential-path test data",
    "scripts/work.py": "no-write: its own tracked writes (.fabrik/work/*.json) are already relative to the invoking repo; the flagged literals are a hub-only script reference (decisions.py, comment says so) and the sanctioned /opt/fabrik-mail store",
    # ── dead: one-off / historical scripts, not part of ongoing automation ──
    "scripts/fix_balanced_tier_agents.py": "dead: one-off generator (last touched 2026-09-06), writes scripts/traycer_agents_fixed/ — a root embedded in a longer literal path, not ongoing automation",
    "scripts/fix_economy_tier_agents.py": "dead: one-off generator (last touched 2026-09-06), same traycer_agents_fixed/ target as fix_balanced_tier_agents.py",
    "scripts/implement_self_review_workflow.py": "dead: one-off generator (last touched 2026-09-06), part of the same traycer_agents_fixed/ batch",
    "scripts/seed_real_ports.py": "dead: its own docstring says 'One-time script' — a historical migration, not ongoing automation",
    "scripts/fabrik_synced_manifest.py": "no-write: the canonical sync-manifest REGISTRY (a dict of source/dest pairs other scripts read) — the matched write-heuristic is a diagnostic self-check block, not a hub-root write site of its own",
    # ── deferred: a real D3 candidate, outside T01's Touches — not silently dropped ──
    "scripts/sysadmin/kaizen_digest.py": "deferred: writes tracked docs/reference/agents/kaizen-log-*.md, which fleet/intel worktree agents also need to write — a genuine D3 candidate outside T01's Touches",
    "scripts/sysadmin/kaizen_shrink_audit.py": "deferred: same tracked kaizen-log-*.md write path as kaizen_digest.py, outside T01's Touches",
    "scripts/update_vps_docs.py": "deferred: writes the same tracked docs/infrastructure/*.md as vps_sync.py via a hardcoded REPO — the same class of gap, outside T01's four named Touches",
}

_EXCLUDED_DIR_PREFIXES = ("tests/", "libs/", "scripts/.archive/", "scripts/archived/")

_LITERAL_RE_SRC = r"""["']/opt/fabrik|FABRIK_ROOT"""
_WRITE_CALL_MARKERS = (
    ".write_text(",
    ".write_bytes(",
    ".write(",
    "yaml.dump(",
    "yaml.safe_dump(",
    "json.dump(",
    "shutil.copy",
    "shutil.move",
    "shutil.copytree",
    "shutil.rmtree",
    ".mkdir(",
    "os.makedirs",
    "os.rename",
    "subprocess.run(",
    "subprocess.call(",
    "subprocess.Popen(",
    "subprocess.check_call(",
    "subprocess.check_output(",
)


def _has_literal(text: str) -> bool:
    import re

    return re.search(_LITERAL_RE_SRC, text) is not None


def _has_write_call(text: str) -> bool:
    if any(m in text for m in _WRITE_CALL_MARKERS):
        return True
    # Shell-script write shapes: `open("w"/"a")` equivalents don't apply, but redirects/cp/mv/tee do.
    import re

    return re.search(r">>?\s*\"?\$|\bcp\s|\bmv\s|\btee\s|\bmkdir\s|\brm\s", text) is not None


def test_every_hub_root_write_hit_is_converted_or_allowlisted():
    """The search: every tracked *.py/*.sh outside tests/, libs/, scripts/.archive/,
    scripts/archived/ containing a `/opt/fabrik` string-literal prefix or `FABRIK_ROOT`, AND a
    write call. Each hit is the four converted files or carries a one-line ALLOWLIST reason —
    an unlisted new hit fails this test naming the file."""
    listed = subprocess.run(
        ["git", "ls-files", "--", "*.py", "*.sh"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout.splitlines()

    hits: list[str] = []
    for rel in listed:
        if any(rel.startswith(p) for p in _EXCLUDED_DIR_PREFIXES):
            continue
        path = REPO_ROOT / rel
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if _has_literal(text) and _has_write_call(text):
            hits.append(rel)

    assert hits, "the search found nothing — the heuristic itself regressed (expected 100+ hits)"

    unresolved = [h for h in hits if h not in CONVERTED_FILES and h not in ALLOWLIST]
    assert not unresolved, (
        f"{len(unresolved)} file(s) hard-code a hub write root with no disposition: {unresolved} "
        "— convert them (mirror src/fabrik/config.py::_resolve_fabrik_root) or add a one-line "
        "reason to ALLOWLIST in this file."
    )

    # The allowlist is a ledger of REAL hits, not a wish list — a reason for a file the search no
    # longer finds (renamed, deleted, converted elsewhere) is stale and hides a shrinking search.
    stale = [p for p in ALLOWLIST if p not in hits]
    assert not stale, (
        f"{len(stale)} ALLOWLIST entr(y/ies) name a file the search no longer hits: {stale} — "
        "remove the stale entry."
    )
