"""One-source CI generator: `.github/workflows/ci.yml` + `scripts/ci_local.sh`.

Root cause of the recurring project CI failures (see
docs/development/plans/2026-07-01-plan-fabrik-ci-parity.md): fabrik scaffolds emit no
CI workflow, so every project hand-rolls one that drifts from what `final_gate` (a
static gate) can check. The clean-room-only failures — test-DB URL format,
shared-DB test pollution, a missing Postgres extension — never surface locally.

This module renders BOTH the GitHub Actions workflow AND a local replica from a single
`CiConfig`, so they cannot diverge: same Postgres image, same *plain* connection-URL
format (the `+asyncpg` mismatch that broke trade-intelligence), same full-suite test
command. Run `scripts/ci_local.sh` before pushing test/dep/migration changes and a
green run means green CI.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The plain URL CI uses — NOT `postgresql+asyncpg://…`. The driver is chosen by the
# app at runtime; the test env var must be the bare libpq URL both here and in CI.
TEST_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/postgres"  # noqa: throwaway CI/localhost container credential (postgres:postgres), not a real secret
DEFAULT_TEST_CMD = "python -m pytest -q"
_PG_PLAIN = "postgres:16"
_PG_PGVECTOR = "pgvector/pgvector:pg16"  # postgres:16 + the vector extension


@dataclass(frozen=True)
class CiConfig:
    """The single source both renderers read (see module docstring)."""

    needs_database: bool = False
    db_extensions: tuple[str, ...] = ()  # e.g. ("pgvector",)
    test_cmd: str = DEFAULT_TEST_CMD
    needs_web: bool = False  # emit the web type-check + unit job
    extra_test_deps: tuple[str, ...] = field(default_factory=lambda: ("pytest", "pytest-asyncio"))

    def pg_image(self) -> str:
        return _PG_PGVECTOR if "pgvector" in self.db_extensions else _PG_PLAIN


def _test_dep_install(cfg: CiConfig) -> str:
    deps = " ".join(cfg.extra_test_deps)
    return f"pip install {deps}" if deps else ""


def render_ci_workflow(cfg: CiConfig) -> str:
    """GitHub Actions `ci.yml`. Mirrors render_ci_local exactly (parity-tested)."""
    lines: list[str] = [
        "# fabrik-managed — regenerate via fabrik scaffold; keep in sync with scripts/ci_local.sh.",
        "name: CI",
        "on:",
        "  push:",
        "  pull_request:",
        "jobs:",
        "  python:",
        "    name: python (ruff + pytest)",
        "    runs-on: ubuntu-latest",
    ]
    if cfg.needs_database:
        lines += [
            "    services:",
            "      postgres:",
            f"        image: {cfg.pg_image()}",
            "        env:",
            "          POSTGRES_PASSWORD: postgres",
            "        ports:",
            "          - 5432:5432",
            "        options: >-",
            "          --health-cmd pg_isready --health-interval 10s"
            " --health-timeout 5s --health-retries 5",
            "    env:",
            f"      TEST_DATABASE_URL: {TEST_DATABASE_URL}",
        ]
    lines += [
        "    steps:",
        "      - uses: actions/checkout@v4",
        "      - uses: actions/setup-python@v5",
        "        with:",
        '          python-version: "3.12"',
        "      - name: install",
        "        run: |",
        "          python -m pip install --upgrade pip",
        "          pip install -r requirements.txt",
    ]
    dep = _test_dep_install(cfg)
    if dep:
        lines.append(f"          pip install ruff {' '.join(cfg.extra_test_deps)}")
    lines += [
        "      - name: ruff",
        "        run: ruff check .",
        "      - name: pytest",
        f"        run: {cfg.test_cmd}",
    ]
    if cfg.needs_web:
        lines += [
            "  web:",
            "    name: web (type-check + unit)",
            "    runs-on: ubuntu-latest",
            "    steps:",
            "      - uses: actions/checkout@v4",
            "      - uses: actions/setup-node@v4",
            "        with:",
            '          node-version: "20"',
            "      - run: npm ci",
            "      - run: npm run type-check --if-present",
            "      - run: npm test --if-present",
        ]
    return "\n".join(lines) + "\n"


def render_ci_local(cfg: CiConfig) -> str:
    """`scripts/ci_local.sh` — reproduces render_ci_workflow in a local clean room.

    Fresh venv + the exact CI Postgres image + the full suite with the plain URL. The
    three clean-room-only failure classes surface here in ~2 min before pushing.
    """
    lines: list[str] = [
        "#!/usr/bin/env bash",
        "# fabrik-managed — regenerate via fabrik scaffold; keep in sync with"
        " .github/workflows/ci.yml.",
        "# Local clean-room replica of CI: catches env drift (test-DB URL format, shared-DB test",
        "# pollution, missing PG extension) that the static final_gate cannot. Run before pushing.",
        "set -euo pipefail",
        'cd "$(dirname "$0")/.."',
        "",
    ]
    if cfg.needs_database:
        lines += [
            f'PG_IMAGE="{cfg.pg_image()}"',
            'echo "[ci_local] starting $PG_IMAGE"',
            'CID=$(docker run -d --rm -e POSTGRES_PASSWORD=postgres -p 5432:5432 "$PG_IMAGE")',
            "trap 'docker stop \"$CID\" >/dev/null 2>&1 || true' EXIT",
            'until docker exec "$CID" pg_isready -U postgres >/dev/null 2>&1; do sleep 0.5; done',
            f'export TEST_DATABASE_URL="{TEST_DATABASE_URL}"',
            "",
        ]
    lines += [
        'VENV="$(mktemp -d)/venv"',
        'python -m venv "$VENV"',
        '"$VENV/bin/pip" install --quiet --upgrade pip',
        '"$VENV/bin/pip" install --quiet -r requirements.txt',
    ]
    if cfg.extra_test_deps:
        lines.append(f'"$VENV/bin/pip" install --quiet ruff {" ".join(cfg.extra_test_deps)}')
    # Run the test command through the fresh venv's interpreter. "python -m pytest -q"
    # -> "$VENV/bin/python" -m pytest -q (the interpreter is quoted, its args are not).
    if cfg.test_cmd.startswith("python "):
        test_line = '"$VENV/bin/python"' + cfg.test_cmd[len("python") :]
    else:
        test_line = cfg.test_cmd
    lines += [
        '"$VENV/bin/ruff" check .',
        test_line,
        'echo "[ci_local] OK — matches CI"',
    ]
    return "\n".join(lines) + "\n"


def ci_files(cfg: CiConfig) -> dict[str, str]:
    """Relative-path -> content for both artifacts (what the scaffolder writes)."""
    return {
        ".github/workflows/ci.yml": render_ci_workflow(cfg),
        "scripts/ci_local.sh": render_ci_local(cfg),
    }
