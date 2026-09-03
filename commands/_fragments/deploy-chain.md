## The deploy chain — ORDER and REPO (this block is shared by every command in it)

Six steps, one operator gate, two repos. **Run each step where its row says** — a step run in the wrong
repo either cannot see its inputs (a project has no fleet creds, no `fabrik` CLI, no spec) or writes its
output where the next step will never read it. Every command below ends by naming the next one.

| # | command | runs in | produces / consumes |
|---|---|---|---|
| 1 | `/fabrik-deploy-checklist` | the **PROJECT** (`/opt/<project>`, its own venv) | authors + freezes `scripts/verify_prod_parity.py` → `FROZEN v<N>` (project-owned, committed) |
| 2 | `/fabrik-release` | the **PROJECT** | release readiness; its VPS path BLOCKs on a `DRAFT` contract; prints the Gate-2 handoff |
| 3 | `/fabrik-deploy-plan` | the **HUB** (`/opt/fabrik`) for VPS surfaces · the **PROJECT** for store surfaces (mobile / extension / desktop) | `docs/development/plans/YYYY-MM-DD-plan-deploy-<service>.md` at `DRAFT`; reads the project's `--header` (`FROZEN v<N>`, `container_leg_service`) as a precondition |
| 4 | `/fabrik-deploy-plan-review` | the same repo as the plan (HUB for VPS · PROJECT for stores) | the plan at `CONVERGED` |
| — | **Gate 2** | the operator | an explicit "go" — nothing auto-chains across it |
| 5 | `/fabrik-deploy` | the same repo as the plan (HUB for VPS · PROJECT for stores) — operator-dispatched only | the runbook executed, the battery green, the plan at `EXECUTED`; re-reads the `--header` pre-flip |
| 6 | `/fabrik-deploy-verify` | the **HUB** (VPS surfaces; store surfaces hand back at Phase 0 with the provenance verdict) | `DEPLOY CONFIRMED` / `VERIFICATION FAILED` / `UNVERIFIED` — executes the FROZEN contract, one leg per site |

Upstream of step 1: `/fabrik-features` REFRESH (the shipped inventory the contract cross-checks). A version
BUMP of the contract after step 6 re-runs step 6 only.
