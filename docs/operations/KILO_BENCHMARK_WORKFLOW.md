# Kilo Agent Benchmark Workflow

Status: **DISABLED in WSL daily startup pipeline** (2026-05-09). Available as manual trigger or opt-in via env flag.

## What it does

Four-step pipeline that keeps the Kilo CLI agent fleet in sync with the latest model benchmark data and AI-assigned roles:

1. **`kilo_agents_db.py all`** — rebuilds the agent SQLite database (`/opt/fabrik/scripts/kilo-benchmarks/kilo_agents_db.py`) from current Kilo Code marketplace data + locally cached benchmarks. No network calls to Kilo CLI; pure data shuffling.
2. **`update_kilo_benchmarks.py --force`** — scrapes external benchmark sites (LiveBench, Aider polyglot, etc.) and updates the agent database with fresh scores. Uses HTTP scraping; no Kilo CLI invocations.
3. **`role_mapper.py`** — uses the Kilo CLI itself (Gemini-3.1-Pro / GPT-5.4 / Claude-Opus-4.7 max thinking modes) to assign agents to roles (coding/reviewing/fixing/documentation/testing). **This is the step that hangs.** See "Why disabled" below.
4. **`generate_kilo_agents.py`** — templates per-agent shell scripts in `/opt/fabrik/scripts/Local_*` from the assigned roles. Pure file generation; no network.

The output is a working Kilo CLI agent fleet — each `Local_Coder_qwen32b.sh`, `Local_Review_llama70b.sh`, etc. invokes the right model with the right role-specific prompt.

## Why disabled

**Symptom (May 3 – May 9, 2026):** the WSL `wsl_startup_hook.sh` daily pipeline left two `bash -c` chains running indefinitely (3 days and 16 hours respectively). Each chain was stuck inside `role_mapper.py`, which was repeatedly spawning `.kilo run --auto --model X --variant max` subprocesses. Stuck Kilo CLI agents accumulated as zombies (`ps` showed PID 1982018 in defunct state since May 8).

**Root cause:** `role_mapper.py` iterates through a `KILO_MODELS` list, calling each model with `subprocess.Popen` + `communicate(timeout=300)`. The 5-minute per-model timeout is supposed to short-circuit hangs, but Kilo CLI's stdio behavior under non-interactive `subprocess.PIPE` evidently keeps the call alive past the timeout in some edge cases (likely when a model's API rate-limits silently or the kilo CLI itself enters an internal retry loop that doesn't return to Python).

**Symptoms (visible signals):**
- `ps -ef | grep -E 'kilo$|\.kilo$'` shows agents running for hours/days.
- `pgrep -af role_mapper` returns a process started ≥1 day ago.
- `update.log` has `=== Fabrik Daily Pipeline — <DATE> ===` headers without matching `=== Pipeline complete — <DATE> ===` footers.
- `/tmp/.fabrik_daily_<YYYYMMDD>` lock file exists but pipeline never finished.

**Collateral damage:** stuck kilo agents block Claude Code's stdio MCP spawn for `fabrik-citation-verifier` because both share the WSL execution boundary. WSL itself doesn't slow down (CPU stays >90% idle per vmstat — the load average was a WSL2 kernel accounting glitch, not real load), but Claude Code's MCP client has tight handshake timeouts (~5s) and intermittent stdio congestion can push past them.

## What stays enabled in the daily pipeline

The other steps in `wsl_startup_hook.sh` are unchanged:

| Step | Script | Purpose |
|---|---|---|
| Env watcher | `watch_env_changes.sh` | Monitors `/opt/*/.env` changes (persistent) |
| Project sync | `sync_projects.py` | Updates `data/projects.yaml`, `BUSINESS_MODEL.md`, `PORTS.md` |
| Cascade backup | `sync_cascade_backup.sh` | Verifies Cascade backup freshness |
| Health summary | `health_summary.py` | Daily system health snapshot |
| ~~Agent DB~~ | ~~`kilo_agents_db.py all`~~ | **DISABLED — see manual trigger** |
| ~~Benchmarks~~ | ~~`update_kilo_benchmarks.py --force`~~ | **DISABLED** |
| ~~Role mapping~~ | ~~`role_mapper.py`~~ | **DISABLED (root cause)** |
| ~~Agent gen~~ | ~~`generate_kilo_agents.py`~~ | **DISABLED** |
| Extensions sync | `sync_extensions.sh` | Auto-updates Windsurf extensions docs |

The four disabled steps run only when `FABRIK_ENABLE_KILO_WORKFLOW=1` is set in the environment when `wsl_startup_hook.sh` is sourced, OR when triggered manually via `run_kilo_workflow.sh`.

## How to run it manually (recommended)

```bash
/opt/fabrik/scripts/run_kilo_workflow.sh
```

This wrapper enforces a **30-minute hard wall-clock cap** on `role_mapper.py` (via Linux `timeout` command, not Python's subprocess timeout — more reliable). If `role_mapper.py` exceeds 30 min, the wrapper:
- Kills `role_mapper.py` itself
- Kills any leftover `kilocode/cli` processes via `pkill -9`
- Aborts before running `generate_kilo_agents.py` (which would generate stale role assignments otherwise)
- Logs to `/opt/fabrik/scripts/kilo-benchmarks/cache/manual_workflow.log`
- Exits non-zero so you notice

Expected runtime when healthy: 5–15 minutes total (1 min DB rebuild, 2–4 min benchmarks, 1–8 min role mapping depending on model availability, <30 sec agent gen).

## How to re-enable as part of WSL daily startup

If you want it to run on every WSL session start (the original behavior):

```bash
# Edit ~/.bashrc — replace the existing "source /opt/fabrik/scripts/wsl_startup_hook.sh" line with:
FABRIK_ENABLE_KILO_WORKFLOW=1 source /opt/fabrik/scripts/wsl_startup_hook.sh
```

Or one-off for the current WSL session only:

```bash
FABRIK_ENABLE_KILO_WORKFLOW=1 source /opt/fabrik/scripts/wsl_startup_hook.sh
```

**Caveat:** the underlying hang in `role_mapper.py` is not fixed by re-enabling — it just removes the skip. If you re-enable for daily startup, you'll get the same accumulating stuck agents the moment a Kilo model hangs again. Use the manual trigger instead (`run_kilo_workflow.sh`), which has the watchdog.

## The actual fix (future work)

The proper solution is to harden `role_mapper.py`:

1. **Replace `subprocess.Popen + communicate(timeout=300)` with `subprocess.run(..., timeout=300)`**, which more reliably kills the child on timeout (different POSIX signal handling).
2. **Wrap the per-model loop in a kill-on-timeout sentinel** — if any single model's call exceeds 5 min, send SIGTERM, then SIGKILL after 5 sec, then move to next model in `KILO_MODELS`.
3. **Add liveness probe to the kilo CLI** before invocation — if `kilo --version` hangs for >10s, skip the kilo step entirely with a warning.
4. **On role_mapper exit, kill any orphan `kilocode/cli` processes** spawned during the run.

Until that work lands, this disable + manual trigger is the safe operational pattern.

## Diagnosing future stuck instances

```bash
# Quick check
pgrep -af "Fabrik Daily Pipeline"
pgrep -af role_mapper
ps -ef | grep -E 'kilo$|\.kilo$' | grep -v grep | wc -l

# Process tree of any stuck role_mapper
pstree -p $(pgrep -f role_mapper | head -1)

# Forced cleanup (will cancel any in-progress legitimate run)
pkill -9 -f "Fabrik Daily Pipeline"
pkill -9 -f role_mapper
pkill -9 -f "kilocode/cli"

# Pipeline log tail
tail -100 /opt/fabrik/scripts/kilo-benchmarks/cache/update.log
tail -100 /opt/fabrik/scripts/kilo-benchmarks/cache/manual_workflow.log
```

## Files involved

| Path | Role |
|---|---|
| `/opt/fabrik/scripts/wsl_startup_hook.sh` | Daily pipeline; kilo workflow guarded by `FABRIK_ENABLE_KILO_WORKFLOW` |
| `/opt/fabrik/scripts/wsl_startup_hook.sh.before-kilo-disable` | Backup of original (pre-2026-05-09) |
| `/opt/fabrik/scripts/run_kilo_workflow.sh` | Manual trigger with 30-min watchdog (NEW 2026-05-09) |
| `/opt/fabrik/scripts/kilo-benchmarks/role_mapper.py` | Hangs unfixed; called only on manual trigger |
| `/opt/fabrik/scripts/kilo-benchmarks/kilo_agents_db.py` | Healthy |
| `/opt/fabrik/scripts/kilo-benchmarks/update_kilo_benchmarks.py` | Healthy |
| `/opt/fabrik/scripts/generate_kilo_agents.py` | Healthy |
| `/opt/fabrik/scripts/kilo-benchmarks/cache/update.log` | Daily pipeline log |
| `/opt/fabrik/scripts/kilo-benchmarks/cache/manual_workflow.log` | Manual trigger log (NEW) |

## Change history

- **2026-05-09** — Initial disable + manual trigger created. See incident notes below.

## Incident notes (2026-05-09)

While debugging an unrelated `fabrik-citation-verifier` MCP connection failure for Claude Code, found two stuck `Fabrik Daily Pipeline` instances (May 3 17:43 and May 9 00:05) plus 11 orphan `kilo` agent processes, all rooted in `role_mapper.py`. Killed all stuck processes, traced trigger to `wsl_startup_hook.sh` (sourced from `~/.bashrc`), surgically disabled steps 5a–5d (the kilo workflow) with the env-flag guard above, created `run_kilo_workflow.sh` manual trigger with timeout watchdog, wrote this document.

The MCP connection failure had a separate root cause (`PYTHONPATH` env var not propagating from Windows-side `.claude.json` `env` field through `wsl.exe` to the Linux Python process). Documented separately in the Claude Code MCP configuration notes.
