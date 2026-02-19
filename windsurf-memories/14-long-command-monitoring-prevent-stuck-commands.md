# Long Command Monitoring - Prevent Stuck Commands

**Tags:** #commands #stuck #monitoring #rund #long_running

## Long Command Monitoring (MANDATORY)

**For commands expected to take >10 seconds, use detached execution:**

### Scripts Location
- Fabrik: `/opt/fabrik/scripts/rund`, `rundsh`, `runc`, `runk`
- New projects: `scripts/rund`, `rundsh`, `runc`, `runk` (from scaffold)

### Usage
```bash
# Start detached (exec mode - safe)
./scripts/rund npm install
# Returns: JOB=.tmp/jobs/job_xxx PID=xxx SID=xxx

# Start detached (shell mode - pipes allowed)
./scripts/rundsh 'npm test && npm build'

# Check status (every 15-30s)
./scripts/runc .tmp/jobs/job_xxx

# Kill if stuck (90s no progress)
./scripts/runk .tmp/jobs/job_xxx
```

### Stuck Detection Rule
STUCK = 90 seconds where ALL are true:
- LOG bytes unchanged
- cputime unchanged
- PROCS count unchanged

Action: `runk` → retry with `--verbose`

### When to Use
| Command Type | Use rund/rundsh? |
|--------------|------------------|
| npm install, pip install | ✅ Yes |
| docker build | ✅ Yes |
| pytest (large suite) | ✅ Yes |
| git clone (large repo) | ✅ Yes |
| Quick commands (<10s) | ❌ No, use normal |

### Job files stored in
`.tmp/jobs/` (gitignored, project-local)
