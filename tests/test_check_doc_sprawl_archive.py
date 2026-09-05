"""A long review rotates its older finding tables into `<stem>-review-archive.md` (/fabrik-review
§ Reporting, web-ecommerce-factory 01M1QT171DPCGA43Q0739WGGNP). The sprawl allowlist admitted only
`…-review.md`, so the first archive a project wrote would have been flagged as sprawl (review of
3833fb16, pass 1, executed against the regex)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "enforcement"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import check_doc_sprawl  # noqa: E402


def _allowed(rel: str) -> bool:
    return any(rx.search(rel) for rx in check_doc_sprawl.ALLOWED_PATTERNS)


def test_a_review_archive_is_allowlisted_beside_its_head():
    assert _allowed("docs/development/reviews/2026-09-05-x-review.md")
    assert _allowed("docs/development/reviews/2026-09-05-x-review-archive.md")


def test_other_names_under_reviews_are_still_sprawl():
    assert not _allowed("docs/development/reviews/2026-09-05-x-notes.md")
    assert not _allowed("docs/development/reviews/2026-09-05-x-archive.md")
