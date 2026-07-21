## ⚠️ Codebase-grounding gate (BINDING — most runs review a project that ALREADY has code)

This command almost always runs against a project with **existing code, a live DB, and real callers** — so the dominant defect is a **{{SUBJECT}}** that reads well but the **actual codebase / schema contradicts**: {{EXAMPLES}}. **No {{SUBJECT}} is validated until it is grounded in what exists TODAY** — not its own wording, not a label, not memory:

- **Open the real file** at every cited `path:line` and confirm the symbol / signature / behavior is actually there — re-read it THIS run (a plausible-looking path is not proof).
- **Read the real schema** (migration / model / `\d <table>`) for every table, column, enum, index, or FK named — the name is not its type, and "should exist" is not "exists".
- **Trace the touching points** — the callers, callees, siblings, configs, and migrations each {{SUBJECT}} wires into — and confirm it agrees with them, not only with itself.
- Any {{SUBJECT}} you cannot tie to a **freshly-read** `path:line` or schema object is **UNVALIDATED** and blocks the exit: fix it, or record it as a named BLOCKING unknown. Self-assertion never counts as grounding.

(This gate exists because a real run converged a spec asserting "reuse `api/auth.py` internal-token" that was never opened — the file had no such auth.)
