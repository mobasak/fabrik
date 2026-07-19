# AFTER-EDIT: none
"""Mine the fabrik git history for code+doc co-change commits → the docs-grader corpus.

Scans a BOUNDED window of recent commits for those that touched BOTH a Markdown doc (modified — so a
``doc@parent`` stale version exists) AND a code/config file. For each, freezes a reconciliation triple:

    stale_doc     the doc as of the commit's PARENT   (``git show <parent>:<doc>``)
    diff          the code hunk of that commit        (``git diff <parent> <commit> -- <code…>``)
    ground_truth  the doc as of the commit            (``git show <commit>:<doc>``)  ← the human's real fix

plus a ready-to-send ``prompt`` (stale doc + code diff + reconcile instruction) and the human's actual
``ground_truth_patch`` (a canonical A+ reference). ~4–8 pairs are frozen to ``corpora/docs_pairs.json``,
deterministically (git traversal order), re-runnable via ``main()``.

Torch-free, stdout-only, no network. Reuses ``doc_reconcile._extract_tokens`` to keep only pairs whose
doc edit actually moved backtick SYMBOLS — so every frozen pair carries a real recall/precision signal.

    python mine_docs_corpus.py                 # freeze the corpus (DOCS_CORPUS_MAX_COMMITS / _TARGET env)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent  # scripts/kilo-benchmarks
sys.path.insert(
    0, str(SCRIPT_DIR.parent)
)  # scripts/ → doc_reconcile (one level up); IMPORT, never fork

import doc_reconcile as _dr  # noqa: E402

_REPO_ROOT = SCRIPT_DIR.parent.parent
_CORPUS = SCRIPT_DIR / "corpora" / "docs_pairs.json"
_GIT_TIMEOUT = 60  # bound every git call so a hung repo degrades instead of stalling the miner
_MAX_DOC_BYTES = 40_000  # keep the corpus small — skip a huge generated doc
_PROMPT_MAX_CHARS = 6000  # bound each prompt half so one giant diff can't blow the generation cost
_CODE_EXT = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".yaml",
    ".yml",
    ".json",
    ".sh",
    ".sql",
    ".toml",
    ".cfg",
    ".ini",
    ".html",
    ".css",
}
# A frozen corpus is committed + gate-scanned. Doc placeholders like `postgres://user:pass@host` are
# not real credentials, but the secret scanner can't tell — and JSON can't carry a `# noqa`. So drop
# any pair whose text carries a credential-in-URL so the corpus is deterministic AND gate-clean.
_CRED_IN_URL = re.compile(r"[a-zA-Z][a-zA-Z0-9+.\-]*://[^/\s:@]+:[^/\s@]+@")


def _has_secretish(text: str) -> bool:
    return bool(_CRED_IN_URL.search(text))


def _git(*args: str) -> str:
    """One read-only git call in the repo root; stdout only ('' on non-zero, never raises the miner)."""
    r = subprocess.run(
        ["git", *args], cwd=str(_REPO_ROOT), capture_output=True, text=True, timeout=_GIT_TIMEOUT
    )
    return r.stdout


def _blob(ref: str, path: str) -> str | None:
    """``git show <ref>:<path>`` — the file's content at a ref, or None if it did not exist there."""
    r = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT,
    )
    return r.stdout if r.returncode == 0 else None


def _changed_files(commit: str) -> list[str]:
    out = _git("show", "--name-only", "--format=", "--no-renames", commit)
    return [line.strip() for line in out.splitlines() if line.strip()]


def _build_prompt(doc: str, stale: str, code_diff: str) -> str:
    def _clip(text: str) -> str:
        return (
            text if len(text) <= _PROMPT_MAX_CHARS else text[:_PROMPT_MAX_CHARS] + "\n…(truncated)…"
        )

    return (
        f"The documentation file `{doc}` is STALE after a code change.\n\n"
        f"=== STALE DOC ===\n{_clip(stale)}\n\n"
        f"=== CODE CHANGE (unified diff) ===\n{_clip(code_diff)}\n\n"
        "Reconcile the doc so it matches the new code. Output ONLY a unified-diff patch to the doc "
        "(add/update/remove backtick-quoted `symbols` as the code change requires). Do not touch code."
    )


def mine(max_commits: int, target: int) -> list[dict]:
    """Walk up to ``max_commits`` recent commits; collect the first ``target`` code+doc co-change pairs
    with a real backtick-symbol delta. Deterministic: same repo state → same pairs (git traversal order)."""
    commits = [c for c in _git("log", "--format=%H", "-n", str(max_commits)).splitlines() if c]
    pairs: list[dict] = []
    for commit in commits:
        if len(pairs) >= target:
            break
        files = _changed_files(commit)
        docs = sorted(f for f in files if f.lower().endswith(".md"))
        code = sorted(f for f in files if Path(f).suffix.lower() in _CODE_EXT)
        if not docs or not code:
            continue
        parent = f"{commit}^"
        for doc in docs:
            stale = _blob(parent, doc)
            ground_truth = _blob(commit, doc)
            if stale is None or ground_truth is None or stale == ground_truth:
                continue  # doc added/deleted this commit, or unchanged text → no stale→fixed pair
            if len(stale.encode()) > _MAX_DOC_BYTES or len(ground_truth.encode()) > _MAX_DOC_BYTES:
                continue
            stale_tok = _dr._extract_tokens(stale)
            gt_tok = _dr._extract_tokens(ground_truth)
            if not (gt_tok - stale_tok) and not (stale_tok - gt_tok):
                continue  # no backtick-symbol added or removed → no recall/precision signal to grade
            code_diff = _git("diff", parent, commit, "--", *code)
            if not code_diff.strip():
                continue
            gt_patch = _git("diff", parent, commit, "--", doc)
            if any(_has_secretish(t) for t in (stale, ground_truth, code_diff, gt_patch)):
                continue  # doc/diff carries a credential-in-URL placeholder → skip (keeps corpus gate-clean)
            pairs.append(
                {
                    "commit": commit,
                    "doc_path": doc,
                    "stale_doc": stale,
                    "diff": code_diff,
                    "ground_truth": ground_truth,
                    "ground_truth_patch": gt_patch,
                    "prompt": _build_prompt(doc, stale, code_diff),
                }
            )
            break  # one doc per commit → diverse commits, not many docs from one mega-commit
    return pairs


def main(argv: list[str] | None = None) -> int:
    max_commits = int(os.getenv("DOCS_CORPUS_MAX_COMMITS", "600"))
    target = int(os.getenv("DOCS_CORPUS_TARGET", "6"))
    pairs = mine(max_commits, target)
    _CORPUS.parent.mkdir(parents=True, exist_ok=True)
    _CORPUS.write_text(json.dumps(pairs, indent=2))
    print(f"[mine_docs] froze {len(pairs)} code+doc pairs → {_CORPUS}")
    for p in pairs:
        print(f"  {p['commit'][:10]}  {p['doc_path']}")
    return 0 if pairs else 1


if __name__ == "__main__":
    raise SystemExit(main())
