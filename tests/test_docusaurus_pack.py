"""The docusaurus pack's serve-stage mandates match how Docusaurus builds (W-47b72050, W-b786311d).

Fleet's static-runtime spec (D-472) routed seven conflicts to the pack owner: an SPA fallback that
masked every 404 as the landing page, a curl layer the nginx image already provides, a gzip
middleware the hub contract gives no public service, immutable caching on unhashed files, an
unstated image choice, a stale `-slim-bookworm` line in /fabrik-spec and a dead APPROVED_BASES.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / ".windsurf" / "rules" / "core" / "42-docusaurus.md"
SPEC_CMD = ROOT / "commands" / "_sources" / "fabrik-spec.md"
CHECK_DOCKER = ROOT / "scripts" / "enforcement" / "check_docker.py"
VERSIONS = ROOT / ".windsurf" / "rules" / "versions.yaml"


def _pack() -> str:
    return PACK.read_text(encoding="utf-8")


def test_missing_pages_answer_404_not_the_landing_page() -> None:
    text = _pack()
    assert "try_files $uri $uri.html $uri/index.html =404;" in text  # no bare-directory step
    assert "error_page 404 /404.html;" in text
    assert "absolute_redirect off;" in text  # relative redirects stay on Traefik's https
    for line in text.splitlines():
        if "try_files" in line:
            assert "/index.html;" not in line, line


def test_no_curl_layer_on_an_image_that_ships_curl() -> None:
    text = _pack()
    assert not re.search(r"apt-get install[^\n]*\bcurl\b", text)
    assert "has `curl` installed" not in text


def test_a_public_docs_site_carries_no_traefik_middleware() -> None:
    assert ".middlewares=" not in _pack()
    assert "gzip on;" in _pack()
    assert "gzip_vary on;" in _pack()


def test_the_health_check_snippets_say_which_page_they_need() -> None:
    """Both health-check snippets carry the root-page condition the prose states."""
    text = _pack()
    for marker in ("HEALTHCHECK --interval", "    healthcheck:"):
        i = text.index(marker)
        window = text[max(0, i - 200) : i + 200]
        assert "root page" in window, marker
    assert "application/wasm" in _pack()


def test_html_revalidates_instead_of_heuristic_caching() -> None:
    """Pages answer no-cache, so a deploy's new chunk hashes are seen on the next load."""
    block = _pack()[_pack().index("location / {") :]
    assert 'add_header Cache-Control "no-cache";' in block.split("}", 1)[0]


def test_immutable_caching_is_scoped_to_hashed_assets() -> None:
    """Every year-long cache line names `/assets/` itself or sits in a `location /assets/` block."""
    lines = _pack().splitlines()
    hits = [
        i
        for i, ln in enumerate(lines)
        if ("immutable" in ln and "Cache-Control" in ln) or "max-age=31536000" in ln
    ]
    assert hits, "the pack states its cache rule"
    for i in hits:
        if "/assets/" in lines[i]:
            continue
        enclosing = next(
            (lines[j] for j in range(i - 1, -1, -1) if lines[j].strip().startswith("location ")),
            "",
        )
        assert "location /assets/" in enclosing, lines[i]


UNPRIVILEGED_SENTENCE = (
    "`nginxinc/nginx-unprivileged` (every process as uid 101) is outside this mandate: the checklist "
    "below and the hub's project audit (`/opt/fabrik/scripts/audit_all_projects.py`, hub-only) accept "
    "only the stock image named above and grade the unprivileged image CRITICAL, so a project wanting "
    "it asks the hub to change this pack and the audit together (`python scripts/mail.py send --to "
    "fabrik --to-agent fleet --kind request`) — never its own Dockerfile alone."
)


def test_the_serve_image_choice_is_stated() -> None:
    """The stock image is the mandate and nginx-unprivileged is outside it (fleet 01M632SH6W).

    The pack once offered the unprivileged image as "the alternative" while its checklist and the
    audit graded it CRITICAL. The paragraph must say the alternative is outside the mandate, name
    what enforces that, and route a project to ask the hub — and the audit must still refuse the
    alternative, so a widened audit turns this red and the pack follows it.
    """
    para = next(ln for ln in _pack().splitlines() if "nginx-unprivileged" in ln)
    assert "The stock image is the deliberate choice" in para
    assert para.endswith(UNPRIVILEGED_SENTENCE), "the alternative's sentence is pinned whole"
    cited = re.search(r"`/opt/fabrik/(scripts/[\w./-]+\.py)`", para)
    assert cited, "the paragraph cites the hub audit by path"
    audit_path = ROOT / cited.group(1)
    assert audit_path.is_file(), audit_path
    spec = importlib.util.spec_from_file_location("_audit_for_42_pack", audit_path)
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    codename = audit._pinned_codename()
    assert audit._base_status(f"nginx:mainline-{codename}", "docusaurus") == "pinned"
    unprivileged = f"nginxinc/nginx-unprivileged:mainline-{codename}"
    assert audit._base_status(unprivileged, "docusaurus") == "noncompliant"  # graded critical


def test_command_sources_name_no_codename_the_registry_left() -> None:
    """/fabrik-spec and /fabrik-vision name the registry key, never a stale Debian codename."""
    m = re.search(r"^\s*debian_codename:\s*['\"]?(\w+)", VERSIONS.read_text(encoding="utf-8"), re.M)
    assert m, "versions.yaml carries debian_codename"
    codename = m.group(1)
    debian = re.compile(r"\b(buster|bullseye|bookworm|trixie|forky|duke)\b", re.I)
    for src in (SPEC_CMD, SPEC_CMD.with_name("fabrik-vision.md")):
        for stale in debian.findall(src.read_text(encoding="utf-8")):
            assert stale.lower() == codename, f"{src.name}: {stale}"
    spec_line = next(
        ln for ln in SPEC_CMD.read_text(encoding="utf-8").splitlines() if "No Alpine" in ln
    )
    assert "debian_codename" in spec_line, spec_line


def test_check_docker_carries_no_dead_base_list_or_stale_codename() -> None:
    text = CHECK_DOCKER.read_text(encoding="utf-8")
    assert "APPROVED_BASES" not in text
    assert "bookworm" not in text


def _nginx_block() -> str:
    text = _pack()
    start = text.index("server {\n")
    return text[start : text.index("\n}\n", start) + 2]


def _location(block: str, head: str) -> str:
    i = block.index(head)
    return block[i : block.index("}", i)]


def test_every_404_shape_answers_404_with_no_cache() -> None:
    """Executed in nginx:mainline-trixie (fleet 01M4D7K84A): an /assets/ directory answered 403,
    GET /404 served 404.html as a 200, and every 404 carried no Cache-Control — `add_header`
    alone skips 4xx. Each closing directive is pinned in its own location."""
    block = _nginx_block()
    assert "try_files $uri =404;" in _location(block, "location /assets/ {")
    assert "internal;" in _location(block, "location = /404 {")
    assert "return " not in block  # a 404 is answered only by the build's 404 page
    page = _location(block, "location = /404.html {")
    assert "internal;" in page and 'add_header Cache-Control "no-cache" always;' in page


def test_the_prose_names_no_403_for_a_missing_page() -> None:
    """Under this block a path with no page answers 404 everywhere; the prose said 403 twice."""
    for line in _pack().splitlines():
        assert not re.search(r"answers 403(?!,? never)", line), line
