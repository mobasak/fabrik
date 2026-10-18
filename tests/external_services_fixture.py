"""The census-class fixture for the external-services inventory (plan 2026-10-18-plan-1, T02).

`census_rows()` returns rows in `inventory.load`'s shape at the counts the spec's census measured
(2026-10-18): 466 rows, 331 of them untriaged (category `?`); 17 real categories holding 115 rows
(the largest 24); 20 `unidentified` rows; cost `?` 351 / paid 49 / freemium 34 / free 19 / self-host 13;
status `?` 331 / active 113 / unidentified 20 / retired 1 / retiring 1; one fresh credit; 97 rows with
keys (88 categorised, 4 unidentified, 5 untriaged); 36 distinct projects; no unattributed key, renewal
or account. Five categorised rows carry a URL that fails the `https` gate. Shared with T04's browser
and height tests, so it imports nothing from the page layer.

`census_rows(**overrides)` replaces a field on EVERY row: a plain value is set as is, a callable is
called with the row's index and its result set (`census_rows(url=lambda i: ...)`).

Cobra check (D-253): the cheapest way to pass "the page copes with census scale" without the outcome is
a fixture that is census-sized but census-blind (all rows one category). This one is built from the
census counts, and its own test (`test_the_fixture_is_the_census`) recounts every one of them.
"""

# AFTER-EDIT: none

from __future__ import annotations

import copy

CENSUS_NOW = 1_790_000_000.0  # the instant the fixture's credit age is measured against
_HOUR = 3600.0

_REAL, _UNIDENTIFIED, _UNTRIAGED = 115, 20, 331
_REAL_SIZES = [24] + [6] * 11 + [5] * 5  # 17 categories, 115 rows
_COSTS = ["paid"] * 49 + ["freemium"] * 34 + ["free"] * 19 + ["self-host"] * 13  # the 115 real rows
PROJECTS = [f"proj-{i:02d}" for i in range(36)]


def _row(provider: str, category: str, cost: str, status: str, url: str) -> dict:
    return {
        "provider": provider,
        "category": category,
        "cost": cost,
        "url": url,
        "status": status,
        "keys": 0,
        "unattributed": 0,
        "projects": [],
        "account": "",
        "balance": None,
        "unit": "",
        "credit_at": None,
        "renews": "",
        "price": "",
    }


def census_rows(**overrides) -> list[dict]:
    rows: list[dict] = []
    n = 0
    for c, size in enumerate(_REAL_SIZES):
        for _ in range(size):
            status = "retiring" if n == 3 else "retired" if n == 4 else "active"
            url = "not a url" if n in (10, 20, 30, 40, 50) else f"https://real-{n:03d}.example"
            rows.append(_row(f"real-{n:03d}", f"cat-{c:02d}", _COSTS[n], status, url))
            n += 1
    for k in range(_UNIDENTIFIED):
        rows.append(_row(f"unid-{k:02d}", "unidentified", "?", "unidentified", "?"))
        n += 1
    for k in range(_UNTRIAGED):
        rows.append(_row(f"untr-{k:03d}", "?", "?", "?", f"https://untr-{k:03d}.example"))
        n += 1
    assert len(rows) == 466
    real, unid, untr = (
        rows[:_REAL],
        rows[_REAL : _REAL + _UNIDENTIFIED],
        rows[_REAL + _UNIDENTIFIED :],
    )
    for group_, count in ((real, 88), (unid, 4), (untr, 5)):
        for k, r in enumerate(group_[:count]):
            r["keys"] = 1
            r["projects"] = [PROJECTS[(k * 7 + 3) % 36]]
    for k in range(36):  # every project name appears at least once
        real[k]["projects"] = sorted({*real[k]["projects"], PROJECTS[k]})
    untr[0]["projects"] = PROJECTS[:9]  # the longest untriaged list: nine names
    real[0].update(balance=12.5, unit="usd", credit_at=CENSUS_NOW - 20 * _HOUR)
    for i, r in enumerate(rows):
        for key, value in overrides.items():
            r[key] = value(i) if callable(value) else copy.deepcopy(value)
    return rows
