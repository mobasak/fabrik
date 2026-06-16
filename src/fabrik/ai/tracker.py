import sqlite3
from datetime import datetime
from pathlib import Path


class UsageTracker:
    def __init__(self, database_path: str | None = None):
        if database_path is None:
            self.database_path = str(Path.home() / ".fabrik" / "ai_usage.db")
        else:
            self.database_path = database_path
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.database_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    tokens_in INTEGER NOT NULL,
                    tokens_out INTEGER NOT NULL,
                    cost_usd REAL NOT NULL,
                    duration_ms INTEGER,
                    project TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON ai_usage(timestamp)")
            # Phase 1 GPU rental: add a `kind` column to discriminate LLM vs GPU
            # rentals (both flow through this tracker). Older rows default to
            # 'llm'. Idempotent: ALTER TABLE on every init is harmless once added.
            existing_cols = {
                row[1] for row in conn.execute("PRAGMA table_info(ai_usage)").fetchall()
            }
            if "kind" not in existing_cols:
                conn.execute("ALTER TABLE ai_usage ADD COLUMN kind TEXT DEFAULT 'llm'")
            if "workload" not in existing_cols:
                # Free-text tag (e.g. "fine-tune-tinyllama", "smoke-test")
                conn.execute("ALTER TABLE ai_usage ADD COLUMN workload TEXT")
            if "session_id" not in existing_cols:
                # Links a row to a gpu_state session
                conn.execute("ALTER TABLE ai_usage ADD COLUMN session_id TEXT")
            conn.commit()

    def get_usage(self, month: str | None = None, project: str | None = None) -> dict:
        query = "SELECT * FROM ai_usage WHERE 1=1"
        params: list[str] = []
        if month:
            query += " AND timestamp LIKE ?"
            params.append(f"{month}%")
        if project:
            query += " AND project = ?"
            params.append(project)

        with sqlite3.connect(self.database_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()

        total_cost = 0.0
        total_tokens_in = 0
        total_tokens_out = 0
        total_calls = len(rows)
        by_model: dict = {}

        for row in rows:
            model = row["model"]
            cost = row["cost_usd"]
            tokens_in = row["tokens_in"]
            tokens_out = row["tokens_out"]

            total_cost += cost
            total_tokens_in += tokens_in
            total_tokens_out += tokens_out

            if model not in by_model:
                by_model[model] = {"calls": 0, "cost": 0.0, "tokens_in": 0, "tokens_out": 0}

            by_model[model]["calls"] += 1
            by_model[model]["cost"] += cost
            by_model[model]["tokens_in"] += tokens_in
            by_model[model]["tokens_out"] += tokens_out

        return {
            "total_calls": total_calls,
            "total_cost": total_cost,
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "by_model": by_model,
        }

    def today_total(self, kind: str | None = None) -> float:
        """Return today's total cost_usd, optionally filtered by ``kind``.

        Added 2026-06-16 for Phase 1 ``MAX_DAILY_GPU_COST`` enforcement in
        ``gpu_rent.rent()``. Uses ``date(timestamp) = date('now')`` against the
        UTC-stored ISO timestamps (matches the ``datetime.utcnow().isoformat()``
        format that ``record()`` writes).
        """
        query = (
            "SELECT COALESCE(SUM(cost_usd), 0) FROM ai_usage WHERE date(timestamp) = date('now')"
        )
        params: list[str] = []
        if kind:
            query += " AND kind = ?"
            params.append(kind)
        with sqlite3.connect(self.database_path) as conn:
            row = conn.execute(query, params).fetchone()
        return float(row[0]) if row else 0.0

    def record_gpu(
        self,
        *,
        session_id: str,
        kind: str,
        workload: str,
        cost_usd: float,
        duration_seconds: float | None = None,
        provider: str = "runpod",
    ) -> None:
        """Record a GPU rental session's cost.

        Mirrors ``record()`` for non-LLM (GPU) rentals. Reuses the same
        SQLite table with the ``kind`` column discriminating LLM from GPU.
        """
        duration_ms = int(duration_seconds * 1000) if duration_seconds else None
        with sqlite3.connect(self.database_path) as conn:
            conn.execute(
                """
                INSERT INTO ai_usage (
                    timestamp, provider, model, tokens_in, tokens_out,
                    cost_usd, duration_ms, project, kind, workload, session_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.utcnow().isoformat(),
                    provider,
                    kind,  # model column reused for kind label
                    0,  # tokens_in (N/A for GPU rentals)
                    0,  # tokens_out
                    cost_usd,
                    duration_ms,
                    None,  # project
                    "gpu",  # discriminator
                    workload,
                    session_id,
                ),
            )
            conn.commit()
