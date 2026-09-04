## ⚠️ Codebase-grounding gate (BINDING — most runs review a project that ALREADY has code)

This command almost always runs against a project with **existing code, a live DB, and real callers** — so the dominant defect is a **{{SUBJECT}}** that reads well but the **actual codebase / schema contradicts**: {{EXAMPLES}}. **No {{SUBJECT}} is validated until it is grounded in what exists TODAY** — not its own wording, not a label, not memory:

- **Open the real file** at every cited `path:line` and confirm the symbol / signature / behavior is actually there — re-read it THIS run (a plausible-looking path is not proof).
- **Read the real schema** (migration / model / `\d <table>`) for every table, column, enum, index, or FK named — the name is not its type, and "should exist" is not "exists".
- **Trace the touching points** — the callers, callees, siblings, configs, and migrations each {{SUBJECT}} wires into — and confirm it agrees with them, not only with itself.
- **A negative claim about a FUNCTION'S BEHAVIOUR ("never returns X", "always raises") is proven by enumerating its CONTROL-FLOW exits — `grep -n 'return\|raise'` over the whole `def` — never by the branches the artifact happens to cite** (live escape: "route() never returns run_on_obat" survived three converged passes citing 3 of 4 return sites; the 4th falsified it in one grep).
- **A UNIVERSAL or NEGATIVE claim ("the only", "no other", "all N", "never", "the sole") needs the
  ENUMERATION that proves it — the command + the count (`grep -c … → 7`), never an example citation.**
  A `path:line` proves the example exists; it can never prove "only". (trade-intelligence 2026-08-29:
  "the only beats are X and Y" sat in an Evidence table through TWO converged passes; there were
  seven, all findable by one grep the evidence never ran.)
- ⚠️ **Verify against the layer the claim is ASSERTED AGAINST, not the layer that is convenient to
  open.** Two independent instances in one day, different surfaces, one shape: a claim about a
  WRITTEN artifact grounded on the dict BUILD site while a `pop` before the write removed the key
  (`01M1KN0H6JR...`), and a claim about a TOOL's behaviour grounded on the MODULE it calls — the
  registry and the raise were both real, but the tool wrapped them per-item and emitted an error
  row, so a defect reported as HIDDEN was self-surfacing and had a kept test pinning it
  (`01M1KZ28H3H...`, retracted by its own author). Both read as thorough because something real WAS
  checked. Name the layer your claim binds to, then open THAT one.
- **A constraint INHERITED from the brief, the session, or a prior report is a CLAIM to re-verify,
  never a datum** — it arrives pre-trusted, which is exactly why it escapes. (Same run: a "standing
  inherited gate red" named two files that no longer existed — worse than stale, it pre-licensed
  dismissing a real future red as "the inherited one".)
- **Never adjudicate from a truncated pipe.** `| head`-cut output is a SAMPLE presented as a total —
  count first (`wc -l`), then read; three misreadings in one measured session each traced to this.
- Any {{SUBJECT}} you cannot tie to a **freshly-read** `path:line` or schema object is **UNVALIDATED** and blocks the exit: fix it, or record it as a named BLOCKING unknown. Self-assertion never counts as grounding.

(This gate exists because a real run converged a spec asserting "reuse `api/auth.py` internal-token" that was never opened — the file had no such auth.)
