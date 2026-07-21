## ⚠️ Codebase-grounding gate (BINDING — a finding is a claim about the LIVE code)

You are reviewing {{SCOPE}} with **existing code, a live DB, and real callers** — so every **finding** (and every "this is correct" you imply by NOT flagging) is a claim about that codebase, and it is **not validated until it is grounded in what exists TODAY** — not comments, not a label, not memory:

- **Open the real file** at every `path:line` you cite and confirm the symbol / signature / behavior is actually there — including the callers and callees the code touches (defects hide in the touching points you didn't open).
- **Read the real schema** (migration / model / `\d <table>`) for every table, column, enum, index, or FK the code reads or writes — the name is not its type, and a wrong-type assumption is a real bug.
- **Reproduce before you report** — a finding you cannot tie to a concrete failing path through the *actual* code (inputs → wrong output) is UNVALIDATED: prove it against the real code, or drop it (no theatre).
- The mirror also binds: an item you *cannot* disprove is NOT "probably fine" — every in-scope finding terminates FIXED or REFUTED (proof required), never silently passed.
