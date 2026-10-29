"""Pins `core/35-security-auth.md` to fastapi-user-auth's refresh-rotation contract (W-ec16d1f4).

fabrik-lib D-420 gave the vendored module two refresh-rotation modes and an opt-in `email` access-token claim
(`/opt/fabrik-lib/fastapi-user-auth/README.md` § Configuration; `fastapi_user_auth/settings.py`). The pack named only
the default's mechanism, so a project agent concluded a repeated refresh MUST sign the user out and hand-rolled a grace
window (fabrik-lib mail 01M4AGEK7Y, trade-intelligence 01M48YX3N3). Four things can go false with no other gate red:

1. the Pattern A summary names the rotation mode (`delete` default, `grace` opt-in) and the client-visible
   `AUTH_EMAIL_CLAIM`;
2. § Token Lifecycle names `delete` with its `DELETE … RETURNING` gate and the 401 ANY second presentation gets;
3. it names `grace` as the opt-in with what a retry and a replay get, the window's security cost, its preconditions,
   and refuses hand-rolling;
4. the session-end bullet says a `grace` session is a token family revoked whole, never one row.

Guards read emphasis-stripped, whitespace-collapsed text and pin the words that carry each clause's force
(`by default`, `Opt-in`, `never hand-roll`, `never one row`), so a reversed verb fails. The cheapest way past is keeping
the pinned phrases while a new sentence beside them says the opposite; no guard here reads such a sentence. The
ellipsis in `DELETE … RETURNING` is U+2026, as the module writes it: an editor typing `...` turns this red.
"""

from __future__ import annotations

import re
from pathlib import Path

PACK = Path(__file__).resolve().parents[1] / ".windsurf" / "rules" / "core" / "35-security-auth.md"


def _line(prefix: str) -> str:
    """The one pack line opening with `prefix` (after `- `), emphasis-stripped and whitespace-collapsed."""
    lines = [
        re.sub(r"\s+", " ", ln.replace("**", ""))
        for ln in PACK.read_text(encoding="utf-8").splitlines()
    ]
    hits = [ln for ln in lines if ln.removeprefix("- ").startswith(prefix)]
    assert len(hits) == 1, f"expected one line opening {prefix!r}, found {len(hits)}"
    return hits[0]


def test_pattern_a_summary_names_modes_and_email_claim() -> None:
    text = _line("The default for ALL new projects")
    assert (
        "atomic refresh-token rotation (mode `AUTH_REFRESH_ROTATION`: `delete` by default, `grace` opt-in "
        "— § Token Lifecycle)" in text
    )
    assert "an opt-in `email` access-token claim (`AUTH_EMAIL_CLAIM`, client-visible)" in text


def test_lifecycle_names_delete_default() -> None:
    text = _line("Rotation mode is `AUTH_REFRESH_ROTATION`")
    assert (
        "By default `AUTH_REFRESH_ROTATION=delete`: delete-on-use through `DELETE … RETURNING`"
        in text
    )
    assert (
        "any second presentation of the same token — a concurrent refresh or a retry after a lost response "
        "— gets a generic 401" in text
    )


def test_lifecycle_names_grace_opt_in() -> None:
    text = _line("Rotation mode is `AUTH_REFRESH_ROTATION`")
    assert "set it, never hand-roll a grace window" in text
    assert "Opt-in, `AUTH_REFRESH_ROTATION=grace`" in text
    assert "gets the same successor while that successor is still the family's live head" in text
    assert "so does a thief: reuse detection is off inside the window" in text
    assert (
        "an unexpired replay after it revokes the token family "
        "(every session of the user under `AUTH_REFRESH_REUSE_SCOPE=user`)" in text
    )
    assert "an `UPDATE` grant on `refresh_tokens`" in text
    assert "switching back to `delete` needs the README's cleanup `DELETE` first" in text


def test_lifecycle_session_end_names_grace_family() -> None:
    text = _line("Deleting the refresh token ends the session")
    assert (
        "Under `grace` a session is a token family: revoke the whole family, never one row" in text
    )
    assert "a sessions screen lists only `rotated_at IS NULL` rows" in text
