"""Pins `core/35-security-auth.md` to fastapi-user-auth's refresh-rotation contract (W-ec16d1f4).

fabrik-lib D-420 gave the vendored module two refresh-rotation modes and an opt-in `email` access-token claim
(`/opt/fabrik-lib/fastapi-user-auth/README.md` § Configuration; `fastapi_user_auth/settings.py`). The pack named only
the default's mechanism, so a project agent concluded a repeated refresh MUST sign the user out and hand-rolled a grace
window (fabrik-lib request 01M4AGEK7Y, trade-intelligence 01M48YX3N3). Four things can go false with no other gate red:

1. the Pattern A summary names the rotation mode (`delete` default, `grace` opt-in) and the client-visible
   `AUTH_EMAIL_CLAIM`;
2. the § Token Lifecycle rotation bullet states what each mode gives a retry and a replay, `grace`'s in-window cost
   and preconditions, and refuses a hand-rolled window;
3. that bullet carries nothing more: a clause appended to it ("enable it freely", "which is harmless") changes its force;
4. the session-end bullet says a `grace` session is a token family revoked whole, never one row.

The rotation bullet and the session-end sentence are this change's own text, so they are pinned WHOLE: any reword turns
this red and is re-pinned deliberately (round 1 of the review measured six force-changing mutants green under clause
pins). Line 25 is shared with other rules, so only its two clauses are pinned. Text is read emphasis-stripped and
whitespace-collapsed. The ellipsis in `DELETE … RETURNING` is U+2026, as the pack writes it: an editor typing `...`
turns this red.
"""

from __future__ import annotations

import re
from pathlib import Path

PACK = Path(__file__).resolve().parents[1] / ".windsurf" / "rules" / "core" / "35-security-auth.md"

ROTATION_BULLET = (
    "- Rotation mode is `AUTH_REFRESH_ROTATION` — set it, never hand-roll a grace window. "
    "By default `AUTH_REFRESH_ROTATION=delete`: delete-on-use through `DELETE … RETURNING`, so any second "
    "presentation of the same token — a concurrent refresh or a retry after a lost response — gets a generic 401. "
    "Opt-in, `AUTH_REFRESH_ROTATION=grace`: a retry inside `AUTH_REFRESH_ROTATION_GRACE_SECONDS` gets the same "
    "successor while that successor is still the family's live head (so does a thief: reuse detection is off "
    "inside the window) and a plain 401 once it is not, and an unexpired replay after the window revokes the "
    "token family (every session of the user under `AUTH_REFRESH_REUSE_SCOPE=user`). `grace` needs the module's "
    "schema columns, an `UPDATE` grant on `refresh_tokens` and a transactional (non-autocommit) session, and "
    "switching back to `delete` needs the README's cleanup `DELETE` first — read its costs in the module "
    "README's § Gotchas before enabling it."
)

GRACE_SESSION_SENTENCE = (
    "Under `grace` a session is a token family: revoke the whole family, never one row (as `POST /auth/logout` "
    "does when it is handed the refresh token), and a sessions screen lists only `rotated_at IS NULL` rows."
)


def _line(prefix: str) -> str:
    """The one pack line opening with `prefix` (after `- `), emphasis-stripped and whitespace-collapsed."""
    lines = [
        re.sub(r"\s+", " ", ln.replace("**", "")).strip()
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


def test_lifecycle_rotation_bullet_is_pinned_whole() -> None:
    assert _line("Rotation mode is `AUTH_REFRESH_ROTATION`") == ROTATION_BULLET


def test_lifecycle_session_end_names_grace_family() -> None:
    text = _line("Deleting the refresh token ends the session")
    assert text.startswith(
        "- Deleting the refresh token ends the session — no new access tokens issue. "
        f"{GRACE_SESSION_SENTENCE} For instant revocation of the outstanding access token"
    )
