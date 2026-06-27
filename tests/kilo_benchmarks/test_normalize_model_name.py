"""Unit tests for `update_kilo_benchmarks.normalize_model_name`.

Phase 0 of the OpenRouter routing plan
(`docs/development/plans/2026-06-27-plan-openrouter-routing.md` §6.3).

Pure function; no DB, no network. Verifies the rewritten normalizer
strips OpenRouter routing suffixes so `<base>:free` model ids in
`kilo_agents.db.agents` join to their base-model leaderboard rows.

Pass 2 corrections embedded:
- `test_double_suffix_strips_both` (was `test_no_double_strip`) — the
  rewritten while-loop strips BOTH suffixes; the original comment
  ("should stop after one strip") was misleading.
- `test_suffix_only_at_end` — confirms middle-of-name routing tokens are
  left alone (OpenRouter spec, verified against /api/v1/models 2026-06-27).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts" / "kilo-benchmarks"
SCRIPT_PATH = SCRIPT_DIR / "update_kilo_benchmarks.py"

# update_kilo_benchmarks.py does sibling imports (`from scrape_benchmarks ...`)
# that only resolve when the script directory is on sys.path. Putting it on
# the path here mirrors what `wsl_startup_hook.sh` does via `cd $FABRIK_ROOT/
# scripts/kilo-benchmarks && $VENV_PYTHON update_kilo_benchmarks.py` and what
# `test_embedding_export_markdown.py` already does for the same reason.
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _import_module():
    spec = importlib.util.spec_from_file_location("update_kilo_benchmarks", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["update_kilo_benchmarks"] = mod
    spec.loader.exec_module(mod)
    return mod


M = _import_module()


def test_strips_free_suffix():
    """`:free` strip is the whole point of Phase 0."""
    assert M.normalize_model_name("deepseek/deepseek-v4-flash:free") == M.normalize_model_name(
        "deepseek/deepseek-v4-flash"
    )


def test_strips_each_known_suffix():
    """Every documented OpenRouter routing suffix collapses to the base."""
    for suf in (":free", ":nitro", ":floor", ":beta", ":online", ":thinking"):
        assert M.normalize_model_name(f"x/y{suf}") == "x/y", (
            f"suffix {suf!r} not stripped — got {M.normalize_model_name(f'x/y{suf}')!r}"
        )


def test_idempotent():
    """Calling normalize twice equals calling it once (pure-function contract)."""
    n1 = M.normalize_model_name("Qwen 3.5 Plus")
    n2 = M.normalize_model_name(n1)
    assert n1 == n2 == "qwen-3.5-plus"


def test_double_suffix_strips_both():
    """`x/y:free:nitro` collapses fully to `x/y` — the while loop iterates
    until no suffix matches (Pass 2A correction)."""
    assert M.normalize_model_name("x/y:free:nitro") == "x/y"
    assert M.normalize_model_name("x/y:nitro:free") == "x/y"
    # Triple-suffix sanity check
    assert M.normalize_model_name("x/y:free:nitro:online") == "x/y"


def test_suffix_only_at_end():
    """Routing suffixes in the MIDDLE of an id are NOT stripped — per
    OpenRouter spec (verified against /api/v1/models 2026-06-27), routing
    tokens only ever appear at the end of an id."""
    assert M.normalize_model_name("x/:free/y") == "x/:free/y"
    # `:free` is suffix-of-pathseg but not suffix-of-id → leave alone
    assert M.normalize_model_name("provider:free/model") == "provider:free/model"


def test_preserves_lowercase_and_dash_substitution():
    """Existing behavior (lowercase + space/underscore → hyphen) preserved."""
    assert M.normalize_model_name("My_Model NAME") == "my-model-name"
    # And in combination with suffix strip:
    assert M.normalize_model_name("Foo Bar:free") == "foo-bar"


def test_empty_and_no_op():
    """Edge cases the function must not crash on."""
    assert M.normalize_model_name("") == ""
    assert M.normalize_model_name("a") == "a"
    # No suffix to strip → just the lowercase+dash normalization
    assert M.normalize_model_name("Plain/Model") == "plain/model"


def test_none_guard():
    """Pass A Finding 1: normalize_model_name(None) used to raise
    AttributeError. After the fix, None is treated like empty string.

    The actual call site `update_agents_json()` reads `model_name` from
    `kilo_selected_agents.json` via `.get("model_name", "")` so today's
    catalog never passes None. But the JSON shadow file is
    operator-editable; a future `"model_name": null` would otherwise
    crash the whole pipeline."""
    assert M.normalize_model_name(None) == ""


def test_non_string_guard():
    """Pass B Finding 1: bare truthiness guard would silently accept
    falsy non-strings (0, False, [], {}) — `not 0 is True` so the bare
    `if not name` would return "" with no signal that the caller passed
    something wrong. After the tightened isinstance check, the same input
    still returns "" (no exception), but the intent is explicit: only
    string inputs proceed past the guard."""
    for non_string in (0, False, [], {}, (), 42, 3.14):
        assert M.normalize_model_name(non_string) == "", (
            f"Non-string {non_string!r} should normalize to '' (got "
            f"{M.normalize_model_name(non_string)!r})"
        )
