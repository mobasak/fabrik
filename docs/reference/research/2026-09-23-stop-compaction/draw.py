"""Draw the judged samples from the 2026-09-23 miner run's reservoirs (seed 923) — reproducible,
byte-for-byte against samples.sha256 (spec 2026-09-23-stop-and-compaction-enforcement-design
§ Derivations). The MINE itself is not re-runnable to the same bytes — it reads the live, growing
transcript tree with no upper time bound — so this draws from THAT run's box-local reservoir files
(samples2.json, compactions2.json), never from a fresh mine; a re-run from scratch is a new
measurement (A-O37).

Writes sample-opdec.json (80), sample-context.json (40) and sample-compact.json (40) into OUT_DIR. Those files hold raw
transcript text and are never committed; samples.sha256 pins what the 2026-09-23 judges read.
"""
import json
import random
import sys
from pathlib import Path

src = Path(sys.argv[1] if len(sys.argv) > 1 else ".")  # the directory holding mine.py's samples2.json + compactions2.json
out = Path(sys.argv[2] if len(sys.argv) > 2 else ".")
rng = random.Random(923)
s = json.loads((src / "samples2.json").read_text())
c = json.loads((src / "compactions2.json").read_text())
cc = [x for x in c if x["first_after"] and x["summary_tail"]]
for name, rows in (("opdec", rng.sample(s["next_opdec"], 80)), ("context", rng.sample(s["context_excuse"], 40)), ("compact", rng.sample(cc, 40))):
    for i, r in enumerate(rows):
        r["id"] = f"{name[0].upper()}{i + 1:02d}"
    (out / f"sample-{name}.json").write_text(json.dumps(rows, indent=1))
