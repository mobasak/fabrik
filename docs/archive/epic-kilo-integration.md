# Traycer Epic + Kilo CLI Integration Guide

**Last Updated:** 2026-06-16
**Purpose:** Enable Traycer Epic to consult Kilo CLI agents (premium tiers) during planning to create flawless WordPress deployment specs and tickets.

---

## Current Architecture

### Traycer Epic (Your Planning Agent)
**Location:** Windsurf Extension (Windows 11 Pro)
**Mode:** Epic Mode (Specs + Tickets)
**Interface:** Chat window in Traycer
**Database:** `~/.traycer/app-assets.db` (SQLite)
**Chat History:** `~/.traycer/epic-chat-transcripts/`

### Kilo CLI (Review/Planning Agent)
**Location:** `/opt/fabrik/scripts/kilo_code_review.py`
**Available Agents:** ask, plan, orchestrator, code, debug, general, summary
**Tier System:** Free → Economy → Balanced → Strong → Prime
**Cost Range:** $0 (Free) → $5 (Prime) per call

### Current Integration Point
**Wrapper:** `/opt/fabrik/scripts/traycer_agent_review.py`
- Used by Traycer CLI agents for code review
- NOT used by Epic Mode (different workflow)

---

## Kilo CLI Agent Capabilities

### Available Agents (for Epic Use)

| Agent | Best For | Recommended Tier |
|-------|----------|------------------|
| **plan** | Architecture planning, strategy | Strong/Prime |
| **orchestrator** | Multi-step workflows, coordination | Strong/Prime |
| **ask** | Q&A, clarification, reasoning | Balanced/Strong |
| **general** | General analysis | Economy/Balanced |

### Tier Models & Costs

**Premium Tiers (Recommended for Epic Planning):**

**Strong Tier (~$3/call):**
- `kilo/anthropic/claude-sonnet-4.6`
- `kilo/openai/gpt-5.3-codex`
- `kilo/google/gemini-3.1-pro-preview`

**Prime Tier (~$5/call):**
- `kilo/anthropic/claude-opus-4.6`
- `kilo/openai/gpt-5.2-pro`

---

## How Epic Should Call Kilo Agents

### Direct Shell Command (Recommended)

Epic can execute Kilo CLI directly from chat window:

```bash
# From Traycer Epic chat, run:
python /opt/fabrik/scripts/kilo_code_review.py review \
  --plan "WordPress deployment for ocoron.com: review architecture spec" \
  --review-agent plan \
  --strategy premium \
  --model kilo/anthropic/claude-opus-4.6 \
  --file /opt/fabrik/specs/sites/ocoron.com.yaml \
  --output json
```

**Parameters Epic Should Use:**

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `--plan` | Epic Brief + Context | What you want Kilo to review/plan |
| `--review-agent` | `plan` or `orchestrator` | Agent type |
| `--strategy` | `premium` or `critical` | Start at Strong/Prime tier |
| `--model` | `kilo/anthropic/claude-opus-4.6` | Force specific model (optional) |
| `--file` | Spec YAML path | Attach relevant files |
| `--output` | `json` | Get structured response |

---

## Workflow: Epic Consulting Kilo for Planning

> **Note (2026-06-16):** The WordPress deployment example below is illustrative.
> WordPress site creation + deployment is a **separate project** at `/opt/wpf`
> (the `wpf` CLI) — it is no longer part of Fabrik (`fabrik wp` and
> `src/fabrik/wordpress/` were removed). The Epic↔Kilo consultation pattern shown
> here applies identically to any project.

### Step 1: Epic Generates Initial Spec Draft

Epic creates Epic Brief + Specs based on user requirements:
- Epic Brief (50 lines)
- Spec artifacts (architecture, pages, plugins)
- Initial ticket breakdown

### Step 2: Epic Consults Kilo (Premium Tier)

**Epic runs:**

```bash
python /opt/fabrik/scripts/kilo_code_review.py review \
  --plan "Review WordPress deployment architecture for ocoron.com. Check: 1) Security hardening, 2) Container isolation, 3) Backup strategy, 4) Scalability for multiple sites" \
  --review-agent orchestrator \
  --strategy premium \
  --file /opt/wpf/specs/sites/ocoron.com.yaml \
  --file /opt/wpf/templates/base/compose.yaml.j2 \
  --output json
```

**Kilo Response (JSON):**
```json
{
  "verdict": "PASS",
  "summary": "Architecture review complete. Found 3 improvement areas.",
  "issues": [
    {
      "severity": "MAJOR",
      "category": "SECURITY",
      "file": "ocoron.com.yaml",
      "lines": "45-50",
      "why": "Missing WP_ENVIRONMENT_TYPE definition for production",
      "fix_hint": "Add deployment.environment: production to spec"
    }
  ],
  "cost": 3.24,
  "model": "kilo/anthropic/claude-sonnet-4.6"
}
```

### Step 3: Epic Updates Spec Based on Kilo Feedback

Epic applies Kilo's recommendations:
- Fix MAJOR issues immediately
- Add MINOR improvements
- Update Epic Brief with rationale
- Regenerate tickets if architecture changed

### Step 4: Epic Re-Consults Kilo (Verification)

```bash
python /opt/fabrik/scripts/kilo_code_review.py review \
  --plan "Verify fixes applied. Previous issues: WP_ENVIRONMENT_TYPE missing, restart policy needed." \
  --review-agent ask \
  --strategy standard \
  --file /opt/fabrik/specs/sites/ocoron.com.yaml \
  --output json
```

### Step 5: Epic Presents Finalized Plan to User

Epic shows:
- ✅ Updated Epic Brief
- ✅ Updated Specs (with Kilo improvements)
- ✅ Updated Tickets
- 💰 Kilo consultation cost: $3.24 (Strong tier, 2 calls)
- 📊 Improvements applied: 3 issues fixed

---

## Cost Management

### Recommended Strategy for Epic

**Per WordPress Site Planning:**
- Initial architecture review: 1 call @ Strong tier (~$3)
- Verification pass: 1 call @ Balanced tier (~$0.50)
- **Total:** ~$3.50 per site

**Monthly Budget:**
- Traycer Pro+: $50 credits/month
- Estimated: ~14 WordPress sites/month with Kilo consultation
- Or mix: 5 sites with Kilo + 39 regular YOLO phases

### When to Use Which Tier

| Epic Task | Kilo Agent | Tier | Cost |
|-----------|------------|------|------|
| **Initial architecture review** | orchestrator | premium (Strong) | ~$3 |
| **Security audit** | plan | premium (Strong) | ~$3 |
| **Spec clarification** | ask | standard (Balanced) | ~$0.50 |
| **Quick sanity check** | general | economy | ~$0.02 |
| **Final verification** | ask | standard (Balanced) | ~$0.50 |

---

## Instructions for Epic

### What Epic Should Tell Users in Chat

When Epic consults Kilo, show this in chat:

```
🤖 Consulting Kilo (Premium Tier) for architecture review...

Running: kilo orchestrator @ Strong tier
Context: ocoron.com WordPress deployment spec
Estimated cost: ~$3.00

[Wait for response...]

✅ Kilo Review Complete
- Verdict: PASS with improvements
- Issues found: 3 (2 MAJOR, 1 MINOR)
- Cost: $3.24

Applying Kilo recommendations:
1. Add WP_ENVIRONMENT_TYPE to deployment config
2. Set explicit restart policy for database
3. Add backup volume mount

Updating Epic Brief and Tickets...
```

---

## Example: Epic Chat Interaction

**User:** "Create WordPress deployment plan for ocoron.com"

**Epic (Traycer):**
```
📋 Creating WordPress deployment plan for ocoron.com...

Step 1: Requirements Analysis
✅ Analyzed requirements:
- Domain: ocoron.com
- Site type: Professional services (company preset)
- Multi-language: English + Turkish
- Services: 8 consulting services

Step 2: Consulting Kilo (Architecture Review)
🤖 Running: kilo orchestrator @ premium tier
📄 Context: ocoron.com.yaml, compose.yaml.j2
⏳ Estimated: ~$3.00

[45 seconds later...]

✅ Kilo Review Complete ($3.24)
- Architecture: PASS with improvements
- Issues: 3 (2 MAJOR, 1 MINOR)

Improvements Applied:
1. ✅ Added WP_ENVIRONMENT_TYPE=production
2. ✅ Set db restart policy: unless-stopped
3. ✅ Added backup volume mount

Step 3: Verification Pass
🤖 Running: kilo ask @ standard tier (~$0.50)

✅ Verification PASS ($0.48)
- All issues resolved
- No new concerns

📊 Final Plan Summary:
- Epic Brief: 48 lines
- Specs: 3 files (deployment, theme, content)
- Tickets: 12 tickets (7 MVP, 5 stretch)
- Kilo Cost: $3.72 (2 consultations)
- Quality Score: PRODUCTION_READY

Would you like to proceed with this plan?
```

---

## Files Epic Needs Access To

### Required Paths (WSL)
```bash
# Kilo CLI wrapper
/opt/fabrik/scripts/kilo_code_review.py

# WordPress specs (separate wpf project)
/opt/wpf/specs/sites/*.yaml

# WordPress templates (separate wpf project)
/opt/wpf/templates/base/

# WordPress source for context (separate wpf project)
/opt/wpf/src/wpf/

# Documentation (for reference, separate wpf project)
/opt/wpf/docs/
```

### Environment Variables (Epic Should Check)
```bash
# Kilo defaults
KILO_DEFAULT_STRATEGY=premium  # Force premium tier for Epic
KILO_MAX_COST=10.0             # Budget cap per consultation
KILO_VERIFY_HIGH_RISK=true     # Always verify critical paths

# Traycer paths
TRAYCER_HOME=~/.traycer/
```

---

## Summary: What to Tell Epic

**Paste this into Epic chat:**

```
You are Traycer Epic managing WordPress deployment planning.

When creating or updating WordPress deployment specs/tickets, you MUST:

1. Generate initial draft (Epic Brief + Specs)

2. Consult Kilo CLI for architecture review:
   python /opt/fabrik/scripts/kilo_code_review.py review \
     --plan "[Epic Brief + specific questions]" \
     --review-agent orchestrator \
     --strategy premium \
     --file [spec.yaml paths] \
     --output json

3. Parse Kilo JSON response, apply recommendations (fix MAJOR/BLOCKER)

4. Run verification pass:
   python /opt/fabrik/scripts/kilo_code_review.py review \
     --plan "Verify fixes: [list issues from step 2]" \
     --review-agent ask \
     --strategy standard \
     --file [spec.yaml] \
     --output json

5. Present final plan:
   - Updated Epic Brief
   - Updated Specs
   - Generated Tickets
   - Kilo cost: ~$3.50
   - Quality improvements applied

Available Kilo agents:
- orchestrator (architecture planning)
- plan (strategy/approach)
- ask (clarification/reasoning)

Premium tier models:
- kilo/anthropic/claude-opus-4.6 (Prime, ~$5)
- kilo/anthropic/claude-sonnet-4.6 (Strong, ~$3)

Budget: ~$3.50 per WordPress site (2 Kilo calls)
```
