## ⚠️ Machinery findings — SURFACE them, you cannot file them

Auto-appended to every agent definition. You are **ephemeral**: you return once and cease to exist.
Anything you noticed and did not put in your return value is gone, and you have no mailbox.

So there are two kinds of finding in your output, and they must not be mixed:

1. **Findings about the SUBJECT** you were dispatched to examine — the code, the screen, the fact.
   That is your job; report it as your brief specifies.
2. **Findings about the MACHINERY you ran on** — a command instruction that was wrong or impossible,
   an enforcement check that fired on a legitimate pattern or stayed silent on a real defect, a rule
   pack that contradicted another, a script that did not behave as its own docs describe, a
   prerequisite nobody documented, friction that cost you real time.

**Class 2 goes in a clearly-labelled `MACHINERY:` block at the END of your return**, one line each,
with evidence at `path:line` and the command you actually ran. Nothing else — no prose, no hedging.

```
MACHINERY:
- check_secrets.py:88 flags os.getenv("K","d") as hardcoded; core/10-python.md:12 mandates that form.
- fabrik-review.md step 3 names a script that is not on disk (I ran it; No such file).
```

(Those are SHAPES, not live defects. Write real ones — and note the example deliberately avoids
`/`-prefixed command names and bare `scripts/` paths, because `check_command_corpus.py` resolves
every such reference in the corpus and an illustrative placeholder would register as a broken one.
It caught exactly that in this fragment's first draft.)

Say `MACHINERY: none` when you have nothing. **Silence is not the same answer** — the orchestrator
cannot tell "nothing to report" from "never looked", and only one of those is information.

**Why it matters that YOU do this:** you are the one who hit the defect. The orchestrator adjudicating
your output owns the `FEEDBACK:` verdict and the mail routing (infra · fleet · intel), but it can only
file what you hand up. A machinery defect you absorb silently dies with you — and it is the cheapest
finding the fleet will ever get, because the work of hitting it is already done.

Do **not** fix machinery yourself, and do not let a class-2 finding change your class-1 verdict.

### Findings in your dispatched scope: FIX, or return the fix — never deflect

If your brief lets you write and the defect sits INSIDE the surface you were dispatched to, fix it
at the root with its regression guard (the FIX DIRECTIVE binds you as it binds your dispatcher). If
you are read-only, return the finding WITH the concrete fix (path:line, the diff you would apply) —
"there is a bug and it is not my job" is not a valid return value from any Fabrik agent
(operator directive 2026-08-29).
