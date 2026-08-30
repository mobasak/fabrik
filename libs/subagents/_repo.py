"""The ONE place that decides what a valid ``repo=`` is.

Every repo-anchored path in this package is ``Path(repo) / …`` — the ledger, receipts, outbox,
worktrees and ``<repo>/.env``. A BARE NAME joins to the current working directory, and because those
directories are created with ``parents=True`` the mistake is silent and self-concealing:
``fanout(repo="job-agent")`` called from inside ``/opt/job-agent`` creates
``/opt/job-agent/job-agent/.tmp/subagents`` and everything "works" while

  · flywheel rows land where ``check_subagent_flywheel`` never reads → the gate reports "ZERO pool
    runs recorded" and pushes the next agent toward a false NO-POOL declaration;
  · ``load_env(repo)`` reads a ``.env`` that is not there → keys silently missing;
  · the stray ``<name>/`` directory namespace-shadows ``import <name>``.

Swept fleet-wide from job-agent 01M0Z2B420: live ``<name>/<name>`` strays in fabrik (12 rows,
recovered), transdoc and tryton-crm. A recurring CALLER mistake, not one bad call.

⚠️ **Why this is a module and not a check at each seam.** The first version of this fix validated at
``arun_agents`` and ``fanout`` only, and a review immediately found the two doors it left open —
``load_env`` and ``env_status``, both PUBLIC exports the README documents as standalone-callable, and
one of them is literally symptom #2 above. Writing the predicate a third and fourth time at those
sites would have created four copies of one rule, which is the divergence class where a guard and its
sibling silently stop agreeing. One predicate, two entry points into it: :func:`resolve_repo` for
callers that may raise, :func:`repo_problem` for callers that may not.
"""

from __future__ import annotations

from pathlib import Path


def repo_problem(repo: str) -> str | None:
    """Return a human-readable problem with ``repo``, or ``None`` if it is usable.

    NON-RAISING — for callers whose contract forbids an exception (``load_env`` documents "Never
    raises", and ``env_status`` returns a report rather than throwing). They warn or report; they do
    not abort.
    """
    if not repo or not repo.strip():
        return (
            "repo is empty — it must be the project ROOT (e.g. '/opt/job-agent'). An empty string "
            "resolves to the current working directory, which would anchor the ledger, receipts and "
            "worktrees on whatever directory this process happens to be in."
        )
    if not Path(repo).expanduser().resolve().is_dir():
        return (
            f"repo={repo!r} is not an existing directory — pass the project ROOT "
            f"(e.g. '/opt/job-agent'). A bare name joined to CWD silently nests "
            f"<cwd>/<name>/.tmp and loses flywheel rows (job-agent 01M0Z2B420)."
        )
    return None


def resolve_repo(repo: str) -> str:
    """Resolve ``repo`` to an existing absolute directory, or raise ``ValueError`` naming the fix.

    ⚠️ The existence check must run BEFORE anything ``mkdir``s. The nested path does not exist at
    validation time, and that is precisely what makes the bare name detectable — deferring the check
    until after the first ``mkdir`` would validate the nest this exists to prevent.

    ⚠️ WHAT THIS BREAKS, stated rather than discovered later: a caller passing a repo root that does
    NOT yet exist used to have it created implicitly and now gets a ``ValueError``. That is the
    intended trade — an auto-created repo root is indistinguishable from this bug — but it IS a
    behavior change for any caller that relied on it.

    A caller pointing at a genuinely existing RELATIVE subdirectory is still honored, resolved to an
    absolute path so every anchor agrees even if the CWD moves mid-run. ``os.path.isabs()`` would
    have broken that caller, which is why the question asked here is existence, not absoluteness.
    """
    problem = repo_problem(repo)
    if problem is not None:
        raise ValueError(problem)
    return str(Path(repo).expanduser().resolve())
