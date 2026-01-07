# Phase 10: The Deployment Orchestrator

**What is this?** A plan to make `fabrik apply` actually work from start to finish.

---

## The Problem

Right now, Fabrik has all the pieces but they don't work together:

- **cli.py** does some deployment stuff
- **provisioner.py** does other deployment stuff (but only for WordPress)
- **wordpress/deployer.py** does even more stuff

When you run `fabrik apply`, things break because these pieces don't talk to each other. You have to manually fix DNS, manually check if it worked, and if something fails... good luck.

---

## The Solution

Build ONE controller that handles everything:

```
You run: fabrik apply my-app.yaml

What happens automatically:
1. Check if the spec file is valid
2. Load secrets (from environment or generate them)
3. Set up DNS records
4. Deploy to Coolify
5. Wait and verify it's actually working
6. If anything fails → undo everything cleanly
```

---

## What We're Building

A new folder: `src/fabrik/orchestrator/` with these files:

| File | What it does |
|------|--------------|
| `states.py` | Tracks where we are: "deploying", "verifying", "failed", etc. |
| `context.py` | Holds all the info about the current deployment |
| `secrets.py` | Finds secrets from env vars, .env files, or creates new ones |
| `validator.py` | Checks if your spec file makes sense before deploying |
| `deployer.py` | Actually sends stuff to Coolify |
| `verifier.py` | Checks if the app is really running (HTTP, health checks) |
| `rollback.py` | Undoes everything if something goes wrong |
| `state_store.py` | Saves deployment history to a database |
| `locks.py` | Prevents two deploys from running at the same time |

---

## Key Decisions (All 4 AI Models Agreed)

### Where to store deployment state?
**SQLite database.** Not JSON files (they break with concurrent access).

### What to undo if deployment fails?
**Only what we created.** If we made a DNS record and then Coolify failed, we delete that DNS record. But we don't touch stuff we didn't create.

### How to handle secrets?
**This order:**
1. Look in environment variables first (for CI/CD)
2. Then look in .env file (for local dev)
3. If not found, auto-generate a 32-character random password

### How to know if we need to redeploy?
**Two checks:**
1. Is there already a deployment with this name?
2. Did the spec file change since last deploy?

If nothing changed, skip. If something changed, update.

---

## Timeline

| Phase | Days | What happens |
|-------|------|--------------|
| **0: Research** | 1 | Look at existing code, understand it |
| **1A: Foundation** | 2 | Build the state tracking and database |
| **1B: Validation** | 1.5 | Build the spec checker and secrets loader |
| **1C: Deploy** | 3 | Build the actual deployment logic |
| **1D: Rollback** | 2 | Build the "undo" system |
| **1E: Tests** | 2 | Write tests to make sure it works |
| **Total** | **11.5 days** | |

---

## How It Works (Step by Step)

### Step 1: You run the command
```bash
fabrik apply my-app.yaml
```

### Step 2: Validation
- Is the YAML file valid?
- Does the template exist?
- Are all required secrets available?

If anything is wrong → Stop and tell you what's missing.

### Step 3: Load Secrets
```
Looking for DATABASE_PASSWORD...
  ✓ Found in environment variable
Looking for API_KEY...
  ✗ Not found anywhere
  → Generated: Kj8mN2pQ5rT7vX9zA1bC3dE5fG7hJ9kL
```

### Step 4: Provision Infrastructure
- Create DNS record pointing to your server
- Set up Cloudflare if needed

### Step 5: Deploy to Coolify
- Push the docker-compose to Coolify
- Wait for build to finish
- If build fails → Go to Step 7 (Rollback)

### Step 6: Verify
- Is the app responding on HTTP?
- Does /health return 200?
- Is SSL working?

If checks fail → Go to Step 7 (Rollback)

### Step 7: Rollback (only if something failed)
- Delete the Coolify app we just created
- Delete the DNS record we just created
- Report what went wrong

### Step 8: Done
```
✓ Deployment complete
  URL: https://my-app.yourdomain.com
  Coolify: https://coolify.yourdomain.com/project/abc123
```

---

## What This Fixes

| Before | After |
|--------|-------|
| DNS setup is manual | DNS created automatically |
| No way to know if deploy worked | Automatic health checks |
| Failed deploy leaves garbage | Automatic cleanup |
| Running `apply` twice creates duplicates | Second run updates existing |
| Secrets passed manually with `-s KEY=VAL` | Auto-loaded from env/.env |
| No history of deployments | SQLite tracks everything |

---

## What We're NOT Building (Yet)

These are for later phases:

- **Web UI** — Command line only for now
- **Natural language specs** — "Deploy a Python API" → auto-generates YAML
- **Staging/Production environments** — One environment per spec for now
- **WordPress content automation** — This handles infrastructure only

---

## Success = When This Works

```bash
# Create a spec
fabrik new --template python-api my-api

# Deploy it (everything automatic)
fabrik apply my-api.yaml
# → DNS created
# → Deployed to Coolify
# → Verified working
# → Done in 2 minutes

# Change something and redeploy
vim my-api.yaml
fabrik apply my-api.yaml
# → Detects changes
# → Updates existing deployment
# → No duplicates

# If something breaks
fabrik apply broken-app.yaml
# → Deploy fails
# → Automatically cleans up DNS and Coolify
# → Shows you what went wrong
```

---

## Files

| File | Location |
|------|----------|
| Gap Analysis | `specs/FABRIK_CONSOLIDATED_GAP_ANALYSIS.md` |
| Technical Plan | `specs/FABRIK_CONDUCTOR_CONSENSUS_PLAN.md` |
| This Document | `docs/reference/phase10.md` |
