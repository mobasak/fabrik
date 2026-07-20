# Kilo Troubleshooting Guide

**Last Updated:** 2026-05-20

Quick solutions for common Kilo CLI issues.

---

## CLI Issues

### Kilo CLI not found

**Symptom:** `kilo: command not found`

**Root cause:** WSL may find the Windows-side kilo (`/mnt/c/.../npm/kilo`) first, which errors on Linux. The real binary is at `/usr/local/bin/kilo`.

```bash
# Check what's found
which kilo

# If it points to /mnt/c/..., use the full path
/usr/local/bin/kilo --version   # Should show 7.3.1

# Or fix PATH priority (add to ~/.bashrc)
export PATH="/usr/local/bin:$PATH"
```

If not installed at all:
```bash
sudo npm install -g @kilocode/cli
```

### Agent script not executable

```bash
chmod +x ~/.traycer/cli-agents/*.sh
```

### Model not available

```bash
# Refresh model cache
kilo models --refresh

# Test specific provider connectivity
kilo roll-call openai
kilo roll-call anthropic
```

---

## Review Script Issues (`kilo_code_review.py`)

### Timeout during review

**Symptom:** Review hangs or times out.

The script uses **liveness-based monitoring**, not blind timeouts. It kills only if truly idle (no stdout/stderr output).

```bash
# Increase idle timeout (default 120s — no output for this long = hung)
export KILO_IDLE_TIMEOUT=300

# Increase hard timeout (default 1200s — absolute max)
export KILO_HARD_TIMEOUT=2400
```

### Empty or truncated response

**Symptom:** Claude responds with "Shift note saved" or partial text.

**Root cause:** `--output-format text` drops content when the agent interleaves tool calls with text. Use `--output-format json` and parse the `result` field.

This is already fixed in `bot.py` (VPS sysadmin) and `kilo_code_review.py`. If you're calling kilo directly:

```bash
# Bad — loses content
kilo run --output-format text "status"

# Good — full response in result field
kilo run --output-format json "status" | python3 -c "import json,sys; print(json.load(sys.stdin)['result'])"
```

### `docker events` hanging forever

**Symptom:** Kilo spawns `docker events` subprocess that never exits, causing 5-minute timeouts.

**Root cause:** `docker events` without `--until now` is a streaming command that blocks forever.

**Fix:** Always use `--until now`:
```bash
# Bad — streams forever
sudo docker events --since 5m --filter event=oom

# Good — returns immediately
sudo docker events --since 5m --until now --filter event=oom
```

### Infinite loop in pre-commit

**Symptom:** `ruff --fix` keeps modifying same files.

```bash
python scripts/kilo_code_review.py review <files> --skip-precommit
```

### Session continuity lost

**Symptom:** `--session continue` not finding previous session.

```bash
# List existing review sessions
ls .droid/reviews/

# Start fresh (omit --session)
python scripts/kilo_code_review.py review <files>

# Session requires tracked-review-id
python scripts/kilo_code_review.py review <files> \
  --session continue --tracked-review-id "feat-xyz"
```

### "Kilo incomplete/garbled response" retry

**What it means:** Upstream Kilo returned incomplete JSONL (no `step_finish` event).

**What happens automatically:**
1. Script detects incomplete response
2. Waits `2^attempt` seconds (exponential backoff)
3. Retries with same prompt (max 3 attempts)

**If persistent:** Check network stability, try different model, reduce batch size.

---

## Debug Mode

```bash
export KILO_DEBUG=1
export KILO_TRACK_COST=1

# Shows: agent name, model, prompt length, task ID, timeout, exit codes, duration
```

---

## Cost Tracking

```bash
# Summary
python scripts/kilo_code_review.py stats

# By model (find expensive patterns)
python scripts/kilo_code_review.py stats --by-model

# By file type
python scripts/kilo_code_review.py stats --by-filetype --days 7

# Kilo built-in stats
kilo stats
```

**Log locations:**
- Session logs: `.droid/kilo_usage.jsonl`
- Review sessions: `.droid/review_sessions.jsonl`
- Metrics: `.droid/kilo_metrics.jsonl`

---

## Agent Health

```bash
# Check all agent scripts (executable, shebang, syntax)
bash scripts/kilo_agent_health.sh

# Regenerate from DB
python scripts/generate_kilo_agents.py

# Dry-run first
python scripts/generate_kilo_agents.py --dry-run
```

---

## Model Routing Issues

Model selection is automated via the pipeline. See [KILO_AGENT_SELECTION_GUIDE.md](KILO_AGENT_SELECTION_GUIDE.md) for current roster, quality floors, and how to override.

Manual override:
```bash
export KILO_REVIEW_MODEL=kilo/anthropic/claude-sonnet-4.6
```

---

## Exit Codes

| Code | Meaning | Action |
|---|---|---|
| 0 | Success | — |
| 1 | Review failed (issues remain) or error | Fix issues or check config |
| 124 | Timeout | Increase `KILO_IDLE_TIMEOUT` / `KILO_HARD_TIMEOUT` |

---

## Getting Help

1. Enable debug: `KILO_DEBUG=1`
2. Check agent health: `bash scripts/kilo_agent_health.sh`
3. Check review sessions: `.droid/reviews/`
4. Test model connectivity: `kilo roll-call <provider>`
5. Check kilo version: `/usr/local/bin/kilo --version`

---

## See Also

- [KILO_CLI_REFERENCE.md](KILO_CLI_REFERENCE.md) — Command reference + programmatic patterns
- [KILO_PERFORMANCE_TUNING.md](KILO_PERFORMANCE_TUNING.md) — Token and speed optimization
- [KILO_REVIEW_GUIDE.md](KILO_REVIEW_GUIDE.md) — Review pipeline details
- [KILO_AGENT_SELECTION_GUIDE.md](KILO_AGENT_SELECTION_GUIDE.md) — Model routing and blocking
