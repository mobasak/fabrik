# Kilo Agent Naming Convention

**Last Updated:** 2026-05-13

> **2026-05 migration:** the old T1–T7 capability-tier naming (Free / Economy /
> Standard / Pro / Expert / Apex / Specialist) has been retired. Agent scripts
> are now grouped by **role + priority**, where role comes from the
> deterministic selector and priority = "P1 cheapest qualified ... P5 most
> expensive qualified" within each role. See
> [docs/workflows/KILO_AGENT_MANAGEMENT.md](../../workflows/KILO_AGENT_MANAGEMENT.md)
> for the full architecture.

---

## Overview

Kilo agent scripts in `~/.traycer/cli-agents/` use a **role-based naming
convention** that encodes:

- Agent role (`coding_simple`, `coding_complex`, `fixing`, etc.)
- Priority within role (P1–P5, where P1 = cheapest qualified)
- Model identifier
- Reasoning-effort variant
- Output cost (encoded)
- Performance-per-dollar (encoded, where available)

Roles are deterministically populated by the selector in
`scripts/kilo-benchmarks/`. Tickets are dispatched to roles at runtime by
[`classify_ticket.py`](../../../scripts/kilo-benchmarks/classify_ticket.py).

---

## Naming Format

```
<role>-<priority>-<model>-<variant>-o<OUT>-ppd<PPD>.sh
```

When a single model fills multiple roles at the same variant, the script is
deduplicated and the role field becomes a `&`-joined label (ordered:
`coding_simple` → `coding_complex` → `fixing`).

### Components

| Component | Description | Values |
| --------- | ----------- | ------ |
| `<role>` | Role assignment | `coding_simple`, `coding_complex`, `fixing`, or `&`-joined dedup label (e.g., `coding_complex&fixing`) |
| `<priority>` | Slot within role | `1`–`5` (P1 = cheapest qualified, P5 = most expensive qualified) |
| `<model>` | Normalized model name | `gemini31pro`, `gpt53codex`, `qwen36plus`, `kimi25`, etc. |
| `<variant>` | Reasoning-effort variant | `auto`, `minimal`, `low`, `medium`, `high`, `max`, `local` (Ollama) |
| `<OUT>` | Output cost per 1M | Encoded (value × 100, no decimal point) |
| `<PPD>` | Performance per dollar | Encoded integer; `-` for local/free models |

### Pricing encoding

**Rule:** value × 100, decimal removed. Output-only because output dominates
real spend on coding workloads.

| Output $/M | Encoded |
| ---------- | ------- |
| $0.10 | `010` |
| $1.92 | `0192` |
| $3.00 | `0300` |
| $12.00 | `1200` |
| $15.00 | `1500` |
| $25.00 | `2500` |
| $30.00 | `3000` |

---

## Examples (current fleet, 2026-05)

### coding_simple (cheap tier, $5/M cap)

```bash
coding_simple-1-qwen36plus-max-o0195-ppd1395.sh    # Qwen3.6 Plus, $2.27/M total
coding_simple-2-kimi25-max-o0190-ppd1320.sh        # Kimi K2.5, $2.30/M total
coding_simple-3-glm5-max-o0192-ppd1311.sh          # Z.ai GLM 5, $2.52/M total
```

### coding_complex (no cost cap, premium tier)

```bash
coding_complex-1-gemini31pro-max-o1200-ppd-.sh     # Gemini 3.1 Pro, $14/M total
coding_complex-2-gpt53codex-max-o1400-ppd-.sh      # GPT-5.3-Codex, $15.75/M total
coding_complex-3-gpt54-max-o1500-ppd0124.sh        # GPT-5.4, $17.50/M total
coding_complex-4-opus46-max-o2500-ppd0077.sh       # Claude Opus 4.6, $30/M total
```

### fixing

```bash
fixing-1-gemini3flash-medium-o0300-ppd0619.sh      # Gemini 3 Flash Preview, $3.50/M
fixing-2-gemini31pro-max-o1200-ppd-.sh
```

### Dedup across roles (same model + same variant)

```bash
coding_complex&fixing-1-gemini31pro-max-o1200-ppd-.sh    # Wins P1 in both roles
coding_simple&coding_complex-1-...-o....sh               # Rare; same model in both tiers
```

---

## Source of truth

```
kilo_agents.db.agent_roles  ──────►  scripts/kilo_47_agents_final.json
                                     (regenerated automatically every time
                                      role_mapper.py applies new assignments)
                                            │
                                            ▼
                              generate_kilo_agents.py
                                            │
                                            ▼
                          ~/.traycer/cli-agents/*.sh
```

**Important:** the filename `kilo_47_agents_final.json` is historical — the
"47" is from an older snapshot count. The file is now refreshed on every
selector run and reflects whatever `agent_roles` contains at that moment.
Treat it as a live export, not a frozen snapshot.

The JSON schema is documented in
[`export_traycer_registry.py`](../../../scripts/kilo-benchmarks/export_traycer_registry.py).
Each role contains an ordered list of priority slots with the agent's
`api_id`, `kilo_id`, name, provider, input/output pricing, throughput, ELO,
tbench, weighted_coding, and capability flags.

---

## When does the JSON get rebuilt?

Automatically, on every path that mutates `agent_roles`:

1. **Manual run** — `python scripts/kilo-benchmarks/role_mapper.py` calls the
   exporter inline after applying assignments to the DB.
2. **Daily WSL pipeline** — `wsl_startup_hook.sh` runs
   `export_traycer_registry.py` as an explicit step after `role_mapper.py`
   (belt-and-suspenders).
3. **Direct export** — `python scripts/kilo-benchmarks/export_traycer_registry.py`
   for ad-hoc refresh without re-running the selector.

If you ever see the JSON `generated_at` more than 24 hours behind the
`agent_roles.assigned_at` column, the pipeline is broken — check
`scripts/kilo-benchmarks/cache/update.log`.

---

## Script generation

**Do NOT rename scripts manually.** Scripts are generated by:

```bash
python /opt/fabrik/scripts/generate_kilo_agents.py
```

This reads `agent_roles` directly from `kilo_agents.db` (no JSON intermediary)
and emits scripts to `~/.traycer/cli-agents/` with:

- **Role grouping** — files sort first by role label, then by priority
- **Dedup** — same model + variant across roles collapses to a single `&`-joined script
- **Orphan cleanup** — `.sh` files for agents no longer in `agent_roles` are removed
- **mtime stability** — unchanged files are touched but not rewritten

---

## Script structure

Each agent script:

1. Saves task context to `.droid/review-context/task-${TRAYCER_TASK_ID}.md` (unique per task)
2. Calls `kilo run` with the assigned model + variant
3. Uses `--format json --auto` for Traycer integration
4. Passes `$TRAYCER_PROMPT` from environment

---

## Migration map (old tier → new role)

| Old tier prefix | What it did | New equivalent |
| --------------- | ----------- | -------------- |
| `T1-Free` / `T2-Economy` | Cheapest models for prototyping | `coding_simple` P1–P3 |
| `T3-Standard` / `T4-Pro` | Daily workhorses | `coding_complex` P1–P3 |
| `T5-Expert` / `T6-Apex` | Premium / mission-critical | `coding_complex` P4–P5, `reviewing` P4–P5 |
| `T7-Specialist` (Codestral) | Task-specific variants | `documentation` / `fixing` / `testing` per the selector |

The old tier naming was capability-descending (best first); the new naming is
**cost-ascending** within each role (cheapest first). When migrating callers,
remember the priority direction has flipped.

---

## See Also

- `/opt/fabrik/scripts/kilo_47_agents_final.json` — current agent registry (auto-refreshed)
- `/opt/fabrik/scripts/kilo-benchmarks/export_traycer_registry.py` — exporter that writes the JSON
- `/opt/fabrik/scripts/kilo-benchmarks/role_configs.yaml` — per-role floors and caps
- `/opt/fabrik/scripts/kilo-benchmarks/classify_ticket.py` — runtime ticket → role classifier
- `/opt/fabrik/scripts/generate_kilo_agents.py` — script generator
- `/opt/fabrik/docs/workflows/KILO_AGENT_MANAGEMENT.md` — full architecture and selection pipeline
- `~/.traycer/cli-agents/` — generated agent scripts
